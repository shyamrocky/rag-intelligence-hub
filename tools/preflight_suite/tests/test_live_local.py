"""Real M8/gate, existing source readers; mock token endpoint only, no live API."""
import copy
from datetime import date
from pathlib import Path

import httpx

from tools.evidence.service import EvidenceService
from tools.generation.current import GenerationService
from tools.generation.tests.test_adapter import sdk_fixture
from tools.pre_generation_gate.current import PromptAssemblyGate
from tools.pre_generation_gate.gate import M8_SELECTOR, M8_SHA
from tools.preflight_suite.artifacts import COMPLETION, baseline
from tools.preflight_suite.provider import CountOnlyAdapter
from tools.preflight_suite.runner import assemble, configuration, equivalence, recipe

ROOT = Path(__file__).resolve().parents[3]


def test_real_local_replay_and_mock_model_qualification():
    store, rows = baseline(ROOT)
    row = rows['M9-Q01']
    result = store.json(COMPLETION + '/m7/M9-Q01.json')
    evidence = EvidenceService(ROOT, selector=M8_SELECTOR, selector_sha256=M8_SHA)
    gate = PromptAssemblyGate(evidence)
    settings, profile, pricing = configuration(ROOT, day=date(2026, 10, 28))
    before = copy.deepcopy(result)
    package, prepared = assemble(evidence, gate, row, result)
    a, request = recipe(row, result, package, prepared, settings, profile)
    again = gate.prepare(row['question'], package, result)
    b, repeated = recipe(row, result, package, again, settings, profile)
    equivalence(a, b)
    assert request == repeated and before == result
    assert prepared.payload['request']['messages'][1]['content'] == row['question']
    assert package['llm_evidence'] in prepared.payload['request']['messages'][2]['content']
    calls = []

    def handler(req):
        calls.append(req.url.path)
        if '/models/' in req.url.path:
            return httpx.Response(200, json={'id': settings.model, 'created': 0, 'object': 'model', 'owned_by': 'owned'})
        assert req.url.path == '/v1/responses/input_tokens'
        return httpx.Response(200, json={'object': 'response.input_tokens', 'input_tokens': 1000})

    service = GenerationService(gate, CountOnlyAdapter(client=sdk_fixture(handler)), settings,
                                pricing=pricing, as_of=date(2026, 10, 28))
    local = service.dry_run(prepared, row['question'], package, result)
    assert not calls and not local.audit['generation_executed']
    qualified = service.dry_run(prepared, row['question'], package, result,
                               allow_provider_preflight=True, allow_source_transfer=True)
    assert qualified.audit['status'] == 'READY'  # OWNED MOCK only, not actual qualification
    assert len(calls) == 2 and qualified.audit['generator_input_tokens'] == 1000
    assert not qualified.audit['generation_executed']
