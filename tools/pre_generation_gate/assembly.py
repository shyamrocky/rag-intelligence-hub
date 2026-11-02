"""Canonical entry point for NEW experimental preparations; v2 is the default.

Versioned implementation modules remain immutable historical replay routes.
This module selects no retrieval release, Top-K, evidence budget or generator.
"""

from tools.pre_generation_gate.prompt_v2 import PromptAssemblyGate as HistoricalV1PromptAssemblyGate
from tools.pre_generation_gate.prompt_v2 import PromptPreparation
from tools.pre_generation_gate.prompt_v3 import TEMPLATE_VERSION as DEFAULT_TEMPLATE_VERSION
from tools.pre_generation_gate.prompt_v3 import PromptAssemblyGate as GateV2
from tools.pre_generation_gate.response_v2 import SCHEMA_VERSION as DEFAULT_RESPONSE_SCHEMA_VERSION

__all__ = [
    "DEFAULT_RESPONSE_SCHEMA_VERSION",
    "DEFAULT_TEMPLATE_VERSION",
    "HistoricalV1PromptAssemblyGate",
    "PromptAssemblyGate",
]


class PromptAssemblyGate(GateV2):
    """Default paired v2 template/schema with unchanged live M8/readiness checks."""

    def prepare(self, question, package, original_m7_result, *, model_configuration=None,
                **configuration):
        with self._lock:
            prepared = super().prepare(question, package, original_m7_result,
                                       model_configuration=model_configuration, **configuration)
            audit = {k: v for k, v in prepared.audit.items() if k != "audit_sha256"}
            audit["model_configuration_status"] = (
                "NOT_CONFIGURED" if model_configuration is None else
                "DECLARED_UNQUALIFIED" if audit.get("model_configuration") is not None else
                "INVALID_OR_NOT_ASSESSED")
            return PromptPreparation(self._seal(audit), prepared.payload)
