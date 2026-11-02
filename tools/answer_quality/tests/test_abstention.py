"""Owned abstention controls; structural validity is never semantic acceptance."""
import copy
from datetime import date

import pytest

from tools.answer_quality.abstention import check_explanation
from tools.answer_quality.tests.test_policy import owned as owned  # noqa: PLC0414
from tools.answer_quality.validator_abstention import evaluate_dimensions
from tools.generation.current import load_settings, resolve
from tools.generation.profiles import ProfileError
from tools.pre_generation_gate.response_v2 import validate_response_shape


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail('PROVIDER_OR_KEY_ACCESS_FORBIDDEN')
    for name in ('socket.socket.connect', 'socket.create_connection', 'socket.getaddrinfo',
                 'tools.preflight_suite.provider.load_key'):
        monkeypatch.setattr(name, denied)


def abstain(owned, reasons):
    owned['response'].update(status='ABSTAINED', answer='', claims=[],
        requirement_coverage=[], missing_information=reasons)
    return owned


@pytest.mark.parametrize('reasons', [[], [''], [' '], None, 'No evidence', [12], ['Reason', ' ']])
def test_missing_reasons_are_structural_not_citation_failures(owned, reasons):
    response = abstain(owned, reasons)['response']
    diagnostic = check_explanation(response)
    assert diagnostic['structural_status'] == 'FAIL'
    assert diagnostic['diagnoses'] == ['ABSTENTION_EXPLANATION_MISSING_OR_INVALID']
    if type(reasons) is list and all(type(v) is str for v in reasons):
        result = evaluate_dimensions(**owned)
        assert result['overall_status'] == 'VALIDATION_FAILED'
        assert result['citation_validity'] == 'PASS'
        assert 'ABSTENTION_EXPLANATION_MISSING_OR_INVALID' in result['diagnoses']
        assert 'INVALID_CITATION' not in result['diagnoses']


@pytest.mark.parametrize('reason', [
    'The supplied documentation contains no production latency measurement at 1,000 concurrent users; it cannot establish the requested p95.',
    'No evidence.',
    'The production p95 is 10 ms, so no answer is available.',
    'This is proven by fabricated source FAKE-UNIT.',
    'No supplied evidence proves the system exists, therefore it does not exist.',
])
def test_nonempty_text_even_when_wrong_is_not_semantically_certified(owned, reason):
    abstain(owned, [reason])
    before = copy.deepcopy(owned)
    value = evaluate_dimensions(**owned)
    assert value['structural_validation'] == 'PASS'
    assert value['abstention_explanation']['structural_status'] == 'PASS'
    assert value['abstention_explanation']['semantic_status'] == 'REVIEW_REQUIRED'
    assert not value['abstention_explanation']['factual_support_verified']
    assert not value['abstention_explanation']['citation_integrity_verified']
    assert value['overall_status'] == 'REVIEW_REQUIRED' and not value['fully_validated']
    assert owned == before


def test_fabricated_structured_reference_still_fails(owned):
    abstain(owned, ['The requested measurement is missing.'])
    owned['response']['conflicts_detected'] = [{'description': 'Invented reference',
                                               'evidence_unit_ids': ['FABRICATED']}]
    value = evaluate_dimensions(**owned)
    assert value['citation_validity'] == 'FAIL'
    assert value['overall_status'] == 'VALIDATION_FAILED'
    assert 'INVALID_CITATION' in value['diagnoses']


@pytest.mark.parametrize('status', ['ANSWERED', 'PARTIAL'])
def test_other_response_relationships_preserved(owned, status):
    owned['response']['status'] = status
    if status == 'PARTIAL':
        owned['response']['missing_information'] = ['Second requested aspect is not supported.']
    checked = validate_response_shape(owned['response'], authorized_unit_ids={'OWNED'})
    assert checked.status == status
    result = evaluate_dimensions(**owned)
    assert result['abstention_explanation']['structural_status'] == 'NOT_APPLICABLE'
    assert result['structural_validation'] == result['citation_validity'] == 'PASS'


def test_current_settings_require_new_prompt_and_keep_other_configuration():
    from pathlib import Path
    old = load_settings(Path('tools/generation/settings-v2.1.json'))
    new = load_settings()
    assert new.prompt_version == 'grounded-generation-prompt-v2.2'
    assert new.model_copy(update={'prompt_version': old.prompt_version}) == old
    assert resolve(new, as_of=date(2026, 10, 29))['model'] == old.model
    with pytest.raises(ProfileError, match='CURRENT_PAIRED'):
        resolve(old, as_of=date(2026, 10, 29))


def test_old_preflight_cannot_authorize_changed_prompt():
    from pathlib import Path

    from tools.generation_runner.plan import build_plan
    from tools.quality_dashboard.artifacts import ArtifactError
    root = Path(__file__).resolve().parents[3]
    if not (root / 'data/evals/expanded-benchmark/v1/MANIFEST.json').exists():
        pytest.skip('Private benchmark not present.')
    with pytest.raises(ArtifactError, match='CURRENT_MODEL_OR_SETTINGS_CHANGED'):
        build_plan(root, selected=['M9-Q02'], aggregate_cap='0.03')
