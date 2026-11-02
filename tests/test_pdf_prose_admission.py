"""Optional scoped QA: synthetic attestations only, never published approvals."""

import copy
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from rag_hub.acquire import digest
from rag_hub.pdf_corpus import encoded, load_corpus
from rag_hub.pdf_prose_execution import assess_persisted
from rag_hub.pdf_prose_handoff import load_passages
from rag_hub.pdf_prose_review import (
    ConsolidatedSubmission,
    preview_submission,
    scoped_evidence_proofs,
    verify_release,
)
from rag_hub.schemas import Section
from rag_hub.shared.contracts import read_source
from rag_hub.validation_models import QualityDecision, ValidationResult

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/validation/pdf/scoped-prose-admission-v1"
RELEASE = os.environ.get("RAG_TEST_QA_RELEASE", "config/pdf-prose-qa-successor.json")


def read(name):
    return json.loads((DATA / name).read_bytes())


def selection():
    return {
        "release_path": RELEASE,
        "expected_release_sha256": digest((ROOT / RELEASE).read_bytes()),
    }


@pytest.fixture(scope="module")
def evidence():
    if not (DATA / "evidence.json").exists():
        pytest.skip("private bounded PDF evidence not present")
    return read("evidence.json")


@pytest.fixture(scope="module")
def corpus(evidence):
    return load_corpus(ROOT)


def package():
    receipt = read("OWNER_APPROVAL_PENDING.json")
    receipt.update(
        decision="APPROVE_SCOPED",
        reviewer="SYNTHETIC_TEST_ONLY",
        submitted_at=datetime.now(UTC).isoformat(),
    )
    receipt_bytes = encoded(receipt)
    evidence, policy = read("evidence.json"), read("policy.json")
    now = datetime.now(UTC)
    authorization = {
        "owner": "SYNTHETIC_TEST_ONLY",
        "action": "authorize_scoped_pdf_qa_execution",
        "policy_sha256": digest(encoded(policy)),
        "owner_submission_sha256": digest(receipt_bytes),
        "evidence_sha256": digest(encoded(evidence)),
        "valid_from": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": (now + timedelta(hours=1)).isoformat(),
    }
    auth = encoded(authorization)
    return dict(
        evidence=evidence,
        policy=policy,
        submission_bytes=receipt_bytes,
        authorization_bytes=auth,
        expected_authorization_sha256=digest(auth),
        **selection(),
    )


def current(corpus, doc="C06"):
    v = corpus["documents"][doc]
    return (
        read_source(v["source"]),
        [Section.model_validate(x) for x in v["sections"]],
        [ValidationResult.model_validate(x) for x in v["qa"]["validation_results"]],
    )


def test_pending_consolidated_record_is_not_owner_approval(evidence):
    value = read("OWNER_APPROVAL_PENDING.json")
    typed = ConsolidatedSubmission.model_validate(value)
    assert typed.submitted_at is None and typed.actual_review_seconds is None
    assert not typed.reviewer and typed.decision == "PENDING"
    assert all("facets" not in c for c in value["cases"])
    assert preview_submission(ROOT, evidence, value)["approval_requests"] == []
    assert load_passages(ROOT, **selection()) == []


@pytest.mark.parametrize(
    "defect",
    [
        "missing_case",
        "duplicate",
        "source_hash",
        "Section_hash",
        "context",
        "safeguards",
        "anonymous",
        "time_missing",
        "corrections",
        "invented_facets",
        "stale_evidence",
    ],
)
def test_consolidated_bad_receipts_reject(evidence, defect):
    value = json.loads(package()["submission_bytes"])
    if defect == "missing_case":
        value["cases"].pop()
    elif defect == "duplicate":
        value["cases"][1] = copy.deepcopy(value["cases"][0])
    elif defect == "source_hash":
        value["cases"][0]["binding"]["source"]["raw_sha256"] = "0" * 64
    elif defect == "Section_hash":
        value["cases"][0]["binding"]["atomic_sections"][0]["normalized_sha256"] = "0" * 64
    elif defect == "context":
        value["cases"][1]["binding"]["context_label"] = "Inherited incorrect heading"
    elif defect == "safeguards":
        value["safeguards"].pop("C06")
    elif defect == "anonymous":
        value["reviewer"] = ""
    elif defect == "time_missing":
        value["submitted_at"] = None
    elif defect == "corrections":
        value["corrections"] = "unresolved change"
    elif defect == "invented_facets":
        value["facets"] = {"all": "PASS"}
    else:
        value["evidence_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        preview_submission(ROOT, evidence, value)


@pytest.mark.parametrize(
    "defect",
    [
        "missing_receipt",
        "missing_authorization",
        "expired",
        "wrong_owner",
        "wrong_release",
        "partial_parent",
        "new_reason",
        "high_risk",
        "context_fail",
        "integrity_fail",
        "wrong_format",
        "changed_source",
        "changed_Section",
        "future_receipt",
    ],
)
def test_preconditions_fail_closed(evidence, corpus, defect):
    args = package()
    source, sections, results = current(corpus)
    ident = evidence["cases"][2]["binding"]["atomic_sections"][0]["section_id"]
    i = next(i for i, r in enumerate(results) if r.section_id == ident)
    if defect == "missing_receipt":
        args["submission_bytes"] = b"{}"
    elif defect == "missing_authorization":
        args["expected_authorization_sha256"] = None
    elif defect in ("expired", "wrong_owner"):
        a = json.loads(args["authorization_bytes"])
        a["expires_at" if defect == "expired" else "owner"] = (
            "2000-01-01T00:00:00Z" if defect == "expired" else "foreign"
        )
        args["authorization_bytes"] = encoded(a)
        args["expected_authorization_sha256"] = digest(encoded(a))
    elif defect == "wrong_release":
        args["expected_release_sha256"] = "0" * 64
    elif defect == "partial_parent":
        sections = [s for s in sections if s.section_id != ident]
    elif defect in ("new_reason", "high_risk", "context_fail", "integrity_fail"):
        updates = {
            "new_reason": {"reasons": results[i].reasons + ("unknown_defect",)},
            "high_risk": {"risk": "high"},
            "context_fail": {"checks": {**results[i].checks, "context": "fail"}},
            "integrity_fail": {"blocking_integrity": True},
        }[defect]
        results[i] = results[i].model_copy(update=updates)
    elif defect == "wrong_format":
        source = source.model_copy(update={"source_format": "html"})
    elif defect == "changed_source":
        source = source.model_copy(update={"snapshot_id": "changed"})
    elif defect == "changed_Section":
        sections = [
            s.model_copy(update={"heading_path": ("changed",)}) if s.section_id == ident else s
            for s in sections
        ]
    else:
        value = json.loads(args["submission_bytes"])
        value["submitted_at"] = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        args["submission_bytes"] = encoded(value)
        a = json.loads(args["authorization_bytes"])
        a["owner_submission_sha256"] = digest(args["submission_bytes"])
        args["authorization_bytes"] = encoded(a)
        args["expected_authorization_sha256"] = digest(encoded(a))
    with pytest.raises((ValueError, KeyError)):
        scoped_evidence_proofs(ROOT, source, sections, results, **args)


@pytest.fixture(scope="module")
def qa_pairs(evidence):
    pairs = {}
    args = package()
    for doc in ("C01", "C02", "C06", "C14"):
        base = assess_persisted(ROOT, doc, **selection())
        candidate = assess_persisted(ROOT, doc, **selection(), admission=args)
        pairs[doc] = base, candidate
    return pairs


@pytest.mark.parametrize("doc,n", [("C01", 1), ("C02", 1), ("C06", 15), ("C14", 2)])
def test_actual_QA_owner_complete_bundles_only(evidence, corpus, qa_pairs, doc, n):
    base, candidate = qa_pairs[doc]
    assert all(d["status"] == "hold" for d in base["quality_decisions"])
    assert base["validation_results"] == corpus["documents"][doc]["qa"]["validation_results"]
    assert base["validation_results"] == candidate["validation_results"]
    assert base["source_fidelity"] == candidate["source_fidelity"] == "manual_required"
    approved = [d for d in candidate["quality_decisions"] if d["status"] != "hold"]
    assert len(approved) == n
    expected = {
        s["section_id"]
        for c in evidence["cases"]
        if c["doc_id"] == doc
        for s in c["binding"]["atomic_sections"]
    }
    assert {d["section_id"] for d in approved} == expected
    for d in approved:
        with pytest.raises(ValidationError):
            QualityDecision.model_validate(d)


def stored_publications(tmp_path, qa_pairs):
    """Use a repository-local temporary directory, removed by the calling fixture."""
    import tempfile

    directory = tempfile.TemporaryDirectory(prefix=".pdf-qa-test-", dir=DATA)
    paths = []
    for doc, (_, qa) in qa_pairs.items():
        p = Path(directory.name) / (doc + ".json")
        raw = encoded({"schema": "pdf-scoped-QA-publication-1.0", "doc_id": doc, "qa": qa})
        p.write_bytes(raw)
        paths.append({"path": str(p.relative_to(ROOT)), "sha256": digest(raw)})
    return directory, paths


def test_read_only_handoff_context_attribution_and_determinism(tmp_path, qa_pairs):
    directory, paths = stored_publications(tmp_path, qa_pairs)
    try:
        first = load_passages(ROOT, paths, **selection())
        assert first == load_passages(ROOT, paths, **selection())
        assert len(first) == 8
        lookup = {v["candidate_id"]: v for v in first}
        c02 = lookup["C02-candidate-b00014"]["retrieval_context"]
        assert c02["source_spans"][0]["block_id"] == "C02:b00009"
        assert c02["source_spans"][0]["end"] == 15
        c14 = lookup["C14-candidate-b00024"]["retrieval_context"]
        assert c14["source_spans"][0]["block_id"] == "C14:b00006"
        assert "arXiv" not in c14["heading_label"]
        attr = lookup["C06-candidate-b00042"]["retrieval_context"]["claim_attribution"]
        assert attr["benchmark_limitation_requires_explicit_report_attribution"]
        assert not attr["universal_fact_verified"]
        assert all(not v["whole_source_ready"] for v in first)
    finally:
        directory.cleanup()


@pytest.mark.parametrize(
    "defect",
    [
        "plain_status",
        "partial",
        "neighbor",
        "context",
        "receipt",
        "publication_hash",
        "unsupported_math",
        "validation_changed",
        "policy_changed",
        "duplicate_source",
    ],
)
def test_handoff_rejects_bad_or_incomplete_publications(tmp_path, qa_pairs, defect):
    directory, paths = stored_publications(tmp_path, qa_pairs)
    try:
        path = ROOT / paths[2]["path"]
        value = json.loads(path.read_bytes())
        q = value["qa"]
        approved = [d for d in q["quality_decisions"] if d["status"] != "hold"]
        if defect == "plain_status":
            q.pop("scoped_pdf_support")
        elif defect == "partial":
            q["quality_decisions"].remove(approved[0])
        elif defect == "neighbor":
            next(d for d in q["quality_decisions"] if d["status"] == "hold")["status"] = (
                "approved_for_index"
            )
        elif defect == "context":
            approved[0]["scope"]["retrieval_context_projection"]["heading_label"] = "Wrong"
        elif defect == "receipt":
            q["scoped_pdf_support"]["original_owner_submission_base64"] = "e30="
        elif defect == "unsupported_math":
            approved[0]["scope"]["parent_id"] = "unverified-equation"
        elif defect == "validation_changed":
            q["validation_results"][0]["checks"]["source_fidelity"] = "pass"
        elif defect == "policy_changed":
            q["policy"]["version"] = "unknown"
        elif defect == "duplicate_source":
            paths.append(paths[2])
        elif defect == "publication_hash":
            paths[2]["sha256"] = "0" * 64
        if defect not in ("duplicate_source", "publication_hash"):
            raw = encoded(value)
            path.write_bytes(raw)
            paths[2]["sha256"] = digest(raw)
        with pytest.raises((ValueError, KeyError)):
            load_passages(ROOT, paths, **selection())
    finally:
        directory.cleanup()


def test_release_pins_actual_implementation(evidence):
    release = verify_release(
        ROOT, path=RELEASE, expected_sha256=selection()["expected_release_sha256"]
    )
    assert release["version"] in {"pdf-scoped-qa-1.0", "combined-scoped-qa-1.0"}
    with pytest.raises(ValueError):
        verify_release(ROOT, RELEASE, "0" * 64)


def test_historical_C04_ledger_unchanged(evidence):
    p = (
        ROOT
        / "data/validation/bf9ec63f85912861a86677647d2056a6e23a7e0758315682cec29d78c0fe4580/decisions.jsonl"
    )
    assert (
        digest(p.read_bytes()) == "3dec07fdd049d9e0a43ff84b78dddcc97d5ae8aef6ab146ea02c9f475f259064"
    )
    rows = [json.loads(s) for s in p.read_text().splitlines()]
    approved = [r for r in rows if r["status"] != "hold"]
    assert len(approved) == 40 and {r["doc_id"] for r in approved} == {"C04"}
    assert len(rows) - len(approved) == 1634


def test_final_QA_replay_never_extracts_PDF_text(evidence, monkeypatch):
    import pymupdf

    import rag_hub.parse_pdf

    def forbidden(*args, **kwargs):
        raise AssertionError("persisted QA replay cannot reparse or extract text")

    monkeypatch.setattr(pymupdf.Page, "get_text", forbidden)
    monkeypatch.setattr(rag_hub.parse_pdf, "parse_pdf", forbidden)
    for doc in ("C01", "C02", "C06", "C14"):
        result = assess_persisted(ROOT, doc, **selection())
        assert all(d["status"] == "hold" for d in result["quality_decisions"])


def test_legacy_models_remain_schema_compatible(evidence):
    import importlib.util

    import rag_hub.validation_models as current_models

    path = ROOT / (
        "workspace/pdf-remediation/phase3/pdf-qa-admission-integration-v1/"
        "rollback/src/rag_hub/validation_models.py"
    )
    spec = importlib.util.spec_from_file_location("pdf_QA_predecessor_models", path)
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    for name in ("ValidationPolicy", "ValidationResult", "QualityDecision", "QualityReview"):
        assert getattr(current_models, name).model_json_schema() == getattr(
            original, name
        ).model_json_schema()
