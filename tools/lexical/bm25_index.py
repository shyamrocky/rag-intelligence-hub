"""Explicit persistent BM25 candidate index. Never returns source evidence."""

import argparse
import importlib.metadata
import json
import math
import os
import platform
import re
import shutil
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from tools.indexing.m5_index import encoded, exclusive, local, no_network, read_bound, sha
from tools.lexical.bindings import validate_payload

SCHEMA = "m6-bm25-1.0"
POLICY = "config/bm25-preprocessing-v1.json"
COMPONENTS = ("tools/lexical/bm25_index.py", "tools/lexical/bindings.py",
              "tools/lexical/export_inputs.py", "tools/lexical/verify_m5_snapshot.py",
              "tools/lexical/pyproject.toml", "tools/lexical/uv.lock", POLICY)
FILTERS = {"document_id", "format", "reference_classification"}
META_FIELDS = {"chunk_id", "unit_id", "document_id", "format", "reference_classification",
               "input_text_sha256", "qualification_sha256"}


def runtime():
    if platform.python_version() != "3.12.15":
        raise ValueError("m6_requires_pinned_python_3_12_15")
    versions = {n: importlib.metadata.version(n) for n in ("rank-bm25", "numpy")}
    if versions != {"rank-bm25": "0.2.2", "numpy": "2.2.6"}:
        raise ValueError("m6_incompatible_lexical_runtime")
    return {"python": platform.python_version(), "unicode": unicodedata.unidata_version,
            "platform": {"system": platform.system(), "machine": platform.machine()},
            "packages": versions, "rank_bm25_py_sha256": sha(Path(
                sys.modules["rank_bm25"].__file__).read_bytes())}


def policy(root):
    value = json.loads(local(root, POLICY).read_bytes())
    # Configuration is versioned and fingerprinted; unsupported changes fail explicitly.
    expected = {"schema": "m6-lexical-preprocessing-1.0", "case": "unicode_casefold",
        "normalization": "no_stemming_no_stopwords_no_unicode_rewrite",
        "pattern": r"[+-]?\w+(?:[-./:]\w+)*(?:\+\+|#|%)?",
        "aliases": "append_distinct_connector_components_for_nonnumeric_tokens",
        "connector_pattern": "[-./:]", "algorithm": "BM25Okapi", "k1": 1.5,
        "b": 0.75, "epsilon": 0.25, "query_duplicates": "preserved",
        "ties": "ascending_exact_chunk_id",
        "matches": "at_least_one_exact_lexical_token_even_if_score_nonpositive",
        "empty_documents": "retained_with_zero_tokens",
        "source": "existing_embedding_input_source_only_plus_authorized_heading_context",
        "scope": "SEARCH_CANDIDATES_ONLY_COMPLETE_PARENT_REQUIRED"}
    if encoded(value) != encoded(expected):
        raise ValueError("m6_unsupported_tokenizer_configuration")
    return value


def tokenize(text, config):
    if not isinstance(text, str):
        raise TypeError("m6_query_must_be_text")
    tokens = []
    for raw in re.findall(config["pattern"], text):
        token = raw.casefold()
        tokens.append(token)
        if re.fullmatch(r"[+-]?\d+(?:[./:]\d+)*(?:%)?", token):
            continue
        parts = re.split(config["connector_pattern"], token)
        # Aliases support multiword queries without deleting the exact identifier.
        tokens.extend(dict.fromkeys(p for p in parts if p and p != token))
    return tokens


def index_rows(rows, config):
    records = []
    for row in sorted(rows, key=lambda r: r["chunk_id"]):
        tokens = tokenize(row["text"], config)
        records.append({"metadata": {k: row[k] for k in META_FIELDS},
                        "tokens": tokens, "lexical_tokens_sha256": sha(encoded(tokens))})
    return records


def parameters(tokens, config):
    if not tokens or not any(tokens):
        raise ValueError("m6_empty_lexical_corpus")
    return BM25Okapi(tokens, k1=config["k1"], b=config["b"], epsilon=config["epsilon"])


def plan(root, payload):
    bindings, rows = validate_payload(root, payload)
    config = policy(root)
    records = index_rows(rows, config)
    spec = {"schema": SCHEMA, "authority": "CANDIDATE_SEARCH_NOT_EVIDENCE",
            "bindings": bindings, "payload_sha256": sha(encoded(payload)),
            "policy": config, "records_sha256": sha(encoded(records)), "records": len(records),
            "components": {p: sha(local(root, p).read_bytes()) for p in COMPONENTS},
            "runtime": runtime()}
    return spec, records


def build(root, payload_path, *, payload_sha256, selector, fail_before_publish=False):
    """Atomic, immutable, explicit opt-in build. No pickle, upserts or fallback."""
    root = Path(root).resolve(strict=True)
    payload = json.loads(read_bound(root, payload_path, payload_sha256))
    spec, records = plan(root, payload)
    identity = sha(encoded(spec))
    folder = local(root, "data/indexes/m6-bm25-v1/" + identity)
    selected = local(root, selector)
    selected.parent.mkdir(parents=True, exist_ok=True)
    folder.parent.mkdir(parents=True, exist_ok=True)
    with exclusive(folder.parent / "build.lock"):
        manifest = {"schema": SCHEMA, "identity": identity, "spec": spec,
                    "payload_path": payload_path, "records_path": str(
                        (folder / "records.json").relative_to(root))}
        selection = {"schema": "m6-selection-1.0", "manifest_path": str(
                        (folder / "manifest.json").relative_to(root)),
                     "manifest_sha256": sha(encoded(manifest))}
        if selected.exists() and selected.read_bytes() != encoded(selection):
            raise ValueError("m6_selector_exists_no_overwrite")
        repeated = folder.exists()
        if repeated:
            if ((folder / "manifest.json").read_bytes() != encoded(manifest)
                    or (folder / "records.json").read_bytes() != encoded(records)):
                raise ValueError("m6_incomplete_or_altered_existing_build")
        else:
            temporary = Path(tempfile.mkdtemp(prefix=".build-", dir=folder.parent))
            try:
                (temporary / "records.json").write_bytes(encoded(records))
                (temporary / "manifest.json").write_bytes(encoded(manifest))
                if fail_before_publish:
                    raise ValueError("m6_injected_incomplete_build")
                os.rename(temporary, folder)
            finally:
                if temporary.exists():
                    shutil.rmtree(temporary)
        if not selected.exists():
            with selected.open("xb") as f:
                f.write(encoded(selection))
    return {"status": "PASS", "identity": identity, "records": len(records),
            "selector": selector, "selector_sha256": sha(encoded(selection)),
            "manifest_sha256": selection["manifest_sha256"], "repeated_build": repeated}


class BM25Index:
    """Pinned read-only candidate API. Evidence requires the existing parent gateway."""

    def __init__(self, root, *, selector, selector_sha256):
        self.root = Path(root).resolve(strict=True)
        self._selector = selector
        self._selector_hash = selector_sha256
        raw = read_bound(self.root, selector, selector_sha256)
        selection = json.loads(raw)
        if set(selection) != {"schema", "manifest_path", "manifest_sha256"} or selection[
                "schema"] != "m6-selection-1.0":
            raise ValueError("m6_invalid_selector")
        raw = read_bound(self.root, selection["manifest_path"], selection["manifest_sha256"])
        manifest = json.loads(raw)
        payload = json.loads(read_bound(self.root, manifest["payload_path"],
                                       manifest["spec"]["payload_sha256"]))
        spec, rows = plan(self.root, payload)
        if (set(manifest) != {"schema", "identity", "spec", "payload_path", "records_path"}
                or manifest["schema"] != SCHEMA or encoded(manifest["spec"]) != encoded(spec)
                or manifest["identity"] != sha(encoded(spec))
                or selection["manifest_path"] != "data/indexes/m6-bm25-v1/" +
                    manifest["identity"] + "/manifest.json"
                or manifest["records_path"] != str(Path(selection["manifest_path"]).with_name("records.json"))):
            raise ValueError("m6_incompatible_release_or_index")
        raw = read_bound(self.root, manifest["records_path"], spec["records_sha256"])
        if raw != encoded(rows):
            raise ValueError("m6_corrupt_lexical_records")
        self._rows = rows
        self._config = spec["policy"]
        self._engine = parameters([r["tokens"] for r in rows], self._config)
        self._identity = manifest["identity"]
        self._files = spec["bindings"] | spec["components"] | {
            selector: selector_sha256, selection["manifest_path"]: selection["manifest_sha256"],
            manifest["payload_path"]: spec["payload_sha256"],
            manifest["records_path"]: spec["records_sha256"]}
        self.check()

    def check(self):
        # Retain a live filesystem lease; cached candidate records cannot bypass drift.
        for name, digest in self._files.items():
            read_bound(self.root, name, digest)

    def inspect(self):
        self.check()
        counts = {}
        for r in self._rows:
            did = r["metadata"]["document_id"]
            counts[did] = counts.get(did, 0) + 1
        return {"authority": "CANDIDATE_SEARCH_NOT_EVIDENCE", "identity": self._identity,
                "records": len(self._rows), "document_counts": counts,
                "complete_parent_rehydration_required": True,
                "selection": {"path": self._selector, "sha256": self._selector_hash}}

    def search(self, query, *, top_k=10, filters=None):
        self.check()
        if type(top_k) is not int or not 1 <= top_k <= 992:
            raise ValueError("m6_top_k_must_be_integer_1_to_992")
        filters = {} if filters is None else filters
        if not isinstance(filters, dict) or set(filters) - FILTERS:
            raise ValueError("m6_unsupported_metadata_filter")
        for key, value in filters.items():
            if not isinstance(value, str) or value not in {r["metadata"][key] for r in self._rows}:
                raise ValueError("m6_unknown_filter_value")
        tokens = tokenize(query, self._config)
        scores = self._engine.get_scores(tokens) if tokens else np.zeros(len(self._rows))
        hits = []
        for i, row in enumerate(self._rows):
            meta = row["metadata"]
            if (not set(tokens).intersection(row["tokens"])
                    or any(meta[k] != v for k, v in filters.items())):
                continue
            score = float(scores[i])
            if not math.isfinite(score):
                raise ValueError("m6_nonfinite_score")
            hits.append({"chunk_id": meta["chunk_id"], "score": score,
                         "document_id": meta["document_id"], "format": meta["format"],
                         "reference_classification": meta["reference_classification"]})
        hits.sort(key=lambda r: (-r["score"], r["chunk_id"]))
        hits = [{**r, "rank": i} for i, r in enumerate(hits[:top_k], 1)]
        self.check()
        return {"authority": "CANDIDATES_ONLY_NOT_AUTHORIZED_EVIDENCE", "identity": self._identity,
                "complete_parent_rehydration_required": True,
                "selection": {"path": self._selector, "sha256": self._selector_hash},
                "candidates": hits}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["build", "inspect", "search"])
    p.add_argument("--root", required=True, type=Path)
    p.add_argument("--selector", required=True)
    p.add_argument("--selector-sha256")
    p.add_argument("--payload")
    p.add_argument("--payload-sha256")
    p.add_argument("--query")
    p.add_argument("--top-k", type=int, default=10)
    p.add_argument("--filters", default="{}")
    args = p.parse_args()
    no_network()
    tick = time.perf_counter()
    try:
        if args.action == "build":
            if not args.payload or not args.payload_sha256:
                p.error("build requires --payload and --payload-sha256")
            result = build(args.root, args.payload, payload_sha256=args.payload_sha256,
                           selector=args.selector)
        else:
            if not args.selector_sha256:
                p.error("inspect/search require --selector-sha256")
            index = BM25Index(args.root, selector=args.selector, selector_sha256=args.selector_sha256)
            result = index.inspect() if args.action == "inspect" else index.search(
                args.query, top_k=args.top_k, filters=json.loads(args.filters))
        print(json.dumps({**result, "seconds": time.perf_counter() - tick}, sort_keys=True))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc), "fallback": False}))
        sys.exit(1)


if __name__ == "__main__":
    main()
