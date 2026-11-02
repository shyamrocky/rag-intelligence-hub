"""One explicit fast/focused/full verification gate; never admission or artifact generation."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

if __package__:
    from .summarize import (
        REQUIRED_FULL,
        TEST_JOBS,
        observed_test_counts,
        summarize,
        validate_selection,
    )
else:
    from summarize import (
        REQUIRED_FULL,
        TEST_JOBS,
        observed_test_counts,
        summarize,
        validate_selection,
    )

ROOT = Path(__file__).resolve().parents[2]
PROJECTS = ('.', 'apps/ingestion_dashboard', 'tools/chunking', 'tools/embeddings')
TREES = {'root': ('tests', '.', 1024), 'chunking': ('tools/chunking/tests', 'tools/chunking', 232),
         'embedding': ('tools/embeddings/tests', 'tools/embeddings', 15)}


def jobs():
    root = ROOT / '.venv/bin/python'
    ui = ROOT / 'apps/ingestion_dashboard/.venv/bin/python'
    embedding = ROOT / 'tools/embeddings/.venv/bin/python'
    chunking = ROOT / 'tools/chunking/.venv/bin/python'
    test = ['-m', 'pytest', '-p', 'regression_plugin', '-o', 'junit_family=legacy',
            '-o', 'addopts=', '-p', 'no:cacheprovider', '-ra']
    return {
        'current': [str(root), *test, 'tests', '-m', 'not historical_replay and not dashboard_ui'],
        'historical': [str(root), *test, 'tests/test_pdf_nontext.py', 'tests/test_validation_local.py',
                       '-m', 'historical_replay'],
        'dashboard': [str(ui), *test, 'tests/test_ingestion_dashboard.py', 'tests/test_chunk_dashboard.py'],
        'chunking': [str(chunking), *test, 'tools/chunking/tests'],
        'm4': [str(embedding), *test, 'tests/test_embedding_inputs.py',
               'tools/embeddings/tests/test_local_embeddings.py'],
        'coordinator': [str(root), *test, 'tests/test_regression_coordinator.py'],
        'm4-artifact-reader': [str(embedding), 'tools/regression/check_m4_artifacts.py'],
        'lint': [str(ROOT / '.venv/bin/ruff'), 'check', '.'],
        'smoke': [str(ROOT / '.venv/bin/rag-hub'), 'smoke'],
    }


def choose_jobs(tier, selected):
    if selected and len(selected) != len(set(selected)):
        raise ValueError('duplicate_job_selection')
    tier = tier or ('focused' if selected else 'full')
    if tier == 'fast' and selected or tier == 'full' and selected:
        raise ValueError('custom_jobs_require_focused_tier')
    chosen = list(selected or (['coordinator'] if tier == 'focused' else
                              ['m4-artifact-reader'] if tier == 'fast' else
                              [name for name in jobs() if name != 'coordinator']))
    if tier == 'full':
        chosen = ['m4-artifact-reader'] + [name for name in chosen if name != 'm4-artifact-reader']
    if not set(chosen) <= set(jobs()):
        raise ValueError('unknown_job')
    return tier, chosen


def environment(output):
    env = os.environ.copy()
    for key in ('PYTEST_ADDOPTS', 'PYTEST_PLUGINS', 'RAG_TEST_QA_RELEASE', 'PYTHONPATH',
                'RAG_REGRESSION_SELECTION', 'PYTHONOPTIMIZE'):
        env.pop(key, None)
    env.update(PYTHONPATH=os.pathsep.join(str(ROOT / p) for p in
               ('tools/regression', 'tools/chunking')),
               RAG_TEST_QA_RELEASE='workspace/pdf-residual-recovery/v1/qa-regression-identity.json',
               PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTHONNOUSERSITE='1',
               PYTHONDONTWRITEBYTECODE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
               HF_HUB_DISABLE_TELEMETRY='1', TOKENIZERS_PARALLELISM='false', UV_OFFLINE='1',
               UV_CACHE_DIR=str(output / 'cache/uv'), LANGSMITH_TRACING='false',
               LANGCHAIN_TRACING_V2='false', STREAMLIT_BROWSER_GATHER_USAGE_STATS='false')
    return env


def check_components(root, components):
    for name, digest in components.items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
            raise ValueError('verification_component_changed_during_run:' + name)


def validate_inventory(inventory):
    union = set()
    for tree, (_, _, minimum) in TREES.items():
        nodes = inventory[tree]
        if len(nodes) != len(set(nodes)) or union & set(nodes):
            raise ValueError('duplicate_inventory_node')
        if len(nodes) < minimum:
            raise ValueError('missing_supported_test_coverage:' + tree)
        union.update(nodes)
    return len(union)


def run_command(output, env, name, command, results, *, pytest=False, collect=False):
    command = list(command)
    child_env = dict(env)
    if pytest:
        child_env['RAG_REGRESSION_SELECTION'] = str(output / (name + '-selection.json'))
        if not collect:
            command.append('--junitxml=' + str(output / (name + '.xml')))
    print('START ' + name, flush=True)
    started = time.perf_counter()
    error = None
    with (output / (name + '.log')).open('w') as log:
        try:
            process = subprocess.run(command, cwd=ROOT, env=child_env, stdout=log,
                                     stderr=subprocess.STDOUT, check=False)
            code = process.returncode
        except OSError as exc:
            error = type(exc).__name__ + ': ' + str(exc)
            log.write(error + '\n')
            code = 127
    row = {'job': name, 'command': command, 'exit_code': code,
           'seconds': time.perf_counter() - started}
    if error:
        row['launch_error'] = error
    results.append(row)
    (output / 'RESULTS.json').write_text(json.dumps(results, indent=2) + '\n')
    print(f'END {name}: exit {code}; {row["seconds"]:.2f}s', flush=True)
    return code == 0


def execute(output, tier, chosen):
    os.umask(0o077)
    output = output.resolve()
    if not output.is_relative_to((ROOT / 'workspace').resolve()):
        raise ValueError('reports_must_stay_in_private_workspace')
    output.mkdir(parents=True, exist_ok=False)
    env = environment(output)
    expected = []
    for project in PROJECTS:
        slug = project.replace('/', '-').replace('.', 'root')
        expected.extend(['environment-' + slug, 'lock-' + slug])
    expected.extend(['inventory-' + tree for tree in TREES])
    if tier != 'fast':
        expected.append('artifact-preflight')
    expected.extend(chosen)
    component_paths = set((ROOT / 'tools/regression').glob('*.py'))
    for tree, _, _ in TREES.values():
        component_paths.update((ROOT / tree).rglob('*.py'))
    run = {'schema': 'regression-jobs-2.0', 'tier': tier, 'selected_jobs': chosen,
           'expected_commands': expected, 'complete_job_set': tier == 'full',
           'scope': 'TEST_ONLY_NOT_QA_AUTHORITY', 'm4_owner_acceptance': 'PENDING',
           'm5_authorized': False, 'environment_policy': 'locked_interpreters_explicit_test_plugin_offline',
           'components': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted(component_paths)}}
    (output / 'RUN.json').write_text(json.dumps(run, indent=2) + '\n')
    results = []
    try:
        for project in PROJECTS:
            slug = project.replace('/', '-').replace('.', 'root')
            python = ROOT / project / '.venv/bin/python'
            probe = [str(python), 'tools/regression/probe_environment.py',
                     '--root', str(ROOT), '--project', project]
            if not run_command(output, env, 'environment-' + slug, probe, results):
                raise ValueError('runtime_preflight_failed:' + project)
            if not run_command(output, env, 'lock-' + slug,
                               ['uv', 'lock', '--check', '--offline', '--project', project], results):
                raise ValueError('lock_preflight_failed:' + project)
        # Use the same artifact checker for preflight; never instantiate an embedding model.
        if tier != 'fast':
            command = jobs()['m4-artifact-reader'] + ['--depth', 'fast', '--output',
                                                       str(output / 'artifact-preflight.json')]
            if not run_command(output, env, 'artifact-preflight', command, results):
                raise ValueError('artifact_preflight_failed')
        inventory = {}
        for tree, (path, project, _) in TREES.items():
            command = [str(ROOT / project / '.venv/bin/python'), '-m', 'pytest', '-p',
                       'regression_plugin', '-o', 'addopts=', '--collect-only', '-q', path]
            name = 'inventory-' + tree
            if not run_command(output, env, name, command, results, pytest=True, collect=True):
                raise ValueError('test_collection_failed:' + tree)
            data = json.loads((output / (name + '-selection.json')).read_bytes())
            validate_selection(data, collect_only=True)
            inventory[tree] = data['selected_nodeids']
        size = validate_inventory(inventory)
        (output / 'INVENTORY.json').write_text(json.dumps({
            'schema': 'supported-test-inventory-1.0', 'nodeids_by_tree': inventory,
            'unique_tests': size, 'scope': list(TREES.values()),
            'outside_scope': 'Frozen private experimental tests outside the three supported trees',
        }, indent=2) + '\n')
        for name in chosen:
            command = jobs()[name]
            if name == 'm4-artifact-reader':
                command += ['--depth', 'full' if tier == 'full' else 'fast',
                            '--output', str(output / 'artifact-results.json')]
            run_command(output, env, name, command, results, pytest=name in TEST_JOBS)
        check_components(ROOT, run['components'])
        summary = summarize(output)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        summary = {'schema': 'regression-verification-summary-2.0', 'status': 'BLOCKED_OR_FAILED',
                   'tier': tier, 'full_release_gate': False, 'error': str(exc), 'jobs': results,
                   'not_run_commands': sorted(set(expected) - {r['job'] for r in results}),
                   **observed_test_counts(output),
                   'command_failures': sum(row['exit_code'] != 0 for row in results),
                   'missing_evidence_is_not_success': True,
                   'm4_acceptance': 'PENDING', 'm5_authorized': False}
        (output / 'SUMMARY.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k not in ('jobs',
          'not_executed_by_tier_or_failure')}, indent=2), flush=True)
    return int(not summary['status'].startswith('PASS_'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New private report directory')
    parser.add_argument('--tier', choices=['fast', 'focused', 'full'])
    parser.add_argument('--job', choices=jobs(), action='append', help='Explicit focused jobs')
    args = parser.parse_args()
    try:
        tier, chosen = choose_jobs(args.tier, args.job)
        if tier == 'full' and set(chosen) != REQUIRED_FULL:
            raise ValueError('missing_full_job_coverage')
        return execute(args.output, tier, chosen)
    except (ValueError, FileExistsError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    sys.exit(main())
