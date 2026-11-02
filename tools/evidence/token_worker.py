"""Offline counting only in the existing chunking runtime; no model inference."""

import json
import sys
from pathlib import Path

from rag_hub.m2_tokenizer import PinnedBgeTokenizer


def main():
    from tools.indexing.m5_index import no_network

    no_network()
    request = json.load(sys.stdin)
    if set(request) != {"root", "texts"} or not isinstance(request["texts"], list) or any(
            not isinstance(t, str) for t in request["texts"]):
        raise ValueError("m8_invalid_count_request")
    tokenizer = PinnedBgeTokenizer(Path(request["root"]))
    result = [{"sha256": __import__("hashlib").sha256(t.encode()).hexdigest(),
               "tokens": tokenizer.count(t)} for t in request["texts"]]
    print(json.dumps({"schema": "m8-token-counts-1.0", "counts": result,
                      "tokenizer": tokenizer.metadata()}, sort_keys=True))


if __name__ == "__main__":
    main()
