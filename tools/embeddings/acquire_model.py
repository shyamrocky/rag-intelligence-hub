"""Acquire only the authorized BGE revision; validate Git/LFS object identities."""

import hashlib
import json
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

REPO = "BAAI/bge-small-en-v1.5"
REVISION = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
NAMES = ["model.safetensors", "modules.json", "1_Pooling/config.json",
         "config_sentence_transformers.json", "config.json", "sentence_bert_config.json",
         "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "vocab.txt",
         "README.md"]


def main():
    root = Path.cwd()
    work = root / "workspace/rag-implementation/v1/m4-embeddings-v1"
    metadata = json.loads((work / "OFFICIAL_MODEL_METADATA.json").read_bytes())
    assert metadata["sha"] == REVISION and metadata["cardData"]["license"] == "mit"
    siblings = {f["rfilename"]: f for f in metadata["siblings"]}
    dest = root / "data/models/bge-small-en-v1.5" / REVISION
    records = {}
    started = time.perf_counter()
    for name in NAMES:
        info = siblings[name]
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://huggingface.co/{REPO}/resolve/{REVISION}/{name}"
        if target.exists():
            raw = target.read_bytes()
        else:
            with urllib.request.urlopen(url, timeout=120) as response:
                raw = response.read()
            assert len(raw) == info["size"], name
            if "lfs" in info:
                assert hashlib.sha256(raw).hexdigest() == info["lfs"]["sha256"], name
            else:
                blob = b"blob " + str(len(raw)).encode() + b"\0" + raw
                assert hashlib.sha1(blob).hexdigest() == info["blobId"], name
            with target.open("xb") as stream:
                stream.write(raw)
        digest = hashlib.sha256(raw).hexdigest()
        assert len(raw) == info["size"]
        if "lfs" in info:
            assert digest == info["lfs"]["sha256"]
        else:
            assert hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == info["blobId"]
        records[name] = {"path": str(target.relative_to(root)), "sha256": digest,
                         "bytes": len(raw), "url": url, "publisher_object": info}
        print(f"Verified {name}: {len(raw)} bytes", flush=True)
    report = {"schema": "m4-model-acquisition-1.0", "repo": REPO, "revision": REVISION,
              "license": "MIT per revision-pinned official model card", "files": records,
              "retrieved_at_utc": datetime.now(UTC).isoformat(),
              "download_seconds": time.perf_counter() - started,
              "total_snapshot_bytes": sum(f["bytes"] for f in records.values()),
              "scope": "Only safetensors and data/config files; no pickle, ONNX, remote code or other model."}
    output = work / "MODEL_ACQUISITION.json"
    with output.open("x") as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({k: v for k, v in report.items() if k != "files"}), flush=True)


if __name__ == "__main__":
    main()
