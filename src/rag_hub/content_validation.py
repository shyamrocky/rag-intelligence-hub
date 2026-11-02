"""Deterministic risk and source checks for immutable ingestion output."""

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from rag_hub.acquire import digest, local_path
from rag_hub.quality import apply_reviews
from rag_hub.schemas import ParsedBlock, ReviewReceipt, Section, SourceManifest
from rag_hub.source_fidelity import check_markdown, contextual_reasons
from rag_hub.validation_models import ValidationPolicy, ValidationResult

KNOWN_ISSUES = {
    "corrupted_or_fragmented_glyphs",
    "empty_or_image_only_page_requires_visual_review",
    "image_content_requires_visual_review",
    "mixed_block_possible_math_do_not_reconstruct",
    "possible_table_values_context_unverified",
    "short_fragment_or_label_unverified",
    "unsupported_mdx_or_html",
    "markdown_unparsed_line_requires_review",
    "unclosed_code_fence",
}
INTEGRITY_REASONS = {
    "missing_or_multiple_parent_blocks",
    "lineage_mismatch",
    "block_metadata_mismatch",
    "normalized_hash_mismatch",
    "invalid_source_lines",
    "invalid_pdf_locator",
    "missing_audit",
    "raw_source_body_mismatch",
    "normalized_source_mismatch",
    "fence_metadata_mismatch",
    "unexpected_code_transformation",
    "unexplained_text_transformation",
    "code_label_mismatch",
    "heading_ancestry_mismatch",
    "provider_mismatch",
    "code_group_mismatch",
    "unsupported_heading_span",
}


@dataclass
class ValidationInput:
    root: Path
    run_id: str
    sections: list[Section]
    blocks: dict[str, ParsedBlock]
    sources: dict[str, SourceManifest]
    raw: dict[str, bytes]
    page_sizes: dict[str, list[tuple[float, float]]]
    audit: dict[str, list[dict]]
    original_receipts: list[ReviewReceipt]
    artifact_sha256: dict[str, str]
    html_evidence: dict | None = None


def load_input(root: Path, policy: ValidationPolicy) -> ValidationInput:
    root = root.resolve()
    directory = local_path(root, Path("data/ingestion") / policy.input_run_id)
    expected_files = {
        "manifest.json",
        "sections.jsonl",
        "holds.jsonl",
        "blocks.jsonl",
        "audit.jsonl",
        "reviews.json",
        "report.json",
        "sidecars.jsonl",
    }
    if set(policy.artifact_sha256) != expected_files:
        raise ValueError("input policy must pin all eight ingestion artifacts")
    actual = {}
    for name, expected in policy.artifact_sha256.items():
        p = local_path(root, directory.relative_to(root) / name)
        actual[name] = digest(p.read_bytes())
        if actual[name] != expected:
            raise ValueError(f"immutable ingestion artifact mismatch: {name}")

    def records(name):
        return [json.loads(line) for line in (directory / name).read_text().splitlines()]

    sections = [Section.model_validate(x) for x in records("sections.jsonl")]
    blocks_list = [ParsedBlock.model_validate(x) for x in records("blocks.jsonl")]
    blocks = {x.block_id: x for x in blocks_list}
    if len({s.section_id for s in sections}) != len(sections) or len(blocks) != len(blocks_list):
        raise ValueError("duplicate ingestion IDs")
    held = [s for s in sections if s.index_status == "hold"]
    if len(held) != policy.expected_hold_count:
        raise ValueError("HOLD coverage differs from pinned baseline")
    if records("holds.jsonl") != [s.model_dump(mode="json") for s in held]:
        raise ValueError("HOLD register differs from source sections")
    approved = [s for s in sections if s.index_status == "approved_for_index"]
    receipts = [
        ReviewReceipt.model_validate(x)
        for x in json.loads((directory / "reviews.json").read_text())
    ]
    if len(approved) != policy.expected_original_approvals or len(receipts) != len(approved):
        raise ValueError("original receipt coverage mismatch")
    if {r.section_id for r in receipts} != {s.section_id for s in approved}:
        raise ValueError("original approval/receipt ID mismatch")
    # Revalidate the original manual receipts, without changing any saved record.
    if apply_reviews(sections, receipts) != sections:
        raise ValueError("original manual receipt no longer validates")
    source_list = [
        SourceManifest.model_validate(x)
        for x in json.loads((directory / "manifest.json").read_text())
    ]
    sources = {s.doc_id: s for s in source_list}
    if len(sources) != len(source_list):
        raise ValueError("duplicate source ID")
    raw, page_sizes = {}, {}
    for source in source_list:
        data = local_path(root, source.raw_path).read_bytes()
        frozen = local_path(root, source.snapshot_path).read_bytes()
        if digest(data) != source.raw_sha256 or data != frozen or len(data) != source.byte_size:
            raise ValueError("raw/snapshot integrity mismatch")
        raw[source.doc_id] = data
        if source.source_format == "pdf":
            with pymupdf.open(stream=data, filetype="pdf") as pdf:
                page_sizes[source.doc_id] = [(p.rect.width, p.rect.height) for p in pdf]
    audit = {}
    for row in records("audit.jsonl"):
        audit.setdefault(row["block_id"], []).append(row)
    return ValidationInput(
        root,
        policy.input_run_id,
        sections,
        blocks,
        sources,
        raw,
        page_sizes,
        audit,
        receipts,
        actual,
    )


def validate_section(
    section: Section, context: ValidationInput, policy: ValidationPolicy
) -> ValidationResult:
    s = section
    source = context.sources.get(s.doc_id)
    reasons = []
    checks = {
        name: "pass" for name in ("integrity", "provenance", "audit", "source_fidelity", "context")
    }
    risk = "medium" if source and source.source_format == "pdf" else "low"
    cohort = f"{s.doc_id}:{s.block_type}"
    parents = [context.blocks.get(i) for i in s.block_ids]
    if len(parents) != 1 or parents[0] is None:
        reasons.append("missing_or_multiple_parent_blocks")
        block = None
    else:
        block = parents[0]
    if source is None or s.raw_sha256 != source.raw_sha256 or s.snapshot_id != source.snapshot_id:
        reasons.append("lineage_mismatch")
    if digest(s.text.encode()) != s.normalized_sha256:
        reasons.append("normalized_hash_mismatch")
    if block:
        if (
            block.doc_id != s.doc_id
            or block.snapshot_id != s.snapshot_id
            or block.raw_sha256 != s.raw_sha256
            or block.block_type != s.block_type
            or (block.locator,) != s.locators
            or block.heading_path != s.heading_path
            or block.provider_tab != s.provider_tab
        ):
            reasons.append("block_metadata_mismatch")
        hazards = set(s.issues) | set(block.issues)
        if s.block_type in ("table", "equation", "figure_caption"):
            reasons.append("unverified_" + str(s.block_type))
            risk = "high"
        if hazards - {"pdf_layout_and_reading_order_unreviewed"}:
            risk = "high"
            reasons.extend(sorted(hazards - {"pdf_layout_and_reading_order_unreviewed"}))
        if any(ord(c) < 32 and c not in "\n\r\t" for c in s.text) or any(
            c in s.text for c in "\ufffd\u200b"
        ):
            reasons.append("corrupted_or_fragmented_glyphs")
            risk = "high"
        if s.block_type != "code" and re.search(
            r"[∑∏∫∩≤≥]|\$[^$]+\$|\\(?:frac|sum|begin)\b|\|\s*:?-{3,}", s.text
        ):
            reasons.append("concealed_math_or_table")
            risk = "high"
        if s.block_type != "code" and re.search(r"\b[A-Za-z]\w*(?:\([^)]*\))?\s*[=≈]\s*\S", s.text):
            reasons.append("concealed_math_or_table")
            risk = "high"
        if s.block_type != "code" and re.search(r"\b\d+(?:\.\d+)?\s*(?:±|\|)\s*\d", s.text):
            reasons.append("concealed_math_or_table")
            risk = "high"
        if s.transformations:
            rows = context.audit.get(block.block_id, [])
            if not any(
                row.get("before_sha256") == block.content_sha256
                and row.get("after_sha256") == s.normalized_sha256
                and row.get("before") == block.content
                and row.get("after") == s.text
                and row.get("action") == list(s.transformations)
                for row in rows
            ):
                reasons.append("missing_audit")
        if source and source.source_format == "markdown_mdx":
            reasons.extend(check_markdown(s, block, context.raw[s.doc_id]))
        elif source and source.source_format == "pdf":
            loc = block.locator
            sizes = context.page_sizes.get(s.doc_id, [])
            if not loc.page or loc.page > len(sizes) or not loc.bbox:
                reasons.append("invalid_pdf_locator")
            else:
                w, h = sizes[loc.page - 1]
                x0, y0, x1, y1 = loc.bbox
                if not (0 <= x0 < x1 <= w + 0.5 and 0 <= y0 < y1 <= h + 0.5):
                    reasons.append("invalid_pdf_locator")
            checks["source_fidelity"] = "manual_required"
            reasons.append("pdf_visual_layout_review_required")
        else:
            reasons.append("unsupported_source_format")
            risk = "high"
        context_reasons = contextual_reasons(s, block)
        if context_reasons:
            reasons.extend(context_reasons)
            checks["context"] = "manual_required"
    blocking = bool(set(reasons) & INTEGRITY_REASONS)
    if blocking:
        risk = "high"
        checks["integrity"] = "fail"
    if any(
        r.endswith("mismatch") or r in ("invalid_source_lines", "invalid_pdf_locator")
        for r in reasons
    ):
        checks["provenance"] = "fail"
    if "missing_audit" in reasons:
        checks["audit"] = "fail"
    if source and source.source_format == "markdown_mdx" and set(reasons) & INTEGRITY_REASONS:
        checks["source_fidelity"] = "fail"
    eligible = (
        risk == "low"
        and not reasons
        and source is not None
        and source.doc_id in policy.automatic_documents
        and source.source_format in policy.automatic_formats
    )
    if risk == "high":
        checks["context"] = "manual_required"
    tags = {
        f"doc:{s.doc_id}",
        f"type:{s.block_type}",
        "length:" + ("short" if len(s.text) < 20 else "medium" if len(s.text) < 160 else "long"),
    }
    if block:
        if block.provider_tab:
            tags.add("provider:" + block.provider_tab)
        if block.code_group:
            tags.add("group:" + block.code_group + ":" + (s.code_label or ""))
        if block.language:
            tags.add("language:" + block.language)
        if block.locator.page and s.doc_id in context.page_sizes:
            n = len(context.page_sizes[s.doc_id])
            tags.add("page_region:" + str(min(3, (block.locator.page - 1) * 4 // n)))
        tags |= {
            "issue:" + i for i in block.issues if i != "pdf_layout_and_reading_order_unreviewed"
        }
    result = ValidationResult(
        section_id=s.section_id,
        doc_id=s.doc_id,
        raw_sha256=s.raw_sha256 or "",
        normalized_sha256=s.normalized_sha256 or "",
        risk=risk,
        cohort=cohort,
        checks=checks,
        reasons=tuple(sorted(set(reasons))),
        eligible_automatic=eligible,
        blocking_integrity=blocking,
        coverage_tags=tuple(sorted(tags)),
    )
    if source and source.source_format == "html":
        from rag_hub.html_validation import enrich_result

        return enrich_result(result, section, context, policy)
    return result


def classify_all(context: ValidationInput, policy: ValidationPolicy) -> list[ValidationResult]:
    held = [s for s in context.sections if s.index_status == "hold"]
    results = [validate_section(s, context, policy) for s in held]
    if len(results) != policy.expected_hold_count or len({r.section_id for r in results}) != len(
        results
    ):
        raise ValueError("validation coverage is not exact")
    return results


def risk_counts(results):
    return dict(Counter(r.risk for r in results))
