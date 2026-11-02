"""Conservative structural records: one atomic block per section, ancestry retained."""

import re

from rag_hub.acquire import digest
from rag_hub.schemas import HazardSidecar, ParsedBlock, Section

# Exact C06 print artifacts, constrained to top/bottom margin blocks only.
PRINT_ARTIFACT = re.compile(
    r"^(?:https://www\.trychroma\.com/research/evaluating-chunking(?:\?[^\s]*)?\s+\d+/\d+|"
    r"\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2}\s*[AP]M.*Evaluating Chunking.*)$",
    re.DOTALL,
)


def removal_reason(b):
    """Existing audited removal predicates, shared without duplicating their logic."""
    text = b.content
    if b.block_type == "metadata":
        return "remove_mdx_container_markup_preserve_provider_on_children"
    elif (
        b.doc_id == "C04"
        and b.locator.line_start == 1
        and text.startswith("> ## Documentation Index")
    ):
        return "remove_documentation_discovery_instructions"
    elif (
        b.doc_id == "C06"
        and b.locator.bbox
        and (b.locator.bbox[1] < 35 or b.locator.bbox[1] > 580)
        and PRINT_ARTIFACT.fullmatch(text.strip())
    ):
        return "remove_verified_print_margin_artifact"
    return None


def normalize_blocks(blocks: list[ParsedBlock]):
    sections, audit, sidecars = [], [], []
    for index, b in enumerate(blocks):
        text = b.content
        transformations = []
        reason = removal_reason(b)
        if reason:
            audit.append(
                {
                    "block_id": b.block_id,
                    "action": reason,
                    "locator": b.locator.model_dump(mode="json"),
                    "before_sha256": b.content_sha256,
                    "before": text,
                    "after": None,
                }
            )
            continue
        if b.block_type == "code":
            marker = "~~~~" if "```" in text else "```"
            text = f"{marker}{b.language or ''}\n{b.content}{'' if b.content.endswith(chr(10)) else chr(10)}{marker}"
            transformations.append("wrap_code_body_in_canonical_fence")
            if b.fence_info:
                transformations.append("strip_nonsemantic_fence_attributes")
        # Do not repair PDF line wrapping or mathematics by inference.
        normalized_hash = digest(text.encode())
        sid = f"{b.doc_id}:{b.raw_sha256[:12]}:{b.block_id.split(':')[-1]}:{normalized_hash[:12]}"
        section = Section(
            section_id=sid,
            doc_id=b.doc_id,
            snapshot_id=b.snapshot_id,
            heading_path=b.heading_path,
            block_ids=(b.block_id,),
            text=text,
            locators=(b.locator,),
            normalized_sha256=normalized_hash,
            raw_sha256=b.raw_sha256,
            provider_tab=b.provider_tab,
            code_group=b.code_group,
            code_label=b.fence_info.split("theme=", 1)[0].strip() if b.fence_info else None,
            block_type=b.block_type,
            verification_status="hold" if b.issues else "unreviewed",
            index_status="hold",
            transformations=tuple(transformations),
            issues=b.issues,
        )
        sections.append(section)
        if transformations:
            audit.append(
                {
                    "block_id": b.block_id,
                    "action": transformations,
                    "before_sha256": b.content_sha256,
                    "after_sha256": normalized_hash,
                    "before": b.content,
                    "after": text,
                }
            )
        if b.block_type in ("table", "equation") or b.locator.page:
            context = [
                p
                for p in blocks[max(0, index - 30) : index]
                if p.doc_id == b.doc_id
                and p.heading_path == b.heading_path
                and p.block_type not in ("table", "metadata")
                and (
                    not b.locator.page or not p.locator.page or b.locator.page - p.locator.page <= 1
                )
            ]
            sidecars.append(
                HazardSidecar(
                    sidecar_id=sid + ":hazard",
                    section_id=sid,
                    doc_id=b.doc_id,
                    snapshot_id=b.snapshot_id,
                    kind=b.block_type if b.block_type in ("table", "equation") else "mixed_pdf",
                    source_locator=b.locator,
                    original_visual_locator=f"{b.doc_id}:page={b.locator.page}:bbox={b.locator.bbox}",
                    context_block_ids=tuple(p.block_id for p in context),
                    context_locators=tuple(p.locator for p in context),
                    issues=b.issues or ("unverified_table",),
                )
            )
    return sections, audit, sidecars
