"""Conservative native-layout evidence for text types and paragraph boundaries.

No source-specific IDs, replacement text, semantic rewriting or eligibility.
Native text is compared exactly; Docling proposals are supporting evidence only.
"""

import re
from collections import defaultdict
from itertools import pairwise
from statistics import median

import pymupdf

from rag_hub.acquire import digest

VERSION = "pdf-native-layout-1.0"
NUMBERED_HEADING = re.compile(r"^(?:[IVX]+\.|[A-Z]\.|\d+(?:\.\d+)*[ .\n])\s*[A-Z]")
MONO = re.compile(r"monaco|courier|cmtt|sftt|mono", re.IGNORECASE)
MATH_FONT = re.compile(r"^(?:CM(?:MI|SY|EX|R)[0-9]|MSAM|MSBM)", re.IGNORECASE)
REFERENCE = re.compile(r"^\[\d+\]\s+\S")
TABLE_CAPTION = re.compile(r"^(?:Table\s+\d+\s*[:.]\s+|TABLE\s+[IVXLCDM\d]+\s*\n\S)")
BULLET = re.compile(r"^[•●▪◦]\s+\S")


def native_layout(data, source, blocks):
    """Page-local decoding; observations and offsets remain the text authority."""
    if digest(data) != source.raw_sha256:
        raise ValueError("layout_source_hash_mismatch")
    bypage = defaultdict(list)
    for b in blocks:
        if b.content:
            bypage[b.locator.page].append(b)
    rows, weighted_sizes = {}, []
    flags = pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        for page_no, page in enumerate(pdf, 1):
            native = [
                b
                for b in page.get_text("dict", flags=flags, sort=False)["blocks"]
                if b["type"] == 0
            ]
            originals = bypage[page_no]
            if len(native) != len(originals):
                raise ValueError("layout_native_count_mismatch")
            # Geometry only, not visual/figure interpretation.
            paths = [p["rect"] for p in page.get_drawings()]
            for b, raw in zip(originals, native, strict=True):
                lines, offset, fonts, chars, math_spans = [], 0, [], [], []
                for line in raw["lines"]:
                    text = "".join(s["text"] for s in line["spans"])
                    line_start = offset
                    span_rows = []
                    for s in line["spans"]:
                        end = offset + len(s["text"])
                        span_rows.append(
                            {
                                "start": offset,
                                "end": end,
                                "size": s["size"],
                                "bbox": list(s["bbox"]),
                                "font": s["font"],
                            }
                        )
                        fonts.append(s["font"])
                        chars.extend([s["size"]] * len(s["text"]))
                        if MATH_FONT.search(s["font"]):
                            math_spans.append(
                                {
                                    "start": offset,
                                    "end": end,
                                    "font": s["font"],
                                    "bbox": list(s["bbox"]),
                                }
                            )
                        offset = end
                    lines.append(
                        {
                            "start": line_start,
                            "end": offset,
                            "direction": list(line["dir"]),
                            "bbox": list(line["bbox"]),
                            "spans": span_rows,
                        }
                    )
                    offset += 1  # Original native line separator, not a new source character.
                text = "\n".join("".join(s["text"] for s in l["spans"]) for l in raw["lines"])
                if text != b.content or tuple(raw["bbox"]) != b.locator.bbox:
                    raise ValueError("layout_original_text_or_geometry_mismatch")
                size = median(chars) if chars else 0
                weighted_sizes.extend(chars)
                rect = pymupdf.Rect(raw["bbox"])
                vector_near = sum(
                    bool(rect.intersects(pymupdf.Rect(r) + (-4, -4, 4, 4))) for r in paths
                )
                rows[b.block_id] = {
                    "page": page_no,
                    "page_size": [page.rect.width, page.rect.height],
                    "font_size": size,
                    "fonts": sorted(set(fonts)),
                    "lines": lines,
                    "vector_paths_near": vector_near,
                    "page_vector_paths": len(paths),
                    "math_spans": math_spans,
                    "text_sha256": b.content_sha256,
                }
    base = median(weighted_sizes) if weighted_sizes else 0
    return rows, base


def plot_heading(block, blocks, layout, base):
    """A small plot title needs aligned numeric-axis and vector evidence to abstain."""
    x = layout[block.block_id]
    size = x["font_size"]
    if (
        block.block_type != "heading"
        or size >= base * 0.85
        or not any("sans" in f.lower() for f in x["fonts"])
        or len(x["lines"]) != 1
        or abs(x["lines"][0]["direction"][1]) > 0.1
        or x["page_vector_paths"] < 10
        or x["vector_paths_near"] < 3
    ):
        return False
    box = block.locator.bbox
    axes = []
    for other in blocks:
        y = layout.get(other.block_id)
        if (
            y is not None
            and y["page"] == x["page"]
            and re.fullmatch(r"[-−+]?\d+(?:\.\d+)?%?", other.content.strip())
            and set(y["fonts"]) == set(x["fonts"])
            and y["font_size"] <= size
            and y["vector_paths_near"] > 0
            and abs(other.locator.bbox[0] - box[0]) <= size * 2
            and box[3] <= other.locator.bbox[1] <= box[3] + x["page_size"][1] * 0.3
        ):
            axes.append(other.locator.bbox)
    return (
        len(axes) >= 3
        and max(b[0] for b in axes) - min(b[0] for b in axes) <= size
        and max(b[1] for b in axes) - min(b[1] for b in axes) >= size * 3
    )


def type_evidence(blocks, layout, base, proposals):
    """Return provisional whole-block roles plus explicit source-span components."""
    proposed = defaultdict(set)
    reference_members = set()
    for p in proposals:
        if p.get("active", True):
            for m in p["members"]:
                proposed[m["block_id"]].add(p["content_type"])
            if p["content_type"] == "prose" and REFERENCE.match(p["text"].strip()):
                reference_members.update(m["block_id"] for m in p["members"])
    output = {}
    in_references = False
    for b in blocks:
        if b.block_id not in layout:
            continue
        x = layout[b.block_id]
        text, lines = b.content.strip(), x["lines"]
        size, (_width, height) = x["font_size"], x["page_size"]
        box = b.locator.bbox
        kind, role, components = None, None, []
        math = bool(x["math_spans"])
        mono = all(MONO.search(f) for f in x["fonts"])
        words = re.findall(r"[^\W\d_]{2,}", text)
        letter_ratio = sum(c.isalpha() for c in text) / max(len(text), 1)
        if text.lower() in ("references", "bibliography"):
            in_references = True
        elif b.block_type == "heading" and text.lower().startswith(("appendix", "appendices")):
            in_references = False
        # Superscript numeric starts, smaller than following text, at page bottom.
        starts = []
        for line in lines:
            spans = line["spans"]
            if len(spans) < 2:
                continue
            first = spans[0]
            marker = b.content[first["start"] : first["end"]]
            if (
                marker.isdigit()
                and first["size"] <= median(s["size"] for s in spans[1:]) * 0.8
                and first["bbox"][1] < spans[1]["bbox"][1]
                and box[1] > height * 0.65
                and size < base * 0.95
            ):
                starts.append((line["start"], first["end"]))
        if (
            re.match(r"^arXiv:\d{4}\.\d{4,5}v\d+", text)
            and box[2] < x["page_size"][0] * 0.08
            and any(abs(line["direction"][1]) > 0.9 for line in lines)
        ):
            kind, role = "page_furniture", "rotated_repository_stamp_retained_not_excluded"
        elif starts and starts[0][0] == 0:
            kind, role = "footnote", "superscript_marked_footnote"
            for i, (a, marker_end) in enumerate(starts):
                z = starts[i + 1][0] if i + 1 < len(starts) else len(b.content)
                components.append(
                    {
                        "start": a,
                        "end": z,
                        "role": "footnote",
                        "marker_start": a,
                        "marker_end": marker_end,
                        "marker_presentation": "native_superscript_geometry",
                        "reference_ownership": "unverified_HOLD",
                    }
                )
        elif (
            text.isdigit()
            and len(lines) == 1
            and size < base * 0.85
            and (box[3] < height * 0.06 or box[1] > height * 0.94)
        ):
            kind, role = "page_furniture", "margin_page_number_retained_not_excluded"
        elif mono and lines:
            kind, role = "code", "monospaced_payload_HOLD"
            for line in lines:
                t = b.content[line["start"] : line["end"]]
                if t.isdigit():
                    components.append(
                        {
                            "start": line["start"],
                            "end": line["end"],
                            "role": "printed_line_number_candidate_HOLD",
                        }
                    )
        elif (
            TABLE_CAPTION.match(text)
            and lines
            and all(abs(line["direction"][1]) < 0.1 for line in lines)
        ):
            kind, role = "table_caption", "numbered_table_caption_candidate"
        elif BULLET.match(text) and lines:
            markers = [line for line in text.splitlines() if BULLET.match(line.strip())]
            # Multiple items within an observation need separately reviewed span partitioning.
            if len(markers) == 1 and all(
                line["bbox"][0] >= lines[0]["bbox"][0] - 1 for line in lines[1:]
            ):
                kind, role = "list", "single_bulleted_item_candidate"
            else:
                kind, role = "unknown", "multiple_bulleted_items_unpartitioned_HOLD"
        elif plot_heading(b, blocks, layout, base) or (
            size < base * 0.72
            and any("sans" in f.lower() for f in x["fonts"])
            and x["page_vector_paths"] >= 10
            and x["vector_paths_near"] > 0
        ):
            kind, role = "unknown", "chart_text_HOLD"
        elif (
            len(text) < 140
            and len(words) <= 18
            and (b.block_type == "heading" or "heading" in proposed[b.block_id])
            and (size > base * 1.15 or NUMBERED_HEADING.match(text))
        ):
            kind, role = "heading", "document_heading_candidate"
        elif in_references and (REFERENCE.match(text) or b.block_id in reference_members):
            kind, role = "prose", "bibliography_entry_candidate"
        elif (
            len(words) >= 6
            and letter_ratio > 0.58
            and base * 0.85 <= size <= base * 1.2
            and not any(c in text for c in ("\x00", "\x01", "\ufffd"))
            and not text.startswith(("Figure ", "Fig. ", "Table "))
        ):
            kind, role = "prose", "prose_with_inline_math_HOLD" if math else "body_prose_candidate"
        # A prose heuristic cannot erase a specialized cached interpretation.
        # The numbered-reference case has additional source section/entry evidence.
        specialized = proposed[b.block_id] & {
            "table",
            "equation",
            "code",
            "figure_caption",
            "table_caption",
        }
        if (
            kind == "prose"
            and role != "bibliography_entry_candidate"
            and (specialized or b.block_type == "table")
        ):
            kind = None
        if kind:
            output[b.block_id] = {
                "content_type": kind,
                "role": role,
                "components": components,
                "math_spans": x["math_spans"],
            }
    # A presentation label is recognized only adjacent to native monospace payload.
    for a, b in pairwise(blocks):
        if (
            a.content.strip().lower() in ("text", "plaintext", "python", "json", "bash", "bibtex")
            and output.get(b.block_id, {}).get("content_type") == "code"
            and a.locator.page == b.locator.page
        ):
            output[a.block_id] = {
                "content_type": "presentation",
                "role": "code_presentation_label",
                "components": [],
                "math_spans": [],
            }
    return output


def compact_layout(layout):
    """Only source-backed geometry needed for deterministic grouping; no copied payloads."""
    return {
        bid: {k: v for k, v in x.items() if k != "lines"}
        | {
            "line_count": len(x["lines"]),
            "first_line_bbox": x["lines"][0]["bbox"],
            "last_line_bbox": x["lines"][-1]["bbox"],
            "column_right": max(
                line["bbox"][2]
                for other in layout.values()
                if other["page"] == x["page"] and abs(other["font_size"] - x["font_size"]) <= 0.6
                for line in other["lines"]
                if abs(line["bbox"][0] - x["lines"][-1]["bbox"][0]) <= 2
            ),
        }
        for bid, x in layout.items()
    }
