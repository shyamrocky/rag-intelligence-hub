"""Objective frozen-HTML qualification evidence, consolidated only by shared QA.

This does not certify publisher claims, CSS appearance, code execution or visual
semantics. It preserves whole source-defined text groups and blocks unresolved
cross-group, mathematical, visual, hidden and interactive dependencies.
"""

import ast
import builtins
import importlib.metadata
import json
import re
from pathlib import Path

from rag_hub.acquire import digest, local_path
from rag_hub.html_acquire import encode
from rag_hub.html_admission_models import ScopedHtmlDecision
from rag_hub.html_validation import (
    SourceIndex,
    check_document,
    furniture,
    lineage,
    load_documents,
)
from rag_hub.validation_sampling import fingerprint

VERSION = "html-objective-qualification-1.0"
RELEASE_VERSION = "combined-html-auto-qa-1.0"
REMEDIATED_RELEASE_VERSION = "combined-html-context-qa-1.0"
TEXT_RELEASE_VERSION = "combined-html-text-qa-1.0"
C10_RELEASE_VERSION = "combined-c10-html-qa-1.0"
TEXT_COMPONENTS = {
    "src/rag_hub/html_text_recovery.py",
    "config/html-text-qualification-policy.json",
    "data/normalized/html/text-recovery-v1/overlays.json",
}
TEXT_COMPATIBILITY_RELEASE = "config/html-text-qa-successor.json"
REMEDIATED_COMPONENTS = {
    "src/rag_hub/html_context_remediation.py",
    "config/html-context-qualification-policy.json",
    "data/normalized/html/context-remediation-v1/overlays.json",
}
COMPATIBILITY_RELEASE = "config/html-context-qa-successor.json"
MARKDOWN_COMPATIBILITY_RELEASE = "config/markdown-integrated-qa-successor-v1-1.json"
MARKDOWN_COMPATIBILITY_CHANGES = {
    "src/rag_hub/shared/qa.py",
    "src/rag_hub/validation_reviews.py",
    "src/rag_hub/html_qualification.py",
    "src/rag_hub/pdf_publication.py",
    "src/rag_hub/html_handoff.py",
}
COMPATIBILITY_CHANGES = {
    "src/rag_hub/html_qualification.py",
    "src/rag_hub/pdf_publication.py",
}
EXTRA_COMPONENTS = (
    "src/rag_hub/html_admission_models.py",
    "src/rag_hub/html_qualification.py",
    "src/rag_hub/html_qa_execution.py",
    "src/rag_hub/html_handoff.py",
    "src/rag_hub/pdf_publication.py",
    "src/rag_hub/ui.py",
    "config/html-qualification-policy.json",
)
SUPPORTED = {"heading", "paragraph", "unordered_list", "ordered_list", "code_block"}
LIMITATIONS = [
    "Frozen textual source scope only; CSS appearance and dynamic state not certified.",
    "Publisher claims and example code are attributed source content, not independently validated facts or executed code.",
    "No whole-source readiness or qualification of excluded neighboring content.",
]
CONTEXT_RE = re.compile(
    r"\b(?:above|below|following|preceding|previous|this (?:figure|diagram|table|example)|"
    r"these results|as shown|in this example|set above|all the above)\b",
    re.IGNORECASE,
)
MATH_RE = re.compile(r"\\(?:frac|sum|prod|begin|\(|\[)|\$\$|\b\d+\s*/\s*\(?[a-z]|[∑∏∫∩≤≥]")


def verify_release(root, path, expected):
    from rag_hub.pdf_prose_review import COMBINED_RELEASE_COMPONENTS

    raw = local_path(root, path).read_bytes()
    value = json.loads(raw)
    if value.get("version") == C10_RELEASE_VERSION:
        from rag_hub.markdown_qualification import verify_release as verify_integrated

        return verify_integrated(root, path, expected)
    if (
        not expected
        or digest(raw) != expected
        or value.get("version")
        not in {RELEASE_VERSION, REMEDIATED_RELEASE_VERSION, TEXT_RELEASE_VERSION}
        or set(value.get("files", {}))
        != (
            set(COMBINED_RELEASE_COMPONENTS)
            | set(EXTRA_COMPONENTS)
            | (
                REMEDIATED_COMPONENTS
                if value.get("version")
                in {REMEDIATED_RELEASE_VERSION, TEXT_RELEASE_VERSION, C10_RELEASE_VERSION}
                else set()
            )
            | (TEXT_COMPONENTS if value.get("version") == TEXT_RELEASE_VERSION else set())
        )
        or Path(__file__).resolve() != Path(root).resolve() / "src/rag_hub/html_qualification.py"
    ):
        raise ValueError("unselected_or_invalid_HTML_QA_release")
    changed = {
        name
        for name, sha in value["files"].items()
        if digest(local_path(root, name).read_bytes()) != sha
    }
    integration_name = (
        "config/c10-qa-successor.json"
        if local_path(root, "config/c10-qa-successor.json").exists()
        else MARKDOWN_COMPATIBILITY_RELEASE
    )
    integration_path = local_path(root, integration_name)
    if changed and integration_path.exists():
        from rag_hub.markdown_qualification import verify_release as verify_markdown_release

        successor = verify_markdown_release(
            root, integration_name, digest(integration_path.read_bytes())
        )
        if (
            successor.get("version") not in {"combined-markdown-qa-1.1", C10_RELEASE_VERSION}
            or successor.get("compatible_html_releases", {}).get(str(path)) != expected
            or not changed <= MARKDOWN_COMPATIBILITY_CHANGES
            or any(name not in successor["files"] for name in value["files"])
        ):
            raise ValueError("HTML_QA_unapproved_Markdown_compatibility")
    elif changed:
        # The immutable predecessor may still be read/replayed under an explicitly
        # installed successor. Its original identity, policy and scopes do not change.
        compatible_path = (
            TEXT_COMPATIBILITY_RELEASE
            if local_path(root, TEXT_COMPATIBILITY_RELEASE).exists()
            else COMPATIBILITY_RELEASE
        )
        successor_path = local_path(root, compatible_path)
        if (
            value.get("version") not in {RELEASE_VERSION, REMEDIATED_RELEASE_VERSION}
            or not changed <= COMPATIBILITY_CHANGES
            or not successor_path.exists()
        ):
            raise ValueError("HTML_QA_fingerprint_mismatch: " + ",".join(sorted(changed)))
        successor_bytes = successor_path.read_bytes()
        successor = verify_release(root, compatible_path, digest(successor_bytes))
        if successor.get(
            "compatible_predecessor_sha256"
        ) != expected and expected not in successor.get("compatible_predecessors", []):
            raise ValueError("HTML_QA_unapproved_predecessor_compatibility")
    if value["dependencies"] != {
        k: importlib.metadata.version(k) for k in ("pydantic", "pymupdf", "markdown-it-py")
    }:
        raise ValueError("HTML_QA_dependency_mismatch")
    return value


def binding(row, document):
    s = row["section"]
    charset = document["acquisition"].get("charset", "utf-8")
    text = document["raw"].decode(charset)
    a, b = row["raw_char_span"]
    return {
        "section_id": s["section_id"],
        "section_sha256": digest(encode(s)),
        "normalized_sha256": s["normalized_sha256"],
        "text": s["text"],
        "classification": row["classification"],
        "dom_path": row["dom_path"],
        "raw_character_span": [a, b],
        "offset_unit": "unicode_codepoints",
        "raw_byte_span": [len(text[:a].encode(charset)), len(text[:b].encode(charset))],
        "raw_fragment_sha256": row["raw_fragment_sha256"],
        "source_tree": row["source_tree"],
        "citation_locators": s["locators"],
    }


def evaluate(document):
    """Evidence supplier, not an eligibility engine. Every input gets one disposition."""
    checks = check_document(document)
    rows = document["normalized"]["records"]
    text = document["raw"].decode(document["acquisition"].get("charset", "utf-8"))
    index = SourceIndex(text)
    facts, headings, path = {}, [], []
    for row in rows:
        s, kind = row["section"], row["classification"]
        sid = s["section_id"]
        c = checks[sid]
        node = index.nodes.get(row["dom_path"])
        bad = {k: v["outcome"] for k, v in c["checks"].items() if v["outcome"] in {"FAIL", "HOLD"}}
        reason, disposition = [], None
        if "FAIL" in bad.values():
            disposition, reason = (
                "Confirmed parsing defect",
                [k for k, v in bad.items() if v == "FAIL"],
            )
        elif kind not in SUPPORTED:
            disposition, reason = "Unsupported content", ["unsupported_type:" + kind]
        elif node is None or index.repairs or document["parsed"]["dom_repairs"]:
            disposition, reason = "Evidence gap", ["unresolved_DOM_repairs_or_locator"]
        else:
            chain = list(lineage(node))

            def active_nodes(n):
                if furniture(n):
                    return
                yield n
                for child in n.get("children", []):
                    yield from active_nodes(child)

            descendants = list(active_nodes(node))
            attrs = [n.get("attrs", {}) for n in chain + descendants]
            dynamic = any(
                a.get("role") in {"tabpanel", "tablist", "tab"}
                or a.get("aria-hidden") == "true"
                or "hidden" in a
                or "aria-controls" in a
                or "data-state" in a
                or re.search(r"display\s*:\s*none|visibility\s*:\s*hidden", a.get("style", ""))
                for a in attrs
            ) or any(
                n.get("tag") in {"details", "summary", "iframe", "video", "canvas"}
                for n in chain + descendants
            )
            specialized = any(
                n.get("tag") in {"math", "sub", "sup", "img", "svg", "table", "figure"}
                or re.search(
                    r"(?:katex|mathjax|equation)",
                    n.get("attrs", {}).get("class", ""),
                    re.IGNORECASE,
                )
                for n in descendants
            ) or (kind != "code_block" and bool(MATH_RE.search(s["text"])))
            issues = set(s["issues"]) - {"source_heading_level_gap"}
            card = any(
                "card" in a.get("class", "").split()
                and "cursor-pointer" in a.get("class", "").split()
                for a in attrs
            )
            if card:
                disposition, reason = "Unsupported content", ["website_navigation_card"]
            elif dynamic or specialized:
                disposition, reason = (
                    "Unsupported content",
                    ["dynamic_hidden_or_specialized_dependency"],
                )
            elif row["contexts"]:
                disposition, reason = (
                    "Context dependency",
                    ["static_container_semantics_require_scoped_review"],
                )
            elif issues:
                disposition, reason = "Evidence gap", sorted(issues)
            elif set(bad) - {"heading_hierarchy", "hidden_dynamic_visual_restrictions"}:
                disposition, reason = "Evidence gap", sorted(bad)
            elif (
                any(
                    v["outcome"] == "HOLD"
                    for k, v in c["checks"].items()
                    if k == "hidden_dynamic_visual_restrictions"
                )
                and "source_heading_level_gap" not in s["issues"]
            ):
                disposition, reason = "Evidence gap", ["unresolved_hidden_or_type_hazard"]
        if kind == "heading" and node is not None:
            level = int(node["tag"][1])
            headings = [(n, r) for n, r in headings if n < level] + [(level, row)]
            path = [r["section"]["text"] for _, r in headings]
        # Resolve source-level heading gaps by exact observed levels, without inventing headings.
        heading_rows = [r for _, r in headings]
        if not disposition and (not heading_rows or path != s["heading_path"]):
            disposition, reason = "Evidence gap", ["unresolved_source_heading_projection"]
        if any(
            r["section"]["section_id"] in facts and facts[r["section"]["section_id"]]["disposition"]
            for r in heading_rows[:-1]
            if kind == "heading"
        ):
            disposition, reason = "Context dependency", ["unqualified_heading_ancestor"]
        facts[sid] = {
            "section_id": sid,
            "doc_id": s["doc_id"],
            "content_type": kind,
            "source_location": binding(row, document),
            "checks": c,
            "disposition": disposition,
            "reasons": reason,
            "heading_ids": [r["section"]["section_id"] for r in heading_rows],
            "human_review_material": disposition in {"Context dependency", "Evidence gap"},
        }

    # Source-defined section runs; never use token budgets or semantic rewriting.
    groups, active = [], []

    def flush():
        nonlocal active
        if active:
            groups.append(active)
            active = []

    for i, row in enumerate(rows):
        sid = row["section"]["section_id"]
        if row["classification"] == "heading" or facts[sid]["disposition"]:
            flush()
        if row["classification"] != "heading" and not facts[sid]["disposition"]:
            active.append(i)
    flush()
    units = []
    for positions in groups:
        members = [rows[i] for i in positions]
        first, last = positions[0], positions[-1]
        content = "\n\n".join(r["section"]["text"] for r in members)
        inherited_context = []
        reasons = []
        # Interrupted source sections cannot silently omit a dependency. Require
        # owner judgment when an excluded element occurs within this heading scope.
        same_heading = members[0]["section"]["heading_path"]
        peers = [
            r
            for r in rows
            if r["section"]["heading_path"] == same_heading and r["classification"] != "heading"
        ]
        blocked_peers = [r for r in peers if facts[r["section"]["section_id"]]["disposition"]]
        if blocked_peers and (
            CONTEXT_RE.search(content)
            or any(r["classification"] == "code_block" for r in members)
            or members[-1]["section"]["text"].rstrip().endswith(":")
        ):
            reasons.append("required_context_crosses_excluded_source_element")
        if members[-1]["section"]["text"].rstrip().endswith(":"):
            reasons.append("incomplete_lead_in_without_verified_following_content")
        back_reference = re.search(
            r"\b(?:above|previous|preceding|earlier|all the above)\b", content, re.IGNORECASE
        )
        resolved_local_code_reference = (
            back_reference
            and re.search(r"parameters set above", content, re.IGNORECASE)
            and any(r["classification"] == "code_block" for r in members)
            and not blocked_peers
        )
        if back_reference and not resolved_local_code_reference:
            reasons.append("cross_section_back_reference_not_objectively_resolved")
        if any(
            r["classification"] == "code_block"
            and re.search(
                r"(?:existing args|defined above|previous example)",
                r["section"]["text"],
                re.IGNORECASE,
            )
            for r in members
        ):
            ancestors = [
                u
                for u in units
                if len(u["heading_path"]) < len(same_heading)
                and same_heading[: len(u["heading_path"])] == u["heading_path"]
            ]
            if ancestors and not blocked_peers:
                inherited_context = list(
                    dict.fromkeys(s for u in ancestors for s in u["required_section_ids"])
                )
            else:
                reasons.append("code_requires_external_example_context")
        if members[-1]["classification"] == "paragraph" and not re.search(
            r"[.!?。！？][\"'’”)]*$", members[-1]["section"]["text"].strip()
        ):
            reasons.append("terminal_prose_fragment_requires_context")
        if (
            not any(r["classification"] == "paragraph" for r in members)
            and first > 0
            and rows[first - 1]["classification"] != "heading"
        ):
            reasons.append("list_or_code_introductory_context_unresolved")
        # Link-only discovery lists and website conversion prompts are not answer evidence.
        discovery = same_heading and re.search(
            r"^(?:related (?:content|resources)|see also|next steps|resources)$",
            same_heading[-1],
            re.IGNORECASE,
        )
        if discovery or all(
            re.search(
                r"^(?:want to get started|create a free|learn more:?$|view an example)",
                r["section"]["text"],
                re.IGNORECASE,
            )
            for r in members
        ):
            for r in members:
                facts[r["section"]["section_id"]].update(
                    disposition="Unsupported content",
                    reasons=["navigation_discovery_or_conversion_content"],
                    human_review_material=False,
                )
            continue
        if reasons:
            for r in members:
                facts[r["section"]["section_id"]].update(
                    disposition="Context dependency", reasons=reasons, human_review_material=True
                )
            continue
        heading_ids = facts[members[0]["section"]["section_id"]]["heading_ids"]
        if any(facts[i]["disposition"] for i in heading_ids):
            for r in members:
                facts[r["section"]["section_id"]].update(
                    disposition="Context dependency",
                    reasons=["heading_dependency_not_qualified"],
                    human_review_material=True,
                )
            continue
        selected = list(
            dict.fromkeys(
                inherited_context + heading_ids + [r["section"]["section_id"] for r in members]
            )
        )
        lookup = {r["section"]["section_id"]: r for r in rows}
        source = document["source"]
        value = {
            "id": "html-unit:" + source.doc_id + ":" + digest(encode(selected))[:20],
            "doc_id": source.doc_id,
            "source": source.model_dump(mode="json"),
            "heading_path": same_heading,
            "required_section_ids": selected,
            "context_section_ids": heading_ids,
            "content_section_ids": [r["section"]["section_id"] for r in members],
            "members": [binding(lookup[s], document) for s in selected],
            "text": content,
            "text_sha256": digest(content.encode()),
            "heading_context": [binding(lookup[s], document) for s in heading_ids],
            "required_parent_context": [
                binding(lookup[s], document) for s in inherited_context if s not in heading_ids
            ],
            "joiner": "\n\n",
            "consumption": "complete_unit_only",
            "limitations": LIMITATIONS,
            "source_interval": [rows[first]["raw_char_span"][0], rows[last]["raw_char_span"][1]],
        }
        value["unit_sha256"] = digest(encode(value))
        units.append(value)
    admitted = {i for u in units for i in u["required_section_ids"]}
    for row in rows:
        sid = row["section"]["section_id"]
        if sid not in admitted and not facts[sid]["disposition"]:
            facts[sid].update(
                disposition="Context dependency",
                reasons=["heading_context_has_no_qualified_content_unit"],
                human_review_material=False,
            )
    return {"version": VERSION, "sections": list(facts.values()), "units": units}


# Only these legacy restrictions may be discharged by exact, complete HTML proof.
# Unknown/new reasons and all integrity failures remain blocking.
RESOLVABLE = {
    "html_independent_source_review_required",
    "html_source_qualification_pending",
    "registered_source_fidelity_manual_required",
    "incomplete_or_list_context",
    "sentence_fragment",
    "unresolved_context_reference",
    "source_heading_level_gap",
    "html_heading_hierarchy_hold",
    "html_hidden_dynamic_visual_restrictions_hold",
    "heading_only_requires_body_context",
    "code_output_or_unsupported_language",
}


def unresolved_reasons(result, unit):
    remaining = (
        set(result.reasons)
        - RESOLVABLE
        - set(unit.get("restriction_resolutions", {}).get(result.section_id, []))
    )
    if "code_requires_external_bindings" in remaining:
        payloads = []
        for member in unit["members"]:
            if member["classification"] == "code_block" and member["text"].startswith(
                "```python\n"
            ):
                payloads.append(member["text"].split("\n", 1)[1].rsplit("\n", 1)[0])
        try:
            tree = ast.parse("\n".join(payloads))
            bound = {
                n.id
                for n in ast.walk(tree)
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
            }
            bound |= {n.arg for n in ast.walk(tree) if isinstance(n, ast.arg)}
            bound |= {
                a.asname or a.name.split(".")[0]
                for n in ast.walk(tree)
                if isinstance(n, (ast.Import, ast.ImportFrom))
                for a in n.names
            }
            bound |= {
                n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))
            }
            loaded = {
                n.id
                for n in ast.walk(tree)
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
            }
            if payloads and not loaded - bound - set(dir(builtins)):
                remaining.remove("code_requires_external_bindings")
        except (SyntaxError, ValueError):
            pass
    return remaining


def evidence_proofs(
    root,
    source,
    data,
    blocks,
    sections,
    audit,
    results,
    *,
    release_path,
    expected_release_sha256,
    authorization_path,
    authorization_sha256,
):
    release = verify_release(root, release_path, expected_release_sha256)
    auth_bytes = local_path(root, authorization_path).read_bytes()
    auth = json.loads(auth_bytes)
    policy_path = release.get("qualification_policy_path", "config/html-qualification-policy.json")
    policy = json.loads(local_path(root, policy_path).read_bytes())
    for path, sha in policy.get("frozen_evidence", {}).items():
        if digest(local_path(root, path).read_bytes()) != sha:
            raise ValueError("HTML_prior_evidence_or_decisions_changed")
    if (
        digest(auth_bytes) != authorization_sha256
        or auth.get("decision") != "AUTHORIZE_AUTOMATED_HTML_QUALIFICATION"
        or auth.get("policy_sha256") != release["files"][policy_path]
        or auth.get("qa_release_sha256") != expected_release_sha256
        or source.doc_id not in policy["source_ids"]
        or source.source_format != "html"
        or policy.get("version") != release.get("qualification_policy_version", VERSION)
        or policy.get("corpus_manifest_sha256") != auth.get("corpus_manifest_sha256")
    ):
        raise ValueError("HTML_admission_authorization_or_policy_mismatch")
    document = load_documents(root)[source.doc_id]
    if (
        document["manifest_sha256"] != auth["corpus_manifest_sha256"]
        or source != document["source"]
        or data != document["raw"]
        or [b.model_dump(mode="json") for b in blocks]
        != [r["block"] for r in document["parsed"]["records"]]
        or [s.model_dump(mode="json") for s in sections]
        != [r["section"] for r in document["normalized"]["records"]]
        or audit != document["normalized"]["audit"]
    ):
        raise ValueError("HTML_admission_current_inputs_not_frozen_corpus")
    evaluation = evaluate(document)
    evidence_version = VERSION
    if release["version"] in {
        REMEDIATED_RELEASE_VERSION,
        TEXT_RELEASE_VERSION,
        C10_RELEASE_VERSION,
    }:
        from rag_hub.html_context_remediation import evaluate as apply_context_overlay

        overlay_path = policy["context_overlay_path"]
        if overlay_path not in release["files"]:
            raise ValueError("HTML_context_overlay_not_fingerprinted")
        overlay = json.loads(local_path(root, overlay_path).read_bytes())
        evaluation = apply_context_overlay(document, evaluation, overlay)
        evidence_version = evaluation["version"]
        if release["version"] in {TEXT_RELEASE_VERSION, C10_RELEASE_VERSION}:
            from rag_hub.html_text_recovery import evaluate as apply_text_recovery

            text_overlay_path = policy["text_overlay_path"]
            if text_overlay_path not in release["files"]:
                raise ValueError("HTML_text_overlay_not_fingerprinted")
            text_overlay = json.loads(local_path(root, text_overlay_path).read_bytes())
            evaluation = apply_text_recovery(document, evaluation, text_overlay)
            evidence_version = evaluation["version"]
    if release["version"] == C10_RELEASE_VERSION:
        from rag_hub.html_c10 import extend

        if source.doc_id != "C10":
            raise ValueError("C10_successor_is_not_a_corpus_reassessment")
        spec_path = policy["c10_scope_path"]
        if spec_path not in release["files"]:
            raise ValueError("C10_scope_not_fingerprinted")
        evaluation = extend(
            document, evaluation, json.loads(local_path(root, spec_path).read_bytes())
        )
        evidence_version = evaluation["version"]
    facts = {r["section_id"]: r for r in evaluation["sections"]}
    lookup = {r.section_id: r for r in results}
    proofs = {}
    for u in evaluation["units"]:
        if any(
            lookup[s].blocking_integrity
            or unresolved_reasons(lookup[s], u)
            or "fail" in lookup[s].checks.values()
            for s in u["required_section_ids"]
        ):
            for s in u["required_section_ids"]:
                if s in u["content_section_ids"]:
                    facts[s].update(
                        disposition="Other explicit QA restriction",
                        reasons=sorted(unresolved_reasons(lookup[s], u))
                        or ["conflicting_unit_QA_check"],
                        human_review_material=True,
                    )
            continue
        for s in u["required_section_ids"]:
            scope = {
                "source_format": "html",
                "unit_id": u["id"],
                "unit_sha256": u["unit_sha256"],
                "required_section_ids": u["required_section_ids"],
                "consumption": "complete_unit_only",
                "role": "context_only" if s in u["context_section_ids"] else "content",
                "qualification_policy_sha256": auth["policy_sha256"],
                "authorization_sha256": authorization_sha256,
                "qa_release_sha256": expected_release_sha256,
                "whole_source_ready": False,
            }
            if release["version"] in {TEXT_RELEASE_VERSION, C10_RELEASE_VERSION}:
                if (
                    u["reference_classification"]
                    not in {"STANDARD_REFERENCE", "ILLUSTRATIVE_REFERENCE"}
                    or not u["limitations"]
                ):
                    raise ValueError("HTML_text_reference_class_or_limitations_missing")
                scope.update(
                    reference_classification=u["reference_classification"],
                    limitations=u["limitations"],
                    allowed_usage=u["allowed_usage"],
                    forbidden_usage=u["forbidden_usage"],
                    admitted_facets="source_text_only",
                    textual_projection_sha256=digest(encode(u["textual_projections"])),
                )
            # A context heading may belong to multiple complete units.
            proof = proofs.setdefault(
                s,
                {
                    "scopes": [],
                    "resolved_restrictions": {
                        r: evidence_version + ":source-backed-complete-unit"
                        for r in lookup[s].reasons
                    },
                },
            )
            proof["scopes"].append(scope)
    selected_units = [
        u
        for u in evaluation["units"]
        if all(
            s in proofs and any(v["unit_id"] == u["id"] for v in proofs[s]["scopes"])
            for s in u["required_section_ids"]
        )
    ]
    if release["version"] == C10_RELEASE_VERSION:
        from rag_hub.html_c10 import validate_relationships

        validate_relationships(selected_units)
    admitted = set(proofs)
    for s, f in facts.items():
        if s not in admitted and not f["disposition"]:
            f.update(
                disposition="Other explicit QA restriction",
                reasons=["no_complete_qualified_unit_after_shared_QA"],
                human_review_material=False,
            )
    # A shared heading can appear in both accepted and rejected candidate units.
    # Its final disposition must reflect the sole authoritative decision, not the
    # last failed candidate visited. Historical publications are never rewritten.
    if release["version"] in {
        REMEDIATED_RELEASE_VERSION,
        TEXT_RELEASE_VERSION,
        C10_RELEASE_VERSION,
    }:
        for s in admitted:
            facts[s].update(disposition=None, reasons=[], human_review_material=False)
            if release["version"] in {TEXT_RELEASE_VERSION, C10_RELEASE_VERSION}:
                memberships = proofs[s]["scopes"]
                facts[s]["reference_classification"] = (
                    "STANDARD_REFERENCE"
                    if any(
                        m["reference_classification"] == "STANDARD_REFERENCE" for m in memberships
                    )
                    else "ILLUSTRATIVE_REFERENCE"
                )
        if release["version"] in {TEXT_RELEASE_VERSION, C10_RELEASE_VERSION}:
            for s in set(facts) - admitted:
                if facts[s].get("reference_classification") not in {
                    "HOLD",
                    "EXCLUDED_NON_TEXT",
                    "EXCLUDED_NON_KNOWLEDGE",
                }:
                    facts[s]["reference_classification"] = "HOLD"
                    facts[s]["disposition"] = "HOLD"
    return proofs, {
        "version": evidence_version,
        "sections": list(facts.values()),
        "units": selected_units,
    }


def decision_from_proof(result, policy, proof):
    """Called solely from existing make_decisions; no independent publication."""
    if (
        result.blocking_integrity
        or "fail" in result.checks.values()
        or set(proof["resolved_restrictions"]) != set(result.reasons)
    ):
        raise ValueError("HTML_proof_cannot_override_integrity_or_unresolved_reasons")
    # One Section decision retains all unit memberships; readers must require an exact full unit.
    scope = dict(proof["scopes"][0], unit_memberships=proof["scopes"])
    return ScopedHtmlDecision(
        section_id=result.section_id,
        doc_id=result.doc_id,
        risk=result.risk,
        status="approved_for_index",
        raw_sha256=result.raw_sha256,
        normalized_sha256=result.normalized_sha256,
        policy_sha256=fingerprint(policy),
        validation_sha256=fingerprint(result),
        receipt_sha256=digest(encode(proof)),
        reasons=(),
        scope=scope,
        resolved_restrictions=proof["resolved_restrictions"],
    )
