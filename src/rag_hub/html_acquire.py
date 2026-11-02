"""Bounded acquisition of the fixed HTML allowlist; never crawl linked content."""

import argparse
import json
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from rag_hub.acquire import digest, local_path

MAX_BYTES = 15 * 1024 * 1024


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def immutable(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError("immutable_artifact_changed: " + str(path))
    else:
        with path.open("xb") as stream:
            stream.write(payload)


class Redirects(HTTPRedirectHandler):
    def __init__(self, host):
        self.host = host.removeprefix("www.")
        self.chain = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urlsplit(newurl)
        if target.scheme != "https" or target.hostname.removeprefix("www.") != self.host:
            raise ValueError("redirect_outside_pinned_publisher: " + newurl)
        if len(self.chain) >= 8:
            raise ValueError("redirect_limit")
        self.chain.append({"from": req.full_url, "to": newurl, "status": code})
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def acquire(root, *, source_ids=None):
    config = json.loads(local_path(root, "config/html-sources.json").read_text())
    results = []
    for spec in config["sources"]:
        if source_ids and spec["doc_id"] not in source_ids:
            continue
        doc = spec["doc_id"]
        destination = local_path(root, f"data/raw/html/{doc}.html")
        receipt_path = local_path(root, f"data/raw/html/{doc}.acquisition.json")
        if receipt_path.exists():
            receipt = json.loads(receipt_path.read_text())
            if receipt["requested_url"] != spec["canonical_url"]:
                raise ValueError("pinned_url_changed")
            if receipt.get("raw_sha256") != digest(destination.read_bytes()):
                raise ValueError("raw_source_integrity_mismatch")
            results.append(receipt)
            continue
        handler = Redirects(urlsplit(spec["canonical_url"]).hostname)
        receipt = {
            "doc_id": doc,
            "requested_url": spec["canonical_url"],
            "retrieved_at": datetime.now(UTC).isoformat(),
            "method": "bounded_urllib_GET_accept_html_identity_encoding",
            "request_headers": {
                "Accept": "text/html",
                "Accept-Encoding": "identity",
                "User-Agent": "RAGIntelligenceHub/0.1 (private fixed-corpus study)",
            },
            "redirects": handler.chain,
            "rights": "owner_authorized_private_local_processing_only; redistribution_uncleared",
        }
        try:
            request = Request(spec["canonical_url"], headers=receipt["request_headers"])
            try:
                response = build_opener(handler).open(request, timeout=30)
            except HTTPError as exc:
                response = exc
            with response:
                raw = response.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise ValueError("response_exceeds_15_MiB")
                receipt.update(
                    final_url=response.url,
                    http_status=response.code,
                    content_type=response.headers.get("Content-Type"),
                    response_headers=dict(response.headers),
                    raw_sha256=digest(raw),
                    byte_size=len(raw),
                    charset=response.headers.get_content_charset() or "utf-8",
                )
            immutable(destination, raw)
            receipt["status"] = (
                "acquired"
                if receipt["http_status"] == 200
                and "html" in (receipt["content_type"] or "").lower()
                else "blocked_response"
            )
            immutable(receipt_path, encode(receipt))
        except (URLError, OSError, ValueError) as exc:
            receipt.update(status="blocked_transport", error=str(exc))
            # Transport failures are separate attempts, never authoritative acquired receipts.
            attempt = digest(encode(receipt))[:16]
            immutable(
                local_path(root, f"data/raw/html/{doc}.failed-{attempt}.json"), encode(receipt)
            )
        results.append(receipt)
        print(doc, receipt["status"], receipt.get("http_status"), flush=True)
    return results


def main():
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--source", action="append")
    args = parser.parse_args()
    acquire(args.root.resolve(), source_ids=args.source)


if __name__ == "__main__":
    main()
