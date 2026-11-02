"""Page-aware PDF extraction. Layout order/heading heuristics never imply verification."""

import re
from statistics import median

import pymupdf

from rag_hub.acquire import digest
from rag_hub.schemas import Locator, ParsedBlock, SourceManifest

PARSER_VERSION = "pdf-v1"
MATH = re.compile(r"[∑∏Σ∫≤≥≈=∩∣]|\b(?:IoU|Precision_Ω)\b")


def parse_pdf(data: bytes, source: SourceManifest, expected_pages: int | None = None):
    blocks = []
    headings: list[str] = []
    with pymupdf.open(stream=data, filetype="pdf") as document:
        if document.needs_pass or document.is_repaired:
            raise ValueError("encrypted or repaired PDFs require explicit source review")
        if expected_pages is not None and len(document) != expected_pages:
            raise ValueError("PDF page count mismatch")
        for page_index, page in enumerate(document):
            # Native order avoids pretending coordinate-sort resolves two-column papers.
            raw = page.get_text("dict", sort=False)
            text_blocks = [
                b if b["type"] == 0 else {"bbox": b["bbox"], "lines": [], "image": True}
                for b in raw["blocks"]
                if b["type"] in (0, 1)
            ]
            sizes = [s["size"] for b in text_blocks for l in b["lines"] for s in l["spans"]]
            base_size = median(sizes) if sizes else 0
            if not text_blocks:
                text_blocks = [{"bbox": (0, 0, page.rect.width, page.rect.height), "lines": []}]
            for raw_block in text_blocks:
                content = "\n".join(
                    "".join(s["text"] for s in l["spans"]) for l in raw_block["lines"]
                )
                spans = [s for l in raw_block["lines"] for s in l["spans"]]
                kind = "prose"
                issues = ["pdf_layout_and_reading_order_unreviewed"]
                if any(char in content for char in ("\x00", "\x01", "\ufffd", "\u200b")):
                    issues.append("corrupted_or_fragmented_glyphs")
                if len(content.strip()) < 4:
                    issues.append("short_fragment_or_label_unverified")
                if raw_block.get("image"):
                    kind = "figure_caption"
                    issues.append("image_content_requires_visual_review")
                if not content.strip():
                    issues.append("empty_or_image_only_page_requires_visual_review")
                number_ratio = sum(c.isdigit() for c in content) / max(len(content), 1)
                if MATH.search(content):
                    kind = "equation"
                    issues.append("mixed_block_possible_math_do_not_reconstruct")
                elif number_ratio > 0.12 and len(content.splitlines()) > 2:
                    kind = "table"
                    issues.append("possible_table_values_context_unverified")
                elif (
                    len(content) < 140
                    and spans
                    and (
                        min(s["size"] for s in spans) > base_size * 1.1
                        or re.match(r"^\d+(?:\.\d+)*\s+[A-Z]", content)
                    )
                ):
                    kind = "heading"
                    depth = len(content.split()[0].split(".")) if content[:1].isdigit() else 1
                    headings = headings[: max(0, depth - 1)] + [content]
                seq = len(blocks)
                blocks.append(
                    ParsedBlock(
                        block_id=f"{source.doc_id}:b{seq:05d}",
                        doc_id=source.doc_id,
                        snapshot_id=source.snapshot_id,
                        sequence=seq,
                        block_type=kind,
                        content=content,
                        heading_path=tuple(headings),
                        locator=Locator(
                            url=source.canonical_url,
                            page=page_index + 1,
                            bbox=tuple(raw_block["bbox"]),
                        ),
                        issues=tuple(issues),
                        verification_status="hold",
                        raw_sha256=source.raw_sha256,
                        content_sha256=digest(content.encode()),
                        parser_version=PARSER_VERSION,
                    )
                )
    return blocks
