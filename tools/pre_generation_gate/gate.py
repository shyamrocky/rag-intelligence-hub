"""Live M8 validation bridge and explicit semantic-unavailable fallback.

No source payload, label, model, retriever or caller-provided semantic verdict is
accepted as an alternative evidence authority. Results are ephemeral audit records.
"""

import copy
import hashlib
import threading

from tools.pre_generation_gate.contract import (
    VERSION,
    GateConfiguration,
    digest,
    question_requirements,
    reduce_assessment,
)

M8_SELECTOR = "config/evidence-reconstruction-m8-v1.json"
M8_SHA = "e0ac189c8b5ffd331f28ae87f81d56c22868e12c45d7b73e6a5e7f1a65c6bef2"


class ValidationGate:
    """Trusted in-process integration, not a detached authorization endpoint.

    Reuse an existing real EvidenceService to avoid a second multi-GB corpus.
    Its accepted public validate(package, result) path executes on EVERY request.
    No validation cache and no externally injected semantic assessments exist.
    """

    def __init__(self, evidence_service, *, configuration):
        from tools.evidence.service import EvidenceService

        if (type(evidence_service) is not EvidenceService
                or evidence_service.selector != M8_SELECTOR
                or evidence_service.selector_sha256 != M8_SHA
                or type(configuration) is not GateConfiguration):
            raise ValueError("real_explicit_M8_service_and_gate_configuration_required")
        evidence_service.check()
        self._service = evidence_service
        self._configuration = configuration
        self._lock = threading.RLock()

    def assess(self, question, package, original_m7_result):
        """Fail-closed ABSTAIN with a distinct status on integrity/operational errors.

        The original M7 result is mandatory because M8 validation needs it. A
        checksum or verification string never replaces live native validation.
        No publisher evidence is included in routine audit output.
        """
        from tools.evidence.service import EvidenceIntegrityError
        from tools.retrieval.contract import parameters

        with self._lock:
            try:
                # Snapshot caller-owned inputs; never mutate the authoritative package.
                package, result = copy.deepcopy(package), copy.deepcopy(original_m7_result)
                p = result["parameters"]
                normalized, _ = parameters(question, result["retrieval_mode"], p["top_k"],
                    p["candidate_depth"], p["rrf_k"], p["filters"], self._service.inventory)
                requirements = question_requirements(normalized)
                qsha = hashlib.sha256(normalized.encode()).hexdigest()
                if (result["query_sha256"] != qsha or package["retrieval"]["query_sha256"] != qsha
                        or package["retrieval"]["candidate_result_sha256"] != digest(result)):
                    raise EvidenceIntegrityError("gate_question_or_candidate_binding_mismatch")
                if self._service.validate(package, result) is not True:
                    raise EvidenceIntegrityError("gate_M8_validation_not_confirmed")
            except (EvidenceIntegrityError, ValueError, TypeError, KeyError, OSError,
                    UnicodeError, RecursionError):
                # Exception strings may contain untrusted or private input; do not echo them.
                return self._failure("VALIDATION_ERROR", "INVALID_UNTRUSTED_OR_STALE_M8_INPUT")
            try:
                output = self._assess_validated(normalized, requirements, package, result)
                # Do not issue an audit result after a bound file changes during assessment.
                self._service.check()
                return output
            except (EvidenceIntegrityError, ValueError, TypeError, KeyError, OSError):
                return self._failure("VALIDATION_ERROR", "EVIDENCE_BINDING_CHANGED_DURING_ASSESSMENT")

    def _failure(self, status, reason):
        return self._audit({"schema": VERSION, "status": status, "decision": "ABSTAIN",
            "gate_criteria_passed": False, "generation_authorized": False,
            "configuration": self._configuration.record(),
            "configuration_sha256": digest(self._configuration.record()),
            "source_integrity": "FAILED_OR_UNCONFIRMED", "semantic_sufficiency": "NOT_ASSESSED",
            "requirements": [], "assessments": [], "available_evidence_references": [],
            "missing_or_uncertain_requirements": [], "blocking_reasons": [reason],
            "evidence_binding": None, "recovery": {"action_authorized": False,
                "advisory": "Repair explicit bindings and reconstruct through accepted M8."}})

    def _assess_validated(self, question, requirements, package, result):
        references, obligations = [], []
        for index, item in enumerate(package["parents"]):
            parent = item["evidence"]["verified_parent"]
            context = parent["consumer"]["llm_context"]
            base = f"/parents/{index}/evidence/verified_parent"
            # Available source pointers establish traceability only, never support.
            for source_index, source in enumerate(context["source_content"]):
                references.append({"unit_id": parent["unit_id"],
                    "document_id": parent["document_id"], "role": "SOURCE_CONTENT",
                    "pointer": base + f"/consumer/llm_context/source_content/{source_index}",
                    "value_sha256": digest(source), "semantic_support": "NOT_ESTABLISHED",
                    "citation_pointer": base + "/citation_locators",
                    "citation_sha256": digest(parent["citation_locators"]),
                    "citation_precision": item["evidence"]["citation_precision"]["parent"]})
            obligations.append({"unit_id": parent["unit_id"],
                "complete_parent_sha256": digest(parent),
                "qualifications_sha256": digest(context["qualification"]),
                "required_context_sha256": digest(context["required_context"]),
                "QA_observations_sha256": digest(context["qa_observations"]),
                "memberships_sha256": digest(parent["memberships"]),
                "publication_sha256": digest(parent["publication_identity"]),
                "complete_parent_required": item["evidence"]["complete_parent_required"],
                "scope_assessment": "RETAINED_NOT_SEMANTICALLY_RESOLVED"})
        assessments = [{"requirement_id": r["requirement_id"], "support": "UNKNOWN",
                        "references": [], "reason": "QUALIFIED_SEMANTIC_ASSESSOR_UNAVAILABLE"}
                       for r in requirements]
        decision = reduce_assessment(requirements, assessments, qualified=False,
                                     evidence_present=bool(package["parents"]))
        reasons = ["QUALIFIED_SEMANTIC_ASSESSOR_UNAVAILABLE", "REQUIREMENT_SCOPE_UNCONFIRMED"]
        if not package["parents"]:
            reasons.append("NO_INCLUDED_AUTHORIZED_EVIDENCE")
        if package["diagnostics"]["omitted"]:
            reasons.append("BUDGET_OMISSIONS_PRESENT_RELEVANCE_UNKNOWN")
        return self._audit({"schema": VERSION, "status": "INDETERMINATE",
            "decision": decision, "gate_criteria_passed": False, "generation_authorized": False,
            "configuration": self._configuration.record(),
            "configuration_sha256": digest(self._configuration.record()),
            "source_integrity": "LIVE_M8_VALIDATED", "semantic_sufficiency": "INDETERMINATE",
            "normalized_question": question, "requirements": requirements,
            "assessments": assessments, "available_evidence_references": references,
            "missing_or_uncertain_requirements": [r["requirement_id"] for r in requirements],
            "blocking_reasons": reasons, "obligations": obligations,
            "evidence_binding": {"package_sha256": digest(package),
                "candidate_result_sha256": digest(result),
                "query_sha256": package["retrieval"]["query_sha256"],
                "M8_release": package["release_identity"], "M8_selection": package["selection"],
                "M7_release": result["release_identity"], "index_bindings": result["index_release_bindings"],
                "budget": package["budget"], "included_parents": [
                    p["evidence"]["unit_id"] for p in package["parents"]],
                "omitted": package["diagnostics"]["omitted"]},
            "recovery": {"action_authorized": False,
                "advisory": "Qualify a semantic assessor or obtain explicit human sufficiency review; "
                            "more retrieval alone cannot resolve assessor unavailability."},
            "limitations": ["Syntax does not establish complete question requirements.",
                "No requirement-level support or contradiction detection is implemented.",
                "Authenticity, rankings, keywords and citations do not establish sufficiency.",
                "Known-positive benchmark labels are never runtime inputs.",
                "Revalidate M8 immediately before any separately authorized future use."]})

    @staticmethod
    def _audit(output):
        return output | {"audit_sha256": digest(output)}
