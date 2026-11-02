"""Source-free deterministic contracts; no relevance labels or evidence admission."""

import hashlib
import json
import re
from dataclasses import asdict, dataclass

VERSION = "pre-generation-gate-1.0"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class GateConfiguration:
    """Only the actually implemented method is selectable; no implicit model fallback."""

    version: str = VERSION
    assessment_method: str = "deterministic-controls-semantic-unavailable-1.0"

    def __post_init__(self):
        if (self.version != VERSION or self.assessment_method !=
                "deterministic-controls-semantic-unavailable-1.0"):
            raise ValueError("unimplemented_gate_configuration")

    def record(self):
        return asdict(self)


def question_requirements(question):
    """Preserve the whole request plus explicit interrogative clauses, never gold groups.

    This is a conservative syntactic decomposition, not semantic interpretation.
    The complete question remains mandatory so an unparsed comparison, enumeration
    or condition cannot disappear. Every component remains epistemically uncertain.
    """
    if (type(question) is not str or not question.strip() or len(question) > 16384
            or any(0xD800 <= ord(c) <= 0xDFFF for c in question)):
        raise ValueError("invalid_question")
    question = question.strip()
    pieces = re.split(r"(?:[?;]\s*|,?\s+and\s+)(?=(?:what|why|how|when|where|which|who)\b)",
                      question, flags=re.IGNORECASE)
    texts = [question]
    if len(pieces) > 1:
        texts += [p.strip(" ,;?") for p in pieces if p.strip(" ,;?")]
    return [{"requirement_id": f"requirement-{i}", "text": text, "mandatory": True,
             "origin": "COMPLETE_QUESTION" if i == 1 else "EXPLICIT_INTERROGATIVE_CLAUSE",
             "interpretation": "SYNTACTIC_ONLY_SEMANTIC_SCOPE_UNCONFIRMED"}
            for i, text in enumerate(dict.fromkeys(texts), 1)]


def reduce_assessment(requirements, assessments, *, qualified, evidence_present,
                      recoverable=False, blocking=False):
    """Pure decision contract; synthetic semantic assertions are NOT a runtime assessor.

    The actual gate always supplies qualified=False. A future assessor requires
    separate implementation and qualification; callers cannot inject assertions
    into ValidationGate.assess.
    """
    ids = [r["requirement_id"] for r in requirements]
    if (not ids or len(ids) != len(set(ids)) or len(assessments) != len(ids)
            or [a["requirement_id"] for a in assessments] != ids
            or any(a["support"] not in {"SUPPORTED", "PARTIAL", "UNSUPPORTED", "UNKNOWN"}
                   for a in assessments)
            or any(a["support"] in {"SUPPORTED", "PARTIAL"} and not a["references"]
                   for a in assessments)
            or any(type(flag) is not bool for flag in
                   (qualified, evidence_present, recoverable, blocking))):
        raise ValueError("invalid_assessment_contract")
    if blocking or not evidence_present:
        return "ABSTAIN"
    if (qualified and any(r["mandatory"] for r in requirements)
            and all(a["support"] == "SUPPORTED" for r, a in
                    zip(requirements, assessments, strict=True) if r["mandatory"])):
        return "PROCEED"
    return "RETRIEVE_MORE" if qualified and recoverable else "ABSTAIN"
