"""Real sealed R03 comparison, no reassembly/provider or historical mutation."""
import json
from pathlib import Path

import pytest

from tools.answer_quality.fidelity import source_fields
from tools.answer_quality.fidelity_v21 import match_quote
from tools.quality_dashboard.artifacts import Store, sha

ROOT=Path(__file__).resolve().parents[3]
BASE='data/evals/generation-runner-reviews/r03-stabilization-v1'


def test_r03_six_quotations_and_separate_original_failure():
    if not (ROOT/BASE/'MANIFEST.json').exists():
        pytest.skip('Private R03 source-reviewed result absent.')
    store=Store(ROOT);store.manifest(BASE+'/MANIFEST.json',schema='answer-quality-evaluation-2.0')
    a=store.json(BASE+'/ASSESSMENT.json');m=store.json(BASE+'/QUOTATION_MATRIX.json')
    assert a['overall_status']=='REVIEW_REQUIRED' and not a['fully_validated']
    assert a['original_native_status']=='VALIDATION_FAILED'
    assert a['raw_exact_matches']=={'numerator':3,'denominator':6}
    assert [q['outcome'] for q in m['original_policy_replay']].count('SUBSTANTIVE_MISMATCH')==1
    assert all(q['outcome'] in {'EXACT_MATCH','PRESENTATION_EQUIVALENT'} for q in m['successor'])
    assert a['known_missing_groups']==['R03-G1'] and a['owner_acceptance'] is False
    assert [x['outcome'] for x in a['additional_assertions']]==['PARTIALLY_SUPPORTED','INDETERMINATE']
    assert a['assessment']['response_status_appropriate'] is None
    for q in m['successor']:
        assert q['source']['start']<q['source']['end']
        assert 'original_text' not in q['source']


def test_r03_actual_same_unit_source_spans_and_tamper_controls():
    path=ROOT/'workspace/rag-implementation/v1/r03-stabilization-v1/FRESH_PRIVATE.json'
    if not path.exists():
        pytest.skip('Protected reconstruction unavailable; do not invent source evidence.')
    v=json.loads(path.read_bytes());ps={p['evidence']['unit_id']:p['evidence']['verified_parent'] for p in v['evidence']['parents']}
    layouts=json.loads((ROOT/BASE/'SOURCE_REVIEW.json').read_bytes())['reviews']
    for c in v['row']['response']['claims']:
        for q in c['supporting_quotes']:
            p=ps[q['evidence_unit_id']]
            r=match_quote(q['quote'],q['evidence_unit_id'],p,layout_reviews=layouts)
            assert r['outcome'] in {'EXACT_MATCH','PRESENTATION_EQUIVALENT'}
            fields=dict(source_fields(p));s=r['source']
            assert sha(path) and s['original_text']==fields[s['pointer']][s['start']:s['end']]
            assert match_quote(q['quote'],'FABRICATED',None)['outcome']=='SOURCE_NOT_FOUND'
