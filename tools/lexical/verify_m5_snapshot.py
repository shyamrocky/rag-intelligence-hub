"""Use the accepted M5 verifier on a disposable local copy; never open original DB."""

import json
import shutil
import tempfile
from pathlib import Path

from tools.indexing.m5_index import (
    client,
    encoded,
    local,
    no_network,
    plan,
    read_bound,
    sha,
)
from tools.lexical.bindings import M5_SELECTOR, M5_SHA


def fingerprints(folder):
    return {str(p.relative_to(folder)): sha(p.read_bytes()) for p in folder.rglob("*")
            if p.is_file()}


def verify(root):
    no_network()
    s = json.loads(read_bound(root, M5_SELECTOR, M5_SHA))
    m = json.loads(read_bound(root, s["manifest_path"], s["manifest_sha256"]))
    payload = json.loads(read_bound(root, m["payload_path"], m["spec"]["payload_sha256"]))
    spec, identity, rows, matrix = plan(root, payload)
    if (encoded(m["spec"]) != encoded(spec) or m["identity"] != identity
            or m["upstream_bindings"] != payload["bindings"] or m["records"] != len(rows)
            or m["collection"] != "m5-" + identity[:48] or len(rows) != 992):
        raise ValueError("m6_m5_snapshot_wrong_release")
    source = local(root, s["manifest_path"]).parent / "chroma"
    before = fingerprints(source)
    from tools.indexing.m5_index import check_collection
    with tempfile.TemporaryDirectory(prefix="m6-local-validation-") as directory:
        target = Path(directory) / "chroma"
        shutil.copytree(source, target)
        if fingerprints(target) != before:
            raise ValueError("m6_chroma_copy_not_exact")
        db = client(target)
        try:
            if [c.name for c in db.list_collections()] != [m["collection"]]:
                raise ValueError("m6_unexpected_m5_collection")
            check_collection(db.get_collection(m["collection"], embedding_function=None),
                             rows, matrix, identity)
        finally:
            db.close()
    if fingerprints(source) != before:
        raise ValueError("m6_original_store_changed_during_validation")
    return {"status": "PASS", "records": len(rows), "dimension": 384,
            "authority": "M5_NATIVE_INTEGRITY_CHECK_NOT_EVIDENCE",
            "manifest_sha256": s["manifest_sha256"], "source_store_hashes": before,
            "original_store_unchanged": True, "temporary_validation_copy_removed": True,
            "vector_query_or_inference": False}


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(verify(args.root.resolve(strict=True)), sort_keys=True))
