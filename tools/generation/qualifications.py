"""Native disclosure presence checks; never invent applicability or entailment."""

from tools.pre_generation_gate.contract import digest
from tools.pre_generation_gate.gate import M8_SELECTOR, M8_SHA
from tools.pre_generation_gate.response_v2 import validate_response_shape

VERSION = "native-qualification-disclosure-1.0"
VALID = "QUALIFICATIONS_VALID"
MISSING = "QUALIFICATIONS_MISSING"
UNDETERMINED = "QUALIFICATION_APPLICABILITY_UNDETERMINED"


def _assess_metadata(response, parents):
    """Pure mechanical helper for owned fixtures; not an evidence authorization API."""
    disclosures, uncertainties = [], []
    cited = sorted({uid for claim in response["claims"] for uid in claim["evidence_unit_ids"]})
    for uid in cited:
        context = parents[uid]["consumer"]["llm_context"]
        consumer = parents[uid]["consumer"]
        q = context.get("qualification")
        if not isinstance(q, dict):
            raise ValueError("INVALID_NATIVE_QUALIFICATION")
        # mandatory/complete_unit_only/allowed_usage are consumption rules, not a
        # machine-readable classification of which claims need user disclosures.
        if q.get("mandatory") is not False and q:
            uncertainties.append({"unit_id": uid, "reason": "NATIVE_QUALIFICATION_HAS_NO_EXPLICIT_USER_FACING_APPLICABILITY",
                                  "qualification_sha256": digest(q)})
        candidates = []
        expiration = consumer.get("publication_expiration")
        if expiration is not None:
            if not isinstance(expiration, dict):
                raise ValueError("INVALID_NATIVE_EXPIRATION")
            candidates.append((expiration, "warning", "/consumer/publication_expiration"))
        for index, observation in enumerate(context.get("qa_observations", [])):
            if not isinstance(observation, dict):
                raise ValueError("INVALID_NATIVE_OBSERVATION")
            candidates.append((observation, "explanation", f"/consumer/llm_context/qa_observations/{index}"))
        seen = set()
        for item, field, pointer in candidates:
            flag = item.get("display_to_user_when_used")
            if flag is not None and type(flag) is not bool:
                raise ValueError("INVALID_NATIVE_DISPLAY_FLAG")
            if flag is True:
                text = item.get(field)
                if type(text) is not str or not text.strip():
                    raise ValueError("MISSING_EXPLICIT_DISCLOSURE_TEXT")
                if text in seen:
                    continue
                seen.add(text)
                exact = text.strip() in [s.strip() for s in response["relevant_qualifications"]]
                if exact:
                    state = "EXACT_METADATA_TEXT_PRESENT"
                elif not response["relevant_qualifications"]:
                    state = "MISSING_EMPTY_QUALIFICATIONS"
                else:
                    # Paraphrases, negations and unrelated strings cannot be
                    # adjudicated semantically by a lexical mismatch.
                    state = "REPRESENTATION_UNDETERMINED"
                    uncertainties.append({"unit_id": uid, "reason": state,
                                          "native_pointer": pointer})
                disclosures.append({"unit_id": uid, "native_pointer": pointer,
                    "disclosure_sha256": digest(text), "status": state,
                    "answer_contains_exact_text": text in response["answer"],
                    "requirement_location": "relevant_qualifications",
                    "semantic_compliance_verified": False})
            elif flag is None and (item.get("must_accompany") is True
                                   or item.get("severity") == "WARNING"):
                uncertainties.append({"unit_id": uid, "reason": "WARNING_HAS_NO_EXPLICIT_DISPLAY_APPLICABILITY",
                                      "native_pointer": pointer})
    missing = [d for d in disclosures if d["status"] == "MISSING_EMPTY_QUALIFICATIONS"]
    status = MISSING if missing else UNDETERMINED if uncertainties else VALID
    return {"schema": VERSION, "status": status, "cited_unit_ids": cited,
        "empty_relevant_qualifications": not response["relevant_qualifications"],
        "explicit_disclosures": disclosures, "missing_disclosures": missing,
        "uncertainties": uncertainties, "machine_presence_checks_satisfied": status == VALID,
        "semantic_compliance_verified": False, "answer_material_qualification_compliance": "NOT_DETERMINED_BY_LEXICAL_CHECKS",
        "fully_validated": False, "response_rewritten": False,
        "scope": "Native explicit disclosure presence only; no new source or applicability authority."}


class QualificationValidator:
    def __init__(self, evidence_service):
        from tools.evidence.service import EvidenceService

        if (type(evidence_service) is not EvidenceService or evidence_service.selector != M8_SELECTOR
                or evidence_service.selector_sha256 != M8_SHA):
            raise ValueError("REAL_EXPLICIT_M8_SERVICE_REQUIRED")
        self.service = evidence_service

    def validate(self, response, package, original_m7_result):
        """Fail integrity before any disclosure verdict; caller input remains unchanged."""
        if self.service.validate(package, original_m7_result) is not True:
            raise ValueError("M8_VALIDATION_NOT_CONFIRMED")
        parents = {p["evidence"]["unit_id"]: p["evidence"]["verified_parent"] for p in package["parents"]}
        checked = validate_response_shape(response, authorized_unit_ids=set(parents)).model_dump()
        assessment = _assess_metadata(checked, parents)
        self.service.check()
        return assessment | {"M8_package_sha256": digest(package), "response_sha256": digest(response),
                             "source_integrity": "LIVE_M8_VALIDATED"}
