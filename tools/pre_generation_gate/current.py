"""Current experimental v2.2 selection; historical v2.1 stays explicitly selectable."""
from .prompt_v21 import PromptAssemblyGate as HistoricalV21PromptAssemblyGate
from .prompt_v22 import (
    DEFAULT_RESPONSE_SCHEMA_VERSION,
    DEFAULT_TEMPLATE_VERSION,
    SYSTEM,
    TEMPLATE,
    VERSION,
    PromptAssemblyGate,
)

__all__ = [
    "DEFAULT_RESPONSE_SCHEMA_VERSION",
    "DEFAULT_TEMPLATE_VERSION",
    "SYSTEM",
    "TEMPLATE",
    "VERSION",
    "HistoricalV21PromptAssemblyGate",
    "PromptAssemblyGate",
]
