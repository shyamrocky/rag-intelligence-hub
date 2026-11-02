"""Explicit opt-in execution and immutable publication through the shared QA owner."""

import json
from pathlib import Path

from rag_hub.acquire import digest, local_path
from rag_hub.html_acquire import encode, immutable
from rag_hub.html_qualification import verify_release
from rag_hub.html_validation import check_document, fidelity, load_documents
from rag_hub.schemas import ParsedBlock, Section
from rag_hub.shared.qa import assess
from rag_hub.shared.registry import Adapter


def assess_document(root, document, admission):
    document["section_checks"] = check_document(document)
    return assess(
        root,
        document["source"],
        document["raw"],
        [ParsedBlock.model_validate(r["block"]) for r in document["parsed"]["records"]],
        [Section.model_validate(r["section"]) for r in document["normalized"]["records"]],
        document["normalized"]["audit"],
        Adapter("html-persisted-QA", "html", "html-QA-evidence-2.0", None, fidelity, None),
        document["corpus_id"],
        {k: v["sha256"] for k, v in document["entry"]["paths"].items()},
        html_evidence={document["source"].doc_id: document},
        html_admission=admission,
    )


def publish(
    root,
    *,
    release_path,
    expected_release_sha256,
    authorization_path,
    authorization_sha256,
    destination,
):
    """No parsing or source readiness; exact authorization supplied by trusted caller."""
    root = Path(root).resolve()
    verify_release(root, release_path, expected_release_sha256)
    admission = {
        "release_path": str(release_path),
        "expected_release_sha256": expected_release_sha256,
        "authorization_path": str(authorization_path),
        "authorization_sha256": authorization_sha256,
    }
    documents = load_documents(root)
    publications = []
    # Compute all records before writing, so an invalid source cannot cause partial admission.
    records = {}
    for doc, document in documents.items():
        records[doc] = {
            "schema": "html-scoped-QA-publication-1.0",
            "doc_id": doc,
            "corpus_manifest_sha256": document["manifest_sha256"],
            "admission": admission,
            "qa": assess_document(root, document, admission),
        }
    verify_release(root, release_path, expected_release_sha256)
    for doc, record in records.items():
        path = Path(destination) / (doc + ".json")
        immutable(local_path(root, path), encode(record))
        publications.append({"path": str(path), "sha256": digest(encode(record))})
    manifest = {
        "schema": "html-scoped-publication-manifest-1.0",
        "version": "html-admission-1.0",
        "release_path": str(release_path),
        "expected_release_sha256": expected_release_sha256,
        "authorization": {"path": str(authorization_path), "sha256": authorization_sha256},
        "corpus_manifest_sha256": next(iter(documents.values()))["manifest_sha256"],
        "publications": publications,
        "readiness_executed": False,
    }
    immutable(local_path(root, Path(destination) / "manifest.json"), encode(manifest))
    return manifest


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "release-path",
        "expected-release-sha256",
        "authorization-path",
        "authorization-sha256",
        "destination",
    ):
        parser.add_argument("--" + name, required=True)
    args = vars(parser.parse_args())
    print(json.dumps(publish(Path.cwd(), **args), indent=2))


if __name__ == "__main__":
    main()
