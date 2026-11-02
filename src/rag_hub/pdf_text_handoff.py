"""Explicit PDF text publication and verified read-only complete-unit consumption.

No default scope change, ranking, chunking, model execution or readiness grant.
"""

import copy
import json
from pathlib import Path

from rag_hub.acquire import digest, local_path
from rag_hub.consumption import SCHEMA, select
from rag_hub.html_acquire import immutable
from rag_hub.pdf_corpus import encoded, load_corpus
from rag_hub.pdf_text_recovery import VERSION, source_text, verify_release
from rag_hub.schemas import ParsedBlock, Section
from rag_hub.shared.builtins import entries
from rag_hub.shared.contracts import read_source
from rag_hub.shared.qa import assess
from rag_hub.validation_models import ValidationPolicy, ValidationResult
from rag_hub.validation_reviews import make_decisions


def assess_document(root, document, admission):
    source = read_source(document["source"])
    original = document["qa"]["policy"]
    return assess(
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
        pdf_text_admission=admission,
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
    release = verify_release(root, release_path, expected_release_sha256)
    admission = {
        "release_path": str(release_path),
        "expected_release_sha256": expected_release_sha256,
        "authorization_path": str(authorization_path),
        "authorization_sha256": authorization_sha256,
    }
    corpus = load_corpus(root)
    records = {
        doc: {
            "schema": "pdf-text-QA-publication-1.0",
            "doc_id": doc,
            "admission": admission,
            "qa": assess_document(root, d, admission),
        }
        for doc, d in corpus["documents"].items()
    }
    verify_release(root, release_path, expected_release_sha256)
    descriptors = []
    for doc, record in records.items():
        p = str(Path(destination) / (doc + ".json"))
        raw = encoded(record)
        immutable(local_path(root, p), raw)
        descriptors.append({"path": p, "sha256": digest(raw)})
    manifest = {
        "schema": "pdf-text-QA-manifest-1.0",
        "version": release.get("policy_version", VERSION),
        "admission": admission,
        "publications": descriptors,
        "canonical_section_count": 2425,
        "corpus_manifest_sha256": digest(
            local_path(root, "data/normalized/pdf/four-pdf-poc-v1/manifest.json").read_bytes()
        ),
        "historical_handoff": json.loads(
            local_path(
                root,
                release.get(
                    "qualification_policy_path", "config/pdf-text-qualification-policy.json"
                ),
            ).read_bytes()
        )["historical_handoff"],
        "readiness_executed": False,
        "default_reader_scope_changed": False,
    }
    if release.get("predecessor_publication"):
        manifest["predecessor_publication"] = release["predecessor_publication"]
    immutable(local_path(root, str(Path(destination) / "manifest.json")), encoded(manifest))
    return manifest


def view(u, identity, descriptor):
    math = u["content_type"] == "mathematical_reference"
    text = u["display_text"]
    if math:
        text = u["structure"]["reference_latex"].replace("\\\\", "\\")
    source = {
        "kind": "SOURCE_CONTENT",
        "text": text,
        "content_type": u["content_type"],
        "source_id": u["doc_id"],
        "source_title": u["source"]["title"],
        "source_url": u["source"]["canonical_url"],
        "source_sha256": u["source"]["raw_sha256"],
        "citations": u["citation_locators"],
        "structure": u["structure"],
    }
    if math:
        source["representation"] = (
            "owner-verified source transcription; not original extractor/model output"
        )
    q = {
        "kind": "QUALIFICATION",
        "mandatory": True,
        "complete_unit_only": True,
        "limitations": u["known_limitations"],
        "allowed_usage": u["allowed_usage"],
        "forbidden_usage": u["forbidden_usage"],
        "source_fidelity_is_not_publisher_truth_certification": True,
    }
    result = {
        "schema_version": SCHEMA,
        "unit_id": u["id"],
        "source_id": u["doc_id"],
        "source_format": "pdf",
        "admission_status": "ADMITTED",
        "source_fidelity": {
            "status": "VERIFIED_SCOPED_PROJECTION",
            "scope": "exact admitted source spans/context only; native glyph replay is not universal visual verification",
        },
        "reference_classification": u["reference_classification"] + "_REFERENCE",
        "required_section_ids": u["required_section_ids"],
        "required_context": u["required_context"],
        "known_limitations": [
            {**x, "issue_type": "source_scope_limitation"} for x in u["qa_observations"]
        ],
        "qa_observations": u["qa_observations"],
        "related_evidence": u["related_evidence"],
        "allowed_usage": u["allowed_usage"],
        "forbidden_usage": u["forbidden_usage"],
        "citation_locators": u["citation_locators"],
        "llm_context": {
            "source_content": [source],
            "required_context": u["required_context"],
            "qa_observations": u["qa_observations"],
            "qualification": q,
        },
        "publication_identity": identity,
        "metadata": {
            "title": u["source"]["title"],
            "content_type": u["content_type"],
            "has_known_issues": bool(u["qa_observations"]),
            "requires_context": bool(u["required_context"]),
        },
        "audit_only": {
            "original_extracted_text": u["text"],
            "source_members": u["source_members"],
            "source_snapshot_id": u["source"]["snapshot_id"],
            "unit_sha256": u["unit_sha256"],
            "authoritative_QA": descriptor,
            "presentation_evidence": u["presentation"],
        },
    }
    result = copy.deepcopy(result)
    if u.get("historical_passage"):
        from rag_hub.pdf_publication import display_metadata

        old = u["historical_passage"]
        result["audit_only"]["historical_passage"] = old
        result["llm_context"]["required_context"].append(
            {"role": "mandatory_historical_reviewed_context", **old["retrieval_context"]}
        )
    if u.get("historical_publication_interval"):
        from rag_hub.pdf_publication import display_metadata

        result["publication_expiration"] = display_metadata(u["historical_publication_interval"])
        warning = result["publication_expiration"]["warning"]
        if warning:
            result["llm_context"]["qa_observations"].append(
                {
                    "kind": "QA_OBSERVATION",
                    "severity": "WARNING",
                    "issue_id": "PDF_PUBLICATION_EXPIRED",
                    "explanation": warning,
                    "display_to_user_when_used": True,
                }
            )
    return result


def load_units(
    root,
    *,
    manifest_path,
    expected_manifest_sha256,
    release_path,
    expected_release_sha256,
    authorization_sha256,
    filters=None,
):
    """Require trusted explicit selector; source text cannot select its own release."""
    from rag_hub.pdf_text_recovery import evidence_proofs

    verify_release(root, release_path, expected_release_sha256)
    raw = local_path(root, manifest_path).read_bytes()
    if digest(raw) != expected_manifest_sha256:
        raise ValueError("pdf_text_publication_hash_mismatch")
    manifest = json.loads(raw)
    admission = manifest["admission"]
    if (
        manifest.get("schema") != "pdf-text-QA-manifest-1.0"
        or admission["release_path"] != str(release_path)
        or admission["expected_release_sha256"] != expected_release_sha256
        or admission["authorization_sha256"] != authorization_sha256
    ):
        raise ValueError("pdf_text_publication_identity_mismatch")
    corpus = load_corpus(root)
    if (
        digest(local_path(root, "data/normalized/pdf/four-pdf-poc-v1/manifest.json").read_bytes())
        != manifest["corpus_manifest_sha256"]
    ):
        raise ValueError("pdf_text_corpus_binding_changed")
    seen = set()
    views = []
    identity = {
        "manifest_path": str(manifest_path),
        "manifest_sha256": expected_manifest_sha256,
        "qa_release_path": str(release_path),
        "qa_release_sha256": expected_release_sha256,
        "authorization_sha256": authorization_sha256,
    }
    for descriptor in manifest["publications"]:
        raw = local_path(root, descriptor["path"]).read_bytes()
        if digest(raw) != descriptor["sha256"]:
            raise ValueError("changed_pdf_text_QA_publication")
        p = json.loads(raw)
        doc = p["doc_id"]
        if doc in seen or doc not in corpus["documents"] or p.get("admission") != admission:
            raise ValueError("duplicate_foreign_or_unbound_pdf_QA")
        seen.add(doc)
        d = corpus["documents"][doc]
        qa = p["qa"]
        inputs = qa["pdf_text_fingerprint_inputs"]
        policy = ValidationPolicy.model_validate_json(inputs["policy_json"])
        results = [ValidationResult.model_validate_json(x) for x in inputs["validation_json"]]
        if (
            policy.model_dump(mode="json") != qa["policy"]
            or [r.model_dump(mode="json") for r in results] != qa["validation_results"]
        ):
            raise ValueError("changed_pdf_decision_fingerprint_inputs")
        if qa["validation_results"] != d["qa"]["validation_results"]:
            raise ValueError("pdf_legacy_diagnostics_changed")
        proofs, evidence = evidence_proofs(
            root,
            read_source(d["source"]),
            local_path(root, d["source"]["snapshot_path"]).read_bytes(),
            [ParsedBlock.model_validate(b) for b in d["blocks"]],
            [Section.model_validate(s) for s in d["sections"]],
            d["audit"],
            results,
            **admission,
        )
        expected = make_decisions(results, policy, qa["cohort_gates"], {}, pdf_text_proofs=proofs)
        if [x.model_dump(mode="json") for x in expected] != qa[
            "quality_decisions"
        ] or evidence != qa["pdf_text_support"]:
            raise ValueError("forged_pdf_QA_decisions_or_recovery")
        approved = {x.section_id for x in expected if x.status == "approved_for_index"}
        for u in evidence["units"]:
            if not set(u["required_section_ids"]) <= approved:
                raise ValueError("partial_pdf_unit_approval")
            if (
                source_text(u["source_members"], {b["block_id"]: b for b in d["blocks"]})
                != u["text"]
            ):
                raise ValueError("changed_pdf_consumable_text")
            views.append(view(u, identity, descriptor))
    if seen != {"C01", "C02", "C06", "C14"}:
        raise ValueError("incomplete_pdf_publication")
    verify_release(root, release_path, expected_release_sha256)
    return select(views, **filters) if filters else views


def validate_consumption_unit(root, value, *, selection):
    # Compare the entire verified envelope, not a caller-recomputed checksum.
    expected = next(
        (u for u in load_units(root, **selection) if u["unit_id"] == value.get("unit_id")), None
    )
    if expected is None or encoded(expected) != encoded(value):
        raise ValueError("altered_unapproved_warning_or_context_stripped_pdf_unit")
    return True


def serialize_consumption_unit(root, value, *, selection):
    validate_consumption_unit(root, value, selection=selection)
    return encoded(value)
