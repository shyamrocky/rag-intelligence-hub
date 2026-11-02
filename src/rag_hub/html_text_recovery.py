"""Source-limited textual projections for the explicitly selected POC policy.

Evidence contribution only. Shared QA and make_decisions remain authoritative.
No browser execution, publisher-content repair, formula OCR or visual inference.
"""

import ast
import copy
import re

from rag_hub.acquire import digest
from rag_hub.html_acquire import encode
from rag_hub.html_context_remediation import (
    decorative,
    hidden_or_dynamic,
    inline_api_proof,
    safe_row,
    title_projection,
    walk,
)
from rag_hub.html_qualification import MATH_RE, binding
from rag_hub.html_validation import SourceIndex, canonical_text, furniture, lineage

VERSION = "html-usable-text-qualification-1.0"
STANDARD = "STANDARD_REFERENCE"
ILLUSTRATIVE = "ILLUSTRATIVE_REFERENCE"
CLASSES = {STANDARD, ILLUSTRATIVE, "HOLD", "EXCLUDED_NON_TEXT", "EXCLUDED_NON_KNOWLEDGE"}
TEXT_RESTRICTIONS = {
    "html_context_dependencies_hold",
    "embedded_visual_or_dynamic_content_unverified",
    "specialized_or_unclassified_content_requires_review",
    "hidden_or_alternative_content_unverified",
    "code_requires_external_bindings",
    "concealed_math_or_table",
    "unverified_table",
}
BASE_LIMITS = [
    "Quote only the admitted frozen source text and retain its attribution and required context.",
    "Do not infer missing visual, linked, dynamic or runtime content.",
    "Source fidelity is not independent verification of publisher claims or whole-source readiness.",
]


def locate(row, index):
    node = index.nodes.get(row["dom_path"])
    if node is not None:
        return node
    # Reuse the original independent verifier's synthetic inline-run convention.
    a, b = row["raw_char_span"]
    parent = index.nodes.get(row["dom_path"].rsplit("/inline-run[", 1)[0])
    if parent is None:
        raise ValueError("text_recovery_unresolved_source_node")
    return {
        "tag": "unknown",
        "path": row["dom_path"],
        "attrs": {},
        "start": a,
        "end": b,
        "parent": parent,
        "children": [n for n in parent["children"] if a <= n["start"] and n["end"] <= b],
    }


def source_span(node, index):
    a, b = node["start"], node["end"]
    return {
        "dom_path": node.get("path"),
        "raw_character_span": [a, b],
        "raw_fragment_sha256": digest(index.text[a:b].encode()),
    }


def simple_table(node, index):
    if node["tag"] != "table":
        raise ValueError("text_recovery_not_native_table")
    if any(
        n.get("tag") in {"math", "sub", "sup", "img", "svg", "iframe", "canvas"} for n in walk(node)
    ):
        raise ValueError("text_recovery_non_text_table_cell")
    rows = []
    for tr in (n for n in walk(node) if n.get("tag") == "tr"):
        cells = [n for n in tr["children"] if n.get("tag") in {"td", "th"}]
        if not cells or any(
            c["attrs"].get("rowspan", "1") != "1" or c["attrs"].get("colspan", "1") != "1"
            for c in cells
        ):
            raise ValueError("text_recovery_merged_or_missing_cells")
        rows.append(
            [
                {
                    **source_span(c, index),
                    "text": canonical_text(c, False),
                    "tag": c["tag"],
                }
                for c in cells
            ]
        )
    if (
        len(rows) < 2
        or not all(c["tag"] == "th" for c in rows[0])
        or any(len(row) != len(rows[0]) for row in rows)
        or any(c["tag"] != "td" for row in rows[1:] for c in row)
    ):
        raise ValueError("text_recovery_ambiguous_table_header_or_grid")
    return {
        "kind": "native_HTML_cell_text_only",
        "rows": rows,
        "headers": [c["text"] for c in rows[0]],
        "association_basis": "explicit source TR and TH/TD; no inferred or merged cells",
        "numeric_semantics_verified": False,
    }


def snapshot_context(row, index, node):
    declared = set(row["contexts"])
    witnesses = []
    for ancestor in lineage(node):
        a = ancestor.get("attrs", {})
        if not hidden_or_dynamic(ancestor):
            continue
        if ancestor.get("path") in declared and (
            a.get("role") == "tabpanel" or ancestor["tag"] == "details"
        ):
            witnesses.append({**source_span(ancestor, index), "tag": ancestor["tag"], "attrs": a})
        elif ancestor["tag"] == "summary" and any(
            p["tag"] == "details" and p["path"] in declared for p in lineage(ancestor)
        ):
            witnesses.append({**source_span(ancestor, index), "tag": "summary", "attrs": a})
        else:
            raise ValueError("text_recovery_hidden_content_outside_declared_snapshot_container")
    if not witnesses:
        raise ValueError("text_recovery_snapshot_container_missing")
    if row["classification"] == "code_block":
        if node["tag"] != "pre" or not node["attrs"].get("language"):
            raise ValueError("text_recovery_code_language_not_source_bound")
    elif node.get("attrs", {}).get("data-component-part") != "accordion-title":
        raise ValueError("text_recovery_non_payload_dynamic_element")
    return {
        "kind": "static_captured_payload_not_executed_UI",
        "containers": witnesses,
        "source_language": node["attrs"].get("language"),
        "selected_or_visible_variant_verified": False,
        "panel_control_label_association": "unverified; use only explicit PRE language, never guessed tab labels",
    }


def projection(row, document, index, mode):
    node = locate(row, index)
    text = row["section"]["text"]
    if not text.strip() or "\ufffd" in text or "\x00" in text:
        raise ValueError("text_recovery_empty_or_corrupt_text")
    result = {"kind": mode, "source": binding(row, document), "qualified_facets": ["text"]}
    if mode == "visible_text":
        safe_row(row, index)
    elif mode == "snapshot_payload":
        result["snapshot_evidence"] = snapshot_context(row, index, node)
        if row["classification"] == "code_block":
            original = next(
                r["block"]
                for r in document["parsed"]["records"]
                if r["block"]["block_id"] in row["section"]["block_ids"]
            )
            if original.get("language") != result["snapshot_evidence"]["source_language"]:
                raise ValueError("text_recovery_source_language_mismatch")
    elif mode == "caption_text":
        captions = [n for n in walk(node) if n.get("tag") == "figcaption"]
        if (
            node["tag"] != "figure"
            or len(captions) != 1
            or canonical_text(captions[0], False) != text
        ):
            raise ValueError("text_recovery_caption_does_not_equal_acquired_text")
        result["caption_binding"] = source_span(captions[0], index)
        if any(n.get("tag") in {"math", "sub", "sup", "svg", "img"} for n in walk(captions[0])):
            raise ValueError("text_recovery_non_text_caption")
        result["unqualified_facets"] = ["image_pixels", "diagram_contents", "graph_values"]
    elif mode == "native_table":
        result["table_text_structure"] = simple_table(node, index)
        result["unqualified_facets"] = ["independent_numerical_or_algorithmic_correctness"]
    elif mode == "native_list_notation":
        if node["tag"] not in {"ol", "ul"}:
            raise ValueError("text_recovery_expected_source_list")
        scripts = [n for n in walk(node) if n.get("tag") in {"sup", "sub", "math"}]
        if scripts and not all(
            n["tag"] == "sup"
            and re.fullmatch(r"\d+", canonical_text(n, False))
            and "caption" in n["attrs"].get("class", "").split()
            for n in scripts
        ):
            raise ValueError("text_recovery_unverified_mathematical_scripts")
        result["source_citation_markers"] = [
            {
                **source_span(n, index),
                "text": canonical_text(n, False),
                "target_content_verified": False,
            }
            for n in scripts
        ]
        if any(
            n.get("tag") in {"img", "figure", "table", "iframe", "video", "script", "canvas"}
            for n in walk(node)
        ):
            raise ValueError("text_recovery_non_text_list_content")
        if MATH_RE.search(text.replace("1/(rank + k)", " ")):
            raise ValueError("text_recovery_other_unqualified_formula")
        if "1/(rank + k)" in text:
            codes = [
                n
                for n in walk(node)
                if n.get("tag") == "code" and canonical_text(n, False) == "1/(rank + k)"
            ]
            if len(codes) != 1:
                raise ValueError("text_recovery_native_literal_formula_binding_missing")
            expression = ast.parse(canonical_text(codes[0], False), mode="eval")
            if ast.dump(expression) != ast.dump(ast.parse("1/(rank + k)", mode="eval")):
                raise ValueError("text_recovery_literal_expression_changed")
            result["native_literal_notation"] = {
                **source_span(codes[0], index),
                "text": "1/(rank + k)",
                "recognition_or_general_math_qualification": False,
            }
    elif mode == "source_card_summary":
        owners = [n for n in lineage(node) if "card" in n.get("attrs", {}).get("class", "").split()]
        if not owners:
            raise ValueError("text_recovery_card_ownership_missing")
        result["source_card_owner"] = source_span(owners[0], index)
        result["unqualified_facets"] = [
            "linked_guide_contents",
            "independent_product_claim_verification",
        ]
    elif mode == "source_unknown_text":
        if row["classification"] != "unknown" or canonical_text(node, False) != text:
            raise ValueError("text_recovery_unknown_text_mismatch")
        result["unqualified_facets"] = ["embedded_media_contents_or_transcript"]
    else:
        raise ValueError("text_recovery_unknown_projection_mode")

    # These are text projections; actual script/math/visual descendants can never
    # silently enter a plain-text or snapshot payload admission.
    def active_nodes(n):
        if furniture(n) and n.get("tag") != "svg":
            return
        yield n
        for child in n.get("children", []):
            yield from active_nodes(child)

    if mode not in {"caption_text", "native_table", "native_list_notation"} and any(
        n.get("tag")
        in {
            "script",
            "iframe",
            "video",
            "canvas",
            "math",
            "sub",
            "sup",
            "img",
            "figure",
            "table",
        }
        or n.get("tag") == "svg"
        and not decorative(n)
        for n in active_nodes(node)
    ):
        raise ValueError("text_recovery_unqualified_embedded_content")
    if mode != "snapshot_payload" and any(hidden_or_dynamic(n) for n in lineage(node)):
        raise ValueError("text_recovery_hidden_content_not_an_explicit_payload")
    return result


def reference(unit, classification, limitations, projections, source_issues):
    if classification not in {STANDARD, ILLUSTRATIVE}:
        raise ValueError("text_recovery_invalid_admitted_reference_class")
    value = copy.deepcopy(unit)
    value["predecessor_unit_sha256"] = value.pop("unit_sha256", None)
    value.update(
        reference_classification=classification,
        limitations=list(
            dict.fromkeys(
                value.get("limitations", [])
                + BASE_LIMITS
                + limitations
                + [issue["limitation"] for issue in source_issues]
            )
        ),
        textual_projections=projections,
        source_issues=source_issues,
        allowed_usage="source_attributed_reference"
        if classification == STANDARD
        else "limited_illustration_with_mandatory_warnings",
        forbidden_usage=[
            "infer_missing_content",
            "claim_unperformed_visual_or_runtime_verification",
        ],
    )
    if classification == ILLUSTRATIVE:
        value["forbidden_usage"] += [
            "treat_example_labels_as_ground_truth",
            "claim_example_is_executable_or_a_verified_numeric_result",
        ]
    value["unit_sha256"] = digest(encode(value))
    return value


def evaluate(document, baseline, overlay):
    """All source checks remain independent; only explicit, pinned scopes added."""
    doc = document["source"].doc_id
    index = SourceIndex(document["raw"].decode(document["acquisition"].get("charset", "utf-8")))
    rows = document["normalized"]["records"]
    lookup = {r["section"]["section_id"]: r for r in rows}
    positions = {r["section"]["section_id"]: i for i, r in enumerate(rows)}
    facts = {f["section_id"]: f for f in baseline["sections"]}
    if overlay["source_hashes"][doc] != document["source"].raw_sha256 or index.repairs:
        raise ValueError("text_recovery_source_identity_or_DOM_failure")
    if overlay["retained_unit_hashes"][doc] != {
        u["id"]: u["unit_sha256"] for u in baseline["units"]
    }:
        raise ValueError("text_recovery_previous_scope_changed")
    issues = overlay["source_issues"]

    def for_issues(ids):
        return [x for x in issues if set(x["section_ids"]) & set(ids)]

    units = []
    for unit in baseline["units"]:
        illustrative = any(
            lookup[s]["classification"] == "code_block" for s in unit["required_section_ids"]
        )
        source_issues = for_issues(unit["required_section_ids"])
        units.append(
            reference(
                unit,
                ILLUSTRATIVE if illustrative or source_issues else STANDARD,
                [x["limitation"] for x in source_issues]
                + (
                    ["Documentation example only; no source code was executed."]
                    if illustrative
                    else []
                ),
                [],
                source_issues,
            )
        )
    for spec in overlay["units"]:
        if spec["doc_id"] != doc:
            continue
        content, context = spec["content_section_ids"], spec["required_context_section_ids"]
        selected = list(dict.fromkeys(context + content))
        if (
            not content
            or len(content) != len(set(content))
            or content != sorted(content, key=positions.__getitem__)
        ):
            raise ValueError("text_recovery_duplicate_or_wrong_order")
        if spec["source_bindings"] != [binding(lookup[s], document) for s in selected]:
            raise ValueError("text_recovery_stale_binding")
        if any(
            any(c["outcome"] == "FAIL" for c in facts[s]["checks"]["checks"].values())
            for s in selected
        ):
            raise ValueError("text_recovery_cannot_waive_failed_source_check")
        projections = [
            projection(lookup[s], document, index, spec["projection_modes"][s]) for s in selected
        ]
        for s in selected:
            cleared = set(spec["restriction_resolutions"].get(s, []))
            if not cleared <= TEXT_RESTRICTIONS:
                raise ValueError("text_recovery_unrecognized_QA_restriction")
            mode = spec["projection_modes"][s]
            if "unverified_table" in cleared and mode != "native_table":
                raise ValueError("text_recovery_table_restriction_requires_verified_native_grid")
            if "hidden_or_alternative_content_unverified" in cleared and mode != "snapshot_payload":
                raise ValueError("text_recovery_cannot_claim_hidden_text_is_visible")
            if "concealed_math_or_table" in cleared and mode not in {
                "native_table",
                "native_list_notation",
            }:
                inline_api_proof(lookup[s], index)
            if "code_requires_external_bindings" in cleared and not (
                spec["reference_classification"] == ILLUSTRATIVE
                and lookup[s]["classification"] == "code_block"
            ):
                raise ValueError("text_recovery_external_bindings_require_illustrative_code_scope")
        titles = [title_projection(document, lookup[s], index) for s in spec["projected_title_ids"]]
        headings = {s for c in selected for s in facts[c]["heading_ids"]}
        if not headings <= set(selected) | set(spec["projected_title_ids"]):
            raise ValueError("text_recovery_heading_context_missing")
        if any(s in overlay["non_admitted"] for s in selected):
            raise ValueError("text_recovery_non_admitted_neighbor_cannot_leak")
        value = {
            "id": "html-text-unit:" + doc + ":" + digest(encode(spec))[:20],
            "doc_id": doc,
            "source": document["source"].model_dump(mode="json"),
            "heading_path": lookup[content[0]]["section"]["heading_path"],
            "required_section_ids": selected,
            "context_section_ids": context,
            "content_section_ids": content,
            "members": [binding(lookup[s], document) for s in selected],
            "text": "\n\n".join(lookup[s]["section"]["text"] for s in content),
            "heading_context": [binding(lookup[s], document) for s in context if s in headings],
            "required_parent_context": [
                binding(lookup[s], document) for s in context if s not in headings
            ],
            "source_context_projections": titles,
            "context_resolution": spec["context_resolution"],
            "restriction_resolutions": spec["restriction_resolutions"],
            "joiner": "\n\n",
            "consumption": "complete_unit_only",
            "source_interval": [
                lookup[content[0]]["raw_char_span"][0],
                lookup[content[-1]]["raw_char_span"][1],
            ],
            "evidence_role": "machine_source_verification_not_human_attestation",
        }
        value["text_sha256"] = digest(value["text"].encode())
        units.append(
            reference(
                value,
                spec["reference_classification"],
                spec["limitations"],
                projections,
                for_issues(selected),
            )
        )
        for s in selected:
            facts[s].update(disposition=None, reasons=[], human_review_material=False)
    for sid, excluded in overlay["non_admitted"].items():
        if sid not in facts:
            continue
        if excluded["classification"] not in CLASSES - {STANDARD, ILLUSTRATIVE}:
            raise ValueError("text_recovery_invalid_exclusion_class")
        if excluded["source_binding"] != binding(lookup[sid], document):
            raise ValueError("text_recovery_exclusion_evidence_changed")
        facts[sid].update(
            disposition=excluded["classification"],
            reasons=[excluded["reason"]],
            reference_classification=excluded["classification"],
            recovery_evidence=excluded,
            human_review_material=False,
        )
    return {"version": VERSION, "sections": list(facts.values()), "units": units}
