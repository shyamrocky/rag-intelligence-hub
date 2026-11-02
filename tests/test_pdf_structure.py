"""Private exposed regressions bind maintained output to independently reviewed hashes."""

import copy
import json
from pathlib import Path

import pytest

from rag_hub.acquire import digest
from rag_hub.pdf_structure import encoded, pdf_parents
from rag_hub.schemas import ParsedBlock, SourceManifest

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / "workspace/pdf-remediation/phase3/nontext-compatibility-v1"
BPR = ROOT / "workspace/pdf-remediation/phase3/bounded-remediation-v1"


@pytest.fixture
def reviewed():
    if not (HOME / "reviewed-c06-split.json").exists():
        pytest.skip("private reviewed constraints not supplied")
    source = SourceManifest.model_validate_json(
        (BPR / "runs/v2-first/C06/source.json").read_bytes()
    )
    blocks = [
        ParsedBlock.model_validate(b)
        for b in json.loads((BPR / "runs/v2-first/C06/blocks.json").read_bytes())
    ]
    return source, blocks, json.loads((HOME / "reviewed-c06-split.json").read_bytes())


def test_reviewed_output_hashes_protected_values_and_unresolved_math(reviewed):
    source, blocks, bundle = reviewed
    before = [b.model_dump(mode="json") for b in blocks]
    parents = pdf_parents(source, blocks, {"reviewed_split": bundle})
    target = [p for p in parents if p.get("source_review_case") == bundle["owner_case"]["case_id"]]
    assert [digest(encoded(p)) for p in target] == bundle["expected_parent_sha256"]
    assert sum(m["end"] - m["start"] for p in target for m in p["members"]) == 460
    assert len(target) == 2
    assert target[0]["hazards"] == ["incomplete_mathematical_notation"]
    assert bundle["owner_case"]["decisions"]["mathematical_completeness"] == "FAIL"
    context = {bundle["constraint"][key] for key in ("unresolved_symbol", "separate_equation")}
    assert all(any(m["block_id"] == bid for p in parents for m in p["members"]) for bid in context)
    assert [b.model_dump(mode="json") for b in blocks] == before
    ordinary = pdf_parents(source, blocks, {})
    touched = {m["block_id"] for p in target for m in p["members"]}
    assert [p for p in parents if not any(m["block_id"] in touched for m in p["members"])] == [
        p for p in ordinary if not any(m["block_id"] in touched for m in p["members"])
    ]


@pytest.mark.parametrize(
    "defect",
    [
        "owner_FAIL",
        "math_implicit_PASS",
        "wrong_operation",
        "stale_hash",
        "invalid_span",
        "missing_block",
        "reversed_groups",
        "changed_text",
        "owner_output_hash",
        "wrong_locator",
        "partial_replacement",
    ],
)
def test_uncertain_or_changed_constraints_fail_closed(reviewed, defect):
    source, blocks, original = reviewed
    bundle = copy.deepcopy(original)
    spec = bundle["constraint"]
    member = spec["groups"][0][0]
    if defect == "owner_FAIL":
        bundle["owner_case"]["decisions"]["paragraph_boundary_fidelity"] = "FAIL"
    if defect == "math_implicit_PASS":
        bundle["owner_case"]["decisions"]["mathematical_completeness"] = "PASS"
    if defect == "wrong_operation":
        spec["operation"] = "paragraph_across_footnote"
    if defect == "stale_hash":
        member["content_sha256"] = "0" * 64
    if defect == "invalid_span":
        member["end"] += 9999
    if defect == "missing_block":
        member["block_id"] = "missing"
    if defect == "reversed_groups":
        spec["groups"].reverse()
    if defect == "changed_text":
        index = next(i for i, b in enumerate(blocks) if b.block_id == member["block_id"])
        blocks[index] = blocks[index].model_copy(update={"content": "Corrupt value -18.25."})
    if defect == "owner_output_hash":
        bundle["expected_parent_sha256"][0] = "0" * 64
    if defect == "wrong_locator":
        member["locator"]["page"] += 1
    if defect == "partial_replacement":
        member["start"] = 1
    with pytest.raises(ValueError):
        pdf_parents(source, blocks, {"reviewed_split": bundle})


def test_other_sources_are_unchanged_not_C02_C14_integration(reviewed):
    _source, _blocks, bundle = reviewed
    for doc in ("C01", "C02", "C14"):
        source = SourceManifest.model_validate_json(
            (BPR / f"runs/v2-first/{doc}/source.json").read_bytes()
        )
        blocks = [
            ParsedBlock.model_validate(b)
            for b in json.loads((BPR / f"runs/v2-first/{doc}/blocks.json").read_bytes())
        ]
        assert pdf_parents(source, blocks, {"reviewed_split": bundle}) == pdf_parents(
            source, blocks, {}
        )
