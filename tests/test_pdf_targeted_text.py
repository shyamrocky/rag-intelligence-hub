"""Synthetic positives and boundary negatives for the focused text candidate."""

import copy

import pytest
from test_pdf_final_bounded import native_pair

from rag_hub.acquire import digest
from rag_hub.pdf_layout import type_evidence
from rag_hub.shared.structure import span


def band_fixture():
    template, _, _ = native_pair()
    blocks, layout = {}, {}
    for i, top in enumerate([60, 90, 105, 120, 135, 150, 180]):
        text = "A complete sentence ends here." if i == 2 else "ordinary body text continues"
        box = (72, top, 280 if i != 5 else 170, top + 11)
        b = template.model_copy(
            update={
                "block_id": f"OWNED:b{i:05}",
                "sequence": i,
                "content": text,
                "content_sha256": digest(text.encode()),
                "locator": template.locator.model_copy(update={"page": 1, "bbox": box}),
            }
        )
        blocks[b.block_id] = b
        layout[b.block_id] = {
            "font_size": 10,
            "fonts": ["OwnedBody"],
            "line_count": 1,
            "first_line_bbox": list(box),
            "last_line_bbox": list(box),
            "column_right": 280,
        }
    parents = [{"kind": "paragraph", "members": [span(b)]} for b in list(blocks.values())[1:6]]
    return parents, blocks, layout


def test_bounded_band_allows_sentence_boundary_with_stronger_source_witness():
    from rag_hub.pdf_structure import paragraph_band_edges

    parents, blocks, layout = band_fixture()
    assert paragraph_band_edges(parents, blocks, layout) == {
        (f"OWNED:b{i:05}", f"OWNED:b{i + 1:05}") for i in range(1, 5)
    }


@pytest.mark.parametrize(
    "negative",
    [
        "gap",
        "indent",
        "short",
        "font",
        "sequence",
        "partial",
        "reviewed",
        "outer_gap",
        "multiline",
        "column",
        "page",
        "two_lines",
    ],
)
def test_band_requires_complete_geometry_and_span_witness(negative):
    from rag_hub.pdf_structure import paragraph_band_edges

    parents, blocks, layout = band_fixture()
    key = "OWNED:b00003"
    b = blocks[key]
    if negative in ("gap", "indent", "column"):
        box = (
            85 if negative == "indent" else 310 if negative == "column" else 72,
            130 if negative == "gap" else 120,
            280,
            141 if negative == "gap" else 131,
        )
        blocks[key] = b.model_copy(update={"locator": b.locator.model_copy(update={"bbox": box})})
        layout[key].update(first_line_bbox=list(box), last_line_bbox=list(box))
    elif negative == "short":
        layout[key]["last_line_bbox"][2] = 180
    elif negative == "font":
        layout[key]["fonts"] = ["DifferentBody"]
    elif negative == "sequence":
        blocks[key] = b.model_copy(update={"sequence": 9})
    elif negative == "partial":
        parents[2]["members"][0]["start"] = 1
    elif negative == "reviewed":
        parents[2]["source_review_case"] = "opaque-review"
    elif negative == "outer_gap":
        layout["OWNED:b00000"]["last_line_bbox"][1] = 75
    elif negative == "multiline":
        layout[key]["line_count"] = 2
    elif negative == "page":
        blocks[key] = b.model_copy(update={"locator": b.locator.model_copy(update={"page": 2})})
    else:
        parents = parents[:2]
    edges = paragraph_band_edges(parents, blocks, layout)
    assert ("OWNED:b00002", "OWNED:b00003") not in edges
    assert ("OWNED:b00003", "OWNED:b00004") not in edges


def chart_fixture():
    template, _, _ = native_pair()
    blocks, layout = [], {}
    values = [
        ("12 Experimental Conditions", (110, 100, 280, 112), 8.2),
        ("10", (106, 125, 116, 135), 7),
        ("20", (106, 145, 116, 155), 7),
        ("30", (106, 165, 116, 175), 7),
    ]
    for i, (text, box, size) in enumerate(values):
        b = template.model_copy(
            update={
                "block_id": f"OWNED:b{i:05}",
                "sequence": i,
                "block_type": "heading" if i == 0 else "prose",
                "content": text,
                "content_sha256": digest(text.encode()),
                "locator": template.locator.model_copy(update={"page": 1, "bbox": box}),
            }
        )
        blocks.append(b)
        layout[b.block_id] = {
            "page": 1,
            "page_size": [600, 800],
            "font_size": size,
            "fonts": ["DejaVuSans"],
            "lines": [
                {"bbox": list(box), "direction": [1, 0], "spans": [], "start": 0, "end": len(text)}
            ],
            "math_spans": [],
            "vector_paths_near": 8,
            "page_vector_paths": 20,
        }
    return blocks, layout


def test_plot_title_cannot_own_document_section():
    blocks, layout = chart_fixture()
    result = type_evidence(blocks, layout, 10, [])
    assert result[blocks[0].block_id]["content_type"] == "unknown"
    assert result[blocks[0].block_id]["role"] == "chart_text_HOLD"


@pytest.mark.parametrize("kind", ["equation", "table", "heading", "bibliography"])
def test_body_band_never_expands_specialized_or_reference_records(kind):
    from rag_hub.pdf_structure import paragraph_band_edges

    parents, blocks, layout = band_fixture()
    first = "OWNED:b00001"
    roles = {}
    if kind == "bibliography":
        roles[first] = {"role": "bibliography_entry_candidate"}
    else:
        blocks[first] = blocks[first].model_copy(update={"block_type": kind})
    assert not paragraph_band_edges(parents, blocks, layout, roles)


@pytest.mark.parametrize(
    "negative",
    ["few_axes", "page", "font", "above", "far_x", "vectors", "body_size", "serif", "rotated"],
)
def test_heading_not_demoted_without_plot_witness(negative):
    blocks, layout = chart_fixture()
    layout = copy.deepcopy(layout)
    if negative == "few_axes":
        blocks = blocks[:3]
    elif negative in ("page", "above", "far_x"):
        for i in range(1, len(blocks)):
            b = blocks[i]
            if negative == "page":
                layout[b.block_id]["page"] = 2
            else:
                box = list(b.locator.bbox)
                box[1] -= 100 if negative == "above" else 0
                box[0] += 150 if negative == "far_x" else 0
                blocks[i] = b.model_copy(
                    update={"locator": b.locator.model_copy(update={"bbox": tuple(box)})}
                )
    elif negative == "font":
        for b in blocks[1:]:
            layout[b.block_id]["fonts"] = ["DifferentSans"]
    elif negative == "vectors":
        layout[blocks[0].block_id]["vector_paths_near"] = 0
    elif negative == "body_size":
        layout[blocks[0].block_id]["font_size"] = 10
    elif negative == "serif":
        layout[blocks[0].block_id]["fonts"] = ["Times-Roman"]
    else:
        layout[blocks[0].block_id]["lines"][0]["direction"] = [0, 1]
    result = type_evidence(blocks, layout, 10, [])
    assert result[blocks[0].block_id]["content_type"] == "heading"
