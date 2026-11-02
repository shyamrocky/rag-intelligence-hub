"""Bounded source-bound context overlays; evidence only, never QA decisions.

Original observations and the earlier admission scopes remain immutable. This
module checks explicit source relationships, not publisher truth or CSS rendering.
"""

import ast
import re

from rag_hub.acquire import digest
from rag_hub.html_acquire import encode
from rag_hub.html_qualification import LIMITATIONS, MATH_RE, SUPPORTED, binding
from rag_hub.html_validation import SourceIndex, canonical_text, furniture, lineage

VERSION = "html-source-context-remediation-1.0"


def walk(node):
    yield node
    for child in node.get("children", []):
        yield from walk(child)


def hidden_or_dynamic(node):
    a = node.get("attrs", {})
    return (
        node.get("tag") in {"details", "summary", "iframe", "video", "canvas"}
        or a.get("role") in {"tabpanel", "tablist", "tab"}
        or a.get("aria-hidden") == "true"
        or "hidden" in a
        or "aria-controls" in a
        or "data-state" in a
        or bool(re.search(r"display\s*:\s*none|visibility\s*:\s*hidden", a.get("style", "")))
    )


def decorative(node):
    """Narrow source evidence for icons, not the legacy blanket SVG exclusion."""
    if node.get("tag") != "svg":
        return False
    a = node.get("attrs", {})
    classes = set(a.get("class", "").split())
    return (
        not canonical_text(node, False)
        and not any(x.get("tag") in {"text", "image", "foreignobject"} for x in walk(node))
        and (
            a.get("aria-hidden") == "true"
            and (
                any("icon" in k for k in classes)
                or any(
                    p.get("attrs", {}).get("data-component-part") == "callout-icon"
                    for p in lineage(node)
                )
            )
            or "gb-icon" in classes
            and "size-3" in classes
            and any(p.get("tag") == "a" and p["attrs"].get("href") for p in lineage(node))
        )
    )


def safe_row(row, index):
    """Strict source guard shared by all bounded overlays and negative controls."""
    if row["classification"] not in SUPPORTED:
        raise ValueError("HTML_overlay_unsupported_member")
    node = index.nodes[row["dom_path"]]
    if any(hidden_or_dynamic(n) for n in lineage(node)):
        raise ValueError("HTML_overlay_hidden_or_dynamic_member")
    permitted = {"source_heading_level_gap", "embedded_visual_or_dynamic_content_unverified"}
    if set(row["section"]["issues"]) - permitted:
        raise ValueError("HTML_overlay_unresolved_original_issue")

    def visit(n):
        if n.get("tag") == "svg":
            if not decorative(n):
                raise ValueError("HTML_overlay_non_decorative_visual")
            return
        if furniture(n):
            # Controls remain explicitly excluded by the original source tree.
            return
        if hidden_or_dynamic(n):
            raise ValueError("HTML_overlay_hidden_or_dynamic_descendant")
        if n.get("tag") in {"math", "sub", "sup", "img", "table", "figure"} or re.search(
            r"katex|mathjax|equation", n.get("attrs", {}).get("class", ""), re.IGNORECASE
        ):
            raise ValueError("HTML_overlay_specialized_member")
        for child in n.get("children", []):
            visit(child)

    visit(node)
    if MATH_RE.search(row["section"]["text"]):
        raise ValueError("HTML_overlay_formula_like_text")
    return node


def inline_api_proof(row, index):
    """Discharge legacy regex only when every matched marker is inline CODE."""
    node = safe_row(row, index)
    original = row["section"]["text"]
    codes = [canonical_text(n, False) for n in walk(node) if n.get("tag") == "code"]
    residual = original
    recognized = []
    for value in codes:
        api = bool(re.fullmatch(r"\$[a-z_][a-z_0-9]*", value))
        try:
            tree = ast.parse(value, mode="eval").body
            api |= (
                isinstance(tree, ast.Call)
                and isinstance(tree.func, ast.Attribute)
                and all(isinstance(a, (ast.Name, ast.Constant)) for a in tree.args)
                and all(isinstance(k.value, (ast.Name, ast.Constant)) for k in tree.keywords)
            )
        except (SyntaxError, ValueError):
            pass
        if api:
            residual = residual.replace(value, " ")
            recognized.append(value)
    expression = re.compile(
        r"[∑∏∫∩≤≥]|\$[^$]+\$|\\(?:frac|sum|begin)\b|\|\s*:?-{3,}"
        r"|\b[A-Za-z]\w*(?:\([^)]*\))?\s*[=≈]\s*\S|\b\d+(?:\.\d+)?\s*(?:±|\|)\s*\d"
    )
    if not recognized or not expression.search(original) or expression.search(residual):
        raise ValueError("HTML_overlay_math_restriction_not_proven_API_syntax")
    return {"kind": "inline_code_not_mathematics", "source_code_values": recognized}


def title_projection(document, row, index):
    """Hidden title is metadata only; never a member or visible-heading claim."""
    node = index.nodes[row["dom_path"]]
    titles = [n for n in index.nodes.values() if n.get("tag") == "h1"]
    articles = [n for n in lineage(node) if n.get("tag") == "article"]
    body = index.nodes[document["parsed"]["body_dom_path"]]
    if (
        len(titles) != 1
        or node is not titles[0]
        or len(articles) != 1
        or articles[0] not in list(lineage(body))
        or canonical_text(node, False) != row["section"]["text"]
        or not any(hidden_or_dynamic(n) for n in lineage(node))
        or any(hidden_or_dynamic(n) for n in lineage(body))
    ):
        raise ValueError("HTML_title_projection_not_source_bound")
    return {
        "kind": "captured_document_title_projection",
        "binding": binding(row, document),
        "source_visibility": "hidden_in_capture",
        "role": "context_metadata_only_not_admitted_Section",
        "article_dom_path": articles[0]["path"],
        "article_body_dom_path": body["path"],
        "visibility_claim": False,
        "note": "The unique captured article H1 supplies title identity, not visible source prose.",
    }


def static_context(row, selected, document, index):
    evidence = []
    for path in row["contexts"]:
        container = index.nodes[path]
        a = container["attrs"]
        if not (
            a.get("role") == "note"
            or container["tag"] == "aside"
            and a.get("aria-label") in {"Tip", "Note", "Warning", "Information"}
            or set(a.get("class", "").split()) & {"NOTE", "TIP", "WARNING", "IMPORTANT"}
        ) or any(hidden_or_dynamic(n) for n in lineage(container)):
            raise ValueError("HTML_overlay_container_not_static_note")
        contained = [
            r
            for r in document["normalized"]["records"]
            if container["start"] <= r["raw_char_span"][0]
            and r["raw_char_span"][1] <= container["end"]
        ]
        labels = []
        for r in contained:
            if r["section"]["section_id"] in selected:
                continue
            n = index.nodes[r["dom_path"]]
            if not (
                n["attrs"].get("aria-hidden") == "true"
                and canonical_text(n, False) == a.get("aria-label")
            ):
                raise ValueError("HTML_overlay_incomplete_static_container")
            labels.append(binding(r, document))
        evidence.append(
            {
                "kind": "static_note_ownership",
                "dom_path": path,
                "raw_character_span": [container["start"], container["end"]],
                "raw_fragment_sha256": digest(
                    index.text[container["start"] : container["end"]].encode()
                ),
                "source_label": a.get("aria-label") or a.get("class"),
                "excluded_presentation_labels": labels,
            }
        )
    return evidence


def evaluate(document, baseline, overlay):
    """Validate pinned additive relationships; shared QA remains the only owner."""
    doc_id = document["source"].doc_id
    rows = document["normalized"]["records"]
    lookup = {r["section"]["section_id"]: r for r in rows}
    positions = {r["section"]["section_id"]: i for i, r in enumerate(rows)}
    index = SourceIndex(document["raw"].decode(document["acquisition"].get("charset", "utf-8")))
    if overlay["source_hashes"][doc_id] != document["source"].raw_sha256:
        raise ValueError("HTML_overlay_source_snapshot_mismatch")
    facts = {r["section_id"]: r for r in baseline["sections"]}
    originals = {u["id"]: u for u in baseline["units"]}
    retained = overlay["retained_units"][doc_id]
    if any(originals.get(u["id"]) != u for u in retained):
        raise ValueError("HTML_overlay_prior_unit_changed")
    units = list(retained)
    unsupported = set(overlay["unsupported_section_ids"])
    for spec in overlay["units"]:
        if spec["doc_id"] != doc_id:
            continue
        content = spec["content_section_ids"]
        context = spec["required_context_section_ids"]
        all_ids = list(dict.fromkeys(context + content))
        if len(content) != len(set(content)) or not content or set(all_ids) & unsupported:
            raise ValueError("HTML_overlay_duplicate_or_unsupported_scope")
        if content != sorted(content, key=positions.__getitem__):
            raise ValueError("HTML_overlay_wrong_content_order")
        if spec["source_bindings"] != [binding(lookup[s], document) for s in all_ids]:
            raise ValueError("HTML_overlay_stale_or_wrong_source_binding")
        for s in all_ids:
            safe_row(lookup[s], index)
            if any(v["outcome"] == "FAIL" for v in facts[s]["checks"]["checks"].values()):
                raise ValueError("HTML_overlay_cannot_override_failed_source_check")
        projections = []
        projected_ids = set()
        for s in spec["projected_title_ids"]:
            if s not in unsupported:
                raise ValueError("HTML_overlay_projection_must_not_admit_hidden_title")
            projections.append(title_projection(document, lookup[s], index))
            projected_ids.add(s)
        heading_ids = list(dict.fromkeys(s for c in content for s in facts[c]["heading_ids"]))
        if not set(heading_ids) <= set(context) | projected_ids:
            raise ValueError("HTML_overlay_missing_required_heading_context")
        evidence = []
        for s in all_ids:
            evidence.extend(static_context(lookup[s], set(all_ids), document, index))
        # Source gaps are permitted only for exact printed code-language labels.
        gaps = [
            rows[i]
            for i in range(positions[content[0]], positions[content[-1]] + 1)
            if rows[i]["section"]["section_id"] not in all_ids
        ]
        if spec["gap_section_ids"] != [r["section"]["section_id"] for r in gaps]:
            raise ValueError("HTML_overlay_unaccounted_internal_gap")
        for gap in gaps:
            matches = [
                n for n in index.nodes.values() if [n["start"], n["end"]] == gap["raw_char_span"]
            ]
            node = matches[0] if len(matches) == 1 else {}
            following = rows[positions[gap["section"]["section_id"]] + 1]
            code_node = index.nodes.get(following["dom_path"])
            if not (
                gap["classification"] == "unknown"
                and node.get("tag") == "span"
                and node["attrs"].get("title") == "JSON"
                and canonical_text(node, False) == "JSON"
                and not any(hidden_or_dynamic(n) for n in lineage(node))
                and following["section"]["section_id"] in content
                and following["classification"] == "code_block"
                and code_node is not None
                and any(
                    n.get("attrs", {}).get("data-component-part") == "code-block-root"
                    for n in lineage(code_node)
                )
                and any(
                    "code-block" in n.get("attrs", {}).get("class", "").split()
                    and n in list(lineage(code_node))
                    for n in lineage(node)
                )
            ):
                raise ValueError("HTML_overlay_gap_not_presentation_label")
            evidence.append(
                {"kind": "excluded_code_presentation_label", "binding": binding(gap, document)}
            )
        resolutions = {}
        for s in all_ids:
            row = lookup[s]
            reasons = []
            if row["contexts"]:
                reasons.append("html_context_dependencies_hold")
            if "embedded_visual_or_dynamic_content_unverified" in row["section"]["issues"]:
                # safe_row has proven only decorative source icons, never substantive visuals.
                reasons.append("embedded_visual_or_dynamic_content_unverified")
            if s in spec["inline_api_section_ids"]:
                evidence.append({"section_id": s, **inline_api_proof(row, index)})
                reasons.append("concealed_math_or_table")
            resolutions[s] = reasons
        value = {
            "id": "html-context-unit:" + doc_id + ":" + digest(encode(spec))[:20],
            "doc_id": doc_id,
            "source": document["source"].model_dump(mode="json"),
            "heading_path": lookup[content[0]]["section"]["heading_path"],
            "required_section_ids": all_ids,
            "context_section_ids": context,
            "content_section_ids": content,
            "members": [binding(lookup[s], document) for s in all_ids],
            "text": "\n\n".join(lookup[s]["section"]["text"] for s in content),
            "heading_context": [binding(lookup[s], document) for s in context if s in heading_ids],
            "required_parent_context": [
                binding(lookup[s], document) for s in context if s not in heading_ids
            ],
            "source_context_projections": projections,
            "relationship_evidence": evidence,
            "context_resolution": spec["context_resolution"],
            "evidence_role": "machine_verified_source_bindings_not_human_attestation",
            "restriction_resolutions": resolutions,
            "joiner": "\n\n",
            "consumption": "complete_unit_only",
            "limitations": LIMITATIONS,
            "source_interval": [
                lookup[content[0]]["raw_char_span"][0],
                lookup[content[-1]]["raw_char_span"][1],
            ],
        }
        value["text_sha256"] = digest(value["text"].encode())
        value["unit_sha256"] = digest(encode(value))
        units.append(value)
        for s in all_ids:
            facts[s].update(disposition=None, reasons=[], human_review_material=False)
    for s, reason in overlay["hold_reasons"].items():
        if s in facts and s not in unsupported:
            facts[s].update(
                disposition=reason["disposition"],
                reasons=reason["reasons"],
                human_review_material=reason["human_review_material"],
            )
    return {"version": VERSION, "sections": list(facts.values()), "units": units}
