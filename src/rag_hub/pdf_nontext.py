"""Account native image observations without treating binary pixels as empty prose."""

import pymupdf

from rag_hub.acquire import digest
from rag_hub.schemas import HazardSidecar


def image_observation(block):
    return (
        block.content == ""
        and block.block_type == "figure_caption"
        and "image_content_requires_visual_review" in block.issues
    )


def inspect_nontext(data, source, blocks):
    """Independently bind each empty observation to the original native PDF object.

    A parser label alone is insufficient. Blank pages, missing text, forged image
    flags and foreign locations fail closed. No OCR or image interpretation.
    """
    if digest(data) != source.raw_sha256:
        raise ValueError("nontext_source_hash_mismatch")
    evidence = []
    sequence = 0
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        for page_number, page_object in enumerate(pdf, 1):
            native_page = page_object.get_text("dict", sort=False)
            native_blocks = [b for b in native_page["blocks"] if b["type"] in (0, 1)]
            if not native_blocks:
                native_blocks = [{"type": 0, "bbox": tuple(page_object.rect), "lines": []}]
            for native in native_blocks:
                if sequence >= len(blocks):
                    raise ValueError("native_observation_count_mismatch")
                block, page = blocks[sequence], page_number
                sequence += 1
                if block.content:
                    if native["type"] == 1:
                        raise ValueError("invented_text_for_native_image")
                    continue
                if (
                    (block.doc_id, block.raw_sha256, block.snapshot_id)
                    != (source.doc_id, source.raw_sha256, source.snapshot_id)
                    or block.sequence != sequence - 1
                    or block.locator.page != page
                    or tuple(native["bbox"]) != block.locator.bbox
                    or not image_observation(block)
                    or native["type"] != 1
                    or not native.get("image")
                    or native.get("width", 0) <= 0
                    or native.get("height", 0) <= 0
                ):
                    raise ValueError(
                        "empty_substantive_or_unconfirmed_image_observation: " + block.block_id
                    )
                evidence.append(
                    {
                        "block_id": block.block_id,
                        "original_observation": block.model_dump(mode="json"),
                        "source_element_type": "image",
                        "native_type": 1,
                        "native_number": native.get("number"),
                        "image_sha256": digest(native["image"]),
                        "image_byte_size": len(native["image"]),
                        "width": native["width"],
                        "height": native["height"],
                        "extension": native.get("ext"),
                        "reason": "native_binary_image_has_no_text_spans",
                        "visual_content_status": "unprocessed_HOLD",
                        "eligibility": "HOLD",
                    }
                )
            # Do not retain decoded image bytes and span dictionaries for the whole PDF.
            del native, native_blocks, native_page
    if sequence != len(blocks):
        raise ValueError("native_observation_count_mismatch")
    return evidence


def account_pdf_nontext(data, source, blocks, sections, audit, sidecars):
    evidence = inspect_nontext(data, source, blocks)
    byid = {r["block_id"]: r for r in evidence}
    section_ids = {}
    remaining = []
    for section in sections:
        matching = set(section.block_ids) & byid.keys()
        if matching:
            if len(section.block_ids) != 1 or section.text != "":
                raise ValueError("nontext_exclusion_would_remove_substantive_text")
            section_ids[section.block_ids[0]] = section.section_id
        else:
            remaining.append(section)
    if set(section_ids) != set(byid):
        raise ValueError("missing_nontext_accounting_section")
    audit = list(audit)
    sidecars = [s for s in sidecars if s.section_id not in set(section_ids.values())]
    for row in evidence:
        block = next(b for b in blocks if b.block_id == row["block_id"])
        audit.append(
            {
                "block_id": block.block_id,
                "action": "account_native_image_in_hold_sidecar_not_text_parent",
                "before": "",
                "before_sha256": block.content_sha256,
                "after": None,
                "locator": block.locator.model_dump(mode="json"),
                "source_element_type": "image",
                "raw_sha256": source.raw_sha256,
                "snapshot_id": source.snapshot_id,
                "image_sha256": row["image_sha256"],
                "visual_content_status": "unprocessed_HOLD",
            }
        )
        sidecars.append(
            HazardSidecar(
                sidecar_id=section_ids[block.block_id] + ":native-image",
                section_id=section_ids[block.block_id],
                doc_id=block.doc_id,
                snapshot_id=block.snapshot_id,
                kind="figure",
                source_locator=block.locator,
                original_visual_locator=f"{block.doc_id}:page={block.locator.page}:bbox={block.locator.bbox}",
                issues=("native_image_not_text", "image_content_requires_visual_review"),
            )
        )
    return remaining, audit, sidecars, evidence
