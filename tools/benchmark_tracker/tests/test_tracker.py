"""Verified historical integration and source-free tracker boundary controls."""
import copy
import json
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from tools.benchmark_tracker import adapter
from tools.quality_dashboard.artifacts import ArtifactError, digest, sha

ROOT = Path(__file__).resolve().parents[3]


def denied(*args, **kwargs):
    raise AssertionError('TRACKER_MUST_NOT_EXECUTE_PIPELINE_PROVIDER_OR_APPROVAL')


@pytest.fixture(scope='module')
def tracker():
    with patch('socket.socket.connect', denied), patch('socket.create_connection', denied):
        return adapter.build(ROOT)


def test_all_questions_grouped_once_and_all_attempt_costs_reconcile(tracker):
    assert len(tracker['rows']) == len({r['Question'] for r in tracker['rows']}) == 34
    assert sum(b['Attempt records'] for b in tracker['batches']) == 36
    from decimal import Decimal
    assert sum(Decimal(b['Known estimated API cost USD']) for b in tracker['batches']) == Decimal('0.384996335')
    assert sum(b['Unknown-cost attempts'] for b in tracker['batches']) == 1
    assert next(b for b in tracker['batches'] if b['Stage'] == 'Batch 4')['Attempt records'] == 5


def test_historical_and_rejected_results_not_hidden_or_promoted(tracker):
    rows = {r['Question']: r for r in tracker['rows']}
    assert rows['M9-Q05']['Model status'] == 'ANSWERED'
    assert rows['M9-Q05']['Validation'] == 'INDETERMINATE'
    assert rows['M9-Q05']['Estimated API cost USD'] == '0.011198925'
    assert rows['M9-Q18']['Model status'] == 'ANSWERED'
    assert rows['M9-Q18']['Contract'] == 'CONTRACT_REJECTED'
    assert rows['M9-Q18']['Raw response'] == 'CAPTURED_VERIFIED'
    assert rows['M9-Q12']['Model status'] == 'UNAVAILABLE'
    assert 'HISTORICAL' in rows['M9-Q12']['Raw response']
    for qid in ['R01', 'R02', 'R04']:
        assert rows[qid]['Contract'] == 'CONTRACT_REJECTED'
        assert rows[qid]['Owner review'] == 'DIAGNOSTIC_TRIAGE_ONLY'
        assert rows[qid]['Raw response'] == 'CAPTURED_VERIFIED'
    assert 'UNAUTHORIZED_EVIDENCE_REFERENCE' in rows['R01']['Main findings']


def test_reassessment_and_owner_acceptance_are_separate(tracker):
    rows = {r['Question']: r for r in tracker['rows']}
    assert rows['M9-Q04']['Original validation'] == 'FAILED'
    assert rows['M9-Q04']['Validation'] == 'REVIEW_REQUIRED'
    assert rows['M9-Q04']['Owner review'] == 'OWNER_APPROVED_POC'
    assert rows['R03']['Original validation'] == 'VALIDATION_FAILED'
    assert rows['R03']['Validation'] == 'REVIEW_REQUIRED'
    assert rows['R03']['Owner review'] == 'COMPLETENESS_ACCEPTED / GROUNDING_REVIEW_REQUIRED'
    assert tracker['summary']['independently_validated_answers'] == 0
    assert 'PRIORITY' in rows['M9-Q29']['Main findings']
    assert 'known evidence gap' in rows['R04']['Main findings']


def test_source_payloads_are_not_exported(tracker):
    text = json.dumps(tracker)
    for forbidden in ['supporting_quotes', 'source_content', 'text_parts', 'OPENAI_API_KEY', str(ROOT)]:
        assert forbidden not in text


def test_changed_response_cannot_inherit_owner_approval():
    response = {'status': 'ANSWERED', 'answer': 'First synthetic answer.'}
    attempt = {'question_id': 'SYNTHETIC', 'response': response,
               'audit': {'request_sha256': 'r', 'M8_package_sha256': 'm'}}
    decision = {'question_id': 'SYNTHETIC', 'bindings': {'response_sha256': digest(response),
        'request_sha256': 'r', 'package_sha256': 'm'}, 'decided_at': '2026-10-30T00:00:00Z',
        'status': 'OWNER_APPROVED_POC'}
    assert adapter.review_state(attempt, [(decision, 'fixture')]) == 'OWNER_APPROVED_POC'
    changed = copy.deepcopy(attempt)
    changed['response']['answer'] = 'Different synthetic answer.'
    assert adapter.review_state(changed, [(decision, 'fixture')]) == 'PENDING_REVIEW'


@pytest.mark.parametrize('key', ['question_sha256', 'response_sha256', 'request_sha256', 'M8_package_sha256'])
def test_reassessment_rejects_changed_binding(key):
    attempt = {'response': {'answer': 'synthetic'}, 'audit': {'request_sha256': 'r', 'M8_package_sha256': 'm'}}
    a = {'question_sha256': 'q', 'response_sha256': digest(attempt['response']),
         'request_sha256': 'r', 'M8_package_sha256': 'm'}
    assert adapter.assessment_matches(a, attempt, 'q')
    a[key] = 'tampered'
    assert not adapter.assessment_matches(a, attempt, 'q')


def test_tampered_capture_is_unavailable_not_repaired():
    attempt = {'row': {'audit': {'raw_response_capture': {'status': 'RAW_RESPONSE_CAPTURED'}}},
               'run': {'manifest': {'run_id': 'fixture'}}}
    with patch('tools.generation.response_capture.verify_capture', side_effect=ArtifactError('TAMPERED')):
        assert adapter.capture_status(ROOT, attempt) == 'UNAVAILABLE_OR_UNVERIFIED'
        assert adapter.returned_status(ROOT, attempt)[0] == 'UNAVAILABLE'


def test_corrupt_stage_manifest_fails_closed(tmp_path):
    from shutil import copytree
    copytree(ROOT / adapter.ROLLOUT, tmp_path / adapter.ROLLOUT)
    copytree(ROOT / adapter.BATCHES, tmp_path / adapter.BATCHES)
    plan = tmp_path / adapter.BATCHES / 'batch-07/PLAN_NOT_AUTHORIZED.json'
    plan.write_text('{}')
    with pytest.raises(ArtifactError):
        adapter.stages(tmp_path)


def test_review_successor_cannot_authorize_paid_execution():
    from tools.generation_runner.trust import load_trust, verify_plan_policy
    from tools.generation_trust_anchor import HUMAN_REVIEW_BASELINE, TRUSTED_BASELINES
    _, policy, receipt = load_trust(ROOT, HUMAN_REVIEW_BASELINE, TRUSTED_BASELINES[HUMAN_REVIEW_BASELINE])
    assert not receipt['blocking_findings'] and policy['permitted_question_ids'] == []
    plan = json.loads((ROOT / 'data/evals/generation-runner-reviews/batch07-live-v1/PLAN.json').read_bytes())
    with pytest.raises(ArtifactError):
        verify_plan_policy(plan, policy)


def test_canonical_tracker_home_link_filters_exports_and_inert_navigation():
    tracked = {p: sha(p) for scope in ['data/evals/generation-runner', 'data/evals/generation',
        'data/evals/human-review/local-poc'] for p in (ROOT / scope).rglob('*') if p.is_file()}
    with ExitStack() as stack:
        for name in ['tools.generation_runner.runner.execute', 'tools.preflight_suite.runner.execute',
            'tools.preflight_suite.provider.load_key', 'tools.generation.current.GenerationService.generate',
            'tools.generation.openai_adapter.OpenAIAdapter.invoke', 'tools.generation.openai_adapter.OpenAIAdapter.count',
            'tools.generation.openai_adapter.OpenAIAdapter.verify_model', 'tools.evidence.service.EvidenceService.assemble',
            'tools.evidence.service.EvidenceService.validate', 'tools.human_review.local_poc.decide',
            'tools.human_review.observation_review.decide', 'socket.socket.connect', 'socket.create_connection']:
            stack.enter_context(patch(name, denied))
        app = AppTest.from_file(str(ROOT / 'apps/master_dashboard/canonical.py'), default_timeout=150).run()
        assert not app.exception
        assert any(x.label == 'Final Generation Benchmark Tracker' for x in app.get('page_link'))
        app.switch_page('views/final_generation_benchmark.py').run()
        assert not app.exception
        assert app.title[0].value == 'Final Generation Benchmark Tracker'
        assert len(app.session_state['final_benchmark_tracker']['rows']) == 34
        app.selectbox(key='tracker_stage').select('Batch 7').run()
        assert not app.exception and len(app.selectbox(key='tracker_question').options) == 4
        app.selectbox(key='tracker_validation').select('Contract rejected').run()
        assert not app.exception and set(app.selectbox(key='tracker_question').options) == {'R01', 'R02', 'R04'}
        app.selectbox(key='tracker_stage').select('Historical').run()
        assert not app.exception
        app.selectbox(key='tracker_validation').select('All results').run()
        assert not app.exception and app.selectbox(key='tracker_question').value == 'M9-Q05'
        next(b for b in app.button if b.label == 'Refresh verified telemetry').click().run()
        assert not app.exception
        app.switch_page('views/explorer.py').run()
        assert not app.exception and 'RAG Retrieval Pipeline Explorer' in str(app.get('iframe')[0].proto)
        app.switch_page('views/preflight_quality.py').run()
        assert not app.exception and len(app.selectbox(key='expanded_question').options) == 34
    assert all(sha(p) == h for p, h in tracked.items())
