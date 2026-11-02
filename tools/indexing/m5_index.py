"""M5 numerical store. No text, model, query search, or evidence authorization."""

import argparse
import contextlib
import hashlib
import importlib.metadata
import json
import os
import resource
import sys
import time
from pathlib import Path

SCHEMA = "m5-chroma-1.1"
RUNTIME = "1.5.9"
UPSTREAM = {
    "config/pdf-durable-admission-publication-v1.json":
        "c1c2ac2235c9266c2e6d1dae695e31cde26c7ababc8168e224aecb58b89a3911",
    "config/unified-durable-selection-v1.json":
        "d9a2bc8452df9da83dd4d2ae7511bb2393203821e2c8218e51e962a090aad681",
    "config/retrieval-chunks-m3-durable-v1.json":
        "8ec4237d894e7c3a045010ca4ad5a767d36d2cd8fdaadef1f9fbbbd6becc9d4a",
    "config/embedding-artifacts-m4-durable-v1.json":
        "6117f3697071bbefbb2ac2c421645846119a37e50073d5665cfed05f952f9a23",
    "config/m4-embedding-baseline-v1.json":
        "2444f602babc045234dba3258e89fa4a7ea26572fa748576c6df0509dc24e3de",
    "config/bge-tokenizer-v1.json":
        "03d41df1a646ed13d41bd8b485c573864da5821109e57750135bf94f0dbde577",
}
COMPONENTS = ("tools/indexing/m5_index.py", "tools/indexing/export_m4.py",
              "tools/indexing/pyproject.toml", "tools/indexing/uv.lock")
FIELDS = {"document_id", "format", "unit_id", "embedding_id", "row_index",
          "input_text_sha256", "token_ids_sha256", "vector_sha256", "qualification_sha256",
          "chunk_sha256", "publication_sha256", "memberships_sha256",
          "reference_classification", "catalog_sha256", "model_config_sha256",
          "complete_parent_rehydration_required"}


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def local(root, name):
    path = root / name
    if (Path(name).is_absolute() or ".." in Path(name).parts
            or not path.resolve().is_relative_to(root.resolve())):
        raise ValueError("m5_unsafe_path")
    # Reject symlink traversal even when it points inside the root.
    if any(p.is_symlink() for p in [path, *path.parents] if p.is_relative_to(root)):
        raise ValueError("m5_symlink_not_supported")
    return path


def read_bound(root, name, digest):
    data = local(root, name).read_bytes()
    if sha(data) != digest:
        raise ValueError("m5_binding_changed:" + name)
    return data


def no_network():
    os.environ.update(ANONYMIZED_TELEMETRY="false", HF_HUB_OFFLINE="1",
                      TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1",
                      OTEL_SDK_DISABLED="true")

    def audit(event, args):
        if event in {"socket.connect", "socket.getaddrinfo", "socket.bind"}:
            raise PermissionError("m5_network_denied")
    sys.addaudithook(audit)


def runtime():
    if sys.version_info[:2] != (3, 12):
        raise ValueError("m5_requires_python_3_12")
    versions = {d.metadata["Name"].lower(): d.version
                for d in importlib.metadata.distributions()}
    if versions.get("chromadb") != RUNTIME or versions.get("numpy") != "2.2.6":
        raise ValueError("m5_wrong_runtime")
    return dict(sorted(versions.items()))


def metadata(record, catalog_sha, model_sha):
    result = {k: record[k] for k in FIELDS if k in record}
    result.update(publication_sha256=record["parent_binding"]["publication_sha256"],
                  memberships_sha256=record["parent_binding"]["memberships_sha256"],
                  catalog_sha256=catalog_sha, model_config_sha256=model_sha)
    if set(result) != FIELDS or result["complete_parent_rehydration_required"] is not True:
        raise ValueError("m5_invalid_metadata")
    if any(type(v) not in {str, int, bool} for v in result.values()):
        raise ValueError("m5_non_scalar_metadata")
    return result


def expected(root, payload):
    """Compare bridge data to immutable saved records; never trust an input receipt alone."""
    import numpy as np

    if payload.get("schema") != "m5-verified-export-1.0":
        raise ValueError("m5_invalid_export_schema")
    if any(payload["bindings"].get(p) != h for p, h in UPSTREAM.items()):
        raise ValueError("m5_wrong_upstream_selection")
    for p, h in payload["bindings"].items():
        if p.startswith("workspace/"):
            raise ValueError("m5_workspace_runtime_dependency")
        read_bound(root, p, h)
    sel = json.loads(read_bound(root, "config/embedding-artifacts-m4-durable-v1.json",
                              UPSTREAM["config/embedding-artifacts-m4-durable-v1.json"]))
    manifest = json.loads(read_bound(root, sel["manifest_path"], sel["manifest_sha256"]))
    for p, h in manifest["files"].items():
        read_bound(root, p, h)
    records = [json.loads(line) for line in local(root, manifest["records_path"]).read_text()
               .splitlines()]
    matrix = np.load(local(root, manifest["vectors_path"]), allow_pickle=False)
    if (matrix.shape != (992, 384) or matrix.dtype != np.float32
            or len(records) != 992 or not np.isfinite(matrix).all()):
        raise ValueError("m5_invalid_saved_vectors")
    rows = [{"id": r["chunk_id"], "metadata": metadata(
        r, manifest["catalog_manifest_sha256"], manifest["model_configuration"]["sha256"])}
        for r in records]
    if len({r["id"] for r in rows}) != 992 or encoded(payload["rows"]) != encoded(rows):
        raise ValueError("m5_export_not_exact_accepted_inventory")
    for record in records:
        if sha(matrix[record["row_index"]].tobytes()) != record["vector_sha256"]:
            raise ValueError("m5_saved_vector_hash_changed")
    if payload.get("verified_live_bindings") != 992:
        raise ValueError("m5_missing_live_parent_verification")
    return rows, matrix


def client(path):
    import chromadb
    from chromadb.config import Settings

    return chromadb.PersistentClient(path=str(path), settings=Settings(
        anonymized_telemetry=False, allow_reset=False, chroma_otel_granularity=None,
        chroma_otel_collection_endpoint=""))


def check_collection(collection, rows, matrix, identity):
    import numpy as np

    if (collection.metadata != {"schema": SCHEMA, "release": identity,
                                "authority": "NUMERICAL_LOOKUP_NOT_EVIDENCE"}
            or collection.configuration["hnsw"]["space"] != "l2"
            or collection.configuration.get("embedding_function") is not None):
        raise ValueError("m5_incompatible_collection")
    if collection.count() != len(rows):
        raise ValueError("m5_wrong_record_count")
    result = collection.get(include=["embeddings", "metadatas", "documents", "uris"])
    ids = result["ids"]
    if len(set(ids)) != len(rows) or set(ids) != {r["id"] for r in rows}:
        raise ValueError("m5_missing_extra_duplicate_ids")
    want = {r["id"]: r["metadata"] for r in rows}
    for i, cid in enumerate(ids):
        m = result["metadatas"][i]
        if (encoded(m) != encoded(want[cid]) or set(m) != FIELDS
                or result["documents"][i] is not None
                or result["uris"][i] is not None):
            raise ValueError("m5_unsupported_or_changed_payload")
        vector = np.asarray(result["embeddings"][i], dtype=np.float32)
        if (vector.shape != (384,) or vector.tobytes() != matrix[m["row_index"]].tobytes()
                or sha(vector.tobytes()) != m["vector_sha256"]):
            raise ValueError("m5_vector_association_changed")
    return True


def plan(root, payload, *, pilot=False):
    rows, matrix = expected(root, payload)
    if pilot:
        seen = set()
        rows = [r for r in rows if r["metadata"]["document_id"] not in seen
                and not seen.add(r["metadata"]["document_id"])]
    spec = {"schema": SCHEMA, "scope": "pilot" if pilot else "full",
            "payload_sha256": sha(encoded(payload)), "rows_sha256": sha(encoded(rows)),
            "components": {p: sha(local(root, p).read_bytes()) for p in COMPONENTS},
            "runtime": runtime(), "hnsw_space": "l2", "dimension": 384,
            "dtype": "float32", "embedding_function": None}
    identity = sha(encoded(spec))
    return spec, identity, rows, matrix


@contextlib.contextmanager
def exclusive(path):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, str(os.getpid()).encode())
        yield
    finally:
        os.close(fd)
        path.unlink()


def build(root, payload_path, selector, *, pilot=False, fail_after_batch=False,
          storage_area="data/indexes/m5-chroma-v1"):
    """Immutable version directory; no upsert, no repair, no implicit selector."""
    payload = json.loads(local(root, payload_path).read_bytes())
    spec, identity, rows, matrix = plan(root, payload, pilot=pilot)
    if not (storage_area == "data/indexes/m5-chroma-v1"
            or storage_area.startswith("data/indexes/m5-chroma-v1/")):
        raise ValueError("m5_invalid_storage_area")
    base = local(root, storage_area)
    base.mkdir(parents=True, exist_ok=True)
    destination = base / identity
    selection = local(root, selector)
    if selection.exists():
        pinned = sha(selection.read_bytes())
        value = inspect(root, selector, pinned)
        if value["identity"] != identity:
            raise ValueError("m5_existing_selector_different_release")
        return {**value, "repeated_build": "VERIFIED_UNCHANGED", "selector_sha256": pinned}
    if destination.exists():
        raise ValueError("m5_unselected_existing_release_requires_review")
    with exclusive(base / (identity + ".lock")):
        staging = base / (identity + ".staging")
        staging.mkdir()  # Failed attempts are retained, never reused automatically.
        db = client(staging / "chroma")
        try:
            coll = db.create_collection("m5-" + identity[:48], embedding_function=None,
                metadata={"schema": SCHEMA, "release": identity,
                          "authority": "NUMERICAL_LOOKUP_NOT_EVIDENCE"},
                configuration={"hnsw": {"space": "l2", "num_threads": 1}})
            for offset in range(0, len(rows), 64):
                batch = rows[offset:offset + 64]
                coll.add(ids=[r["id"] for r in batch],
                         embeddings=[matrix[r["metadata"]["row_index"]].tolist() for r in batch],
                         metadatas=[r["metadata"] for r in batch])
                if fail_after_batch:
                    raise ValueError("m5_injected_partial_failure")
            check_collection(coll, rows, matrix, identity)
        finally:
            db.close()
        # Reopen storage before selecting it; a separate-process check follows publication.
        db = client(staging / "chroma")
        try:
            check_collection(db.get_collection("m5-" + identity[:48], embedding_function=None),
                             rows, matrix, identity)
        finally:
            db.close()
        manifest = {"schema": SCHEMA, "authority": "NUMERICAL_LOOKUP_NOT_EVIDENCE",
            "identity": identity, "spec": spec, "payload_path": payload_path,
            "collection": "m5-" + identity[:48], "records": len(rows),
            "upstream_bindings": payload["bindings"],
            "parent_rehydration": "EmbeddingArtifacts.open_bound_chunk; never database payload"}
        (staging / "manifest.json").write_bytes(encoded(manifest))
        # Recheck leases and inputs immediately before atomic publication.
        if plan(root, payload, pilot=pilot)[0] != spec:
            raise ValueError("m5_build_components_changed")
        staging.rename(destination)
        selection.parent.mkdir(parents=True, exist_ok=True)
        selected = {"schema": "m5-selection-1.0", "manifest_path": str(
            (destination / "manifest.json").relative_to(root)),
            "manifest_sha256": sha(encoded(manifest))}
        with selection.open("xb") as f:
            f.write(encoded(selected))
    return {**inspect(root, selector, sha(encoded(selected))),
            "selector_sha256": sha(encoded(selected)), "repeated_build": False}


def inspect(root, selector, selector_sha256, *, document=None, chunk_id=None):
    """Hash-pinned, complete inventory verification before exact-ID/filter reads."""
    selected = json.loads(read_bound(root, selector, selector_sha256))
    if set(selected) != {"schema", "manifest_path", "manifest_sha256"} or selected[
            "schema"] != "m5-selection-1.0":
        raise ValueError("m5_unsupported_selector")
    m = json.loads(read_bound(root, selected["manifest_path"], selected["manifest_sha256"]))
    payload = json.loads(local(root, m["payload_path"]).read_bytes())
    spec, identity, rows, matrix = plan(root, payload, pilot=m["spec"]["scope"] == "pilot")
    if (encoded(m["spec"]) != encoded(spec) or m["identity"] != identity
            or m["upstream_bindings"] != payload["bindings"] or m["records"] != len(rows)
            or m["collection"] != "m5-" + identity[:48]
            or m["schema"] != SCHEMA or m["authority"] != "NUMERICAL_LOOKUP_NOT_EVIDENCE"
            or not selected["manifest_path"].startswith("data/indexes/m5-chroma-v1/")):
        raise ValueError("m5_release_incompatible")
    folder = local(root, selected["manifest_path"]).parent
    if not (folder / "chroma/chroma.sqlite3").is_file():
        raise ValueError("m5_persistent_database_missing")
    db = client(folder / "chroma")
    try:
        collections = db.list_collections()
        if [c.name for c in collections] != [m["collection"]]:
            raise ValueError("m5_unexpected_collection")
        coll = db.get_collection(m["collection"], embedding_function=None)
        check_collection(coll, rows, matrix, identity)
        if document is not None and document not in {r["metadata"]["document_id"] for r in rows}:
            raise ValueError("m5_unknown_document")
        if chunk_id is not None and chunk_id not in {r["id"] for r in rows}:
            raise ValueError("m5_unknown_chunk")
        filters = {"document_id": document} if document else None
        result = coll.get(ids=[chunk_id] if chunk_id else None, where=filters,
                          include=["metadatas"])
        # Recheck provenance after the store operation, before releasing metadata.
        for p, h in payload["bindings"].items():
            read_bound(root, p, h)
        counts = {}
        for row in rows:
            did = row["metadata"]["document_id"]
            counts[did] = counts.get(did, 0) + 1
        return {"authority": "INSPECTION_ONLY_NOT_EVIDENCE", "status": "PASS",
            "identity": identity, "collection": m["collection"], "records": len(rows),
            "dimension": 384, "model": "BAAI/bge-small-en-v1.5",
            "manifest_sha256": selected["manifest_sha256"], "document_counts": counts,
            "storage": str(folder.relative_to(root)),
            "disk_bytes": sum(p.stat().st_size for p in folder.rglob("*") if p.is_file()),
            "matching_records": len(result["ids"]), "exact_record": (
                {"chunk_id": result["ids"][0], "metadata": result["metadatas"][0]}
                if chunk_id and result["ids"] else None),
            "complete_parent_rehydration_required": True}
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["build", "inspect"])
    parser.add_argument("--root", required=True)
    parser.add_argument("--selector", required=True)
    parser.add_argument("--selector-sha256")
    parser.add_argument("--payload")
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--document")
    parser.add_argument("--chunk-id")
    args = parser.parse_args()
    no_network()
    start = time.perf_counter()
    try:
        if args.operation == "build":
            if not args.payload:
                raise ValueError("m5_explicit_payload_required")
            value = build(Path(args.root).resolve(), args.payload, args.selector, pilot=args.pilot)
        else:
            if not args.selector_sha256:
                raise ValueError("m5_explicit_selector_hash_required")
            value = inspect(Path(args.root).resolve(), args.selector, args.selector_sha256,
                            document=args.document, chunk_id=args.chunk_id)
        value.update(seconds=time.perf_counter() - start,
                     max_rss_native=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                     network_policy="PYTHON_AUDIT_DENIAL_NOT_KERNEL_ISOLATION")
        print(json.dumps(value, sort_keys=True))
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
