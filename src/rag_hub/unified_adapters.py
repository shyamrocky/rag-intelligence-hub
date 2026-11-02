"""Three explicit adapters over unchanged verified native loaders.

Catalog labels are reconciled with publications, never used to authorize payloads.
Native envelopes stay opaque; only verified consumer projections leave the gateway.
"""

import json

from rag_hub.unified_models import AdaptedUnit, Membership, encode


def resolve(bound, index, ref):
    artifact = index["artifacts"][ref["artifact_id"]]
    value = bound.json(artifact["path"], artifact["sha256"])
    for part in ref["json_pointer"].strip("/").split("/") if ref["json_pointer"] else []:
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def index_sections(bound, index, fmt, approved):
    rows = {}
    for sid, row in index["sections"].items():
        if row["format"].lower() != fmt:
            continue
        decisions = [resolve(bound, index, ref) for ref in row["decision_refs"]]
        if any(d["section_id"] != sid for d in decisions):
            raise ValueError("unified_wrong_section_decision")
        is_approved = any(d["status"] == "approved_for_index" for d in decisions)
        if is_approved != (sid in approved) or is_approved != (row["qa_disposition"] == "ADMITTED"):
            raise ValueError("unified_catalog_publication_disagreement")
        # Explicit allowlist: no raw/normalized Section payload or broad JSON accessor.
        rows[sid] = {
            "section_id": sid, "document_id": row["document_id"], "format": fmt,
            "admission_status": "ADMITTED" if is_approved else "EXCLUDED",
            "native_disposition": row["qa_disposition"],
            "reference_classification": row["reference_classification"],
            "native_reference_classification": row.get("native_reference_classification"),
            "citation_locators": row["citations"], "provenance": row["provenance"],
            "issue_ids": row["issue_ids"],
            "issues": [index["issues"][i] for i in row["issue_ids"]],
            "reason": row.get("exclusion_reason"),
            "exclusion_category": row.get("exclusion_category"),
            "evidence_refs": [
                {**index["artifacts"][ref["artifact_id"]], "json_pointer": ref["json_pointer"]}
                for ref in [row["normalized_record_ref"], *row["decision_refs"]]
            ],
            "scope_limited_projection": False,
        }
    return rows


def html_adapter(root, selection, bound, index):
    from rag_hub.html_handoff import load_units

    # ALL also validates publication-bound intentional exclusions; never evidence.
    views = load_units(root, **selection, filters={"admission_status": "ALL"})
    admitted = [v for v in views if v["admission_status"] == "ADMITTED"]
    approved = {sid for v in admitted for sid in v["required_section_ids"]}
    rows = index_sections(bound, index, "html", approved)
    excluded = {v["required_section_ids"][0] for v in views if v["admission_status"] == "EXCLUDED"}
    if excluded != {sid for sid, s in rows.items() if s["admission_status"] == "EXCLUDED"}:
        raise ValueError("unified_HTML_exclusion_disagreement")
    units = []
    for v in admitted:
        native_id = v["unit_id"]
        metadata = index["units"][native_id]
        content = {x["section_id"] for x in v["llm_context"]["source_content"]}
        context = {x["section_id"] for x in v["llm_context"]["required_context"] if "section_id" in x}
        if not (content | context) <= set(v["required_section_ids"]) or (
            content != set(metadata["content_section_ids"])
            or context != set(metadata["context_section_ids"])
        ):
            raise ValueError("unified_HTML_membership_disagreement")
        memberships = [Membership(sid, "content", "content_section_ids") for sid in sorted(content)]
        memberships += [Membership(sid, "required_context", "context_section_ids")
                        for sid in sorted(context)]
        memberships += [Membership(sid, "required_context", "approval_scope_dependency")
                        for sid in sorted(set(v["required_section_ids"]) - content - context)]
        if set(metadata["required_section_ids"]) != set(v["required_section_ids"]):
            raise ValueError("unified_HTML_required_scope_disagreement")
        # Related context is already expanded and qualified by the native view.
        # Preserve these extra many-to-many edges without merging source units.
        for relation in v["related_evidence"]:
            if relation.get("required"):
                memberships += [Membership(sid, "required_context", "related_evidence")
                                for sid in relation["section_ids"]]
        units.append(AdaptedUnit(
            native_id, v["source_id"], "html", v["reference_classification"],
            v["reference_classification"], tuple(dict.fromkeys(memberships)), encode(v),
            encode({"llm_context": v["llm_context"], "source_fidelity": v["source_fidelity"],
                    "related_evidence": v["related_evidence"]}),
            encode(v["publication_identity"]),
            encode([c for x in v["llm_context"]["source_content"] for c in x["citations"]]),
            False,
        ))
    return rows, units


def markdown_consumer(v):
    """Project verified typed Sections, with restricted source_evidence kept opaque."""
    restricted = v.get("restricted_projection")
    scope = v["documentation_scope"]
    source = v["source"]

    def text(m):
        s = m["section"]
        return {"kind": "SOURCE_CONTENT", "section_id": s.section_id, "text": s.text,
                "citations": [c.model_dump(mode="json") for c in s.locators],
                "content_type": s.block_type, "source_sha256": source["raw_sha256"]}

    warnings = scope.get("limitations", [])
    # Restricted payload is the sole native consumable projection, including its
    # exact warning-bearing rendering; raw source_evidence is never a fallback.
    content = [{"kind": "SOURCE_CONTENT", "restricted_projection": restricted}] if restricted else [
        text(m) for m in v["members"]
        if m["section"].section_id not in v["context_only_section_ids"]]
    return {
        "llm_context": {
            "source_content": content,
            "required_context": [text(m) for m in v["heading_context"]] + (
                [] if restricted else [dict(text(m), role="required_context") for m in v["members"]
                                      if m["section"].section_id in v["context_only_section_ids"]]
            ),
            "qa_observations": [
                {"kind": "QA_OBSERVATION", "origin": "ingestion_QA_not_publisher",
                 "severity": "WARNING", "explanation": warning} for warning in warnings],
            "qualification": {
                "kind": "QUALIFICATION", "mandatory": True, "complete_unit_only": True,
                "documentation_scope": scope, "source_semantics": v["source_semantics"],
                "allowed_usage": ["Attributed documentation within complete native unit scope."],
                "forbidden_usage": ["Strip warnings, headings or provider boundaries.",
                                    "Certify example execution or unverified score semantics."],
                "code_execution_verified": False,
            },
        },
        "source": source, "context": v["context"], "provider_tab": v["provider_tab"],
        "context_only_section_ids": v["context_only_section_ids"],
        "source_fidelity": {"status": "VERIFIED_NATIVE_SCOPED_UNIT"},
    }


def markdown_adapter(root, selection, bound, index):
    from rag_hub.markdown_handoff import load_units

    views = load_units(root, **selection)  # Never call historical default.
    approved = {sid for v in views for sid in v["required_section_ids"] + v["supporting_heading_ids"]}
    rows = index_sections(bound, index, "markdown", approved)
    units = []
    publication = selection["admission"]
    actual = bound.json(publication["publication_path"])
    if approved != {d["section_id"] for d in actual["qa"]["quality_decisions"]
                    if d["status"] == "approved_for_index"}:
        raise ValueError("unified_Markdown_membership_disagreement")
    for v in views:
        m = index["units"][v["unit_id"]]
        if (v["required_section_ids"] != m["required_section_ids"]
                or v["supporting_heading_ids"] != m["supporting_heading_ids"]):
            raise ValueError("unified_Markdown_index_disagreement")
        context = set(v["context_only_section_ids"])
        memberships = [Membership(
            sid, "required_context" if sid in context else
            "projection" if v.get("restricted_projection") else "content",
            "context_only_section_ids" if sid in context else "required_section_ids",
        ) for sid in v["required_section_ids"]]
        memberships += [Membership(sid, "supporting_heading", "supporting_heading_ids")
                        for sid in v["supporting_heading_ids"]]
        native_class = v["documentation_scope"].get("classification")
        if native_class != m["native_reference_classification"]:
            raise ValueError("unified_Markdown_classification_disagreement")
        consumer = markdown_consumer(v)
        citations = [c.model_dump(mode="json") for member in
                     v.get("source_evidence", v["members"]) for c in member["section"].locators]
        units.append(AdaptedUnit(
            v["unit_id"], source_id(v), "markdown", m["reference_classification"],
            native_class, tuple(memberships), encode(v), encode(consumer), encode(publication),
            encode(citations), bool(v.get("restricted_projection")),
        ))
    return rows, units


def source_id(v):
    return v["source"]["doc_id"]


def pdf_adapter(root, selection, bound, issue_register):
    from rag_hub.pdf_text_handoff import load_units

    views = load_units(root, **selection)
    lookup = {v["unit_id"]: v for v in views}
    rows, units = {}, []
    manifest = bound.json(selection["manifest_path"])
    issues = {s["section_id"]: s for s in issue_register["sections"]}
    for desc in manifest["publications"]:
        publication = json.loads(bound.bind(desc["path"], desc["sha256"]))
        evidence = publication["qa"]["pdf_text_support"]
        canonical_path = f'data/normalized/pdf/four-pdf-poc-v1/{publication["doc_id"]}/sections.json'
        canonical = bound.json(canonical_path)
        blocks = {bid: s["section_id"] for s in canonical for bid in s["block_ids"]}
        decisions = {d["section_id"]: d for d in publication["qa"]["quality_decisions"]}
        accounting = {s["section_id"]: s for s in evidence["section_accounting"]}
        if set(decisions) != set(accounting) or set(decisions) != {s["section_id"] for s in canonical}:
            raise ValueError("unified_PDF_missing_canonical_Section")
        for sid, a in accounting.items():
            d = decisions[sid]
            status = "ADMITTED" if d["status"] == "approved_for_index" else a["disposition"]
            item = issues[sid]
            if status not in {"ADMITTED", "HOLD", "EXCLUDED"} or (
                (status == "ADMITTED") != (a["disposition"] in {"STANDARD", "ILLUSTRATIVE"})
                or status != item["admission_status"] or a["disposition"] != item["disposition"]
                or set(a["unit_ids"]) != set(item["unit_ids"])
            ):
                raise ValueError("unified_PDF_catalog_publication_disagreement")
            rows[sid] = {
                "section_id": sid, "document_id": a["doc_id"], "format": "pdf",
                "admission_status": status, "native_disposition": a["disposition"],
                "reference_classification": a["disposition"] + "_REFERENCE"
                if status == "ADMITTED" else None,
                "native_reference_classification": a["disposition"] if status == "ADMITTED" else None,
                "citation_locators": a["source_locators"],
                "provenance": {"source_sha256": evidence["source"]["raw_sha256"],
                               "original_block_ids": a["original_block_ids"],
                               "original_section_sha256": a["original_section_sha256"]},
                "reason": a["reason"], "issue_ids": [item["original_issue_family"]]
                if item.get("original_issue_family") else [],
                "issues": [{"issue_type": item.get("original_issue_family", "scope_qualification"),
                            "description": a["reason"],
                            "remaining_unqualified_aspects": a["remaining_unqualified_aspects"]}],
                "evidence_refs": [desc, {"path": canonical_path, "section_id": sid}],
                "scope_limited_projection": a["scope_limited_projection"],
            }
        expected_unit_ids = {u["id"] for u in evidence["units"]}
        if expected_unit_ids != {v["unit_id"] for v in views if v["source_id"] == publication["doc_id"]}:
            raise ValueError("unified_PDF_reader_units_disagree")
        for u in evidence["units"]:
            v = lookup[u["id"]]
            body = {blocks[m["block_id"]] for m in u["source_members"] if m["block_id"] in blocks}
            context = {blocks[c["source_span"]["block_id"]] for c in u["required_context"]}
            if not set(v["required_section_ids"]) <= (body | context) or not body <= set(
                v["required_section_ids"]
            ):
                raise ValueError("unified_PDF_span_membership_disagreement")
            memberships = [Membership(sid, "projection", "source_members") for sid in sorted(body)]
            memberships += [Membership(blocks[c["source_span"]["block_id"]], "supporting_heading",
                                       c["role"]) for c in u["required_context"]]
            # Explicit consumer projection only; native audit_only original text stays opaque.
            consumer = {k: v[k] for k in [
                "llm_context", "source_fidelity", "known_limitations", "qa_observations",
                "related_evidence", "allowed_usage", "forbidden_usage", "required_context"]}
            if "publication_expiration" in v:
                consumer["publication_expiration"] = v["publication_expiration"]
            units.append(AdaptedUnit(
                v["unit_id"], v["source_id"], "pdf", v["reference_classification"],
                u["reference_classification"], tuple(memberships), encode(v), encode(consumer),
                encode(v["publication_identity"]), encode(v["citation_locators"]),
                any(accounting[sid]["scope_limited_projection"] for sid in body),
            ))
    if set(issues) != set(rows):
        raise ValueError("unified_PDF_issue_inventory_disagreement")
    return rows, units
