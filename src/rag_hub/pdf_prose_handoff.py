"""Read-only consumption of externally pinned, authoritative scoped QA records.

No ranking, chunking, source parsing, status inference or eligibility decisions.
The caller must obtain publication hashes and release selection from trusted run
configuration, not source content or the publication being verified.
"""

import json
from base64 import b64decode

from rag_hub.acquire import digest, local_path
from rag_hub.pdf_corpus import encoded, load_corpus
from rag_hub.pdf_prose_review import scoped_evidence_proofs, verify_release
from rag_hub.pdf_publication import (
    HISTORICAL_RELEASE_SHA256,
    publication_metadata,
    published_evidence_proofs,
    verify_reader,
)
from rag_hub.schemas import Section
from rag_hub.shared.contracts import read_source
from rag_hub.validation_models import ScopedPdfDecision, ValidationPolicy, ValidationResult
from rag_hub.validation_reviews import make_decisions


def load_passages(root, publications=(), *, release_path, expected_release_sha256):
    published_read = expected_release_sha256 == HISTORICAL_RELEASE_SHA256
    release_check = verify_reader if published_read else verify_release
    reader = release_check(root, release_path, expected_release_sha256)
    if not publications:
        return []
    corpus = load_corpus(root)
    passages, seen_docs = [], set()
    for descriptor in publications:
        raw = local_path(root, descriptor["path"]).read_bytes()
        if digest(raw) != descriptor["sha256"]:
            raise ValueError("unbound_or_stale_authoritative_QA_publication")
        if (
            published_read
            and reader["approved_publications"].get(descriptor["path"]) != descriptor["sha256"]
        ):
            raise ValueError("unapproved_or_changed_frozen_publication")
        publication = json.loads(raw)
        if publication.get("schema") != "pdf-scoped-QA-publication-1.0":
            raise ValueError("unsupported_QA_publication")
        doc_id = publication["doc_id"]
        if doc_id in seen_docs or doc_id not in corpus["documents"]:
            raise ValueError("duplicate_or_foreign_QA_source")
        seen_docs.add(doc_id)
        document = corpus["documents"][doc_id]
        qa = publication["qa"]
        support = qa.get("scoped_pdf_support")
        if not support or (
            support.get("schema") != "scoped-pdf-QA-support-1.0"
            or support.get("release_path") != str(release_path)
            or support.get("release_sha256") != expected_release_sha256
            or support.get("source_wide_fidelity_changed") is not False
            or support.get("consumption") != "complete_parent_bundle_only"
            or qa.get("source_fidelity") != "manual_required"
            or qa.get("validation_results") != document["qa"]["validation_results"]
            or qa.get("fidelity_checks") != document["qa"]["fidelity_checks"]
            or qa.get("policy") != document["qa"]["policy"]
        ):
            raise ValueError("missing_or_changed_authoritative_QA_support")
        arguments = {
            "evidence": support["evidence"],
            "policy": support["policy"],
            "submission_bytes": b64decode(
                support["original_owner_submission_base64"], validate=True
            ),
            "authorization_bytes": b64decode(
                support["original_policy_authorization_base64"], validate=True
            ),
            "expected_authorization_sha256": support["authorization_sha256"],
            "release_path": release_path,
            "expected_release_sha256": expected_release_sha256,
        }
        sections = [Section.model_validate(s) for s in document["sections"]]
        fingerprints = support["decision_fingerprint_inputs"]
        policy = ValidationPolicy.model_validate_json(fingerprints["policy_json"])
        results = [
            ValidationResult.model_validate_json(fingerprints["validation_json"][r["section_id"]])
            for r in qa["validation_results"]
        ]
        if (
            policy.model_dump(mode="json") != qa["policy"]
            or [r.model_dump(mode="json") for r in results] != qa["validation_results"]
            or len(fingerprints["validation_json"]) != len(results)
        ):
            raise ValueError("decision_fingerprint_input_mismatch")
        proof_check = published_evidence_proofs if published_read else scoped_evidence_proofs
        proofs = proof_check(root, read_source(document["source"]), sections, results, **arguments)
        # Replay the existing sole decision function; never reimplement its policy.
        expected = make_decisions(
            results,
            policy,
            qa["cohort_gates"],
            {},
            scoped_pdf_proofs=proofs,
        )
        if qa.get("quality_decisions") != [d.model_dump(mode="json") for d in expected]:
            raise ValueError("partial_forged_or_neighboring_QA_decisions")
        accepted = {d.section_id: d for d in expected if isinstance(d, ScopedPdfDecision)}
        if set(accepted) != set(proofs):
            raise ValueError("incomplete_scoped_parent_decisions")
        for case in support["evidence"]["cases"]:
            if case["doc_id"] != doc_id:
                continue
            binding = case["binding"]
            ids = [s["section_id"] for s in binding["atomic_sections"]]
            if not set(ids) & accepted.keys():
                continue
            if not set(ids) <= accepted.keys():
                raise ValueError("incomplete_parent_bundle")
            scope = accepted[ids[0]].scope
            if any(accepted[i].scope != scope for i in ids):
                raise ValueError("conflicting_parent_scopes")
            passages.append(
                {
                    "candidate_id": case["candidate_id"],
                    "parent_id": binding["parent"]["id"],
                    "text": binding["parent"]["text"],
                    "text_sha256": binding["text_sha256"],
                    "parent_sha256": binding["parent_sha256"],
                    "source": binding["source"],
                    "source_members": binding["members"],
                    "required_section_ids": ids,
                    "retrieval_context": scope["retrieval_context_projection"],
                    "owner_receipt_sha256": accepted[ids[0]].receipt_sha256,
                    "policy_authorization_sha256": support["authorization_sha256"],
                    "authoritative_publication": descriptor,
                    "consumption": "complete_parent_bundle_only",
                    "whole_source_ready": False,
                    "publication": publication_metadata(
                        json.loads(arguments["authorization_bytes"])
                    ),
                }
            )
    release_check(root, release_path, expected_release_sha256)
    return passages


def publication_descriptor(path, value):
    """Canonical serialization helper; a computed hash alone establishes no trust."""
    return {"path": str(path), "sha256": digest(encoded(value))}
