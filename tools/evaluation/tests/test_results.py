"""Actual measured release and disposable corruption controls; no evidence payload access."""

import json
import shutil
from pathlib import Path

import pytest

from tools.evaluation.contract import APPROVAL, BENCHMARK, COMPONENTS, CONFIG
from tools.evaluation.results import SELECTOR, load_results
from tools.indexing.m5_index import sha

ROOT = Path(__file__).resolve().parents[3]


def selected():
    return sha((ROOT / SELECTOR).read_bytes())


def copy_release(target):
    pick = json.loads((ROOT / SELECTOR).read_bytes())
    manifest = json.loads((ROOT / pick['manifest_path']).read_bytes())
    config = json.loads((ROOT / CONFIG).read_bytes())
    review = json.loads((ROOT / BENCHMARK).read_bytes())
    paths = {SELECTOR, pick['manifest_path'], CONFIG, APPROVAL, BENCHMARK,
             manifest['results_path'], manifest['analysis_path'], manifest['verification_path'],
             manifest['oversized_path'], *COMPONENTS}
    paths |= {str(Path(BENCHMARK).parent / name) for name in review['files']}
    paths |= {b['path'] for b in review['selected_releases'].values()}
    for path in paths:
        p = target / path
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / path, p)
    assert config['schema'] == 'm9-evaluation-config-1.0'
    return pick, manifest


def test_real_complete_measurements_and_owner_approval():
    data = load_results(ROOT, expected_sha=selected())
    assert data['authority'] == 'MEASUREMENTS_ONLY_NOT_SOURCE_EVIDENCE'
    assert len(data['results']['cases']) == 87
    assert data['results']['budget_observation_count'] == 348
    assert data['results']['integrity_failures'] == []
    assert all(v['answerable_denominator'] == 26 for v in data['results']['summary'].values())
    assert all(v['unsupported_denominator'] == 3 for v in data['results']['summary'].values())
    assert set(data['results']['settings']['modes']) == {'bm25', 'vector', 'hybrid'}


@pytest.mark.parametrize('component', ['selector', 'manifest', 'results', 'analysis',
                                      'approval', 'qrels', 'configuration', 'implementation', 'verification', 'oversized'])
def test_changed_measured_or_review_bindings_reject(tmp_path, component):
    pick, manifest = copy_release(tmp_path)
    paths = {'selector': SELECTOR, 'manifest': pick['manifest_path'],
             'results': manifest['results_path'], 'analysis': manifest['analysis_path'],
             'approval': APPROVAL, 'qrels': str(Path(BENCHMARK).parent / 'PROPOSED_EVIDENCE_LABELS.json'),
             'configuration': CONFIG, 'implementation': COMPONENTS[1],
             'verification': manifest['verification_path'], 'oversized': manifest['oversized_path']}
    p = tmp_path / paths[component]
    p.write_bytes(p.read_bytes() + b' ')
    with pytest.raises(ValueError):
        load_results(tmp_path, expected_sha=selected())


def test_absent_results_are_not_empty_success(tmp_path):
    _, manifest = copy_release(tmp_path)
    (tmp_path / manifest['results_path']).unlink()
    with pytest.raises((ValueError, OSError)):
        load_results(tmp_path, expected_sha=selected())


def test_dashboard_pins_the_actual_completed_selector():
    from rag_hub.m9_dashboard import RESULT_SELECTOR_SHA256

    assert RESULT_SELECTOR_SHA256 == selected()
