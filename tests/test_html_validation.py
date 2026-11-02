"""Owned HTML QA challenge controls; synthetic reviews are never owner evidence."""

import copy
from pathlib import Path

import pytest

from rag_hub.acquire import digest
from rag_hub.content_validation import ValidationInput
from rag_hub.html_acquire import encode
from rag_hub.html_corpus import normalize
from rag_hub.html_reviews import review_binding, validate_cohort, validate_receipt
from rag_hub.html_validation import check_document, fidelity
from rag_hub.parse_html import parse_html
from rag_hub.schemas import ParsedBlock, Section, SourceManifest
from rag_hub.shared.qa import assess
from rag_hub.shared.registry import Adapter
from rag_hub.validation_models import QualityReview, ValidationPolicy, ValidationResult
from rag_hub.validation_reviews import cohort_gates, make_decisions
from rag_hub.validation_sampling import fingerprint, sample_sections


def example(body='<h1 id="title">Owned</h1><p>A complete owned paragraph.</p>'):
    raw = f"<html><body><main>{body}</main></body></html>".encode()
    source = SourceManifest(
        doc_id="OWNED",
        snapshot_id="sha256-" + digest(raw),
        title="Owned",
        publisher="Owned",
        source_format="html",
        canonical_url="https://example.org/owned",
        original_url="https://example.org/owned",
        byte_size=len(raw),
        raw_path=Path("data/raw/owned.html"),
        raw_sha256=digest(raw),
        snapshot_path=Path("data/snapshots/owned.html"),
        rights_status="local_use_approved",
    )
    parsed = parse_html(raw, source)
    return {
        "source": source,
        "raw": raw,
        "snapshot": raw,
        "acquisition": {"charset": "utf-8"},
        "parsed": parsed,
        "normalized": normalize(parsed),
        "bindings_verified": True,
        "corpus_id": digest(b"owned-corpus"),
    }


def target(document, kind="paragraph"):
    record = next(r for r in document["parsed"]["records"] if r["classification"] == kind)
    norm = next(
        r
        for r in document["normalized"]["records"]
        if r["section"]["block_ids"] == [record["block"]["block_id"]]
    )
    return record, norm


def outcome(document, kind="paragraph"):
    _, row = target(document, kind)
    return check_document(document)[row["section"]["section_id"]]


def test_valid_source_checks_pass_but_independent_fidelity_remains_hold():
    result = outcome(example())
    assert result["technical_outcome"] == "PASS"
    assert result["independent_source_fidelity"] == "HOLD"
    assert result["checks"]["table_structure"]["outcome"] == "not_applicable"


def test_source_scan_and_fences_preserve_unicode_entities_and_code_whitespace():
    doc = example(
        '<h1>Owned</h1><p>Café &amp; Ω.</p><pre><code class="language-python">if x &lt; 2:\n    print("``` é")\n</code></pre>'
    )
    assert outcome(doc)["technical_outcome"] == "PASS"
    assert outcome(doc, "code_block")["checks"]["code_block_fidelity"]["outcome"] == "PASS"


def test_table_and_nested_list_markup_are_checked_without_semantic_promotion():
    doc = example(
        '<h1>Owned</h1><ul><li>A<ul><li>B</li></ul></li></ul><table><tr><th colspan="2">Header</th></tr><tr><td>A</td><td>2</td></tr></table>'
    )
    assert outcome(doc, "unordered_list")["checks"]["list_structure"]["outcome"] == "PASS"
    table = outcome(doc, "table")
    assert table["checks"]["table_structure"]["outcome"] == "PASS"
    assert table["technical_outcome"] == "HOLD"


@pytest.mark.parametrize(
    "body,kind",
    [
        (
            '<h1>Owned</h1><figure><img src="a.png"><figcaption>Caption</figcaption></figure>',
            "figure",
        ),
        ("<h1>Owned</h1><div>Unclassified words.</div>", "unknown"),
        (
            '<h1>Owned</h1><div role="tabpanel" hidden><p>Alternative paragraph.</p></div>',
            "paragraph",
        ),
        ('<h1>Owned</h1><aside role="doc-footnote"><p>Footnote text.</p></aside>', "paragraph"),
    ],
)
def test_unknown_visual_alternative_and_footnote_dependencies_stay_hold(body, kind):
    assert outcome(example(body), kind)["technical_outcome"] == "HOLD"


def test_missing_manifest_verification_is_hold():
    doc = example()
    doc["bindings_verified"] = False
    assert outcome(doc)["checks"]["corpus_artifact_bindings"]["outcome"] == "HOLD"


def test_changed_original_bytes_fail_identity():
    doc = example()
    doc["raw"] += b" "
    assert outcome(doc)["checks"]["original_snapshot_identity"]["outcome"] == "FAIL"


def test_changed_snapshot_fails_identity():
    doc = example()
    doc["snapshot"] += b" "
    assert outcome(doc)["checks"]["original_snapshot_identity"]["outcome"] == "FAIL"


def test_forged_DOM_locator_fails_source_trace():
    doc = example()
    record, row = target(doc)
    record["dom_path"] += "/fake[1]"
    row["dom_path"] = record["dom_path"]
    assert outcome(doc)["checks"]["DOM_locator_traceability"]["outcome"] == "FAIL"


def test_missing_source_text_fails_even_when_derived_hashes_are_recomputed():
    doc = example()
    record, row = target(doc)
    record["block"]["content"] = "A complete paragraph."
    record["block"]["content_sha256"] = digest(record["block"]["content"].encode())
    row["section"]["text"] = record["block"]["content"]
    row["section"]["normalized_sha256"] = record["block"]["content_sha256"]
    assert outcome(doc)["checks"]["exact_source_text"]["outcome"] == "FAIL"


def test_entire_dropped_paragraph_fails_independent_body_accounting():
    doc = example("<h1>Owned</h1><p>First paragraph.</p><p>Second paragraph.</p>")
    doc["parsed"]["records"].pop()
    doc["normalized"]["records"].pop()
    assert outcome(doc)["checks"]["body_text_accounting"]["outcome"] == "FAIL"


def test_truncated_paragraph_span_is_not_a_complete_source_element():
    doc = example()
    record, row = target(doc)
    start, end = record["raw_char_span"]
    record["raw_char_span"] = [start, end - 4]
    record["raw_fragment_sha256"] = digest(doc["raw"][start : end - 4])
    row.update({k: record[k] for k in ("raw_char_span", "raw_fragment_sha256")})
    assert outcome(doc)["checks"]["DOM_locator_traceability"]["outcome"] == "FAIL"


def test_dropped_table_cell_fails_structural_completeness():
    doc = example("<h1>Owned</h1><table><tr><td>A</td><td>B</td></tr></table>")
    record, row = target(doc, "table")
    record["source_tree"]["children"][0]["children"].pop()
    row["source_tree"] = copy.deepcopy(record["source_tree"])
    assert outcome(doc, "table")["checks"]["table_structure"]["outcome"] == "FAIL"


def test_wrong_heading_ownership_fails_even_if_section_and_block_agree():
    doc = example()
    record, row = target(doc)
    record["block"]["heading_path"] = ["Wrong"]
    row["section"]["heading_path"] = ["Wrong"]
    assert outcome(doc)["checks"]["heading_ownership"]["outcome"] == "FAIL"


def test_source_heading_level_gap_remains_hold():
    doc = example("<h1>Owned</h1><h3>Skipped level</h3><p>Paragraph.</p>")
    values = list(check_document(doc).values())
    assert values[1]["checks"]["heading_hierarchy"]["outcome"] == "HOLD"


def test_unresolved_container_fails_dependency_binding():
    doc = example()
    record, row = target(doc)
    record["contexts"] = ["/missing-container"]
    row["contexts"] = ["/missing-container"]
    assert outcome(doc)["checks"]["context_locator_bindings"]["outcome"] == "FAIL"


def test_explicit_navigation_contamination_is_a_failure():
    doc = example()
    doc["raw"] = doc["raw"].replace(b"<p>", b'<p role="navigation">')
    assert outcome(doc)["checks"]["navigation_furniture"]["outcome"] == "FAIL"


def receipt_fixture(tmp_path):
    doc = example()
    _, row = target(doc)
    section = row["section"]
    result = ValidationResult(
        section_id=section["section_id"],
        doc_id="OWNED",
        raw_sha256=section["raw_sha256"],
        normalized_sha256=section["normalized_sha256"],
        risk="medium",
        cohort="OWNED:prose",
        checks={"source_fidelity": "manual_required", "integrity": "pass"},
        reasons=("html_independent_source_review_required", "html_source_qualification_pending"),
        eligible_automatic=False,
        coverage_tags=("doc:OWNED", "type:prose"),
    )
    policy = ValidationPolicy(
        input_run_id="owned-QA",
        artifact_sha256={},
        expected_hold_count=1,
        expected_original_approvals=0,
    )
    plan = sample_sections([result], policy)
    qa_bytes = b"owned QA artifact"
    binding = review_binding(doc, row, result, qa_artifact_sha256=digest(qa_bytes))
    review = QualityReview(
        section_id=result.section_id,
        raw_sha256=result.raw_sha256,
        normalized_sha256=result.normalized_sha256,
        policy_sha256=fingerprint(policy),
        sample_sha256=fingerprint(plan),
        role="acceptance",
        reviewer="Synthetic test operator",
        method="source_comparison",
        evidence_note="Owned fixture only, not a corpus owner review",
        verdict="pass",
    )
    (tmp_path / "owned-evidence.txt").write_bytes(b"owned evidence")
    for path, data in [
        (doc["source"].raw_path, doc["raw"]),
        (doc["source"].snapshot_path, doc["snapshot"]),
        (Path("data/validation/html/v2/OWNED.json"), qa_bytes),
    ]:
        dest = tmp_path / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    receipt = {
        "schema_version": "html-section-review-1.0",
        "binding": binding,
        "review": review.model_dump(mode="json"),
        "evidence_references": {
            **binding["required_evidence_references"],
            "owned-evidence.txt": digest(b"owned evidence"),
        },
    }
    kwargs = {
        "expected_binding": binding,
        "results": [result],
        "plan": plan,
        "policy": policy,
        "root": tmp_path,
    }
    return receipt, kwargs


def validate_owned(receipt, kwargs):
    data = encode(receipt)
    return validate_receipt(data, expected_submission_sha256=digest(data), **kwargs)


def test_valid_receipt_is_review_only_and_existing_engine_still_holds(tmp_path):
    receipt, kwargs = receipt_fixture(tmp_path)
    review = validate_owned(receipt, kwargs)
    gates, mapped = cohort_gates(kwargs["results"], kwargs["plan"], kwargs["policy"], [review])
    decisions = make_decisions(kwargs["results"], kwargs["policy"], gates, mapped)
    assert decisions[0].status == "hold" and decisions[0].receipt_sha256 is None


def test_missing_owner_confirmation_and_forged_submission_are_rejected(tmp_path):
    receipt, kwargs = receipt_fixture(tmp_path)
    raw = encode(receipt)
    with pytest.raises(ValueError, match="unconfirmed"):
        validate_receipt(raw, expected_submission_sha256=None, **kwargs)
    receipt["review"]["reviewer"] = "Forged"
    with pytest.raises(ValueError, match="unconfirmed"):
        validate_receipt(encode(receipt), expected_submission_sha256=digest(raw), **kwargs)


@pytest.mark.parametrize(
    "key",
    [
        "corpus_id",
        "source_snapshot_sha256",
        "normalized_sha256",
        "raw_locator",
        "heading_path",
        "dependencies",
        "qa_artifact_sha256",
    ],
)
def test_stale_source_DOM_context_or_validation_binding_is_rejected(tmp_path, key):
    receipt, kwargs = receipt_fixture(tmp_path)
    receipt["binding"] = copy.deepcopy(receipt["binding"])
    receipt["binding"][key] = "stale"
    with pytest.raises(ValueError, match="stale"):
        validate_owned(receipt, kwargs)


def test_receipt_cannot_request_manual_override(tmp_path):
    receipt, kwargs = receipt_fixture(tmp_path)
    receipt["review"]["manual_approval"] = True
    with pytest.raises(ValueError, match="cannot_override"):
        validate_owned(receipt, kwargs)


def test_required_source_and_QA_artifacts_cannot_be_omitted(tmp_path):
    receipt, kwargs = receipt_fixture(tmp_path)
    receipt["evidence_references"] = {"owned-evidence.txt": digest(b"owned evidence")}
    with pytest.raises(ValueError, match="missing_required_source"):
        validate_owned(receipt, kwargs)


def test_HTML_review_contract_rejects_other_formats(tmp_path):
    receipt, kwargs = receipt_fixture(tmp_path)
    receipt["binding"]["source_format"] = "pdf"
    with pytest.raises(ValueError, match="requires_HTML_format"):
        validate_owned(receipt, kwargs)


def test_stale_quality_plan_and_changed_evidence_reference_fail_closed(tmp_path):
    receipt, kwargs = receipt_fixture(tmp_path)
    receipt["review"]["sample_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="stale quality"):
        validate_owned(receipt, kwargs)
    receipt, kwargs = receipt_fixture(tmp_path)
    (tmp_path / "owned-evidence.txt").write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed_evidence"):
        validate_owned(receipt, kwargs)


def test_duplicate_incomplete_or_extra_cohort_receipts_are_rejected(tmp_path):
    receipt, kwargs = receipt_fixture(tmp_path)
    raw = encode(receipt)
    sid = receipt["review"]["section_id"]
    common = {k: v for k, v in kwargs.items() if k != "expected_binding"}
    common.update(expected_submission_hashes={sid: digest(raw)}, bindings={sid: receipt["binding"]})
    with pytest.raises(ValueError, match="duplicate"):
        validate_cohort([raw, raw], expected_ids={sid}, **common)
    with pytest.raises(ValueError, match="incomplete"):
        validate_cohort([raw], expected_ids={sid, "missing"}, **common)
    with pytest.raises(ValueError, match="out_of_scope"):
        validate_cohort([raw], expected_ids=set(), **common)


@pytest.mark.skipif(
    "html_evidence" not in ValidationInput.__dataclass_fields__,
    reason="shared HTML dispatch is staged; main shared files intentionally unchanged",
)
def test_staged_shared_QA_owner_recognizes_HTML_without_eligibility(tmp_path):
    doc = example()
    doc["section_checks"] = check_document(doc)
    blocks = [ParsedBlock.model_validate(r["block"]) for r in doc["parsed"]["records"]]
    sections = [Section.model_validate(r["section"]) for r in doc["normalized"]["records"]]
    adapter = Adapter("owned-html", "html", "test", None, fidelity, None)
    result = assess(
        tmp_path,
        doc["source"],
        doc["raw"],
        blocks,
        sections,
        doc["normalized"]["audit"],
        adapter,
        "owned",
        {},
        html_evidence={"OWNED": doc},
    )
    assert all(
        "unsupported_source_format" not in r["reasons"] for r in result["validation_results"]
    )
    assert all(d["status"] == "hold" for d in result["quality_decisions"])
    # Missing bound evidence is still recognized HTML, but never silently PASS.
    held = assess(tmp_path, doc["source"], doc["raw"], blocks, sections, [], adapter, "owned", {})
    assert all("html_bound_evidence_missing" in r["reasons"] for r in held["validation_results"])
    # A current Section cannot borrow technical results from a different frozen record.
    changed = sections[1].model_copy(
        update={"text": "Changed paragraph.", "normalized_sha256": digest(b"Changed paragraph.")}
    )
    rejected = assess(
        tmp_path,
        doc["source"],
        doc["raw"],
        blocks,
        [sections[0], changed],
        [],
        adapter,
        "owned",
        {},
        html_evidence={"OWNED": doc},
    )
    assert rejected["validation_results"][1]["blocking_integrity"]
    assert rejected["validation_results"][1]["checks"]["integrity"] == "fail"
    assert "html_current_section_binding_fail" in rejected["validation_results"][1]["reasons"]
