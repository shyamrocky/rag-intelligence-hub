"""Owned synthetic experiment records: no real generation or source authorization."""
import json
from pathlib import Path

import pytest

from tools.pre_generation_gate.response_v2 import synthetic_example
from tools.quality_dashboard.adapter import FREEZE
from tools.quality_dashboard.artifacts import Store, sha
from tools.quality_dashboard.expanded_adapter import (
    MANIFEST_SHA,
    discover_expanded_generation,
    discover_expanded_validations,
    validate_future_binding,
)

ROOT = Path(__file__).resolve().parents[3]


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


@pytest.fixture
def synthetic_record(tmp_path, monkeypatch):
    # Scope this test to discovery, not native gateway qualification. The public
    # contract itself is exercised separately and never replaced in application code.
    monkeypatch.setattr('tools.quality_dashboard.expanded_adapter.validate_future_binding', lambda *args: None)
    root = tmp_path
    base = root/'data/evals/generation/owned-v1'
    answer = json.loads(json.dumps(synthetic_example()).replace('EXAMPLE-UNIT-001','UNIT-owned-fixture'))
    prep = {'M8_package_sha256':'fixture-package','included_parent_ids':['UNIT-owned-fixture']}
    audit = {'schema':'generation-result-1.0','generation_executed':True,'source_integrity':'LIVE_M8_VALIDATED',
             'response_status':'completed','status':'GENERATED_STRUCTURE_VALID','response_schema':'grounded-response-2.0',
             'M8_package_sha256':'fixture-package','model':'owned-fixture-model','prompt_template':'grounded-generation-prompt-v2.1',
             'request_sha256':'0'*64,'response_id':'owned-response-1',
             'usage':{'usage_status':'MEASURED_API_USAGE','input_tokens':20,'output_tokens':8,'total_tokens':28}}
    values={'GENERATED_RESPONSE.json':answer,'GENERATION_AUDIT.json':audit,
            'PREPARATION_AUDIT.json':prep,'M7_RESULT.json':{'parameters':{'top_k':30}}}
    for name,value in values.items():save(base/name,value)
    manifest={'schema':'quality-generation-experiment-1.0','status':'COMPLETED_SEALED','question_id':'M9-Q01',
              'expanded_benchmark_manifest_sha256':MANIFEST_SHA,'dataset_freeze_manifest_sha256':FREEZE,
              'files':{name:sha(base/name) for name in values},'date':'2026-10-28'}
    save(base/'MANIFEST.json',manifest)
    questions={'M9-Q01':{'question_text':'Owned fixture question'}}
    records={'M9-Q01':{'attempts':[],'latest':None}}
    return root,base,manifest,questions,records


def test_automatic_future_c_question_discovery(synthetic_record):
    root,base,_manifest,questions,records=synthetic_record
    store=Store(root);rejected=[]
    discover_expanded_generation(store,records,questions,rejected)
    assert not rejected
    assert records['M9-Q01']['latest']['completed']
    assert records['M9-Q01']['latest']['response']['status']=='ANSWERED'
    # Repeated refs with same provider response identity are not another result.
    discover_expanded_generation(store,records,questions,rejected)
    assert len(records['M9-Q01']['attempts'])==1
    result={'schema':'post-generation-validation-1.0','question_id':'M9-Q01',
        'response_file_sha256':sha(base/'GENERATED_RESPONSE.json'),'M8_package_sha256':'fixture-package',
        'overall_status':'INDETERMINATE','qualification_status':'QUALIFICATION_APPLICABILITY_UNDETERMINED',
        'semantic_status':'PENDING_REVIEW','fully_validated':False,
        'checks':[{'check':'Owned control','status':'MEASURED','outcome':'PASS'}]}
    out=root/'data/evals/post-generation/owned-v1'
    save(out/'VALIDATION.json',result)
    save(out/'MANIFEST.json',{'schema':'post-generation-validation-manifest-1.0','status':'COMPLETED_SEALED',
        'expanded_benchmark_manifest_sha256':MANIFEST_SHA,'dataset_freeze_manifest_sha256':FREEZE,
        'input_bindings':{str((base/'GENERATED_RESPONSE.json').relative_to(root)):sha(base/'GENERATED_RESPONSE.json')},
        'files':{'VALIDATION.json':sha(out/'VALIDATION.json')}})
    discover_expanded_validations(store,records,rejected)
    assert not rejected and records['M9-Q01']['latest']['validation']['semantic_status']=='PENDING_REVIEW'
    assert not records['M9-Q01']['latest']['validation']['fully_validated']


@pytest.mark.parametrize('problem',['unsealed','wrong_dataset','corrupt_payload','missing_preparation'])
def test_future_artifact_fail_closed(synthetic_record,problem):
    root,base,manifest,questions,records=synthetic_record
    if problem=='unsealed':manifest['status']='RUNNING'
    elif problem=='wrong_dataset':manifest['expanded_benchmark_manifest_sha256']='0'*64
    elif problem=='corrupt_payload':(base/'GENERATED_RESPONSE.json').write_text('{}')
    else:
        # Unavailable file is not replaced by a different receipt.
        manifest['files'].pop('PREPARATION_AUDIT.json')
    save(base/'MANIFEST.json',manifest)
    rejected=[]
    discover_expanded_generation(Store(root),records,questions,rejected)
    assert rejected and records['M9-Q01']['latest'] is None
    assert not records['M9-Q01']['attempts']


def test_native_candidate_contract_rejects_forged_envelope():
    store=Store(ROOT)
    with pytest.raises(ValueError):
        validate_future_binding(store,{'question_text':'Owned control'}, {}, {'candidates':[]}, {})


def test_no_pipeline_execution_imports_in_dashboard():
    import ast

    for name in ['expanded_adapter.py','expanded_ui.py']:
        tree=ast.parse((ROOT/'tools/quality_dashboard'/name).read_text())
        names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
        assert not names & {'OpenAI','OpenAIAdapter','EvidenceService','GenerationService'}
        assert not any(isinstance(n,ast.Attribute) and n.attr in {'invoke','generate','assemble','search','encode'}
                       for n in ast.walk(tree) if not (isinstance(n,ast.Attribute) and n.attr=='encode'))
