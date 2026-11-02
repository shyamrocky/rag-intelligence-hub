"""Bounded C10 evidence, severity semantics and actual selected consumer contract."""

import copy
import json
from decimal import Decimal
from pathlib import Path

import pytest

from rag_hub.acquire import digest
from rag_hub.consumption import SEVERITIES, html_view, select
from rag_hub.html_acquire import encode
from rag_hub.html_c10 import ISSUE, SECTION, extend, validate_relationships
from rag_hub.html_handoff import load_units, serialize_consumption_unit, validate_consumption_unit
from rag_hub.html_validation import load_documents

ROOT = Path(__file__).resolve().parents[1]
SELECTOR = ROOT / "config/html-c10-admission-publication.json"


@pytest.fixture(scope="module")
def source_case():
    document = load_documents(ROOT)["C10"]
    selection = json.loads((ROOT / "config/html-text-admission-publication.json").read_bytes())
    manifest = json.loads((ROOT / selection["manifest_path"]).read_bytes())
    descriptor = next(p for p in manifest["publications"] if p["path"].endswith("C10.json"))
    raw = (ROOT / descriptor["path"]).read_bytes()
    assert digest(raw) == descriptor["sha256"]
    baseline = json.loads(raw)["qa"]["scoped_html_support"]
    spec = json.loads((ROOT / "data/normalized/html/c10-admission-v1/scope.json").read_bytes())
    return document, baseline, spec


def test_source_table_is_complete_and_separate_from_RRF_context(source_case):
    doc, base, spec = source_case
    result = extend(doc, base, spec)
    table = result["units"][-1]
    assert base["units"] == result["units"][:-1]
    assert table["content_section_ids"] == [SECTION]
    assert table["reference_classification"] == "ILLUSTRATIVE_REFERENCE"
    structure = table["textual_projections"][-1]["table_text_structure"]
    assert structure["headers"] == [
        "Match found",
        "Position in results",
        "@search.score",
        "weight multiplier",
        "@search.score (weighted)",
    ]
    assert len(structure["rows"]) == 4 and all(len(r) == 5 for r in structure["rows"])
    data = [[c["text"] for c in row] for row in structure["rows"][1:]]
    assert [row[2] for row in data] == ["0.8383955", "0.81514114", "0.8577363"]
    # Only literal displayed multiplications, not independent RRF/runtime certification.
    for row in data[:2]:
        assert Decimal(row[2]) * Decimal(row[3]) == Decimal(row[4])
    assert structure["numeric_semantics_verified"] is False
    assert table["source_issues"][0]["severity"] == "WARNING"
    assert table["source_issues"][0]["origin"] == "ingestion_QA_not_publisher"
    assert table["source_issues"][0]["confirmed_source_error"] is False
    validate_relationships(result["units"])


@pytest.mark.parametrize("tamper", ["raw", "binding", "formula", "missing_formula", "source_check"])
def test_C10_insufficient_or_changed_source_evidence_blocks(source_case, tamper):
    doc, base, spec = copy.deepcopy(source_case)
    if tamper == "raw":
        doc["raw"] = doc["raw"].replace(b"0.8383955", b"0.8383956")
    elif tamper == "binding":
        spec["source_bindings"][-1]["raw_fragment_sha256"] = "0" * 64
    elif tamper == "formula":
        spec["formula_unit_sha256"] = "0" * 64
    elif tamper == "missing_formula":
        base["units"] = [u for u in base["units"] if u["id"] != spec["formula_unit_id"]]
    else:
        f = next(f for f in base["sections"] if f["section_id"] == SECTION)
        next(iter(f["checks"]["checks"].values()))["outcome"] = "FAIL"
    with pytest.raises(ValueError):
        extend(doc, base, spec)


@pytest.mark.parametrize("severity", ["BLOCKING", "UNRECOGNIZED"])
def test_warning_cannot_override_a_blocker(source_case, severity):
    doc, base, spec = source_case
    units = extend(doc, base, spec)["units"]
    unit = copy.deepcopy(units[-1])
    unit["source_issues"][0]["severity"] = severity
    assert set(SEVERITIES) == {"BLOCKING", "WARNING", "INFORMATIONAL"}
    with pytest.raises(ValueError):
        html_view(unit, {u["id"]: u for u in units}, {})


@pytest.fixture(scope="module")
def published():
    if not SELECTOR.exists():
        pytest.skip("explicit C10 publication not yet installed")
    selection = json.loads(SELECTOR.read_bytes())
    views = load_units(ROOT, **selection, filters={"admission_status": "ALL"})
    unit = next(v for v in views if SECTION in v["required_section_ids"])
    return selection, views, unit


def test_actual_HTML_totals_and_C10_distinct_evidence_kinds(published):
    _, views, unit = published
    admitted = select(views)
    excluded = select(views, admission_status="EXCLUDED")
    assert len(admitted) == 155 and len(excluded) == 30
    assert len({s for v in admitted for s in v["required_section_ids"]}) == 427
    assert all(v["llm_context"] is None for v in excluded)
    assert unit["reference_classification"] == "ILLUSTRATIVE_REFERENCE"
    context = unit["llm_context"]
    assert context["source_content"][0]["kind"] == "SOURCE_CONTENT"
    assert context["source_content"][0]["table"]["rows"][1][2]["text"] == "0.8383955"
    assert context["qa_observations"][0]["kind"] == "QA_OBSERVATION"
    assert context["qa_observations"][0]["issue_id"] == ISSUE
    assert context["qualification"]["kind"] == "QUALIFICATION"
    relation = next(c for c in context["required_context"] if c.get("unit_id"))
    assert any("1/(rank + k)" in c["text"] for c in relation["source_content"])
    assert relation["required_context"] and relation["qualification"]["limitations"]
    assert unit["publication_identity"]["schema"] == "html-scoped-publication-manifest-1.1"


@pytest.mark.parametrize(
    "field,value",
    [
        ("reference_classification", "STANDARD_REFERENCE"),
        ("reference_classification", "ILLUSTRATIVE_REFERENCE"),
        ("has_known_issues", True),
        ("requires_context", True),
        ("source_id", "C10"),
        ("issue_type", "ambiguity"),
        ("admission_status", "EXCLUDED"),
        ("source_format", "html"),
    ],
)
def test_filters_select_whole_unchanged_contracts(published, field, value):
    _, views, _ = published
    result = select(views, **{field: value})
    assert result
    original = {v["unit_id"]: v for v in views}
    assert all(v == original[v["unit_id"]] for v in result)
    for v in result:
        if v["admission_status"] == "ADMITTED":
            assert v["llm_context"]["qualification"]["limitations"]
            assert v["contract_sha256"] == original[v["unit_id"]]["contract_sha256"]


@pytest.mark.parametrize("tamper", ["warning", "context"])
def test_end_to_end_stripped_consumption_contract_fails(published, tamper):
    selection, _, unit = published
    broken = copy.deepcopy(unit)
    if tamper == "warning":
        broken["llm_context"]["qualification"]["limitations"] = []
        broken["llm_context"]["qa_observations"] = []
        broken["known_limitations"] = []
    else:
        broken["llm_context"]["required_context"] = []
        broken["related_evidence"] = []
    broken.pop("contract_sha256")
    broken["contract_sha256"] = digest(encode(broken))  # Rehashing never establishes authority.
    with pytest.raises(ValueError, match="altered_or_incomplete"):
        validate_consumption_unit(ROOT, broken, selection=selection)


def test_serialized_example_uses_verified_path(published):
    selection, _, unit = published
    assert json.loads(serialize_consumption_unit(ROOT, unit, selection=selection)) == unit
