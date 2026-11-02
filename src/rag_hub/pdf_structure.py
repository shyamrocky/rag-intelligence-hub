"""Reviewed, source-bound paragraph split; no general PDF reconstruction or eligibility."""

import json

from rag_hub.acquire import digest
from rag_hub.pdf_nontext import image_observation


def encoded(value):
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()


def split_constraint(source, blocks, bundle):
    spec = bundle["constraint"]
    owner = bundle["owner_case"]
    identity = (source.doc_id, source.raw_sha256, source.snapshot_id)
    expected = tuple(owner["source"][k] for k in ("doc_id", "raw_sha256", "snapshot_id"))
    if identity != expected:
        return None
    if (
        spec.get("operation") != "paragraph_split"
        or spec.get("case_id") != owner.get("case_id")
        or not spec.get("submitted_human_entry")
        or owner["decisions"].get("paragraph_boundary_fidelity") != "PASS"
        or owner["decisions"].get("prose_reading_order") != "PASS"
        or owner["decisions"].get("mathematical_completeness") != "FAIL"
    ):
        raise ValueError("unsupported_or_unreviewed_split_constraint")
    if bundle["expected_parent_sha256"] != [p["sha256"] for p in owner["output_parents"]]:
        raise ValueError("owner_output_binding_mismatch")
    lookup = {b.block_id: b for b in blocks}
    groups = spec["groups"]
    if len(groups) != 2 or not all(groups):
        raise ValueError("invalid_split")
    all_members = [m for group in groups for m in group]
    for m in all_members + spec["context"]:
        b = lookup.get(m["block_id"])
        if b is None or (b.doc_id, b.raw_sha256, b.snapshot_id) != identity:
            raise ValueError("foreign_or_missing_source")
        if (
            (m["raw_sha256"], m["snapshot_id"]) != identity[1:]
            or m["content_sha256"] != b.content_sha256
            or digest(b.content.encode()) != b.content_sha256
            or m["locator"] != b.locator.model_dump(mode="json")
        ):
            raise ValueError("stale_observation")
        if not (
            type(m["start"]) is int
            and type(m["end"]) is int
            and 0 <= m["start"] < m["end"] <= len(b.content)
        ):
            raise ValueError("invalid_review_span")
    seq = [lookup[m["block_id"]].sequence for m in all_members]
    if seq != sorted(set(seq)):
        raise ValueError("invalid_source_order")
    if groups[0][-1]["locator"]["page"] >= groups[1][0]["locator"]["page"]:
        raise ValueError("not_reviewed_cross_page_split")
    # This bounded operation replaces full atomic prose blocks only.
    if any(m["start"] != 0 or m["end"] != len(lookup[m["block_id"]].content) for m in all_members):
        raise ValueError("partial_atomic_replacement_not_supported")
    return spec, lookup, groups


def pdf_parents(source, blocks, options):
    # Native evidence must be checked by the normalization owner before this callback.
    from rag_hub.shared.structure import atomic_parents, span

    original = atomic_parents(source, [b for b in blocks if not image_observation(b)], {})
    bundle = options.get("reviewed_split")
    if not bundle:
        return original
    validated = split_constraint(source, blocks, bundle)
    if validated is None:
        return original
    spec, lookup, groups = validated
    units = []
    for i, group in enumerate(groups):
        members = [
            span(lookup[m["block_id"]], m["start"], m["end"])
            | {"bbox_scope": "whole original block, not per-character geometry"}
            for m in group
        ]
        text = "\n".join(lookup[m["block_id"]].content[m["start"] : m["end"]] for m in members)
        units.append(
            {
                "id": "bpr01:" + spec["case_id"] + ":" + str(i),
                "doc_id": source.doc_id,
                "kind": "paragraph",
                "members": members,
                "text": text,
                "text_sha256": digest(text.encode()),
                "display_text": text,
                "display_inverse": [],
                "raw_sha256": source.raw_sha256,
                "snapshot_id": source.snapshot_id,
                "heading_block_id": spec.get("heading"),
                "structure_status": "machine_provisional_HOLD",
                "construction": "review_constrained_source_span_operation",
                "canonical_joiner": "one synthetic newline between exact original source spans",
                "experimental_eligibility": "HOLD",
                "independent_structure_verified": False,
                "source_review_case": spec["case_id"],
                "review_constraint_sha256": digest(encoded(spec)),
                "geometry_evidence": {
                    "basis": "explicit_human_boundary_constraint; page transition alone is insufficient"
                },
                "issues": ["unresolved_detached_math_dependency_not_reconstructed"]
                if i == 0
                else [],
                "hazards": ["incomplete_mathematical_notation"] if i == 0 else [],
            }
        )
    if [digest(encoded(u)) for u in units] != bundle["expected_parent_sha256"]:
        raise ValueError("reviewed_output_hash_mismatch")
    touched = {m["block_id"] for group in groups for m in group}
    result = [
        p for p in original if not any(m["block_id"] in touched for m in p["members"])
    ] + units
    result.sort(
        key=lambda p: min((lookup[m["block_id"]].sequence, m["start"]) for m in p["members"])
    )
    return result


def continuation(left, right, layout, *, suggested=False, bibliography=False):
    """Conservative full-block continuation; return evidence or an explicit abstention."""
    import re

    a, b = layout[left.block_id], layout[right.block_id]
    if right.sequence != left.sequence + 1:
        return None, "intervening_records_flat_graph_contract"
    if abs(a["font_size"] - b["font_size"]) > 0.6:
        return None, "font_transition"
    ab, bb = left.locator.bbox, right.locator.bbox
    first = b["first_line_bbox"]
    size = max(a["font_size"], 1)
    if bibliography and re.match(r"^\[\d+\]", right.content.strip()):
        return None, "new_reference_entry"
    if left.locator.page == right.locator.page:
        same_column = abs(ab[0] - bb[0]) <= (24 if bibliography else 2)
        if same_column and -0.5 <= bb[1] - ab[3] <= size * 0.7:
            if first[0] - bb[0] > size * 0.35 and not bibliography:
                return None, "new_paragraph_indent"
            if suggested:
                return "native_spacing_and_Docling_suggestion", None
            last = a["last_line_bbox"]
            width = a.get("column_right", last[2]) - last[0]
            # Source-native line geometry can support a join without a cached proposal.
            # Require a nearly full line, ordinary baseline pitch and lexical continuation.
            if (
                not bibliography
                and "column_right" in a
                and width >= size * 20
                and (last[2] - last[0]) >= width * 0.95
                and abs(first[0] - last[0]) <= 2
                and size * 1.25 <= first[1] - last[1] <= size * 1.65
                and right.content[:1].islower()
                and left.content.rstrip()[-1:] not in ".!?:;"
            ):
                return "native_full_line_and_baseline_continuation", None
        # Page/column transition must have an unfinished source line and an
        # unindented lowercase continuation, never just topical similarity.
        if (
            ab[2] < bb[0]
            and ab[3] > a["page_size"][1] * 0.8
            and bb[1] < ab[1]
            and abs(first[0] - bb[0]) < size * 0.25
            and right.content[:1].islower()
            and left.content.rstrip()[-1:] not in ".!?:;"
        ):
            return "native_cross_column_continuation", None
    elif right.locator.page == left.locator.page + 1:
        if (
            ab[3] > a["page_size"][1] * 0.8
            and bb[1] < b["page_size"][1] * 0.25
            and abs(first[0] - bb[0]) < size * 0.25
            and right.content[:1].islower()
            and left.content.rstrip()[-1:] not in ".!?:;"
        ):
            return "native_cross_page_continuation", None
    return None, "boundary_not_sufficiently_supported"


def paragraph_band_edges(parents, blocks, layout, roles=None):
    """Contiguous long body lines bounded by larger native paragraph gaps.

    This stronger run witness is separate from pair-only lexical continuation.
    It never crosses non-prose, partial, reviewed, page or column observations.
    """
    from itertools import pairwise

    roles = roles or {}
    eligible = []
    for p in parents:
        if p["kind"] != "paragraph" or p.get("source_review_case") or len(p["members"]) != 1:
            continue
        m = p["members"][0]
        b = blocks[m["block_id"]]
        x = layout.get(b.block_id, {})
        if (
            b.block_type == "prose"
            and roles.get(b.block_id, {}).get("role") != "bibliography_entry_candidate"
            and m["start"] == 0
            and m["end"] == len(b.content)
            and x.get("line_count") == 1
            and x.get("fonts")
            and "column_right" in x
        ):
            eligible.append(b)

    def adjacent(a, b):
        x, y = layout[a.block_id], layout[b.block_id]
        size = x["font_size"]
        return (
            b.sequence == a.sequence + 1
            and a.locator.page == b.locator.page
            and abs(a.locator.bbox[0] - b.locator.bbox[0]) <= 2
            and abs(size - y["font_size"]) <= 0.6
            and x["fonts"] == y["fonts"]
            and size * 1.25 <= y["first_line_bbox"][1] - x["last_line_bbox"][1] <= size * 1.65
        )

    runs = []
    for b in eligible:
        if runs and adjacent(runs[-1][-1], b):
            runs[-1].append(b)
        else:
            runs.append([b])
    sequences = {b.sequence: b for b in blocks.values()}
    edges = set()
    for run in runs:
        first, last = run[0], run[-1]
        before, after = sequences.get(first.sequence - 1), sequences.get(last.sequence + 1)
        size = layout[first.block_id]["font_size"]
        if len(run) < 3 or before is None or after is None:
            continue
        if before.block_id not in layout or after.block_id not in layout:
            continue
        if any(b.locator.page != first.locator.page for b in (before, after)):
            continue
        if any(abs(b.locator.bbox[0] - first.locator.bbox[0]) > 2 for b in (before, after)):
            continue
        start_gap = (
            layout[first.block_id]["first_line_bbox"][1]
            - layout[before.block_id]["last_line_bbox"][1]
        )
        end_gap = (
            layout[after.block_id]["first_line_bbox"][1]
            - layout[last.block_id]["last_line_bbox"][1]
        )
        if min(start_gap, end_gap) < size * 1.9:
            continue
        if any(
            (layout[b.block_id]["last_line_bbox"][2] - b.locator.bbox[0])
            < (layout[b.block_id]["column_right"] - b.locator.bbox[0]) * 0.85
            or layout[b.block_id]["column_right"] - b.locator.bbox[0] < size * 20
            for b in run[:-1]
        ):
            continue
        edges.update((a.block_id, b.block_id) for a, b in pairwise(run))
    return edges


def reconstruct_pdf(packet, parents, blocks, source):
    """Derived source-span parents using the unchanged flat conformance contract.

    All new structures remain provisional/HOLD. Reviewed C06 records are opaque:
    their exact hashes and independent failed math facet remain untouched.
    """
    import re
    from itertools import pairwise

    from rag_hub.shared.structure import parent, span

    lookup = {b.block_id: b for b in blocks}
    coverage = {r["block_id"]: r for r in packet["coverage"]}
    layout, roles = packet["native_layout"], packet["layout_roles"]
    suggestions = set()
    blocked = []
    for row in packet["regions"]:
        if (
            row["active"]
            and row["content_type"] == "prose"
            and row["evidence"].get("component") == "cached_hybrid_structural_proposal"
        ):
            ids = list(dict.fromkeys(m["block_id"] for m in row["members"]))
            suggestions.update(pairwise(ids))
    replacements = []
    for p in parents:
        if p.get("source_review_case") or len(p["members"]) != 1:
            replacements.append(p)
            continue
        bid = p["members"][0]["block_id"]
        components = roles.get(bid, {}).get("components", [])
        footnotes = [c for c in components if c["role"] == "footnote"]
        if p["kind"] == "footnote_observation" and footnotes:
            for i, c in enumerate(footnotes):
                u = parent(
                    p["id"] + f":footnote:{i}",
                    "footnote",
                    [span(lookup[bid], c["start"], c["end"])],
                    source,
                    lookup,
                )
                u["marker_source_span"] = span(lookup[bid], c["marker_start"], c["marker_end"])
                u["marker_presentation"] = c["marker_presentation"]
                u["reference_ownership"] = "unverified_HOLD"
                replacements.append(u)
        else:
            replacements.append(p)
    band_edges = paragraph_band_edges(replacements, lookup, layout, roles)
    groups = []
    for p in replacements:
        if groups and p["kind"] == groups[-1]["kind"] == "paragraph":
            previous = groups[-1]
            left, right = (
                lookup[previous["members"][-1]["block_id"]],
                lookup[p["members"][0]["block_id"]],
            )
            if not previous.get("source_review_case") and not p.get("source_review_case"):
                # Never merge partial-span or duplicate-member representations.
                full = all(
                    m["start"] == 0 and m["end"] == len(lookup[m["block_id"]].content)
                    for m in previous["members"] + p["members"]
                )
                bib = roles.get(left.block_id, {}).get("role") == "bibliography_entry_candidate"
                evidence, reason = (
                    continuation(
                        left,
                        right,
                        layout,
                        suggested=(left.block_id, right.block_id) in suggestions,
                        bibliography=bib,
                    )
                    if full
                    else (None, "partial_span_parent")
                )
                if not evidence and full and (left.block_id, right.block_id) in band_edges:
                    evidence, reason = "native_bounded_paragraph_band", None
                if evidence:
                    members = previous["members"] + p["members"]
                    u = parent(
                        "layout-parent:" + members[0]["block_id"],
                        "paragraph",
                        members,
                        source,
                        lookup,
                    )
                    u.update(
                        {
                            "construction": "native_source_span_continuation",
                            "structure_status": "machine_provisional_HOLD",
                            "grouping_evidence": previous.get("grouping_evidence", []) + [evidence],
                        }
                    )
                    groups[-1] = u
                    continue
                if (left.block_id, right.block_id) in suggestions:
                    blocked.append(
                        {
                            "from_block": left.block_id,
                            "to_block": right.block_id,
                            "reason": reason,
                            "status": "unresolved_HOLD",
                        }
                    )
        groups.append(p)
    # Record suggestions crossing non-prose/furniture/footnote records; never hide them.
    for a, b in sorted(suggestions):
        if lookup[b].sequence != lookup[a].sequence + 1:
            blocked.append(
                {
                    "from_block": a,
                    "to_block": b,
                    "reason": "intervening_records_flat_graph_contract",
                    "status": "unresolved_HOLD",
                }
            )
    prose_blocks = [b for b in blocks if coverage[b.block_id]["content_type"] == "prose"]
    for a, b in pairwise(prose_blocks):
        between = blocks[a.sequence + 1 : b.sequence]
        if (
            between
            and all(
                coverage[x.block_id]["content_type"] in ("page_furniture", "footnote")
                for x in between
            )
            and not any(
                x.get("from_block") == a.block_id and x.get("to_block") == b.block_id
                for x in blocked
            )
        ):
            blocked.append(
                {
                    "from_block": a.block_id,
                    "to_block": b.block_id,
                    "reason": "intervening_records_flat_graph_contract",
                    "status": "candidate_continuation_unverified_HOLD",
                }
            )
    stack, pending_heading = [], None
    for p in groups:
        if p.get("source_review_case"):
            continue
        p["structure_status"] = "machine_provisional_HOLD"
        bid = p["members"][0]["block_id"]
        b = lookup[bid]
        if p["kind"] == "section_parent":
            pending_heading = None
            match = re.match(r"^(\d+(?:\.\d+)*)\s", b.content.strip())
            size = layout[bid]["font_size"]
            level = len(match[1].split(".")) if match else None
            while stack and (
                (stack[-1][2] is None or stack[-1][2] >= level)
                if level is not None
                else stack[-1][1] <= size + 0.5
            ):
                stack.pop()
            if stack:
                p["heading_block_id"] = stack[-1][0]
            stack.append((bid, size, level))
        elif p["kind"] in ("paragraph", "code_observation", "presentation_observation"):
            if pending_heading:
                p["proposed_heading_block_id"] = pending_heading
                p["heading_relationship_status"] = "raw_heading_contract_blocked_HOLD"
            elif stack:
                p["heading_block_id"] = stack[-1][0]
        elif coverage[bid]["content_type"] == "heading":
            pending_heading = bid
            blocked.append(
                {
                    "block_id": bid,
                    "reason": "heading_requires_raw_heading_contract",
                    "status": "unresolved_HOLD",
                }
            )
    # Return supporting evidence to the existing Normalization stage owner.
    return groups, {
        "version": "pdf-native-grouping-1.0",
        "abstentions": blocked,
        "new_structures_status": "provisional_HOLD",
        "eligibility": "HOLD",
    }
