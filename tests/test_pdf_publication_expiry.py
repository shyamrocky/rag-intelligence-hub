"""Read-only expiration and integrity controls on the actual frozen publication."""

import copy
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import rag_hub.pdf_corpus as corpus_module
import rag_hub.pdf_publication as publication_module
from rag_hub.acquire import digest
from rag_hub.pdf_corpus import encoded, load_corpus
from rag_hub.pdf_prose_handoff import load_passages
from rag_hub.pdf_prose_review import scoped_evidence_proofs
from rag_hub.schemas import Section
from rag_hub.shared.contracts import read_source
from rag_hub.ui import format_answer_for_display
from rag_hub.validation_models import ValidationResult

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / (
    "data/validation/pdf/scoped-prose-admission-v1/publications/"
    "8e25375a13e1f7c20524d6df438a1bea5b49f06bac0945889e091115a3106004"
)


@pytest.fixture(scope="module")
def handoff():
    if not (BASE / "handoff.json").exists():
        pytest.skip("private owner-approved publication not present")
    return json.loads((BASE / "handoff.json").read_bytes())


def selection(handoff):
    return {k: handoff[k] for k in ("release_path", "expected_release_sha256")}


def expiration():
    return datetime.fromisoformat(
        json.loads((BASE / "QA_EXECUTION_AUTHORIZATION.json").read_bytes())["expires_at"]
    )


@pytest.mark.parametrize("offset,status", [(-1, "VALID"), (0, "EXPIRED"), (86400, "EXPIRED")])
def test_valid_and_expired_publication_remains_readable(handoff, monkeypatch, offset, status):
    monkeypatch.setattr(
        publication_module, "utc_now", lambda: expiration() + timedelta(seconds=offset)
    )
    before = digest((BASE / "QA_EXECUTION_AUTHORIZATION.json").read_bytes())
    passages = load_passages(ROOT, handoff["publications"], **selection(handoff))
    original = json.loads((BASE / "verified-passages.json").read_bytes())
    assert len(passages) == 8
    assert len({s for p in passages for s in p["required_section_ids"]}) == 19
    for passage, old in zip(passages, original, strict=True):
        metadata = passage["publication"]
        assert metadata["status"] == status
        assert metadata["expires_at"] == handoff["authorization_expires_at"]
        assert metadata["retrieval_allowed"]
        assert metadata["display_to_user_when_used"] == (status == "EXPIRED")
        assert bool(metadata["warning"]) == (status == "EXPIRED")
        assert {k: v for k, v in passage.items() if k != "publication"} == old
    assert digest((BASE / "QA_EXECUTION_AUTHORIZATION.json").read_bytes()) == before


def test_expiration_warning_is_visible_only_for_used_content(handoff, monkeypatch):
    monkeypatch.setattr(publication_module, "utc_now", lambda: expiration() + timedelta(days=1))
    passages = load_passages(ROOT, handoff["publications"], **selection(handoff))
    text = "Answer with its original citation [C01, page 1]."
    assert format_answer_for_display(text, []) == text
    displayed = format_answer_for_display(text, passages[:2])
    assert displayed.startswith(text)
    assert displayed.count("Warning:") == 1
    assert "Publication authorization expired" in displayed
    assert "previously approved PDF content" in displayed


def test_valid_content_has_no_warning(handoff, monkeypatch):
    monkeypatch.setattr(publication_module, "utc_now", lambda: expiration() - timedelta(seconds=1))
    passages = load_passages(ROOT, handoff["publications"], **selection(handoff))
    assert format_answer_for_display("Answer [C02, page 1].", passages) == "Answer [C02, page 1]."


def test_answer_finishing_after_expiry_warns_for_previously_valid_passage(handoff, monkeypatch):
    monkeypatch.setattr(publication_module, "utc_now", lambda: expiration() - timedelta(seconds=1))
    passages = load_passages(ROOT, handoff["publications"][:1], **selection(handoff))
    assert passages[0]["publication"]["status"] == "VALID"
    monkeypatch.setattr(publication_module, "utc_now", lambda: expiration() + timedelta(seconds=1))
    assert "Warning: Publication authorization expired" in format_answer_for_display(
        "Answer.", passages
    )
    assert passages[0]["publication"]["status"] == "VALID"  # No mutation of cached evidence.


@pytest.mark.parametrize("missing", ["publication", "warning", "display_to_user_when_used"])
def test_display_cannot_silently_omit_required_warning(handoff, monkeypatch, missing):
    monkeypatch.setattr(publication_module, "utc_now", lambda: expiration() + timedelta(days=1))
    passage = load_passages(ROOT, handoff["publications"][:1], **selection(handoff))[0]
    if missing == "publication":
        passage.pop("publication")
    else:
        passage["publication"].pop(missing)
    with pytest.raises(ValueError, match="missing_publication_display_metadata"):
        format_answer_for_display("Answer.", [passage])


def test_expired_publication_invalid_hash_still_rejects(handoff, monkeypatch):
    monkeypatch.setattr(publication_module, "utc_now", lambda: expiration() + timedelta(days=1))
    refs = copy.deepcopy(handoff["publications"])
    refs[0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="unbound_or_stale"):
        load_passages(ROOT, refs, **selection(handoff))


def test_tampered_source_records_reject_without_writing_corpus(handoff, tmp_path, monkeypatch):
    manifest = json.loads((ROOT / "data/normalized/pdf/four-pdf-poc-v1/manifest.json").read_bytes())
    target = manifest["documents"]["C01"]["blocks"]
    changed = json.loads((ROOT / target).read_bytes())
    changed[8]["content"] += " corrupted"
    replacement = tmp_path / "changed-blocks.json"
    replacement.write_bytes(encoded(changed))
    original = corpus_module.local_path
    monkeypatch.setattr(
        corpus_module,
        "local_path",
        lambda root, name: replacement if str(name) == target else original(root, name),
    )
    monkeypatch.setattr(publication_module, "utc_now", lambda: expiration() + timedelta(days=1))
    with pytest.raises(ValueError, match="persisted_artifact_hash_mismatch"):
        load_passages(ROOT, handoff["publications"], **selection(handoff))


@pytest.mark.parametrize(
    "defect", ["partial", "neighbor", "context", "attribution", "owner_receipt"]
)
def test_expired_publication_integrity_checks_not_weakened(handoff, tmp_path, monkeypatch, defect):
    # A trusted hash/config is deliberately supplied for a corrupted copy to
    # exercise the underlying QA/parent guards beyond the frozen allowlist.
    import tempfile

    monkeypatch.setattr(publication_module, "utc_now", lambda: expiration() + timedelta(days=1))
    descriptor = handoff["publications"][2]
    value = json.loads((ROOT / descriptor["path"]).read_bytes())
    qa = value["qa"]
    approved = [d for d in qa["quality_decisions"] if d["status"] != "hold"]
    if defect == "partial":
        qa["quality_decisions"].remove(approved[0])
    elif defect == "neighbor":
        next(d for d in qa["quality_decisions"] if d["status"] == "hold")["status"] = (
            "approved_for_index"
        )
    elif defect == "context":
        approved[0]["scope"]["retrieval_context_projection"]["heading_label"] = "Wrong"
    elif defect == "attribution":
        approved[0]["scope"]["retrieval_context_projection"]["claim_attribution"][
            "universal_fact_verified"
        ] = True
    else:
        qa["scoped_pdf_support"]["original_owner_submission_base64"] = "e30="
    with tempfile.TemporaryDirectory(prefix=".expiry-test-", dir=BASE.parent) as directory:
        p = Path(directory) / "bad.json"
        raw = encoded(value)
        p.write_bytes(raw)
        path = str(p.relative_to(ROOT))
        config = json.loads((ROOT / publication_module.READER_CONFIG).read_bytes())
        config["approved_publications"].pop(descriptor["path"])
        config["approved_publications"][path] = digest(raw)
        config_path = tmp_path / "trusted-test-reader.json"
        config_path.write_bytes(encoded(config))
        original = publication_module.local_path
        monkeypatch.setattr(
            publication_module,
            "local_path",
            lambda root, name: (
                config_path
                if str(name) == publication_module.READER_CONFIG
                else original(root, name)
            ),
        )
        with pytest.raises((ValueError, KeyError, TypeError)):
            load_passages(ROOT, [{"path": path, "sha256": digest(raw)}], **selection(handoff))


def test_new_QA_execution_still_rejects_expired_authorization(handoff, monkeypatch):
    import rag_hub.pdf_prose_review as review

    v = load_corpus(ROOT)["documents"]["C01"]
    evidence = json.loads(
        (ROOT / "data/validation/pdf/scoped-prose-admission-v1/evidence.json").read_bytes()
    )
    auth = json.loads((BASE / "QA_EXECUTION_AUTHORIZATION.json").read_bytes())
    auth.update(valid_from="2000-01-01T00:00:00Z", expires_at="2000-01-02T00:00:00Z")
    # Only bypass release preflight in this unit control to reach the strict
    # execution time check. Real publication/QA artifacts are never modified.
    monkeypatch.setattr(review, "verify_release", lambda *args: None)
    with pytest.raises(ValueError, match="authorization_expired_or_not_yet_valid"):
        scoped_evidence_proofs(
            ROOT,
            read_source(v["source"]),
            [Section.model_validate(x) for x in v["sections"]],
            [ValidationResult.model_validate(x) for x in v["qa"]["validation_results"]],
            evidence=evidence,
            policy=json.loads(
                (ROOT / "data/validation/pdf/scoped-prose-admission-v1/policy.json").read_bytes()
            ),
            submission_bytes=(BASE / "OWNER_APPROVAL.json").read_bytes(),
            authorization_bytes=encoded(auth),
            expected_authorization_sha256=digest(encoded(auth)),
            **selection(handoff),
        )


@pytest.mark.parametrize(
    "start,end",
    [
        ("2090-01-01T00:00:00Z", "2090-01-02T00:00:00Z"),
        ("2000-01-02T00:00:00Z", "2000-01-01T00:00:00Z"),
        ("2000-01-01", "2000-01-02"),
    ],
)
def test_malformed_or_not_yet_valid_publication_is_not_expiry_exception(start, end):
    with pytest.raises(ValueError):
        publication_module.publication_metadata({"valid_from": start, "expires_at": end})
