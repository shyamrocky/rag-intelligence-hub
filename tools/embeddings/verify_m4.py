"""Fresh-process numerical replay and adversarial checks, no retrieval evaluation."""

import copy
import io
import json
import resource
import socket
import time
from pathlib import Path

import numpy as np

from rag_hub.c14_unified_selection import load_c14_verified_corpus
from rag_hub.embedding_artifacts import EmbeddingArtifacts
from rag_hub.local_embeddings import LocalBGE
from rag_hub.qualified_chunk_catalog import QualifiedChunkCatalog
from rag_hub.unified_models import encode, sha


def main():
    root = Path.cwd()
    work = root / "workspace/rag-implementation/v1/m4-embeddings-v1"
    start = time.perf_counter()
    corpus = load_c14_verified_corpus(root)
    catalog = QualifiedChunkCatalog(root, corpus,
        selector="config/retrieval-chunks-m3-c14-scope-v2.json")
    artifacts = EmbeddingArtifacts(root, catalog, selector="config/embedding-artifacts-m4-v1.json")
    spec = artifacts.manifest["model_configuration"]
    model = LocalBGE(root, configuration=spec["path"], expected_sha256=spec["sha256"])
    runtime_path = next(p for p in artifacts.manifest["files"] if p.endswith("/runtime.json"))
    runtime = json.loads((root / runtime_path).read_bytes())
    assert model.loaded_components == runtime["loaded_implementation_sha256"]
    records = list(artifacts.records.values())
    inputs = [json.loads(line) for line in (root / artifacts.manifest["inputs_path"]).read_text().splitlines()]
    print("Fresh process loaded pinned model and accepted live catalog", flush=True)
    outputs = []
    replay_start = time.perf_counter()
    for a in range(0, len(inputs), 16):
        batch = inputs[a:a + 16]
        bound = records[a:a + 16]
        texts = [r["text"] for r in batch]
        limits = [r["total_token_limit"] for r in bound]
        ids = model.token_ids(texts, limits)
        assert all(sha(encode(token_ids)) == r["token_ids_sha256"]
                   for token_ids, r in zip(ids, bound, strict=True))
        outputs.append(model.encode(texts, limits))
    repeated = np.concatenate(outputs)
    delta = float(np.max(abs(artifacts.vectors - repeated)))
    assert np.array_equal(artifacts.vectors, repeated), delta
    replay_seconds = time.perf_counter() - replay_start
    controls = []

    def attempt(label, change, payload_change=None):
        dest = work / "negative-controls" / label
        dest.mkdir(parents=True, exist_ok=False)
        manifest = copy.deepcopy(artifacts.manifest)
        if payload_change:
            field, mutate = payload_change
            original_path = root / manifest[field]
            new = mutate(original_path.read_bytes())
            p = dest / original_path.name
            p.write_bytes(new)
            manifest[field] = str(p.relative_to(root))
            manifest["files"].pop(str(original_path.relative_to(root)))
            manifest["files"][str(p.relative_to(root))] = sha(new)
        change(manifest)
        p = dest / "manifest.json"
        p.write_bytes(encode(manifest))
        selector = dest / "selector.json"
        selector.write_bytes(encode({"schema": "embedding-selection-1.0",
            "manifest_path": str(p.relative_to(root)), "manifest_sha256": sha(p.read_bytes())}))
        try:
            EmbeddingArtifacts(root, catalog, selector=str(selector.relative_to(root)))
        except ValueError as exc:
            controls.append({"case": label, "status": "PASS_REJECTED", "reason": str(exc)})
        else:
            raise AssertionError(f"false_acceptance:{label}")

    def alter_rows(fn):
        def mutate(raw):
            rows = [json.loads(line) for line in raw.decode().splitlines()]
            fn(rows)
            return b"".join(encode(r) + b"\n" for r in rows)
        return mutate

    no_change = lambda _: None
    for name, fn in [
        ("missing-chunk", lambda r: r.pop()),
        ("duplicate-chunk", lambda r: r.__setitem__(1, copy.deepcopy(r[0]))),
        ("wrong-order", lambda r: r.reverse()),
        ("forged-parent", lambda r: r[0].update(unit_id="forged")),
        ("stripped-parent-obligation", lambda r: r[0].update(complete_parent_rehydration_required=False)),
        ("stripped-context-references", lambda r: r[0].update(mandatory_evidence_refs={})),
        ("forged-input-hash", lambda r: r[0].update(input_text_sha256="0" * 64)),
        ("forged-vector-row", lambda r: r[0].update(vector_sha256="0" * 64)),
    ]:
        attempt(name, no_change, ("records_path", alter_rows(fn)))
    attempt("altered-source-input", no_change, ("inputs_path", alter_rows(
        lambda r: r[0].update(text=r[0]["text"] + " altered"))))
    attempt("wrong-catalog", lambda m: m.update(catalog_manifest_sha256="0" * 64))
    attempt("wrong-model-binding", lambda m: m["model_configuration"].update(sha256="0" * 64))

    def corrupt_vectors(raw):
        array = np.load(io.BytesIO(raw), allow_pickle=False)
        array[0, 0] = np.nan
        out = io.BytesIO()
        np.save(out, array, allow_pickle=False)
        return out.getvalue()

    attempt("nonfinite-vector", no_change, ("vectors_path", corrupt_vectors))
    for disposition in ["HOLD", "EXCLUDED"]:
        section = corpus.catalog.list_sections(
            filters={"admission_status": disposition}, limit=1)["items"][0]
        attempt("unauthorized-" + disposition.lower(), no_change, ("records_path", alter_rows(
            lambda r, sid=section["section_id"]: r[0].update(chunk_id=sid))))
    try:
        artifacts.get_vector("unknown-or-HOLD-or-excluded-id")
    except ValueError as exc:
        controls.append({"case": "unknown-or-unauthorized-id", "status": "PASS_REJECTED", "reason": str(exc)})
    else:
        raise AssertionError("unknown_id_accepted")
    # Returned arrays are detached copies, not writable aliases to artifact rows.
    vector, record = artifacts.get_vector(records[0]["chunk_id"])
    vector[:] = 0
    record["complete_parent_rehydration_required"] = False
    again, record = artifacts.get_vector(records[0]["chunk_id"])
    assert np.linalg.norm(again) > 0.99 and record["complete_parent_rehydration_required"]
    controls.append({"case": "returned-copy-mutation", "status": "PASS"})
    stale_selector = work / "negative-controls/stale-selector.json"
    original_selector = (root / "config/embedding-artifacts-m4-v1.json").read_bytes()
    stale_selector.write_bytes(original_selector)
    stale = EmbeddingArtifacts(root, catalog, selector=str(stale_selector.relative_to(root)))
    stale_selector.write_bytes(original_selector + b"\n")
    try:
        stale.get_vector(records[0]["chunk_id"])
    except ValueError as exc:
        controls.append({"case": "stale-artifact-lease", "status": "PASS_REJECTED", "reason": str(exc)})
    else:
        raise AssertionError("stale_artifact_accepted")
    # Supported source access always rehydrates the live full parent, including
    # qualifications. Prove this for the four >384-token cases and C04 guards.
    chosen = [r for r in records if r["tokens_including_specials"] > 384]
    chosen += [r for r in records if r["document_id"] == "C04"
               and r["lineage"]["precision"] == "AUTHORIZED_PROTECTED_QUOTATION_EXACT_SOURCE_SPAN"]
    for record in chosen:
        view = artifacts.open_bound_chunk(record["chunk_id"])
        assert catalog.validate_view(view)
        context = view["verified_parent"]["consumer"]["llm_context"]
        assert context["qualification"]["mandatory"]
    protected = next(r for r in chosen if r["document_id"] == "C04")
    original = artifacts.open_bound_chunk(protected["chunk_id"])
    for field in ["qualification", "required_context", "qa_observations"]:
        forged = copy.deepcopy(original)
        forged["verified_parent"]["consumer"]["llm_context"].pop(field)
        try:
            catalog.validate_view(forged)
        except ValueError as exc:
            controls.append({"case": "stripped-live-" + field,
                             "status": "PASS_REJECTED", "reason": str(exc)})
        else:
            raise AssertionError("stripped_live_qualification_accepted")
    artifacts.check()
    result = {"status": "PASS", "fresh_process_full_replay_rows": len(inputs),
        "fresh_process_bit_exact": True, "max_abs_vector_difference": delta,
        "replay_seconds": replay_seconds, "adversarial_controls": controls,
        "live_qualified_views_revalidated": len(chosen),
        "total_seconds": time.perf_counter() - start,
        "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "scope": "Numerical reproducibility and supported API safety, not retrieval relevance or QA admission."}
    (work / "REPLAY_AND_ADVERSARIAL_RESULTS.json").write_bytes(encode(result))
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    def offline(*_args, **_kwargs):
        raise RuntimeError("M4_verification_offline_only")

    socket.socket.connect = offline
    main()
