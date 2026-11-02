"""Consolidate existing PDF type evidence; never rewrite observations or grant eligibility.

Coverage objects partition observations. Semantic proposals may overlap and carry
partial/multiple source spans. Neither their count nor their labels proves accuracy.
"""

import copy
import json
from collections import Counter, defaultdict
from itertools import pairwise

from rag_hub.acquire import digest, local_path
from rag_hub.normalize import removal_reason
from rag_hub.pdf_nontext import inspect_nontext
from rag_hub.shared.guard import validate_unit
from rag_hub.shared.structure import span

VERSION = "pdf-classification-1.0"
TYPES = frozenset(
    (
        "heading",
        "prose",
        "list",
        "table",
        "equation",
        "inline_math",
        "image",
        "figure_caption",
        "table_caption",
        "code",
        "footnote",
        "page_furniture",
        "presentation",
        "unknown",
    )
)
STATUSES = frozenset(("supported", "provisional", "ambiguous", "unsupported"))
KIND = {
    "paragraph": "prose",
    "paragraph_suggestion": "prose",
    "section": "heading",
    "section_parent": "heading",
    "code": "code",
    "figure_caption": "figure_caption",
    "table_caption": "table_caption",
    "equation": "equation",
    "table": "table",
    "footnote": "footnote",
    "presentation": "presentation",
    "presentation_header": "presentation",
}
POLICY = {t: "retain_exact_source_HOLD_no_semantic_reconstruction" for t in TYPES}
POLICY.update(
    prose="source_bound_paragraph_rules_only_HOLD",
    heading="retain_heading_candidate_HOLD",
    image="native_object_sidecar_visual_HOLD",
    code="preserve_payload_and_presentation_roles_HOLD",
    table="retain_unflattened_source_table_topology_HOLD",
    equation="retain_symbols_math_topology_HOLD",
    inline_math="retain_symbol_dependency_HOLD",
    page_furniture="existing_audited_exclusion_only_HOLD",
)


def encoded(value):
    return (
        json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode()


def load_evidence(root, path):
    """Trusted local evidence only; source documents cannot select/import code."""

    def private(name):
        p = local_path(root, name)
        if not any(p.is_relative_to(root / d) for d in ("workspace", "data")):
            raise ValueError("classification_evidence_must_be_private")
        return p

    path = private(path)
    bundle = json.loads(path.read_bytes())
    if bundle.get("schema") != "pdf-classification-input-1.0":
        raise ValueError("unsupported_classification_input")
    files = bundle["files"]
    assets = [path]
    for name, expected in files.items():
        p = private(name)
        if digest(p.read_bytes()) != expected:
            raise ValueError("classification_evidence_hash_mismatch")
        assets.append(p)

    def read(name):
        if name not in files:
            raise ValueError("unbound_classification_evidence")
        return json.loads(private(name).read_bytes())

    parents, inactive = [], []
    for row in bundle["parent_artifacts"]:
        value = read(row["path"])
        parents.extend(value[row["collection"]])
        inactive.extend(x["from"] for x in value.get("bpr01", {}).get("forward_alternatives", []))
    result = {
        "parents": parents,
        "inactive_parent_ids": inactive,
        "phase1d_reviews": read(bundle["phase1d_receipts"])["observations"],
        "owner_reviews": read(bundle["owner_output_review"])["cases"],
        "bindings": files,
        "bundle_sha256": digest(path.read_bytes()),
    }
    return result, tuple(assets)


def identity(source):
    return {k: getattr(source, k) for k in ("doc_id", "raw_sha256", "snapshot_id")}


def reviewed_type(unit, evidence):
    """Reuse only bound type/structure facets; FAIL facets never become approvals."""
    sha = digest(encoded(unit))
    for receipt in evidence.get("phase1d_reviews", []):
        binding = receipt["unit_binding"]
        if (
            binding["unit_id"] == unit["id"]
            and binding["unit_record_sha256"] == sha
            and binding["members"] == unit["members"]
            and binding["source_sha256"] == unit["raw_sha256"]
            and binding["snapshot_id"] == unit["snapshot_id"]
        ):
            facets = receipt["human_confirmed_facets"]
            required = {
                "code": "code_type",
                "figure_caption": "figure_caption_type",
                "prose": "bibliography_grouping",
            }.get(KIND.get(unit["kind"]))
            if required in facets:
                return {
                    "case_id": receipt["case_id"],
                    "facet": required,
                    "kind": "existing_user_scoped_facet",
                    "full_fidelity_certified": False,
                }
    for case in evidence.get("owner_reviews", []):
        if any(case["source"][k] != unit[k] for k in ("doc_id", "raw_sha256", "snapshot_id")):
            continue
        if {"id": unit["id"], "sha256": sha} not in case["output_parents"]:
            continue
        decisions = case["decisions"]
        required = {
            "section_parent": "heading_body_partition",
            "footnote": "footnote_separation",
        }.get(unit["kind"])
        if unit["kind"] == "paragraph":
            required = next(
                (
                    n
                    for n in (
                        "paragraph_boundary_fidelity",
                        "drop_cap_attachment",
                        "paragraph_continuation",
                    )
                    if n in decisions
                ),
                None,
            )
        if required and decisions.get(required) == "PASS":
            return {
                "case_id": case["case_id"],
                "facet": required,
                "kind": "existing_owner_output_facet",
                "full_fidelity_certified": False,
                "failed_facets": {k: v for k, v in decisions.items() if v != "PASS"},
            }
    return None


def classify_pdf(data, source, blocks, evidence=None, reviewed_split=None):
    evidence = evidence or {}
    images = {r["block_id"]: r for r in inspect_nontext(data, source, blocks)}
    lookup = {b.block_id: b for b in blocks}
    regions, relations = [], []

    def region(ident, kind, members, status, origin, *, support=None, level="region", active=True):
        kind = kind if kind in TYPES else "unknown"
        text = "\n".join(lookup[m["block_id"]].content[m["start"] : m["end"]] for m in members)
        row = {
            "id": ident,
            **identity(source),
            "content_type": kind,
            "classification_status": status,
            "members": copy.deepcopy(members),
            "text": text,
            "text_sha256": digest(text.encode()),
            "evidence": origin,
            "review_support": support,
            "level": level,
            "active": active,
            "handling_policy": POLICY[kind],
            "eligibility": "HOLD",
        }
        _, issues = validate_unit(row, lookup)
        if issues:
            raise ValueError("invalid_classification_source_spans")
        regions.append(row)
        return row

    for b in blocks:
        if b.block_id in images:
            continue
        reason = removal_reason(b)
        kind = (
            "page_furniture"
            if reason == "remove_verified_print_margin_artifact"
            else (
                b.block_type if b.block_type in ("heading", "table", "code", "list") else "unknown"
            )
        )
        status = (
            "supported"
            if kind == "page_furniture"
            else "provisional"
            if kind != "unknown"
            else "ambiguous"
        )
        region(
            "native-type:" + b.block_id,
            kind,
            [span(b)],
            status,
            {
                "component": "parse_pdf.py / existing normalization predicate",
                "raw_type": b.block_type,
                "issues": list(b.issues),
                "removal_rule": reason,
                "candidate_types": [b.block_type]
                if b.block_type != "equation"
                else ["equation", "inline_math", "table", "code", "prose"],
                "limit": "raw prose fallback and math-character hints are not semantic truth",
            },
            level="native",
        )

    for unit in evidence.get("parents", []):
        if any(unit.get(k) != v for k, v in identity(source).items()):
            continue
        supported = reviewed_type(unit, evidence)
        status = "supported" if supported else "provisional"
        if unit["kind"] not in KIND:
            status = "unsupported"
        active = unit["id"] not in evidence.get(
            "inactive_parent_ids", []
        ) and "superseded" not in unit.get("structure_status", "")
        row = region(
            "proposal:" + unit["id"],
            KIND.get(unit["kind"], "unknown"),
            unit["members"],
            status,
            {
                "component": "cached_hybrid_structural_proposal",
                "unit_id": unit["id"],
                "unit_sha256": digest(encoded(unit)),
                "requested_kind": unit["kind"],
                "construction": unit.get("construction"),
                "native_refs": unit.get("suggestion_refs", []),
                "bindings": evidence.get("bindings", {}),
            },
            support=supported,
            active=active,
        )
        for n, line in enumerate(unit.get("typed_code_lines", [])):
            for name, kind in (
                ("payload_span", "code"),
                ("printed_line_number_span", "presentation"),
                ("number_payload_layout_separator_span", "presentation"),
            ):
                child = region(
                    row["id"] + f":{n}:{name}",
                    kind,
                    [line[name]],
                    status,
                    {
                        "component": "existing_typed_code_roles",
                        "role": name,
                        "indentation_characters": line["indentation_characters"],
                    },
                    support=supported,
                    level="component",
                    active=active,
                )
                relations.append(
                    {
                        "from": child["id"],
                        "to": row["id"],
                        "type": "component_of",
                        "status": status,
                        "reconstruction": "not_performed_HOLD",
                    }
                )
        for n, attachment in enumerate(unit.get("inline_relationships", [])):
            child = region(
                row["id"] + f":inline:{n}",
                "inline_math",
                [attachment["symbol_span"]],
                "provisional",
                {
                    "component": "existing_inline_symbol_relationship",
                    "source_relationship": attachment,
                },
                level="component",
                active=active,
            )
            relations.append(
                {
                    "from": child["id"],
                    "to": row["id"],
                    "type": "inline_math_dependency",
                    "status": "provisional",
                    "reconstruction": "not_performed_HOLD",
                }
            )

    if reviewed_split:
        from rag_hub.pdf_structure import split_constraint

        bound = split_constraint(source, blocks, reviewed_split)
        if bound is not None:
            spec, _lookup, groups = bound
            for n, group in enumerate(groups):
                region(
                    "reviewed-split-type:" + spec["case_id"] + ":" + str(n),
                    "prose",
                    [span(lookup[m["block_id"]], m["start"], m["end"]) for m in group],
                    "supported",
                    {
                        "component": "existing_reviewed_split_constraint",
                        "source_case": spec["case_id"],
                    },
                    support={
                        "case_id": spec["case_id"],
                        "facet": "paragraph_boundary_fidelity",
                        "kind": "existing_owner_output_facet",
                        "full_fidelity_certified": False,
                    },
                )

    # Native typography/geometry is evidence, never an independent approval.
    from rag_hub.pdf_layout import compact_layout, native_layout, type_evidence

    layout, body_size = native_layout(data, source, blocks)
    layout_types = type_evidence(blocks, layout, body_size, regions)
    for bid, interpretation in layout_types.items():
        # Partial heading/body composites require their separately gated contract.
        if any(
            r["active"]
            and r["content_type"] == "heading"
            and any(
                m["block_id"] == bid and (m["start"] != 0 or m["end"] != len(lookup[bid].content))
                for m in r["members"]
            )
            for r in regions
            if r["level"] == "region"
        ):
            continue
        region(
            "layout-type:" + bid,
            interpretation["content_type"],
            [span(lookup[bid])],
            "provisional",
            {"component": "native_layout_rules", **interpretation},
            level="layout",
        )

    byblock = defaultdict(list)
    for row in regions:
        if not row["active"]:
            continue
        for m in row["members"]:
            byblock[m["block_id"]].append((row, m))
    coverage = []
    for b in blocks:
        if b.block_id in images:
            coverage.append(
                {
                    "id": "coverage:" + b.block_id,
                    **identity(source),
                    "block_id": b.block_id,
                    "native_type": "image",
                    "object_reference": images[b.block_id],
                    "members": [],
                    "content_type": "image",
                    "classification_status": "supported",
                    "component_types": ["image"],
                    "mixed": False,
                    "segments": [],
                    "handling_policy": POLICY["image"],
                    "eligibility": "HOLD",
                }
            )
            continue
        entries = byblock[b.block_id]
        cuts = sorted({0, len(b.content), *(m[k] for _, m in entries for k in ("start", "end"))})
        segments = []
        for a, z in pairwise(cuts):
            candidates = [row for row, m in entries if m["start"] <= a < z <= m["end"]]

            def rank(row):
                return (
                    2
                    if row["classification_status"] == "supported"
                    else 1
                    if row["classification_status"] == "provisional"
                    else 0,
                    2 if row["level"] == "layout" else int(row["level"] == "component"),
                )

            highest = max(map(rank, candidates))
            winners = [row for row in candidates if rank(row) == highest]
            types = {row["content_type"] for row in winners}
            kind = next(iter(types)) if len(types) == 1 else "unknown"
            status = "ambiguous" if kind == "unknown" else winners[0]["classification_status"]
            segments.append(
                {
                    "start": a,
                    "end": z,
                    "content_type": kind,
                    "classification_status": status,
                    "evidence_region_ids": sorted(row["id"] for row in winners),
                    "conflicting_types": sorted(types) if len(types) > 1 else [],
                }
            )
        types = sorted({s["content_type"] for s in segments})
        kind = types[0] if len(types) == 1 else "unknown"
        state = (
            "ambiguous"
            if kind == "unknown"
            else (
                "supported"
                if all(s["classification_status"] == "supported" for s in segments)
                else "provisional"
            )
        )
        coverage.append(
            {
                "id": "coverage:" + b.block_id,
                **identity(source),
                "block_id": b.block_id,
                "native_type": "text",
                "object_reference": None,
                "members": [span(b)],
                "content_type": kind,
                "classification_status": state,
                "component_types": types,
                "mixed": len(types) > 1,
                "segments": segments,
                "handling_policy": POLICY[kind],
                "eligibility": "HOLD",
            }
        )
    packet = {
        "schema": VERSION,
        "source": identity(source),
        "coverage": coverage,
        "regions": regions,
        "relationships": relations,
        "native_layout": compact_layout(layout),
        "layout_roles": layout_types,
        "evidence_bundle_sha256": evidence.get("bundle_sha256"),
        "semantic_accuracy": "not_established_by_coverage",
        "eligibility": "HOLD",
    }
    validate_classification(packet, source, blocks, object_evidence=images)
    packet["summary"] = summarize(packet, blocks)
    return packet


def validate_classification(packet, source, blocks, *, object_evidence=None):
    if (
        packet.get("schema") != VERSION
        or packet.get("source") != identity(source)
        or packet.get("eligibility") != "HOLD"
    ):
        raise ValueError("invalid_classification_identity_or_version")
    lookup = {b.block_id: b for b in blocks}
    coverage = packet["coverage"]
    if len(coverage) != len(blocks) or {r["block_id"] for r in coverage} != set(lookup):
        raise ValueError("classification_missing_or_duplicate_observations")
    ids = [r["id"] for r in packet["regions"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate_classification_region_ids")
    coverage_ids = {r["id"] for r in coverage}
    for row in [*coverage, *packet["regions"]]:
        if (
            any(row.get(k) != v for k, v in identity(source).items())
            or row.get("content_type") not in TYPES
            or row.get("classification_status") not in STATUSES
            or row.get("eligibility") != "HOLD"
        ):
            raise ValueError("invalid_classification_type_status_or_source")
        if row["id"] in coverage_ids:
            b = lookup[row["block_id"]]
            if row["native_type"] not in ("image", "text"):
                raise ValueError("unknown_native_observation_type")
            if row["native_type"] == "image":
                proof = row.get("object_reference")
                if (
                    b.content
                    or row["members"]
                    or not proof
                    or proof["original_observation"] != b.model_dump(mode="json")
                    or proof["native_type"] != 1
                    or row["content_type"] != "image"
                    or proof.get("image_byte_size", 0) <= 0
                    or proof.get("visual_content_status") != "unprocessed_HOLD"
                    or (object_evidence is not None and proof != object_evidence.get(b.block_id))
                ):
                    raise ValueError("invalid_nontext_object_reference")
            elif (
                row["members"] != [span(b)]
                or row["segments"][0]["start"] != 0
                or row["segments"][-1]["end"] != len(b.content)
            ):
                raise ValueError("incomplete_classification_coverage")
            else:
                for s in row["segments"]:
                    if (
                        type(s["start"]) is not int
                        or type(s["end"]) is not int
                        or not 0 <= s["start"] < s["end"] <= len(b.content)
                        or s["content_type"] not in TYPES
                        or s["classification_status"] not in STATUSES
                        or not s["evidence_region_ids"]
                        or not set(s["evidence_region_ids"]) <= set(ids)
                    ):
                        raise ValueError("invalid_classification_segment")
                types = sorted({s["content_type"] for s in row["segments"]})
                expected_type = types[0] if len(types) == 1 else "unknown"
                if row["component_types"] != types or row["content_type"] != expected_type:
                    raise ValueError("inconsistent_classification_segments")
                for a, z in pairwise(row["segments"]):
                    if a["end"] != z["start"]:
                        raise ValueError("classification_coverage_gap")
        else:
            _, issues = validate_unit(row, lookup)
            if issues:
                raise ValueError("invalid_classification_source_spans")
            if (
                row["classification_status"] == "supported"
                and row["content_type"] == "page_furniture"
                and not all(
                    removal_reason(lookup[m["block_id"]]) == "remove_verified_print_margin_artifact"
                    for m in row["members"]
                )
            ):
                raise ValueError("unverified_furniture_exclusion_claim")
            support = row.get("review_support")
            if support and (
                support.get("kind")
                not in ("existing_user_scoped_facet", "existing_owner_output_facet")
                or support.get("full_fidelity_certified") is not False
                or not support.get("case_id")
                or not support.get("facet")
            ):
                raise ValueError("invalid_review_support_provenance")
            if (
                row["classification_status"] == "supported"
                and not row.get("review_support")
                and row["content_type"] != "page_furniture"
            ):
                raise ValueError("supported_semantic_type_requires_bound_review")
    for edge in packet["relationships"]:
        if edge["from"] not in ids or edge["to"] not in ids:
            raise ValueError("unresolved_classification_relationship")
    return True


def summarize(packet, blocks):
    coverage, regions = packet["coverage"], packet["regions"]
    return {
        "raw_observations": len(blocks),
        "native_text": sum(r["native_type"] == "text" for r in coverage),
        "native_images": sum(r["native_type"] == "image" for r in coverage),
        "accounted_observations": len(coverage),
        "missing_observations": [],
        "source_codepoints": sum(len(b.content) for b in blocks),
        "known_type_codepoints": sum(
            s["end"] - s["start"]
            for r in coverage
            for s in r["segments"]
            if s["content_type"] != "unknown"
        ),
        "coverage_types": dict(Counter(r["content_type"] for r in coverage)),
        "coverage_statuses": dict(Counter(r["classification_status"] for r in coverage)),
        "semantic_regions_by_type": dict(Counter(r["content_type"] for r in regions)),
        "semantic_region_statuses": dict(Counter(r["classification_status"] for r in regions)),
        "inactive_proposals": sum(not r["active"] for r in regions),
        "mixed_observations": sum(r["mixed"] for r in coverage),
        "conflicting_observations": sum(
            any(s.get("conflicting_types") for s in r["segments"]) for r in coverage
        ),
        "unknown_observations": sum(r["content_type"] == "unknown" for r in coverage),
        "unprocessed_visual_objects": sum(r["native_type"] == "image" for r in coverage),
        "unqualified_math_observations": sum(
            any(t in ("equation", "inline_math") for t in r["component_types"])
            or any("mixed_block_possible_math" in issue for issue in b.issues)
            for r, b in zip(coverage, blocks, strict=True)
        ),
        "semantic_region_counts_overlap": True,
        "content_eligibility": "HOLD",
    }


def route_parents(packet, parents, blocks):
    """Retype atomic containers only; do not introduce unapproved reconstruction."""
    byid = {r["block_id"]: r for r in packet["coverage"]}
    result, routes = copy.deepcopy(parents), []
    for p in result:
        ids = sorted({m["block_id"] for m in p["members"]})
        types = sorted({t for bid in ids for t in byid[bid]["component_types"]})
        reviewed = bool(p.get("source_review_case"))
        before = p["kind"]
        if not reviewed:
            typ = byid[ids[0]]["content_type"] if len(ids) == 1 else "unknown"
            p["kind"] = (
                "section_parent"
                if typ == "heading" and p["kind"] == "section_parent"
                else "paragraph"
                if typ == "prose"
                else typ + "_observation"
            )
            if any(
                packet.get("layout_roles", {}).get(bid, {}).get("role") == "chart_text_HOLD"
                for bid in ids
            ):
                p["kind"] = "chart_text_observation"
            if typ == "table_caption":
                # A numbered caption is not proof of ownership of a flattened table region.
                p["caption_attachment"] = {
                    "status": "unresolved_HOLD",
                    "target": None,
                    "reason": "independent_table_region_ownership_not_established",
                }
        routes.append(
            {
                "parent_id": p["id"],
                "original_container_kind": before,
                "effective_container_kind": p["kind"],
                "source_block_ids": ids,
                "component_types": types,
                "policy": "existing_hash_bound_reviewed_split"
                if reviewed
                else "typed_atomic_retention_only",
                "structural_reconstruction": "existing_C06_only" if reviewed else "not_performed",
                "specialized_reconstruction": "not_performed_HOLD",
                "eligibility": "HOLD",
            }
        )
    return result, routes
