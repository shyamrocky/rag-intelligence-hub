"""Offline post-generation checks. Source integrity is distinct from semantic support."""
import copy
import hashlib
import importlib.util

from .artifacts import ArtifactError, digest, safe_path, sha

VERSION = "post-generation-validation-1.0"
QUOTE_HELPER = "workspace/rag-implementation/v1/generation-live-q05-v1/run_once.py"
QUOTE_HELPER_SHA = "b83f5ada38455a1c7283604280d33048461f2941d28cacb3948b69af04f92b53"


def quote_reader(root):
    """Reuse the sealed, nonexecuting source-only quotation inspector. Never call main."""
    path = safe_path(root, QUOTE_HELPER)
    if sha(path) != QUOTE_HELPER_SHA:
        raise ArtifactError("QUOTE_INSPECTOR_BINDING_CHANGED")
    spec = importlib.util.spec_from_file_location("quality_sealed_quote_reader", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.quote_check


def assess_structure(response, package, quote_check):
    """Pure fixture/mechanical checks only; public validator first requires live M8."""
    from tools.pre_generation_gate.response_v2 import validate_response_shape

    parents = {p["evidence"]["unit_id"]: p["evidence"]["verified_parent"]
               for p in package["parents"]}
    checked = validate_response_shape(response, authorized_unit_ids=set(parents)).model_dump()
    quotations = quote_check(checked, package)
    cited = sorted({u for c in checked["claims"] for u in c["evidence_unit_ids"]})
    citations = [{"unit_id": uid, "native_citations_present": bool(parents[uid].get("citation_locators")),
                  "precision": "NATIVE_LOCATORS_ONLY_NO_PRECISION_UPGRADE"} for uid in cited]
    quotes = quotations["checks"]
    return {"checks": [
        {"check": "Response schema and field/status relationships", "status": "MEASURED", "outcome": "PASS"},
        {"check": "Authorized included Unit IDs; no omitted/example references", "status": "MEASURED",
         "outcome": "PASS", "numerator": len(cited), "denominator": len(cited)},
        {"check": "Verbatim quotations in publisher source fields", "status": "MEASURED",
         "outcome": "PASS" if not quotes or quotations["all_verbatim"] else "FAIL",
         "numerator": sum(q["status"] == "VERBATIM_SOURCE_MATCH" for q in quotes),
         "denominator": len(quotes)},
        {"check": "Native citation references on cited parents", "status": "MEASURED",
         "outcome": "PASS" if all(c["native_citations_present"] for c in citations) else "FAIL",
         "numerator": sum(c["native_citations_present"] for c in citations), "denominator": len(citations)}],
        "quote_checks": quotations, "citation_checks": citations, "cited_unit_ids": cited,
        "structural_validation": "PASS", "semantic_entailment": "NOT_CERTIFIED",
        "source_authority": "REQUIRES_PUBLIC_LIVE_VALIDATOR_NOT_THIS_FIXTURE_HELPER"}


class PostGenerationValidator:
    def __init__(self, evidence_service):
        from tools.generation.qualifications import QualificationValidator

        # Existing validator enforces the exact real explicitly selected service.
        self.qualifications = QualificationValidator(evidence_service)
        self.service = evidence_service
        self.quote_check = quote_reader(evidence_service.root)

    def validate(self, response, package, original_m7_result, *, question):
        from tools.retrieval.contract import parameters

        response_before, package_before = digest(response), digest(package)
        cfg = original_m7_result["parameters"]
        normalized, _ = parameters(question, original_m7_result["retrieval_mode"], cfg["top_k"],
                                   cfg["candidate_depth"], cfg["rrf_k"], cfg["filters"],
                                   self.service.inventory)
        if original_m7_result.get("query_sha256") != hashlib.sha256(normalized.encode()).hexdigest():
            raise ArtifactError("QUESTION_SOURCE_BINDING_MISMATCH")
        # Public native qualification path reassembles and compares the complete
        # M8 package, including publications, source content, warnings and citations.
        qualification = self.qualifications.validate(response, package, original_m7_result)
        result = assess_structure(response, package, self.quote_check)
        result["checks"].insert(0, {"check": "Live M8 source/publication/question bindings",
                                    "status": "MEASURED", "outcome": "PASS"})
        status = qualification["status"]
        result["checks"].append({"check": "Mandatory user-facing qualification disclosure",
                                 "status": "INDETERMINATE" if "UNDETERMINED" in status else "MEASURED",
                                 "outcome": status})
        failures = [c for c in result["checks"] if c.get("outcome") == "FAIL"]
        missing = status == "QUALIFICATIONS_MISSING"
        result.update(schema=VERSION, M8_package_sha256=digest(package), response_sha256=digest(response),
                      qualification_status=status, qualification_assessment=qualification,
                      overall_status="FAILED" if failures or missing else
                      "INDETERMINATE" if "UNDETERMINED" in status else "MEASURED",
                      semantic_status="PENDING_REVIEW", fully_validated=False,
                      answer_rewritten=False, model_calls=0, source_integrity="LIVE_M8_VALIDATED")
        result["diagnoses"] = []
        if missing:
            result["diagnoses"].append({"category": "MISSING_QUALIFICATION",
                                        "basis": "Explicit native disclosure missing from response"})
        elif "UNDETERMINED" in status:
            result["diagnoses"].append({"category": "INDETERMINATE",
                                        "basis": "Native user-facing qualification applicability unresolved"})
        if any(c["outcome"] == "FAIL" for c in result["checks"][:5]):
            result["diagnoses"].append({"category": "INVALID_CITATION",
                                        "basis": "Verbatim quote or native locator check failed"})
        self.service.check()
        if digest(response) != response_before or digest(package) != package_before:
            raise ArtifactError("INPUT_MUTATION_DETECTED")
        return copy.deepcopy(result)
