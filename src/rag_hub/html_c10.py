"""One source-bound illustrative addition; evidence only, never an admission engine."""

import copy

from rag_hub.acquire import digest
from rag_hub.html_acquire import encode
from rag_hub.html_qualification import binding
from rag_hub.html_text_recovery import ILLUSTRATIVE, locate, projection, reference
from rag_hub.html_validation import SourceIndex, canonical_text

VERSION = "html-c10-illustrative-1.0"
SECTION = "C10:7e72080f353e:h00027:68c8ad3d5a22"
ISSUE = "HTML-SRC-SCORE-STAGE"
LIMITATION = (
    "QA observation (not a Microsoft statement): the captured weighting example does not "
    "fully establish how its displayed scores relate to raw 1/(rank + k) contributions. "
    "Quote the source values and documented multiplications without inventing a scoring-stage "
    "explanation or claiming a publisher error, independently verified RRF values or Azure runtime results."
)


def extend(document, baseline, spec):
    if document["source"].doc_id != "C10":
        raise ValueError("C10_policy_cannot_cross_sources")
    rows = {r["section"]["section_id"]: r for r in document["normalized"]["records"]}
    if (
        spec["source_sha256"] != document["source"].raw_sha256
        or digest(document["raw"]) != spec["source_sha256"]
        or spec["section_id"] != SECTION
    ):
        raise ValueError("C10_source_identity_mismatch")
    selected = spec["context_section_ids"] + [SECTION]
    if spec["source_bindings"] != [binding(rows[s], document) for s in selected]:
        raise ValueError("C10_source_binding_mismatch")
    facts = {f["section_id"]: f for f in baseline["sections"]}
    if any(c["outcome"] == "FAIL" for s in selected for c in facts[s]["checks"]["checks"].values()):
        raise ValueError("C10_blocking_source_check")
    formula = next((u for u in baseline["units"] if u["id"] == spec["formula_unit_id"]), None)
    if formula is None or formula["unit_sha256"] != spec["formula_unit_sha256"]:
        raise ValueError("C10_required_formula_context_missing")
    if "1/(rank + k)" not in formula["text"]:
        raise ValueError("C10_formula_not_source_bound")
    index = SourceIndex(document["raw"].decode(document["acquisition"].get("charset", "utf-8")))
    if canonical_text(locate(rows[SECTION], index), False) != rows[SECTION]["section"]["text"]:
        raise ValueError("C10_table_payload_not_exact_source")
    projections = [
        projection(rows[s], document, index, "native_table" if s == SECTION else "visible_text")
        for s in selected
    ]
    unit = {
        "id": "html-c10-unit:" + digest(encode(spec))[:20],
        "doc_id": "C10",
        "source": document["source"].model_dump(mode="json"),
        "heading_path": rows[SECTION]["section"]["heading_path"],
        "required_section_ids": selected,
        "context_section_ids": spec["context_section_ids"],
        "content_section_ids": [SECTION],
        "members": spec["source_bindings"],
        "text": rows[SECTION]["section"]["text"],
        "text_sha256": rows[SECTION]["section"]["normalized_sha256"],
        "heading_context": [b for b in spec["source_bindings"] if b["classification"] == "heading"],
        "required_parent_context": [
            b for b in spec["source_bindings"] if b["classification"] == "paragraph"
        ],
        "source_context_projections": [],
        "consumption": "complete_unit_only",
        "joiner": "",
        "restriction_resolutions": spec["restriction_resolutions"],
        "context_resolution": "Source weighting example with separate source-bound RRF context; no mathematical equivalence inferred.",
        "evidence_role": "machine_source_verification_not_human_attestation",
        "related_evidence": [
            {
                "relationship_type": "documented_RRF_context_not_numerical_equivalence",
                "required": True,
                "doc_id": "C10",
                "unit_id": formula["id"],
                "unit_sha256": formula["unit_sha256"],
                "section_ids": formula["required_section_ids"],
                "source_sha256": document["source"].raw_sha256,
            }
        ],
    }
    issue = {
        "issue_id": ISSUE,
        "kind": "QA_OBSERVATION",
        "origin": "ingestion_QA_not_publisher",
        "issue_type": "ambiguity",
        "severity": "WARNING",
        "disposition": "admitted_with_mandatory_qualification",
        "doc_id": "C10",
        "section_ids": [SECTION],
        "limitation": LIMITATION,
        "must_accompany": True,
        "mitigation": "Retain exact table and linked RRF context as attributed illustrative evidence only.",
        "confirmed_source_error": False,
        "evidence": spec["source_bindings"],
    }
    unit = reference(unit, ILLUSTRATIVE, [LIMITATION], projections, [issue])
    unit["allowed_usage"] = [
        "quote_the_original_source_table",
        "explain_displayed_weighting_multiplications",
        "explain_the_RRF_formula_as_documented_in_linked_source_context",
        "disclose_unresolved_score_stage_interpretation",
    ]
    unit["forbidden_usage"] += [
        "claim_the_table_numerically_proves_RRF",
        "claim_independently_reproduced_Azure_runtime_outcomes",
        "present_unresolved_score_semantics_as_fact",
        "suppress_the_QA_observation_or_required_context",
    ]
    unit.pop("unit_sha256")
    unit["unit_sha256"] = digest(encode(unit))
    result = copy.deepcopy(baseline)
    result["units"].append(unit)
    target = next(f for f in result["sections"] if f["section_id"] == SECTION)
    target.update(
        disposition=None,
        reasons=[],
        reference_classification=ILLUSTRATIVE,
        human_review_material=False,
    )
    result["version"] = VERSION
    return result


def validate_relationships(units):
    lookup = {u["id"]: u for u in units}
    for unit in units:
        for relation in unit.get("related_evidence", []):
            target = lookup.get(relation["unit_id"])
            if relation["required"] and (
                target is None
                or target["unit_sha256"] != relation["unit_sha256"]
                or target["required_section_ids"] != relation["section_ids"]
                or target["source"]["raw_sha256"] != relation["source_sha256"]
            ):
                raise ValueError("C10_missing_or_changed_qualified_relationship")
