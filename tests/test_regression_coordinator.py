"""H1 gate controls: real interpreter/binding guards and owned accounting fixtures."""

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# Import repository tools consistently for both pytest console and python -m pytest.
original_path = list(sys.path)
sys.path.insert(0, str(ROOT))
try:
    from tools.regression import check_m4_artifacts as gate
    from tools.regression import run as coordinator
    from tools.regression import summarize as accounting
finally:
    sys.path[:] = original_path


def receipt(nodes=('tests/owned.py::test_one',)):
    return {'collect_only': False, 'collected_nodeids': list(nodes),
            'selected_nodeids': list(nodes), 'deselected_nodeids': [],
            'executed_nodeids': list(nodes), 'call_executed_nodeids': list(nodes),
            'outcomes': dict.fromkeys(nodes, 'PASSED'), 'exitstatus': 0}


def evidence(tier='focused'):
    selected = (sorted(accounting.REQUIRED_FULL) if tier == 'full' else
                ['m4-artifact-reader'] if tier == 'fast' else ['coordinator'])
    commands = accounting.PREFLIGHT | set(selected)
    if tier != 'fast':
        commands |= {'artifact-preflight'}
    run = {'tier': tier, 'selected_jobs': selected, 'expected_commands': sorted(commands)}
    results = [{'job': name, 'exit_code': 0} for name in sorted(commands)]
    selections = {name: receipt() for name in selected if name in accounting.TEST_JOBS}
    inventory = {'owned': ['tests/owned.py::test_one']}
    return run, results, inventory, selections


@pytest.mark.parametrize('tier,selected,expected', [
    ('fast', None, {'m4-artifact-reader'}), ('focused', None, {'coordinator'}),
    ('full', None, accounting.REQUIRED_FULL), (None, ['chunking'], {'chunking'}),
])
def test_tiers_select_supported_jobs(tier, selected, expected):
    actual, chosen = coordinator.choose_jobs(tier, selected)
    assert set(chosen) == expected
    assert actual == (tier or 'focused')
    assert coordinator.jobs()['chunking'][0] == str(ROOT / 'tools/chunking/.venv/bin/python')
    assert 'tools/chunking/tests' in coordinator.jobs()['chunking']


@pytest.mark.parametrize('tier,selected,error', [
    ('full', ['current'], 'custom_jobs_require_focused_tier'),
    ('fast', ['m4'], 'custom_jobs_require_focused_tier'),
    ('focused', ['chunking', 'chunking'], 'duplicate_job_selection'),
    ('focused', ['unknown'], 'unknown_job'),
])
def test_invalid_or_duplicate_job_selection_fails(tier, selected, error):
    with pytest.raises(ValueError, match=error):
        coordinator.choose_jobs(tier, selected)


def test_inherited_selection_cannot_hide_tests(monkeypatch, tmp_path):
    monkeypatch.setenv('PYTEST_ADDOPTS', '-k never_run --ignore=tests')
    monkeypatch.setenv('PYTEST_PLUGINS', 'untrusted_plugin')
    monkeypatch.setenv('RAG_TEST_QA_RELEASE', 'forged.json')
    monkeypatch.setenv('HF_HUB_OFFLINE', '0')
    env = coordinator.environment(tmp_path)
    assert 'PYTEST_ADDOPTS' not in env and 'PYTEST_PLUGINS' not in env
    assert env['RAG_TEST_QA_RELEASE'] == 'workspace/pdf-residual-recovery/v1/qa-regression-identity.json'
    assert env['HF_HUB_OFFLINE'] == '1'
    assert env['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] == '1'


def test_actual_environment_probe_rejects_wrong_interpreter():
    command = [sys.executable, 'tools/regression/probe_environment.py', '--root', str(ROOT)]
    good = subprocess.run([*command, '--project', '.'], cwd=ROOT, capture_output=True, text=True, check=False)
    assert good.returncode == 0, good.stderr
    wrong = subprocess.run([*command, '--project', 'tools/chunking'], cwd=ROOT,
                           capture_output=True, text=True, check=False)
    assert wrong.returncode != 0 and 'wrong_python_environment' in wrong.stderr


@pytest.fixture
def selected_copy(tmp_path):
    for name in gate.SELECTIONS:
        dest = tmp_path / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, dest)
    for name in list(gate.SELECTIONS)[1:]:
        selection = json.loads((ROOT / name).read_bytes())
        path = selection['manifest_path']
        dest = tmp_path / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / path, dest)
    gate.verify_selections(tmp_path)  # Actual BoundFiles guard passes before each mutation.
    return tmp_path


@pytest.mark.parametrize('defect', ['missing_manifest', 'missing_selector', 'altered_manifest',
                                   'forged_publication', 'stale_selector'])
def test_real_binding_guard_rejects_missing_or_forged_selection(selected_copy, defect):
    root = selected_copy
    path = root / list(gate.SELECTIONS)[1]
    if defect in {'missing_manifest', 'altered_manifest'}:
        path = root / json.loads(path.read_bytes())['manifest_path']
    if defect.startswith('missing'):
        path.unlink()
        with pytest.raises(FileNotFoundError):
            gate.verify_selections(root)
    else:
        if defect == 'forged_publication':
            path = root / next(iter(gate.SELECTIONS))
            data = json.loads(path.read_bytes())
            data['pdf_selector']['sha256'] = '0' * 64
            path.write_text(json.dumps(data))
        else:
            path.write_bytes(path.read_bytes() + b'\n')
        with pytest.raises(ValueError, match='unified_binding_changed'):
            gate.verify_selections(root)


def test_wrong_model_catalog_selection_is_not_reinterpreted(selected_copy):
    selection = dict(gate.SELECTIONS)
    selection[list(selection)[2]] = gate.M3_MANIFEST
    with pytest.raises(ValueError, match='wrong_release_selection'):
        gate.verify_selections(selected_copy, selection)


@pytest.mark.parametrize('tree', ['root', 'chunking', 'embedding'])
def test_missing_supported_test_tree_is_blocked(tree):
    nodes = {name: [f'{name}::test_{i}' for i in range(count)]
             for name, (_, _, count) in coordinator.TREES.items()}
    coordinator.validate_inventory(nodes)
    nodes[tree].pop()
    with pytest.raises(ValueError, match='missing_supported_test_coverage:' + tree):
        coordinator.validate_inventory(nodes)


def test_duplicate_inventory_nodes_rejected():
    nodes = {name: [f'{name}::test_{i}' for i in range(count)]
             for name, (_, _, count) in coordinator.TREES.items()}
    nodes['chunking'][-1] = nodes['chunking'][0]
    with pytest.raises(ValueError, match='duplicate_inventory_node'):
        coordinator.validate_inventory(nodes)


@pytest.mark.parametrize('tier', ['fast', 'focused', 'full'])
def test_accounting_distinguishes_tiers_and_permitted_cross_job_overlap(tier):
    run, results, inventory, selections = evidence(tier)
    summary = accounting.analyze(run, results, inventory, selections)
    assert summary['status'] == 'PASS_' + tier.upper()
    assert summary['full_release_gate'] == (tier == 'full')
    assert summary['unique_tests_executed'] == (0 if tier == 'fast' else 1)
    assert all(k in summary['test_totals_with_overlaps']
               for k in ['selected', 'executed', 'failed', 'errored', 'skipped', 'deselected'])
    if tier == 'full':
        assert summary['overlap_executions'] == len(selections) - 1


@pytest.mark.parametrize('outcome', ['FAILED', 'ERROR', 'SKIPPED'])
def test_nonpassing_outcomes_never_produce_green_gate(outcome):
    run, results, inventory, selections = evidence()
    selections['coordinator']['outcomes']['tests/owned.py::test_one'] = outcome
    summary = accounting.analyze(run, results, inventory, selections)
    assert summary['status'] == 'INCOMPLETE_OR_FAILED'


@pytest.mark.parametrize('defect,error', [
    ('missing_chunking', 'missing_full_job_coverage'),
    ('duplicate_job', 'duplicate_job_accounting'),
    ('duplicate_node', 'duplicate_test_accounting'),
    ('missing_outcome', 'selected_test_not_executed'),
    ('unreported_deselection', 'unreported_or_wrong_deselection'),
    ('missing_preflight', 'verification_plan_missing_required_command'),
])
def test_accounting_failure_controls(defect, error):
    run, results, inventory, selections = evidence('full')
    assert accounting.analyze(run, results, inventory, selections)['status'] == 'PASS_FULL'
    if defect == 'missing_chunking':
        run['selected_jobs'].remove('chunking')
        run['expected_commands'].remove('chunking')
        results[:] = [r for r in results if r['job'] != 'chunking']
        del selections['chunking']
    elif defect == 'duplicate_job':
        results.append(copy.deepcopy(results[0]))
    elif defect == 'duplicate_node':
        selections['current']['selected_nodeids'] *= 2
    elif defect == 'missing_outcome':
        selections['current']['outcomes'].clear()
    elif defect == 'unreported_deselection':
        selections['current']['collected_nodeids'].append('tests/owned.py::hidden')
    else:
        run['expected_commands'].remove('artifact-preflight')
    with pytest.raises(ValueError, match=error):
        accounting.analyze(run, results, inventory, selections)


def test_unexecuted_inventory_cannot_be_hidden_by_successful_jobs():
    run, results, inventory, selections = evidence('full')
    inventory['owned'].append('tests/owned.py::not_run')
    summary = accounting.analyze(run, results, inventory, selections)
    assert summary['status'] == 'INCOMPLETE_OR_FAILED'
    assert summary['not_executed_by_tier_or_failure'] == ['tests/owned.py::not_run']


def test_changed_verification_implementation_is_not_silently_fingerprinted(tmp_path):
    import hashlib

    p = tmp_path / 'owned.py'
    p.write_text('immutable verification component\n')
    snapshot = {'owned.py': hashlib.sha256(p.read_bytes()).hexdigest()}
    coordinator.check_components(tmp_path, snapshot)
    p.write_text('changed during run\n')
    with pytest.raises(ValueError, match='verification_component_changed_during_run'):
        coordinator.check_components(tmp_path, snapshot)


@pytest.mark.parametrize('defect', ['shape', 'count', 'inference', 'parent', 'binding', 'depth'])
def test_missing_artifact_verification_cannot_be_replaced_by_exit_zero(defect):
    report = {'schema': 'current-artifact-gate-2.0', 'result': 'PASS', 'depth': 'full',
              'inference': False, 'shape': [992, 384], 'records': 992,
              'corpus': {'units': 553, 'HOLD': 358, 'membership_edges': 3727},
              'all992_saved_input_token_vector_and_catalog_lineage_bindings': True,
              'all992_live_parent_input_bindings': True, 'live_complete_parent_rehydrations': 992,
              'protected_markdown_parents_checked': 4, 'unique_live_parents_checked': 553,
              'C10_required_context_and_QA_observation_checked': True}
    accounting.validate_artifact_report(report, 'full')
    if defect == 'shape':
        report['shape'] = [1, 384]
    elif defect == 'count':
        report['corpus']['units'] = 550
    elif defect == 'inference':
        report['inference'] = True
    elif defect == 'parent':
        report['live_complete_parent_rehydrations'] = 1
    elif defect == 'binding':
        report['all992_saved_input_token_vector_and_catalog_lineage_bindings'] = False
    else:
        report['depth'] = 'fast'
    with pytest.raises(ValueError):
        accounting.validate_artifact_report(report, 'full')


@pytest.fixture
def published_c10_parent():
    # Reuse the actual accepted consumable example; this creates no new QA approval.
    native = json.loads((ROOT / 'data/validation/html/c10-admission-v1/C10-VERIFIED-CONSUMER-UNIT.json').read_bytes())
    parent = {'native_unit_id': native['unit_id'], 'document_id': 'C10',
              'consumer': {'llm_context': native['llm_context']}}
    assert gate.verify_c10_context(parent, native['unit_id'])
    return parent, native['unit_id']


def test_c10_qualification_guard_does_not_reclassify_unrelated_tables(published_c10_parent):
    parent, required_id = published_c10_parent
    ordinary = copy.deepcopy(parent)
    ordinary['native_unit_id'] = 'owned-unrelated-C10-table'
    ordinary['consumer']['llm_context']['qa_observations'] = []
    ordinary['consumer']['llm_context']['required_context'] = []
    assert gate.verify_c10_context(ordinary, required_id) is False


@pytest.mark.parametrize('defect', ['missing_warning', 'missing_RRF_context',
                                   'publisher_misattribution', 'nonmandatory_warning'])
def test_actual_C10_qualified_parent_still_requires_warning_and_context(published_c10_parent, defect):
    parent, required_id = published_c10_parent
    bad = copy.deepcopy(parent)
    context = bad['consumer']['llm_context']
    if defect == 'missing_warning':
        context['qa_observations'] = []
    elif defect == 'missing_RRF_context':
        context['required_context'] = []
    elif defect == 'publisher_misattribution':
        for observation in context['qa_observations']:
            observation['origin'] = 'publisher'
    else:
        for observation in context['qa_observations']:
            observation['must_accompany'] = False
    with pytest.raises(ValueError, match='missing_C10_'):
        gate.verify_c10_context(bad, required_id)
