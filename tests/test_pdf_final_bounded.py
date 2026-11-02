"""Bounded native text rules: exact spans, typed abstentions and boundary negatives."""

import copy

import pytest
from test_pdf_layout import owned, pair_fixture, reconstructed

from rag_hub.pdf_layout import compact_layout, native_layout
from rag_hub.pdf_structure import continuation


@pytest.mark.parametrize(
    "caption", ["Table 12: Comparison of baseline scores.", "TABLE IV\nSUMMARY OF BASELINE SCORES"]
)
def test_caption_has_exact_text_and_unresolved_attachment(caption):
    data, source, blocks = owned([(0, 72, 72, caption, "tiro", 10)])
    packet, parents, _ = reconstructed(data, source, blocks)
    assert packet["coverage"][0]["content_type"] == "table_caption"
    p = parents[0]
    assert p["kind"] == "table_caption_observation"
    assert p["text"] == blocks[0].content
    assert p["caption_attachment"]["target"] is None
    assert p["caption_attachment"]["status"] == "unresolved_HOLD"
    assert p["experimental_eligibility"] == "HOLD"


@pytest.mark.parametrize(
    "text",
    [
        "Table 12 shows the comparison of the various baseline scores.",
        "Figure 12: Baseline scores.",
        "table 12: quoted body text",
        "TABLE IV shows results in the discussion.",
    ],
)
def test_table_mentions_do_not_become_captions(text):
    data, source, blocks = owned([(0, 72, 72, text, "tiro", 10)])
    packet, _, _ = reconstructed(data, source, blocks)
    assert packet["coverage"][0]["content_type"] != "table_caption"


def bullet_pdf(text):
    from pathlib import Path

    import pymupdf
    from test_pdf_nontext import fixture

    from rag_hub.acquire import digest
    from rag_hub.parse_pdf import parse_pdf

    font = Path("/System/Library/Fonts/Supplemental/Arial.ttf")
    if not font.exists():
        pytest.skip("Unicode fixture font not available")
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_font(fontname="fixture_unicode", fontfile=str(font))
        page.insert_text((72, 72), text, fontname="fixture_unicode", fontsize=10)
        data = pdf.tobytes()
    _, template, _ = fixture()
    source = template.model_copy(
        update={"raw_sha256": digest(data), "snapshot_id": "sha256-" + digest(data)}
    )
    blocks = parse_pdf(data, source)
    assert blocks[0].content.replace("\xa0", " ") == text
    return data, source, blocks


@pytest.mark.parametrize("marker", ["•", "●", "▪", "◦"])
def test_bullet_item_retains_boundary_without_grouping(marker):
    from rag_hub.pdf_layout import BULLET

    assert BULLET.match(marker + " Preserve source values and model identifiers.")
    data, source, blocks = bullet_pdf(marker + " Preserve source values and model identifiers.")
    packet, parents, _ = reconstructed(data, source, blocks)
    assert packet["coverage"][0]["content_type"] == "list"
    assert parents[0]["kind"] == "list_observation"
    assert parents[0]["text"] == blocks[0].content
    assert len(parents[0]["members"]) == 1
    assert "list_parent" not in parents[0]


def test_two_items_in_one_block_abstain_without_fabricated_partition():
    data, source, blocks = bullet_pdf(
        "• First item retains its source.\n• Second item retains its source."
    )
    packet, parents, _ = reconstructed(data, source, blocks)
    assert len(blocks) == 1
    assert packet["coverage"][0]["content_type"] == "unknown"
    assert parents[0]["text"] == blocks[0].content


def native_pair():
    data, source, blocks = pair_fixture()
    layout = compact_layout(native_layout(data, source, blocks)[0])
    left, right = blocks
    left = left.model_copy(
        update={"locator": left.locator.model_copy(update={"bbox": (72, 100, 280, 111)})}
    )
    right = right.model_copy(
        update={
            "locator": right.locator.model_copy(update={"page": 1, "bbox": (72, 115, 260, 126)})
        }
    )
    layout[left.block_id].update(font_size=10, last_line_bbox=[72, 100, 280, 111], column_right=280)
    layout[right.block_id].update(font_size=10, first_line_bbox=[72, 115, 260, 126])
    return left, right, layout


@pytest.mark.parametrize(
    "negative",
    [
        None,
        "terminal",
        "indent",
        "short_line",
        "column",
        "gap",
        "pitch",
        "font",
        "uppercase",
        "no_column_proof",
    ],
)
def test_native_continuation_requires_all_geometric_and_lexical_conditions(negative):
    left, right, layout = native_pair()
    layout = copy.deepcopy(layout)
    if negative == "terminal":
        left = left.model_copy(update={"content": left.content + "."})
    elif negative == "indent":
        layout[right.block_id]["first_line_bbox"][0] += 10
    elif negative == "short_line":
        layout[left.block_id]["last_line_bbox"][2] -= 40
    elif negative == "column":
        right = right.model_copy(
            update={"locator": right.locator.model_copy(update={"bbox": (310, 115, 550, 126)})}
        )
    elif negative == "gap":
        right = right.model_copy(update={"sequence": left.sequence + 2})
    elif negative == "pitch":
        layout[right.block_id]["first_line_bbox"][1] += 5
    elif negative == "font":
        layout[right.block_id]["font_size"] += 2
    elif negative == "uppercase":
        right = right.model_copy(update={"content": "New paragraph starts here."})
    elif negative == "no_column_proof":
        del layout[left.block_id]["column_right"]
    evidence, _ = continuation(left, right, layout)
    assert bool(evidence) == (negative is None)
