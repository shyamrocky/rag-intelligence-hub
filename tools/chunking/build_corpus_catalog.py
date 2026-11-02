"""Checkpoint B full-corpus builder, using the passed C01 foundation unchanged."""

import argparse
import json
import socket
from pathlib import Path

from build_catalog import build

from rag_hub.chunk_preparation import write_once
from rag_hub.corpus_chunking import CorpusChunker
from rag_hub.unified_models import encode, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, default=Path("data/chunking/m3-corpus-v2"))
    p.add_argument("--selector", type=Path)
    args = p.parse_args()
    root = Path.cwd()
    checkpoint = root / "workspace/rag-implementation/v1/m3/CHECKPOINT_A.json"
    if json.loads(checkpoint.read_text())["status"] != "PASS":
        raise ValueError("checkpoint_A_has_not_passed")
    attempts = []
    connect = socket.socket.connect

    def offline(sock, address):
        attempts.append(str(address))
        raise RuntimeError("M3_network_not_authorized")

    socket.socket.connect = offline
    try:
        manifest, runtime = build(root, root / args.output, None, engine_factory=CorpusChunker,
                                  component_paths=["src/rag_hub/corpus_chunking.py",
                                                   "tools/chunking/build_corpus_catalog.py"])
        assert not attempts
        if args.selector:
            write_once(root / args.selector, encode({
                "schema": "chunk-catalog-selection-1.0",
                "manifest_path": str(args.output / "manifest.json"),
                "manifest_sha256": sha(encode(manifest))}))
        print(json.dumps({"summary": manifest["summary"], "runtime": runtime,
                          "network_attempts": attempts}, indent=2), flush=True)
    finally:
        socket.socket.connect = connect


if __name__ == "__main__":
    main()
