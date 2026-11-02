"""Versioned abstention successor; historical v2.1 remains explicitly replayable."""

import copy
import json
from pathlib import Path

from tools.pre_generation_gate.contract import digest
from tools.pre_generation_gate.prompt_v2 import PromptPreparation
from tools.pre_generation_gate.prompt_v21 import (
    PromptAssemblyGate as HistoricalV21PromptAssemblyGate,
)
from tools.pre_generation_gate.response_v2 import SCHEMA_VERSION, synthetic_example

DEFAULT_TEMPLATE_VERSION = "grounded-generation-prompt-v2.2"
DEFAULT_RESPONSE_SCHEMA_VERSION = SCHEMA_VERSION
VERSION = "prompt-quality-gate-3.2"
TEMPLATE = Path(__file__).with_name("grounded-generation-prompt-v2.2.txt").read_text()
SYSTEM = TEMPLATE.replace("{synthetic_response_json}", json.dumps(
    synthetic_example(), ensure_ascii=False, separators=(",", ":")))


class PromptAssemblyGate(HistoricalV21PromptAssemblyGate):
    """Reuse real live M8 validation; change only versioned system instructions."""

    def prepare(self, question, package, original_m7_result, *, model_configuration=None,
                **configuration):
        with self._lock:
            base = super().prepare(question, package, original_m7_result,
                                   model_configuration=model_configuration, **configuration)
            audit = {k: copy.deepcopy(v) for k, v in base.audit.items() if k != "audit_sha256"}
            audit.update(schema=VERSION, template_version=DEFAULT_TEMPLATE_VERSION,
                         response_schema_version=SCHEMA_VERSION, template_sha256=digest(SYSTEM),
                         provider_requalification_required=True,
                         historical_token_receipts_reusable=False)
            if base.payload is None:
                return PromptPreparation(self._seal(audit))
            payload = copy.deepcopy(base.payload)
            payload.update(schema=VERSION, template_version=DEFAULT_TEMPLATE_VERSION)
            payload["request"]["messages"][0]["content"] = SYSTEM
            if payload["request"]["messages"][1:] != base.payload["request"]["messages"][1:]:
                raise ValueError("QUESTION_OR_EVIDENCE_CHANGED")
            self._service.check()
            audit.update(request_sha256=digest(payload["request"]), payload_sha256=digest(payload),
                         exact_messages_sha256=digest(payload["request"]["messages"]),
                         qualification_validation="SEPARATE_LIVE_M8_BOUND_POST_GENERATION_CHECK")
            return PromptPreparation(self._seal(audit), payload)
