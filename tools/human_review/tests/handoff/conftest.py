"""Owned synthetic native publications, never real owner decisions or provider access."""
import copy
import hashlib

import pytest

from tools.human_review import handoff
from tools.human_review.tests.poc.conftest import (
    no_signing_or_human_authentication as no_signing_or_human_authentication,  # noqa: PLC0414
)
from tools.human_review.tests.poc.conftest import poc_context as poc_context  # noqa: PLC0414
from tools.preflight_suite.artifacts import now, save
from tools.quality_dashboard.artifacts import digest, sha


def publish(context, *, status='ANSWERED', validation='REVIEW_REQUIRED', name='native-owned', mode='live'):
    root = context['root']
    row = copy.deepcopy(context['row'])
    if status == 'ABSTAINED':
        row['response'].update(status='ABSTAINED', answer='', claims=[],
            missing_information=['No supplied support for the synthetic requirement.'], requirement_coverage=[])
    elif status == 'PARTIAL':
        row['response'].update(status='PARTIAL', missing_information=['Second component is not supported.'])
    row.update(mode=mode, status='GENERATED_SYNTHETIC_FIXTURE', provider_calls=0,
        post_validation={'schema': 'post-generation-validation-2.0', 'overall_status': validation,
            'structural_validation': 'PASS', 'citation_validity': 'PASS',
            'source_integrity': 'LIVE_M8_VALIDATED', 'quotation_fidelity': [],
            'qualification_status': 'QUALIFICATION_APPLICABILITY_UNDETERMINED',
            'diagnoses': ['SUBSTANTIVE_MISQUOTATION'] if validation == 'VALIDATION_FAILED' else []})
    plan = {'questions': [{'question_id': row['question_id']}], 'owned_fixture': True}
    plan['plan_sha256'] = digest(plan)
    run = root / 'data/evals/generation-runner' / name
    save(run / 'questions' / row['question_id'] / 'RESULT.json', row)
    save(run / 'PLAN.json', plan)
    save(run / 'RESULTS.json', {'mode': mode, 'questions': [row]})
    save(run / 'MANIFEST.json', {'schema': 'grounded-generation-runner-1.0', 'mode': mode,
        'status': 'SEALED_PENDING_OWNER_REVIEW', 'run_id': name, 'created_at': now(),
        'plan_sha256': plan['plan_sha256'], 'question_ids': [row['question_id']],
        'files': {p.relative_to(run).as_posix(): sha(p) for p in run.rglob('*') if p.is_file()}})
    return run, row


@pytest.fixture
def native(poc_context, monkeypatch):
    c = poc_context
    question = c['package']['question']
    monkeypatch.setattr(handoff, 'inventory_context', lambda _:
        (None, {'SYNTHETIC-Q1': {'question': question}}, {}, {}))
    monkeypatch.setattr(handoff, 'review_trust', lambda: c['package']['trust'])
    assert hashlib.sha256(question.encode()).hexdigest() == c['row']['question_sha256']
    return c


def assessment_input(c, entry, *, assessment=None, name='owned-assessment'):
    value = assessment or c['package']['assessment_draft']
    base = c['root'] / handoff.INPUTS / name
    save(base / 'ASSESSMENT.json', value)
    save(base / 'INPUT.json', {'question': c['package']['question'], 'response_source': entry['source'],
        'supporting_artifacts': {}, 'layout_reviews': []})
    save(base / 'MANIFEST.json', {'schema': 'human-review-assessment-input-1.0', 'created_at': now(),
        'files': {p.name: sha(p) for p in base.iterdir()}})
    return base
