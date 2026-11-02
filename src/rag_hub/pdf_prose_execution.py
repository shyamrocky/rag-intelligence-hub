"""Explicit QA-only replay of persisted PDF observations; no parser execution.

Returns the existing QA owner's record. No files, eligibility ledger or readiness
pointer are published by this helper. Owner execution authorization is checked by
the QA owner whenever scoped evidence is supplied.
"""

from rag_hub.acquire import local_path
from rag_hub.pdf_corpus import load_corpus
from rag_hub.pdf_prose_review import verify_release
from rag_hub.schemas import ParsedBlock, Section
from rag_hub.shared.builtins import entries
from rag_hub.shared.contracts import read_source
from rag_hub.shared.qa import assess


def assess_persisted(
    root,
    doc_id,
    *,
    release_path,
    expected_release_sha256,
    admission=None,
):
    verify_release(root, release_path, expected_release_sha256)
    document = load_corpus(root)["documents"][doc_id]
    source = read_source(document["source"])
    original = document["qa"]["policy"]
    if admission is not None and (
        admission.get("release_path") != str(release_path)
        or admission.get("expected_release_sha256") != expected_release_sha256
    ):
        raise ValueError("QA_execution_release_selection_mismatch")
    result = assess(
        root,
        source,
        local_path(root, source.snapshot_path).read_bytes(),
        [ParsedBlock.model_validate(b) for b in document["blocks"]],
        [Section.model_validate(s) for s in document["sections"]],
        document["audit"],
        entries()[0],
        original["input_run_id"],
        original["artifact_sha256"],
        classifications=document["pdf_classification"],
        pdf_prose_admission=admission,
        pdf_replay={
            "release_path": str(release_path),
            "expected_release_sha256": expected_release_sha256,
        },
    )
    verify_release(root, release_path, expected_release_sha256)
    return result
