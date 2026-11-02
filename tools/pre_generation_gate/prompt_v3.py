"""Opt-in prompt anatomy v2; reuse sealed gate validation without editing v1."""

import copy
import json
from pathlib import Path

from tools.pre_generation_gate.contract import digest
from tools.pre_generation_gate.prompt_v2 import EVIDENCE_PREFIX, PromptPreparation
from tools.pre_generation_gate.prompt_v2 import PromptAssemblyGate as GateV1
from tools.pre_generation_gate.response_v2 import (
    SCHEMA_VERSION,
    response_schema,
    synthetic_example,
    validate_synthetic_example,
)

VERSION = "prompt-quality-gate-3.0"
TEMPLATE_VERSION = "grounded-generation-prompt-v2"
_DEFAULT_SCHEMA = object()
TEMPLATE = Path(__file__).with_name("grounded-generation-prompt-v2.txt").read_text()
validate_synthetic_example()
SYSTEM = TEMPLATE.replace("{synthetic_response_json}", json.dumps(
    synthetic_example(), ensure_ascii=False, separators=(",", ":")))
ANATOMY = {
    "Role": "system/ROLE", "Goal / Task": "system/GOAL / TASK",
    "Context": "system/CONTEXT + exact question + unchanged evidence message",
    "Instructions": "system/INSTRUCTIONS", "Constraints": "system/CONSTRAINTS",
    "Examples": "system/EXAMPLE (one synthetic demonstration only)",
    "Output Format": "system/OUTPUT FORMAT + separate response_format schema",
}


def build_request(question, package, schema, model_configuration):
    """Mechanical construction only; live source checks belong to prepare()."""
    if digest(schema) != digest(response_schema()):
        raise ValueError("missing_modified_or_cross_version_response_schema")
    evidence = package["llm_evidence"]
    if type(evidence) is not str or not evidence:
        raise ValueError("missing_authorized_evidence_text")
    return {"messages": [{"role": "system", "content": SYSTEM},
        {"role": "user", "content": question},
        {"role": "user", "content": EVIDENCE_PREFIX + evidence}],
        "response_format": {"schema_version": SCHEMA_VERSION, "schema": copy.deepcopy(schema)},
        "generation_configuration": copy.deepcopy(model_configuration)}


class PromptAssemblyGate(GateV1):
    """Explicit v2 opt-in; inherited live M8/query/config controls stay authoritative."""

    def prepare(self, question, package, original_m7_result, *, model_configuration=None,
                schema=_DEFAULT_SCHEMA):
        with self._lock:
            # No v1 schema/template/source file changes. Parent validates source,
            # question and config live, before the separately versioned rendering.
            base = super().prepare(question, package, original_m7_result,
                                   model_configuration=model_configuration)
            if base.payload is None:
                audit = {k: copy.deepcopy(v) for k, v in base.audit.items() if k != "audit_sha256"}
                audit.update(schema=VERSION, template_version=TEMPLATE_VERSION,
                             response_schema_version=SCHEMA_VERSION)
                return PromptPreparation(self._seal(audit))
            try:
                selected_schema = response_schema() if schema is _DEFAULT_SCHEMA else copy.deepcopy(schema)
                schema_matches = digest(selected_schema) == digest(response_schema())
            except (TypeError, ValueError, RecursionError):
                schema_matches = False
            if not schema_matches:
                return self._blocked("BLOCKED_CONFIGURATION", "RESPONSE_SCHEMA_UNVERIFIED",
                                     evidence_validated=True)
            p = base.payload["m8_package"]
            ids = [r["evidence"]["unit_id"] for r in p["parents"]]
            if any(i.startswith("EXAMPLE-") for i in ids):
                return self._blocked("BLOCKED_INTEGRITY", "EXAMPLE_ID_IN_LIVE_EVIDENCE",
                                     evidence_validated=True)
            request = build_request(question, p, selected_schema, base.audit["model_configuration"])
            if request["messages"][2] != base.payload["request"]["messages"][2]:
                return self._blocked("BLOCKED_INTEGRITY", "EVIDENCE_BYTES_CHANGED")
            try:
                self._service.check()
            except (ValueError, TypeError, KeyError, OSError):
                return self._blocked("BLOCKED_INTEGRITY", "SOURCE_BINDINGS_CHANGED_DURING_BUILD")
            payload = {"schema": VERSION, "request": request, "m8_package": p,
                "template_version": TEMPLATE_VERSION, "response_schema_version": SCHEMA_VERSION}
            audit = {k: copy.deepcopy(v) for k, v in base.audit.items() if k != "audit_sha256"}
            audit.update(schema=VERSION, template_version=TEMPLATE_VERSION,
                template_sha256=digest(SYSTEM), response_schema_version=SCHEMA_VERSION,
                response_schema_sha256=digest(selected_schema), request_sha256=digest(request),
                payload_sha256=digest(payload), exact_messages_sha256=digest(request["messages"]),
                prompt_anatomy=ANATOMY.copy(), synthetic_example_count=1,
                example_ids_authorized_for_live_request=False,
                model_reported_coverage_is_verified=False,
                model_reported_conflicts_are_verified=False)
            return PromptPreparation(self._seal(audit), payload)

    def _blocked(self, status, reason, *, evidence_validated=False):
        base = super()._blocked(status, reason, evidence_validated=evidence_validated)
        audit = {k: v for k, v in base.audit.items() if k != "audit_sha256"}
        audit.update(schema=VERSION, template_version=TEMPLATE_VERSION,
                     response_schema_version=SCHEMA_VERSION)
        return PromptPreparation(self._seal(audit))
