"""Residual-source dispositions and consumer scope, without repeating the audit."""

import copy
import json
from pathlib import Path

import pytest
from test_markdown_qualification import census, staged  # noqa: F401 -- shared synthetic fixtures

from rag_hub.acquire import digest
from rag_hub.html_acquire import encode
from rag_hub.markdown_handoff import load_units
from rag_hub.markdown_qualification import assess
from rag_hub.markdown_residual import BASE, BOILERPLATE, DEFECTS, OUTPUTS, SCORE, source_issues

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def residual():
    return assess(ROOT)


@pytest.mark.parametrize("number", range(42))
def test_each_residual_has_exact_source_and_non_authoritative_issue(residual, number):
    register = source_issues(residual)
    issue = register["issues"][number]
    raw = (ROOT / residual["source"]["raw_path"]).read_text().splitlines(keepends=True)
    a, b = issue["source_line_start"], issue["source_line_end"]
    fragment = "".join(raw[a - 1 : b])
    assert fragment == issue["evidence"]["raw_source_text"]
    assert digest(fragment.encode()) == issue["evidence"]["raw_fragment_sha256"]
    assert issue["qa_decision_reference"]["assessment_sha256"] == digest(encode(residual))
    assert issue["acquisition_status"] == "source_acquired_and_verified"
    assert issue["retrieval_eligible"] is False
    assert issue["retrieval_exclusion_reason"]
    assert issue["confirmed_parser_failure"] is False
    if issue["qa_disposition"] == "candidate":
        assert issue["resolution_status"] == "mitigated"
        assert issue["required_context"]
    else:
        assert issue["recommended_action"]


def test_original_40_decisions_and_76_candidates_and_38_units_preserved(residual):
    initial = json.loads((ROOT / BASE).read_bytes())
    new = {c["section_id"]: c for c in residual["sections"]}
    assert len(new) == 158
    assert residual["counts"] == {"historical": 40, "candidate": 114, "excluded": 4}
    assert residual["units"][: len(initial["units"])] == initial["units"]
    for c in initial["sections"]:
        assert new[c["section_id"]]["historical_decision"] == c["historical_decision"]
        if c["assessment"] in ("candidate", "historical"):
            assert new[c["section_id"]]["assessment"] == c["assessment"]
            assert set(c["qualified_unit_ids"]) <= set(new[c["section_id"]]["qualified_unit_ids"])
    assert len(source_issues(residual)["issues"]) == 42
    assert residual["confirmed_extraction_defects"] == 0
    assert residual["confirmed_original_source_defects"] == 3


def test_source_errors_and_metric_group_are_retained_not_repaired(residual):
    rows = {int(c["block_id"].rsplit("b", 1)[1]): c for c in residual["sections"]}
    for n in set(DEFECTS) | SCORE:
        assert rows[n]["assessment"] == "candidate"
        assert rows[n]["qualified_unit_ids"]
        assert rows[n]["raw_Section_not_qualified_for_direct_retrieval"]
    assert "langchain-voyageai" in rows[91]["residual_source_evidence"]["raw_source_text"]
    source = rows[103]["residual_source_evidence"]["raw_source_text"].splitlines()
    assert len(source[4]) - len(source[4].lstrip()) == len(source[5]) - len(source[5].lstrip())
    assert set(rows[119]["code_analysis"]["unresolved"]) >= {
        "AWS4Auth",
        "OpenSearchVectorSearch",
        "boto3",
    }
    for n in BOILERPLATE:
        assert rows[n]["assessment"] == "excluded"


def test_outputs_only_appear_inside_their_exact_attributed_example(residual):
    rows = {int(c["block_id"].rsplit("b", 1)[1]): c for c in residual["sections"]}
    for output, example in OUTPUTS.items():
        row = rows[output]
        units = [u for u in residual["units"] if u["unit_id"] in row["qualified_unit_ids"]]
        assert len(units) == 1
        u = units[0]
        assert rows[example]["section_id"] in u["required_section_ids"]
        assert row["section_id"] in u["context_only_section_ids"]
        assert u["documentation_scope"]["tested_or_executable_guidance"] is False
        assert u["documentation_scope"]["provider_selection"] is None
        assert (
            u["context"][row["section_id"]]["consumption_role"] == "attributed_example_output_only"
        )
    assert "partial Document excerpt" in " ".join(
        next(u for u in residual["units"] if rows[188]["section_id"] in u["required_section_ids"])[
            "documentation_scope"
        ]["limitations"]
    )


def test_context_never_invents_a_provider_and_keeps_async_requirement(residual):
    for u in residual["units"]:
        scope = u.get("documentation_scope")
        if not scope:
            continue
        assert scope["selected_embedding_provider"] is None
        assert scope["selected_vector_store_provider"] is None
        providers = {v["provider_tab"] for v in u["context"].values()} - {None}
        assert len(providers) <= 1
        assert all(m not in u["context_only_section_ids"] for m in u["supporting_heading_ids"])
    asynchronous = next(
        u for u in residual["units"] if any(":b00179:" in m for m in u["required_section_ids"])
    )
    assert any("async/notebook" in s for s in asynchronous["documentation_scope"]["limitations"])


def test_active_handoff_still_contains_only_historical_approvals(residual):
    approved = {c["section_id"] for c in residual["sections"] if c["assessment"] == "historical"}
    units = load_units(ROOT)
    assert {m["section"].section_id for u in units for m in u["members"]} == approved
    assert len(units) == 40


@pytest.mark.parametrize("change", ["base_evidence", "raw", "canonical", "source_metadata"])
def test_rehashed_local_claims_cannot_change_frozen_inputs(tmp_path, residual, change):
    # Fail before any parser or full audit can run.
    import shutil

    paths = set(residual["bindings"])
    for name in paths:
        out = tmp_path / name
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, out)
    name = (
        BASE
        if change == "base_evidence"
        else residual["source"]["raw_path"]
        if change == "raw"
        else "data/normalized/markdown/C04.json"
        if change == "canonical"
        else "data/manifests/markdown/corpus-manifest.json"
    )
    p = tmp_path / name
    p.write_bytes(p.read_bytes() + b"\nchanged\n")
    with pytest.raises(ValueError, match="changed_"):
        assess(tmp_path)


def test_42_only_reassessment_does_not_call_initial_audit(monkeypatch):
    import rag_hub.markdown_qualification as policy

    def forbidden(*args, **kwargs):
        raise AssertionError("must reuse the frozen initial audit")

    monkeypatch.setattr(policy, "audit", forbidden)
    assert policy.assess(ROOT)["residual_sections_reassessed"] == 42


def test_shared_owner_consumer_preserves_new_scope_and_rejects_rehashed_partial_units(staged):  # noqa: F811
    # The fixture and QA publication are disposable synthetic controls, not an
    # owner enablement or an authoritative corpus admission.
    from test_markdown_qualification import _arguments

    from rag_hub.shared.qa import assess as shared_assess

    root, selection, evidence = staged
    qa = shared_assess(*_arguments(root), markdown_qualification=selection)
    publication = {
        "schema": "markdown-unit-QA-publication-1.0",
        "status": "AUTHORITATIVE_SHARED_QA",
        "qa": qa,
    }
    path = root / "SYNTHETIC-scope-publication.json"
    path.write_bytes(encode(publication))
    descriptor = dict(
        selection, publication_path=path.name, publication_sha256=digest(path.read_bytes())
    )
    units = load_units(root, admission=descriptor)
    quoted = [u for u in units if u["documentation_scope"]]
    assert len(quoted) == 21
    assert all(u["documentation_scope"]["quoted_documentation_only"] for u in quoted)
    assert sum(len(u["context_only_section_ids"]) for u in quoted) == 7
    unsupported = {
        c["section_id"] for c in evidence["sections"] if c["assessment"] in ("hold", "excluded")
    }
    assert not unsupported & {
        m.get("section_id") or m["section"].section_id for u in units for m in u["members"]
    }
    forged = copy.deepcopy(publication)
    output = next(m for u in quoted for m in u["context_only_section_ids"])
    for d in forged["qa"]["quality_decisions"]:
        if d["section_id"] == output:
            d["scope"]["units"][0]["context_only_section_ids"] = []
    path.write_bytes(encode(forged))
    with pytest.raises(ValueError, match="not_authoritative_engine_output"):
        load_units(root, admission=dict(descriptor, publication_sha256=digest(path.read_bytes())))
