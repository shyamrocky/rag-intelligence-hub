"""Small serialized consumption vocabulary; projections of verified QA, not authority.

SOURCE_CONTENT is attributed publisher evidence. QA_OBSERVATION is our finding.
QUALIFICATION is a mandatory consumption restriction, never a publisher claim.
"""

import copy

from rag_hub.acquire import digest
from rag_hub.html_acquire import encode

SCHEMA = "qa-consumption-unit-1.0"
SEVERITIES = {
    "BLOCKING": "Integrity/evidence/scope failure prevents admission; warning never overrides it.",
    "WARNING": "Admitted content has a mandatory limitation; does not alone imply HOLD.",
    "INFORMATIONAL": "Nonblocking observation or intentional POC exclusion; not a new approval.",
}


def observation(issue):
    return {
        "kind": "QA_OBSERVATION",
        "issue_id": issue["issue_id"],
        "origin": "ingestion_QA_not_publisher",
        "issue_type": issue.get("issue_type")
        or ("source_defect" if issue.get("confirmed_source_error") else "source_limitation"),
        "severity": issue.get("severity", "WARNING"),
        "description": issue["limitation"],
        "evidence": issue.get("evidence", []),
        "disposition": issue.get("disposition", "admitted_with_mandatory_qualification"),
        "mitigation": issue.get(
            "mitigation", "Preserve source attribution and mandatory limitations."
        ),
        "must_accompany": issue.get("must_accompany", True),
        "publisher_error_confirmed": issue.get("confirmed_source_error", False),
    }


def source_content(unit):
    projections = {p["source"]["section_id"]: p for p in unit.get("textual_projections", [])}
    return [
        {
            "kind": "SOURCE_CONTENT",
            "source_id": unit["doc_id"],
            "section_id": m["section_id"],
            "text": m["text"],
            "content_type": m["classification"],
            "citations": m["citation_locators"],
            "source_sha256": unit["source"]["raw_sha256"],
            "table": projections.get(m["section_id"], {}).get("table_text_structure"),
        }
        for m in unit["members"]
        if m["section_id"] in unit["content_section_ids"]
    ]


def html_view(unit, lookup, identity, *, current_issues=None):
    """Caller supplies only units returned by the verified authoritative handoff."""
    issues = [
        observation((current_issues or {}).get(i["issue_id"], i))
        for i in unit.get("source_issues", [])
    ]
    if any(i["severity"] not in SEVERITIES for i in issues):
        raise ValueError("unknown_consumption_issue_severity")
    if any(i["severity"] == "BLOCKING" for i in issues):
        raise ValueError("blocking_failure_cannot_be_admitted_with_warning")
    contexts = []
    for m in unit["members"]:
        if m["section_id"] in unit["context_section_ids"]:
            contexts.append(
                {
                    "relationship_type": "required_source_context",
                    "section_id": m["section_id"],
                    "source_content": {
                        "kind": "SOURCE_CONTENT",
                        "text": m["text"],
                        "citations": m["citation_locators"],
                    },
                }
            )
    for relation in unit.get("related_evidence", []):
        target = lookup.get(relation["unit_id"])
        if target is None or target["unit_sha256"] != relation["unit_sha256"]:
            raise ValueError("missing_or_changed_consumption_context")
        contexts.append(
            {
                **relation,
                "source_content": source_content(target),
                "required_context": [
                    {
                        "section_id": m["section_id"],
                        "kind": "SOURCE_CONTENT",
                        "text": m["text"],
                        "citations": m["citation_locators"],
                    }
                    for m in target["members"]
                    if m["section_id"] in target["context_section_ids"]
                ],
                "qualification": {
                    "kind": "QUALIFICATION",
                    "limitations": target["limitations"],
                    "allowed_usage": target["allowed_usage"],
                    "forbidden_usage": target["forbidden_usage"],
                },
            }
        )
    qualification = {
        "kind": "QUALIFICATION",
        "limitations": unit["limitations"],
        "allowed_usage": unit["allowed_usage"],
        "forbidden_usage": unit["forbidden_usage"],
        "mandatory": True,
        "complete_unit_only": True,
        "source_fidelity_is_not_publisher_truth_certification": True,
        "scope_note": (
            "Inherited prose-only scope retains its historical limitations. The separately admitted "
            "C10 table has its own illustrative unit; earlier table-withheld wording is historical, "
            "not a current whole-publication exclusion."
            if unit["doc_id"] == "C10"
            and any(i["issue_id"] == "HTML-SRC-SCORE-STAGE" for i in issues)
            and not unit.get("related_evidence")
            else None
        ),
    }
    view = {
        "schema_version": SCHEMA,
        "unit_id": unit["id"],
        "source_id": unit["doc_id"],
        "source_format": "html",
        "admission_status": "ADMITTED",
        "reference_classification": unit["reference_classification"],
        "source_fidelity": {
            "status": "VERIFIED",
            "scope": "captured_text_structure_and_source_bindings_only",
        },
        "required_section_ids": unit["required_section_ids"],
        "llm_context": {
            "source_content": source_content(unit),
            "required_context": contexts,
            "qa_observations": issues,
            "qualification": qualification,
        },
        "known_limitations": issues,
        "related_evidence": unit.get("related_evidence", []),
        "publication_identity": identity,
        "metadata": {
            "has_known_issues": bool(issues),
            "requires_context": bool(contexts),
            "title": unit["source"]["title"],
            "url": unit["source"]["canonical_url"],
            "heading_path": unit["heading_path"],
            "highest_issue_severity": "WARNING" if issues else "INFORMATIONAL",
            "whole_source_ready": False,
        },
        "audit_only": {
            "source_sha256": unit["source"]["raw_sha256"],
            "source_snapshot_id": unit["source"]["snapshot_id"],
            "unit_sha256": unit["unit_sha256"],
            "authoritative_publication": unit["authoritative_publication"],
            "decision_qa_release_sha256": unit["qa_release_sha256"],
            "member_bindings": [
                {k: v for k, v in m.items() if k not in {"text", "source_tree"}}
                for m in unit["members"]
            ],
        },
    }
    view["contract_sha256"] = digest(encode(view))
    return view


def excluded_view(entry, identity):
    """Dashboard-only exclusion; never expose excluded payload as LLM evidence."""
    issue = {
        "kind": "QA_OBSERVATION",
        "issue_id": "EXCLUSION:" + entry["source_binding"]["section_id"],
        "origin": "ingestion_QA_not_publisher",
        "issue_type": "POC_exclusion",
        "severity": "INFORMATIONAL",
        "description": entry["reason"],
        "disposition": entry["classification"],
        "evidence": [
            {k: v for k, v in entry["source_binding"].items() if k not in {"text", "source_tree"}}
        ],
        "must_accompany": False,
        "mitigation": "Exclude from consumable source evidence.",
    }
    return {
        "schema_version": SCHEMA,
        "unit_id": issue["issue_id"],
        "source_id": entry["doc_id"],
        "source_format": "html",
        "admission_status": "EXCLUDED",
        "reference_classification": entry["classification"],
        "required_section_ids": [entry["source_binding"]["section_id"]],
        "source_fidelity": {"status": "UNVERIFIED", "scope": "no_qualified_knowledge_payload"},
        "llm_context": None,
        "known_limitations": [issue],
        "related_evidence": [],
        "publication_identity": identity,
        "metadata": {
            "has_known_issues": True,
            "requires_context": False,
            "highest_issue_severity": "INFORMATIONAL",
        },
        "audit_only": {"source_binding": entry["source_binding"]},
    }


def select(
    views,
    *,
    admission_status="ADMITTED",
    reference_classification=None,
    source_id=None,
    has_known_issues=None,
    requires_context=None,
    issue_type=None,
    source_format=None,
):
    """Filter whole verified envelopes, never rewrite class or strip qualifications."""
    if admission_status not in {"ADMITTED", "EXCLUDED", "ALL"}:
        raise ValueError("unsupported_consumption_filter")
    return [
        copy.deepcopy(v)
        for v in views
        if (admission_status == "ALL" or v["admission_status"] == admission_status)
        and (
            reference_classification is None
            or v["reference_classification"] == reference_classification
        )
        and (source_id is None or v["source_id"] == source_id)
        and (source_format is None or v["source_format"] == source_format)
        and (has_known_issues is None or v["metadata"]["has_known_issues"] == has_known_issues)
        and (requires_context is None or v["metadata"]["requires_context"] == requires_context)
        and (
            issue_type is None or any(i["issue_type"] == issue_type for i in v["known_limitations"])
        )
    ]
