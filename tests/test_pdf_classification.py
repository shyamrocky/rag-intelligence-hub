"""Owned contract/abstention controls; no fabricated corpus approval or new ML classifier."""

import copy

import pytest
from test_pdf_nontext import fixture

from rag_hub.acquire import digest
from rag_hub.pdf_classification import classify_pdf, encoded, route_parents, validate_classification
from rag_hub.shared.structure import atomic_parents, span


def unit(source, blocks, kind="paragraph", members=None, ident="owned-region"):
    members = members or [span(blocks[0])]
    lookup = {b.block_id: b for b in blocks}
    text = "\n".join(lookup[m["block_id"]].content[m["start"] : m["end"]] for m in members)
    return {
        "id": ident,
        "doc_id": source.doc_id,
        "raw_sha256": source.raw_sha256,
        "snapshot_id": source.snapshot_id,
        "kind": kind,
        "members": members,
        "text": text,
        "text_sha256": digest(text.encode()),
        "construction": "owned_synthetic_expectation",
    }


def test_native_object_fallback_unknown_and_typed_handling():
    data, source, blocks = fixture()
    before = [b.model_dump(mode="json") for b in blocks]
    packet = classify_pdf(data, source, blocks)
    assert packet["summary"]["raw_observations"] == 2
    assert packet["summary"]["native_text"] == packet["summary"]["native_images"] == 1
    assert packet["coverage"][0]["content_type"] == "unknown"
    assert packet["coverage"][1]["content_type"] == "image"
    assert packet["coverage"][1]["eligibility"] == "HOLD"
    parents = atomic_parents(source, [blocks[0]], {})
    routed, _routes = route_parents(packet, parents, blocks)
    assert routed[0]["kind"] == "unknown_observation"
    assert routed[0]["members"] == parents[0]["members"]
    assert routed[0]["text"] == parents[0]["text"]
    assert before == [b.model_dump(mode="json") for b in blocks]


def test_cached_proposal_is_not_independent_even_with_machine_approval_flag():
    data, source, blocks = fixture()
    u = unit(source, blocks, "code") | {
        "output_human_verified": True,
        "classification_status": "supported",
    }
    p = classify_pdf(data, source, blocks, {"parents": [u]})
    row = next(r for r in p["regions"] if r["id"] == "proposal:owned-region")
    assert row["classification_status"] == "provisional"
    assert row["review_support"] is None
    assert all(r["eligibility"] == "HOLD" for r in p["coverage"])


@pytest.mark.parametrize(
    "kind",
    ["table", "equation", "code", "footnote", "figure_caption", "table_caption", "section_parent"],
)
def test_specialized_proposals_preserve_source_without_reconstruction(kind):
    data, source, blocks = fixture()
    p = classify_pdf(data, source, blocks, {"parents": [unit(source, blocks, kind)]})
    r = next(r for r in p["regions"] if r["id"].startswith("proposal:"))
    assert r["classification_status"] == "provisional"
    parents = atomic_parents(source, [blocks[0]], {})
    after, routes = route_parents(p, parents, blocks)
    assert after[0]["members"] == parents[0]["members"]
    assert after[0]["text"] == parents[0]["text"]
    assert routes[0]["specialized_reconstruction"] == "not_performed_HOLD"


def test_mixed_partial_and_overlapping_source_regions_are_not_counted_as_partition():
    data, source, blocks = fixture()
    a = unit(source, blocks, "section_parent", [span(blocks[0], 0, 5)], "heading")
    b = unit(source, blocks, "paragraph", [span(blocks[0], 5)], "body")
    overlay = unit(source, blocks, "equation", [span(blocks[0], 2, 8)], "overlap")
    p = classify_pdf(data, source, blocks, {"parents": [a, b, overlay]})
    assert len(p["coverage"]) == 2
    assert p["coverage"][0]["mixed"]
    assert p["coverage"][0]["content_type"] == "unknown"
    assert p["summary"]["semantic_region_counts_overlap"] is True
    assert len(p["regions"]) > len(p["coverage"])
    assert p["summary"]["source_codepoints"] == len(blocks[0].content)


def test_unsupported_proposal_not_silently_prose():
    data, source, blocks = fixture()
    p = classify_pdf(
        data, source, blocks, {"parents": [unit(source, blocks, "unrecognized-element")]}
    )
    r = next(r for r in p["regions"] if r["id"].startswith("proposal:"))
    assert (r["content_type"], r["classification_status"]) == ("unknown", "unsupported")


@pytest.mark.parametrize(
    "fault",
    [
        "bad_hash",
        "prefix",
        "suffix",
        "out_of_range",
        "foreign_span",
        "corrupt_identifier",
        "corrupt_sign",
    ],
)
def test_bad_source_claims_reject(fault):
    data, source, blocks = fixture()
    u = unit(source, blocks)
    if fault == "bad_hash":
        u["members"][0]["block_content_sha256"] = "0" * 64
    if fault == "prefix":
        u["members"][0]["start"] = 1
    if fault == "suffix":
        u["members"][0]["end"] -= 1
    if fault == "out_of_range":
        u["members"][0]["end"] += 999
    if fault == "foreign_span":
        u["members"][0]["block_id"] = "missing"
    if fault in ("corrupt_identifier", "corrupt_sign"):
        b = blocks[0]
        content = (
            b.content.replace("all-MiniLM-L6-v2", "allMiniLM-L6-v2")
            if fault == "corrupt_identifier"
            else b.content.replace("-17.25", "17.25")
        )
        blocks[0] = b.model_copy(
            update={"content": content, "content_sha256": digest(content.encode())}
        )
    with pytest.raises((ValueError, KeyError)):
        classify_pdf(data, source, blocks, {"parents": [u]})


@pytest.mark.parametrize(
    "fault",
    [
        "missing_observation",
        "duplicate_observation",
        "bad_object",
        "object_text_span",
        "wrong_type",
        "wrong_status",
        "native_type",
        "coverage_gap",
        "segment_outside",
        "missing_prefix",
        "missing_suffix",
        "foreign_source",
        "forged_supported",
        "broken_composite",
    ],
)
def test_malformed_classification_evidence_fails(fault):
    data, source, blocks = fixture()
    p = copy.deepcopy(classify_pdf(data, source, blocks))
    if fault == "missing_observation":
        p["coverage"].pop()
    if fault == "duplicate_observation":
        p["coverage"][1] = copy.deepcopy(p["coverage"][0])
    if fault == "bad_object":
        p["coverage"][1]["object_reference"]["native_type"] = 0
    if fault == "object_text_span":
        p["coverage"][1]["members"] = [span(blocks[1])]
    if fault == "wrong_type":
        p["regions"][0]["content_type"] = "invented"
    if fault == "wrong_status":
        p["regions"][0]["classification_status"] = "approved"
    if fault == "native_type":
        p["coverage"][0]["native_type"] = "other"
    if fault == "coverage_gap":
        p["coverage"][0]["segments"] = [
            {
                "start": 0,
                "end": 3,
                "content_type": "unknown",
                "classification_status": "ambiguous",
                "evidence_region_ids": [p["regions"][0]["id"]],
            },
            {
                "start": 4,
                "end": len(blocks[0].content),
                "content_type": "unknown",
                "classification_status": "ambiguous",
                "evidence_region_ids": [p["regions"][0]["id"]],
            },
        ]
    if fault == "segment_outside":
        p["coverage"][0]["segments"][0]["end"] += 1
    if fault == "missing_prefix":
        p["coverage"][0]["members"][0]["start"] = 1
    if fault == "missing_suffix":
        p["coverage"][0]["members"][0]["end"] -= 1
    if fault == "foreign_source":
        p["regions"][0]["snapshot_id"] = "foreign"
    if fault == "forged_supported":
        p["regions"][0]["classification_status"] = "supported"
        p["regions"][0]["review_support"] = {"machine": True}
    if fault == "broken_composite":
        p["relationships"] = [
            {"from": p["regions"][0]["id"], "to": "missing", "type": "component_of"}
        ]
    with pytest.raises(ValueError):
        validate_classification(p, source, blocks)


def test_native_equation_hint_is_ambiguous_not_semantic_truth():
    data, source, blocks = fixture()
    blocks[0] = blocks[0].model_copy(
        update={
            "block_type": "equation",
            "issues": ("mixed_block_possible_math_do_not_reconstruct",),
        }
    )
    p = classify_pdf(data, source, blocks)
    assert p["coverage"][0]["content_type"] == "unknown"
    assert p["regions"][0]["evidence"]["candidate_types"] == [
        "equation",
        "inline_math",
        "table",
        "code",
        "prose",
    ]


def test_missing_classification_cannot_reach_pdf_QA():
    from rag_hub.shared.qa import assess

    data, source, blocks = fixture()
    with pytest.raises(ValueError, match="missing_required_pdf_classification"):
        assess(None, source, data, blocks, [], [], None, "owned", {})


def test_existing_normalization_predicates_remain_equivalent_on_frozen_sources():
    import importlib.util
    import json
    from pathlib import Path

    from rag_hub.normalize import normalize_blocks
    from rag_hub.schemas import ParsedBlock

    root = Path(__file__).resolve().parents[1]
    home = root / "workspace/pdf-remediation/phase3/content-classification-v1"
    if not (home / "before/src/rag_hub/normalize.py").exists():
        pytest.skip("private pre-change normalization not provided")
    spec = importlib.util.spec_from_file_location(
        "owned_normalization_before", home / "before/src/rag_hub/normalize.py"
    )
    before = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(before)
    for doc in ("C01", "C02", "C06", "C14"):
        p = home.parent / f"bounded-remediation-v1/runs/v2-first/{doc}/blocks.json"
        blocks = [ParsedBlock.model_validate(b) for b in json.loads(p.read_bytes())]
        assert normalize_blocks(blocks) == before.normalize_blocks(blocks)
    old = (
        root
        / "data/ingestion/e78db572b9287860a350bb0c53f4e7fe822d394f9969744a75c2b0881a8ed169/blocks.jsonl"
    )
    blocks = [ParsedBlock.model_validate_json(s) for s in old.read_text().splitlines()]
    assert normalize_blocks(blocks) == before.normalize_blocks(blocks)


def test_legacy_registry_entry_also_emits_pdf_classification(tmp_path):
    import json

    from rag_hub.pipeline import ingest

    data, _source, _blocks = fixture()
    (tmp_path / "data/raw").mkdir(parents=True)
    (tmp_path / "data/raw/owned.pdf").write_bytes(data)
    (tmp_path / "config").mkdir()
    (tmp_path / "config/sources.json").write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "sources": [
                    {
                        "doc_id": "OWNED",
                        "file": "owned.pdf",
                        "byte_size": len(data),
                        "sha256": digest(data),
                        "title": "Owned PDF",
                        "publisher": "Owned synthetic fixture",
                        "canonical_url": "https://example.invalid/owned",
                        "source_format": "pdf",
                        "expected_pages": 1,
                        "original_url": "https://example.invalid/owned.pdf",
                        "source_version": None,
                        "language": "en",
                    }
                ],
            }
        )
    )
    record = ingest(tmp_path, use_basis="Owned synthetic fixture")
    result = json.loads((tmp_path / record["output"] / "report.json").read_bytes())
    assert result["pdf_classification"]["OWNED"]["summary"]["accounted_observations"] == 2
    assert record["approved_sections"] == 0
    assert ingest(tmp_path, use_basis="Owned synthetic fixture") == record


def test_bound_input_hashes_reject_modified_evidence(tmp_path):
    import json

    from rag_hub.pdf_classification import load_evidence

    private = tmp_path / "workspace"
    private.mkdir()
    data = private / "parents.json"
    data.write_text("{}")
    conf = private / "classification.json"
    conf.write_text(
        json.dumps(
            {
                "schema": "pdf-classification-input-1.0",
                "files": {"workspace/parents.json": "0" * 64},
                "parent_artifacts": [],
                "phase1d_receipts": "workspace/parents.json",
                "owner_output_review": "workspace/parents.json",
            }
        )
    )
    with pytest.raises(ValueError, match="classification_evidence_hash_mismatch"):
        load_evidence(tmp_path, "workspace/classification.json")


def test_conflicting_supported_type_facets_abstain_without_promoting():
    data, source, blocks = fixture()
    parents = [
        unit(source, blocks, "code", ident="owned-code"),
        unit(source, blocks, "paragraph", ident="owned-prose"),
    ]
    reviews = []
    for p, facet in zip(parents, ("code_type", "bibliography_grouping"), strict=True):
        reviews.append(
            {
                "case_id": "owned-synthetic-contract-fixture",
                "human_confirmed_facets": [facet],
                "unit_binding": {
                    "unit_id": p["id"],
                    "unit_record_sha256": digest(encoded(p)),
                    "members": p["members"],
                    "source_sha256": p["raw_sha256"],
                    "snapshot_id": p["snapshot_id"],
                },
            }
        )
    packet = classify_pdf(data, source, blocks, {"parents": parents, "phase1d_reviews": reviews})
    assert packet["coverage"][0]["content_type"] == "unknown"
    assert packet["coverage"][0]["classification_status"] == "ambiguous"
    assert packet["summary"]["conflicting_observations"] == 1
    assert packet["coverage"][0]["eligibility"] == "HOLD"


def test_furniture_status_cannot_be_forged_to_drop_valid_text():
    data, source, blocks = fixture()
    packet = classify_pdf(data, source, blocks)
    packet["regions"][0]["classification_status"] = "supported"
    packet["regions"][0]["content_type"] = "page_furniture"
    with pytest.raises(ValueError, match="unverified_furniture"):
        validate_classification(packet, source, blocks)
