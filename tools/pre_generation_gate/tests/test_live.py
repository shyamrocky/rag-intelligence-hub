"""Actual M8 validation. No retrieval, model inference or fabricated source authority."""

import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.indexing.m5_index import no_network, sha
from tools.pre_generation_gate.contract import GateConfiguration, digest
from tools.pre_generation_gate.gate import M8_SELECTOR, M8_SHA, ValidationGate

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def service():
    from tools.evidence.service import EvidenceService

    no_network()
    return EvidenceService(ROOT, selector=M8_SELECTOR, selector_sha256=M8_SHA)


@pytest.fixture(scope="session")
def sample(service):
    path = ROOT / "data/evals/m8-delivery/experiment-v1/common.py"
    spec = importlib.util.spec_from_file_location("gate_control_replay", path)
    common = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(common)
    ranking = json.loads((ROOT / "data/evals/ranking/phase3-experiment-v1/rankings/R01-rrf.json"
                          ).read_bytes())
    return common.replay(ranking, [ranking["candidates"][0]["chunk_id"]],
                         service.m7, service.inventory)


@pytest.fixture(scope="session")
def question():
    return "What is RAG, and why would I use it instead of asking an LLM directly?"


@pytest.fixture(scope="session")
def package(service, sample):
    return service.assemble(sample, token_budget=128000)


@pytest.fixture(scope="session")
def gate(service):
    return ValidationGate(service, configuration=GateConfiguration())


def test_real_valid_evidence_is_not_semantic_pass(gate, question, package, sample):
    before = digest(package), digest(sample)
    output = gate.assess(question, package, sample)
    assert output["source_integrity"] == "LIVE_M8_VALIDATED"
    assert output["decision"] == "ABSTAIN" and output["status"] == "INDETERMINATE"
    assert not output["gate_criteria_passed"] and not output["generation_authorized"]
    assert all(a["support"] == "UNKNOWN" and not a["references"] for a in output["assessments"])
    assert before == (digest(package), digest(sample))
    assert output == gate.assess(question, package, sample)


@pytest.mark.parametrize("kind", [
    "source", "context", "qualification", "citation", "publication", "precision",
    "warning", "membership", "classification", "llm_text", "budget", "parent",
])
def test_tampered_authoritative_input_fails_live_validation(gate, question, package, sample, kind):
    altered = copy.deepcopy(package)
    block = altered["parents"][0]["evidence"]
    parent = block["verified_parent"]
    context = parent["consumer"]["llm_context"]
    if kind == "source":
        context["source_content"] = [{"kind": "SOURCE_CONTENT", "text": "forged"}]
    elif kind == "context":
        context["required_context"] = ["invented"]
    elif kind == "qualification":
        context["qualification"] = {}
    elif kind == "citation":
        parent["citation_locators"] = []
    elif kind == "publication":
        parent["publication_identity"] = {"version": "historical"}
    elif kind == "precision":
        block["citation_precision"]["parent"] = "EXACT_UNSUPPORTED_COORDINATES"
    elif kind == "warning":
        context["qa_observations"] = ["warning_removed_or_changed"]
    elif kind == "membership":
        parent["memberships"] = []
    elif kind == "classification":
        parent["admission_status"] = "HOLD"
    elif kind == "llm_text":
        altered["llm_evidence"] = "detached source text"
    elif kind == "budget":
        altered["budget"]["exact_llm_evidence_tokens"] = 0
    elif kind == "parent":
        parent["unit_id"] = "forged"
    output = gate.assess(question, altered, sample)
    assert output["status"] == "VALIDATION_ERROR" and output["decision"] == "ABSTAIN"
    assert output["semantic_sufficiency"] == "NOT_ASSESSED"
    assert output["evidence_binding"] is None


@pytest.mark.parametrize("question", [None, "", "wrong bound question", "bad\ud800", "x" * 16385])
def test_question_binding_failures(gate, package, sample, question):
    output = gate.assess(question, package, sample)
    assert output["status"] == "VALIDATION_ERROR" and not output["gate_criteria_passed"]


def test_M7_normalization_reused(gate, question, package, sample):
    assert gate.assess("  " + question + "\n", package, sample) == gate.assess(
        question, package, sample)


@pytest.mark.parametrize("field,value", [
    ("release_identity", "historical"), ("candidates", []), ("query_sha256", "0" * 64),
    ("index_release_bindings", {}), ("source_content", "raw fallback"),
])
def test_changed_candidate_transport_not_trusted(gate, question, package, sample, field, value):
    altered = copy.deepcopy(sample)
    altered[field] = value
    output = gate.assess(question, package, altered)
    assert output["status"] == "VALIDATION_ERROR"


@pytest.mark.parametrize("package", [None, [], {}, {"verification": True}, "source text"])
def test_detached_or_malformed_evidence_rejected(gate, question, sample, package):
    assert gate.assess(question, package, sample)["status"] == "VALIDATION_ERROR"


def test_empty_actual_M8_package_is_not_integrity_failure(gate, service, sample, question):
    empty = copy.deepcopy(sample)
    empty["candidates"] = []
    empty["parameters"]["top_k"] = 1
    package = service.assemble(empty, token_budget=128000)
    output = gate.assess(question, package, empty)
    assert output["status"] == "INDETERMINATE" and output["decision"] == "ABSTAIN"
    assert output["source_integrity"] == "LIVE_M8_VALIDATED"
    assert "NO_INCLUDED_AUTHORIZED_EVIDENCE" in output["blocking_reasons"]


def test_atomic_budget_omission_is_surfaced_not_claimed_relevant(gate, service, sample, question):
    package = service.assemble(sample, token_budget=1)
    output = gate.assess(question, package, sample)
    assert package["status"] == "INSUFFICIENT_EVIDENCE_FOR_BUDGET"
    assert output["evidence_binding"]["omitted"] == package["diagnostics"]["omitted"]
    assert "BUDGET_OMISSIONS_PRESENT_RELEVANCE_UNKNOWN" in output["blocking_reasons"]
    assert all(not o["partial_parent_returned"] for o in output["evidence_binding"]["omitted"])


@pytest.mark.parametrize("question", [
    "Compare oak and pine for building an outdoor staircase.",
    "Explain RAG, list its benefits, and specify today's weather in Iceland.",
    "Does this source establish every requested fact without any uncertainty?",
])
def test_semantic_negative_controls_remain_unknown_not_falsely_detected(gate, service, sample, question):
    # Real M8 parent, manufactured query binding for a CONTROL, not a search result.
    value = copy.deepcopy(sample)
    value["query_sha256"] = sha(question.encode())
    value["diagnostics"] = {"origin": "AUTHORED_SEMANTIC_CONTROL_NOT_REAL_RETRIEVAL"}
    package = service.assemble(value, token_budget=128000)
    output = gate.assess(question, package, value)
    assert output["source_integrity"] == "LIVE_M8_VALIDATED"
    assert output["status"] == "INDETERMINATE" and output["decision"] == "ABSTAIN"
    assert not any(a["support"] != "UNKNOWN" for a in output["assessments"])


def test_fake_validation_service_cannot_authorize():
    fake = SimpleNamespace(validate=lambda *args: True, selector=M8_SELECTOR, selector_sha256=M8_SHA)
    with pytest.raises(ValueError):
        ValidationGate(fake, configuration=GateConfiguration())
