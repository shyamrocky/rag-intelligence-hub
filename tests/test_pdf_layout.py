"""Source-backed layout positives and adversarial negatives; no corpus eligibility."""

import copy
import json
from pathlib import Path

import pymupdf
import pytest
from test_pdf_nontext import fixture

from rag_hub.acquire import digest
from rag_hub.parse_pdf import parse_pdf
from rag_hub.pdf_classification import classify_pdf, route_parents
from rag_hub.pdf_layout import compact_layout, native_layout, type_evidence
from rag_hub.pdf_structure import continuation, reconstruct_pdf
from rag_hub.shared.pipeline import encoded
from rag_hub.shared.structure import assess, atomic_parents


def owned(lines, pages=1):
    with pymupdf.open() as pdf:
        for _ in range(pages):
            pdf.new_page()
        for page, x, y, text, font, size in lines:
            pdf[page].insert_text((x, y), text, fontname=font, fontsize=size)
        data = pdf.tobytes()
    _, template, _ = fixture()
    source = template.model_copy(
        update={"raw_sha256": digest(data), "snapshot_id": "sha256-" + digest(data)}
    )
    return data, source, parse_pdf(data, source)


def reconstructed(data, source, blocks, evidence=None):
    packet = classify_pdf(data, source, blocks, evidence)
    parents = atomic_parents(source, blocks, {})
    routed, _ = route_parents(packet, parents, blocks)
    result, report = reconstruct_pdf(packet, routed, blocks, source)
    assess(result, blocks, [])
    return packet, result, report


def test_native_source_evidence_rejects_rewritten_words_or_locations():
    data, source, blocks = fixture()
    for field in ("text", "location"):
        values = copy.deepcopy(blocks)
        values[0] = (
            values[0].model_copy(update={"content": "Invented content"})
            if field == "text"
            else values[0].model_copy(
                update={"locator": values[0].locator.model_copy(update={"bbox": (0, 0, 1, 1)})}
            )
        )
        with pytest.raises(ValueError, match="layout_original"):
            native_layout(data, source, values)


def test_prose_run_in_label_is_not_a_heading():
    data, source, blocks = owned(
        [
            (
                0,
                72,
                72,
                "Retrieval Challenges. The source paragraph keeps this label in its body.",
                "tiro",
                10,
            )
        ]
    )
    packet, parents, _ = reconstructed(data, source, blocks)
    assert packet["coverage"][0]["content_type"] == "prose"
    assert parents[0]["kind"] == "paragraph"
    assert parents[0]["text"] == blocks[0].content


def test_monospaced_document_prompt_never_becomes_instructions_or_headings():
    data, source, blocks = owned(
        [(0, 72, 72, "1 You are an agent. Keep all-MiniLM-L6-v2 and -17.25 unchanged.", "cour", 10)]
    )
    packet, parents, _ = reconstructed(data, source, blocks)
    assert packet["coverage"][0]["content_type"] == "code"
    assert parents[0]["kind"] == "code_observation"
    assert parents[0]["text"] == blocks[0].content
    assert parents[0]["experimental_eligibility"] == "HOLD"


def pair_fixture():
    return owned(
        [
            (0, 72, 750, "This source paragraph continues with language", "tiro", 10),
            (1, 72, 60, "models that retain exact values and original identifiers.", "tiro", 10),
        ],
        pages=2,
    )


def test_cross_page_continuation_is_exact_and_source_accounted():
    data, source, blocks = pair_fixture()
    original = [b.model_dump(mode="json") for b in blocks]
    packet, parents, _ = reconstructed(data, source, blocks)
    assert len(parents) == 1 and len(parents[0]["members"]) == 2
    assert parents[0]["text"] == "\n".join(b.content for b in blocks)
    assert packet["eligibility"] == "HOLD"
    assert [b.model_dump(mode="json") for b in blocks] == original


@pytest.mark.parametrize(
    "negative", ["ended_sentence", "indent", "font", "gap", "uppercase", "not_page_boundary"]
)
def test_continuation_adversarial_negatives(negative):
    data, source, blocks = pair_fixture()
    raw, _ = native_layout(data, source, blocks)
    layout = compact_layout(raw)
    left, right = blocks
    if negative == "ended_sentence":
        left = left.model_copy(update={"content": left.content + "."})
    elif negative == "indent":
        layout[right.block_id]["first_line_bbox"][0] += 15
    elif negative == "font":
        layout[right.block_id]["font_size"] += 2
    elif negative == "gap":
        right = right.model_copy(update={"sequence": 3})
    elif negative == "uppercase":
        right = right.model_copy(update={"content": "New unrelated paragraph begins here."})
    else:
        left = left.model_copy(
            update={"locator": left.locator.model_copy(update={"bbox": (72, 100, 280, 110)})}
        )
    assert continuation(left, right, layout)[0] is None


def test_footnote_superscript_spans_split_without_dropping_newlines():
    data, source, blocks = owned(
        [
            (
                0,
                72,
                70,
                "Main document text establishes the ordinary document body font size.",
                "tiro",
                10,
            ),
            (0, 72, 728, "2", "tiro", 6),
            (0, 76, 732, "https://example.invalid/a", "tiro", 8),
            (0, 72, 738, "3", "tiro", 6),
            (0, 76, 742, "https://example.invalid/b", "tiro", 8),
        ]
    )
    _packet, parents, _ = reconstructed(data, source, blocks)
    footnotes = [p for p in parents if p["kind"] == "footnote"]
    assert len(footnotes) == 2
    assert all(p["reference_ownership"] == "unverified_HOLD" for p in footnotes)
    assert all(p["marker_presentation"] == "native_superscript_geometry" for p in footnotes)


def test_small_digits_inside_body_are_not_automatically_furniture():
    data, source, blocks = owned(
        [
            (
                0,
                72,
                70,
                "Main document text establishes the ordinary document body font size.",
                "tiro",
                10,
            ),
            (0, 72, 300, "42", "tiro", 7),
        ]
    )
    packet = classify_pdf(data, source, blocks)
    assert packet["coverage"][-1]["content_type"] != "page_furniture"


def test_prose_heuristic_does_not_override_table_suggestion():
    data, source, blocks = owned(
        [
            (
                0,
                72,
                72,
                "Dataset Method Accuracy Recall Precision Precision Recall Accuracy",
                "tiro",
                10,
            )
        ]
    )
    raw, base = native_layout(data, source, blocks)
    proposal = {
        "content_type": "table",
        "members": [{"block_id": blocks[0].block_id}],
        "text": blocks[0].content,
    }
    assert blocks[0].block_id not in type_evidence(blocks, raw, base, [proposal])


@pytest.mark.parametrize(
    "value",
    [None, "Ω θ − all-MiniLM-L6-v2", {"a": [1, None, -17.25], "Ω": "\n"}, list(range(1000))],
)
def test_streaming_canonical_encoding_is_byte_identical(value):
    expected = (
        json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode()
    assert encoded(value) == expected


def test_canonical_encoding_still_rejects_nan():
    with pytest.raises(ValueError):
        encoded({"bad": float("nan")})


def test_streamed_native_image_evidence_equals_prior_verified_algorithm():
    import importlib.util

    from rag_hub.pdf_nontext import inspect_nontext

    root = Path(__file__).resolve().parents[1]
    before = (
        root
        / "workspace/pdf-remediation/phase3/level1-remediation-v1/before/src/rag_hub/pdf_nontext.py"
    )
    if not before.exists():
        pytest.skip("private preserved predecessor not supplied")
    spec = importlib.util.spec_from_file_location("prior_nontext", before)
    previous = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(previous)
    data, source, blocks = fixture()
    assert inspect_nontext(data, source, blocks) == previous.inspect_nontext(data, source, blocks)


@pytest.mark.parametrize(
    "reason", ["no_docling", "new_indent", "wide_gap", "new_reference", "valid"]
)
def test_same_page_spacing_requires_support_and_respects_boundaries(reason):
    data, source, blocks = pair_fixture()
    raw, _ = native_layout(data, source, blocks)
    layout = compact_layout(raw)
    left, right = blocks
    left = left.model_copy(
        update={"locator": left.locator.model_copy(update={"bbox": (72, 100, 280, 110)})}
    )
    right = right.model_copy(
        update={
            "locator": right.locator.model_copy(update={"page": 1, "bbox": (72, 112, 280, 122)})
        }
    )
    layout[right.block_id]["first_line_bbox"] = [72, 112, 280, 122]
    if reason == "new_indent":
        layout[right.block_id]["first_line_bbox"][0] += 10
    if reason == "wide_gap":
        right = right.model_copy(
            update={"locator": right.locator.model_copy(update={"bbox": (72, 130, 280, 140)})}
        )
    if reason == "new_reference":
        right = right.model_copy(update={"content": "[2] New bibliography entry starts here."})
    evidence, _ = continuation(
        left,
        right,
        layout,
        suggested=reason != "no_docling",
        bibliography=reason == "new_reference",
    )
    assert bool(evidence) == (reason == "valid")
