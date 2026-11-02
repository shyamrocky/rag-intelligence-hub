"""Offline JSON-lines workers in the three unchanged, isolated locked runtimes."""

import argparse
import contextlib
import json
import platform
import resource
import shutil
import sys
import tempfile
import time
from pathlib import Path

from tools.indexing.m5_index import encoded, local, no_network, read_bound, sha
from tools.retrieval.contract import (
    AUTHORITY,
    PREFIX,
    check_files,
    load_release,
    native_hits,
    validate_query_vector,
)


class Worker:
    def __init__(self, root, kind, selector, selector_sha256):
        self.root, self.kind = root, kind
        self.manifest, self.files, self.inventory = load_release(root, selector, selector_sha256)
        if platform.python_version() != "3.12.15":
            raise ValueError("m7_wrong_python_runtime")
        self.model = self.db = self.temporary = None
        self.index = None
        selections = self.manifest["spec"]["selections"]
        if kind == "encode":
            from rag_hub.local_embeddings import LocalBGE

            self.model = LocalBGE(root, configuration="config/m4-embedding-baseline-v1.json",
                expected_sha256=self.files["config/m4-embedding-baseline-v1.json"])
            # Compare the actual loaded class implementations to accepted M4 evidence.
            m4s = json.loads(read_bound(root, selections["m4"]["path"], selections["m4"]["sha256"]))
            m4 = json.loads(read_bound(root, m4s["manifest_path"], m4s["manifest_sha256"]))
            runtimes = [p for p in m4["files"] if p.endswith("runtime.json")]
            if len(runtimes) != 1:
                raise ValueError("m7_missing_M4_runtime_witness")
            runtime = json.loads(read_bound(root, runtimes[0], m4["files"][runtimes[0]]))
            if runtime["loaded_implementation_sha256"] != self.model.loaded_components:
                raise ValueError("m7_loaded_model_implementation_drift")
        elif kind == "bm25":
            from tools.lexical.bm25_index import BM25Index

            self.index = BM25Index(root, selector=selections["m6"]["path"],
                                  selector_sha256=selections["m6"]["sha256"])
        elif kind == "vector":
            from tools.indexing.m5_index import check_collection, client, plan

            selection = json.loads(read_bound(root, selections["m5"]["path"], selections["m5"]["sha256"]))
            manifest = json.loads(read_bound(root, selection["manifest_path"], selection["manifest_sha256"]))
            payload = json.loads(read_bound(root, manifest["payload_path"], manifest["spec"]["payload_sha256"]))
            spec, identity, self.rows, self.matrix = plan(root, payload)
            if (encoded(spec) != encoded(manifest["spec"]) or identity != manifest["identity"]
                    or {r["id"] for r in self.rows} != set(self.inventory)):
                raise ValueError("m7_wrong_M5_release")
            self.m5_identity = identity
            source = local(root, selection["manifest_path"]).parent / "chroma"
            self.temporary = tempfile.TemporaryDirectory(prefix="m7-readonly-chroma-")
            target = Path(self.temporary.name) / "chroma"
            shutil.copytree(source, target)
            for path in source.rglob("*"):
                if path.is_file() and sha(path.read_bytes()) != sha((target / path.relative_to(source)).read_bytes()):
                    raise ValueError("m7_store_copy_changed")
            self.db = client(target)
            if [c.name for c in self.db.list_collections()] != [manifest["collection"]]:
                raise ValueError("m7_wrong_collection")
            self.collection = self.db.get_collection(manifest["collection"], embedding_function=None)
            check_collection(self.collection, self.rows, self.matrix, identity)
        else:
            raise ValueError("m7_unknown_worker")
        check_files(root, self.files)

    def request(self, request):
        check_files(self.root, self.files)
        if self.kind == "encode":
            if set(request) != {"query"} or not isinstance(request["query"], str) or not request["query"]:
                raise ValueError("m7_invalid_encoding_request")
            query = request["query"]
            text = PREFIX + query
            ids = self.model.token_ids([text], [512])[0]
            vector = self.model.encode([text], [512])[0]
            result = {"vector": vector.tolist(), "vector_sha256": sha(vector.tobytes()),
                "query_sha256": sha(query.encode()), "encoded_text_sha256": sha(text.encode()),
                "token_ids_sha256": sha(encoded(ids)), "tokens": len(ids),
                "model_configuration_sha256": self.model.config_sha256,
                "policy": "bge-query-instruction-1.0"}
            validate_query_vector(result, query)
        elif self.kind == "bm25":
            if set(request) != {"query", "depth", "filters"}:
                raise ValueError("m7_invalid_lexical_request")
            result = self.index.search(request["query"], top_k=request["depth"],
                                       filters=request["filters"])["candidates"]
        else:
            if set(request) != {"query", "query_vector", "depth", "filters"}:
                raise ValueError("m7_invalid_vector_request")
            vector = validate_query_vector(request["query_vector"], request["query"])
            if type(request["depth"]) is not int or not 1 <= request["depth"] <= 992:
                raise ValueError("m7_invalid_depth")
            filters = request["filters"]
            from tools.indexing.m5_index import check_collection
            from tools.retrieval.contract import parameters

            parameters(request["query"], "vector", 1, request["depth"], 60, filters, self.inventory)
            # Validate the working copy too; it cannot silently acquire records or payloads.
            check_collection(self.collection, self.rows, self.matrix, self.m5_identity)
            clauses = [{k: {"$eq": v}} for k, v in sorted(filters.items())]
            where = None if not clauses else clauses[0] if len(clauses) == 1 else {"$and": clauses}
            count = sum(all(m[k] == v for k, v in filters.items()) for m in self.inventory.values())
            result = []
            if count:
                # Ask native Chroma for the whole eligible small corpus, then sort all ties.
                # This avoids unstable boundary ties in a truncated native candidate set.
                native = self.collection.query(query_embeddings=[vector.tolist()],
                    n_results=count, where=where, include=["distances", "metadatas"])
                ids = native["ids"][0]
                if len(ids) != count or len(set(ids)) != count:
                    raise ValueError("m7_incomplete_native_results")
                for cid, distance, meta in zip(ids, native["distances"][0], native["metadatas"][0], strict=True):
                    if cid not in self.inventory or any(meta[k] != self.inventory[cid][k] for k in self.inventory[cid]):
                        raise ValueError("m7_unauthorized_vector_result")
                    result.append({"chunk_id": cid, "distance": float(distance), **self.inventory[cid]})
                result.sort(key=lambda r: (r["distance"], r["chunk_id"]))
                result = [{**r, "rank": i} for i, r in enumerate(result, 1)]
                native_hits(result, "vector", self.inventory, filters)
                result = result[:request["depth"]]
        check_files(self.root, self.files)
        return result

    def close(self):
        if self.db is not None:
            self.db.close()
        if self.temporary is not None:
            self.temporary.cleanup()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=["encode", "vector", "bm25"], required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--selector", required=True)
    parser.add_argument("--selector-sha256", required=True)
    args = parser.parse_args()
    no_network()
    output = sys.stdout
    worker = None
    try:
        start = time.perf_counter()
        with contextlib.redirect_stdout(sys.stderr):
            worker = Worker(args.root.resolve(strict=True), args.kind, args.selector, args.selector_sha256)
        print(json.dumps({"status": "READY", "kind": args.kind,
            "identity": worker.manifest["identity"], "seconds": time.perf_counter() - start}),
              file=output, flush=True)
        for line in sys.stdin:
            if line.strip() == '{"close":true}':
                break
            start = time.perf_counter()
            with contextlib.redirect_stdout(sys.stderr):
                result = worker.request(json.loads(line))
            print(json.dumps({"status": "PASS", "kind": args.kind, "authority": AUTHORITY,
                "identity": worker.manifest["identity"], "result": result,
                "seconds": time.perf_counter() - start,
                "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
                allow_nan=False), file=output, flush=True)
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, ImportError) as exc:
        print(json.dumps({"status": "FAIL", "error": type(exc).__name__ + ":" + str(exc)}),
              file=output, flush=True)
        return 1
    finally:
        if worker is not None:
            worker.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
