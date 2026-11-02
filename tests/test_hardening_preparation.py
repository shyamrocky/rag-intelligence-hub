"""Owned preparation controls. Synthetic records confer no publication authority."""

import copy
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    'hardening_prepare', Path(__file__).resolve().parents[1] / 'tools/hardening/prepare.py')
prep = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prep)


def test_json_pointer_literal_paths_and_arrays():
    assert prep.pointer({'a/b': {'~z': [4]}}, '/a~1b/~0z/0') == 4


@pytest.mark.parametrize('name', ['', '/absolute', '../escape', 'a/../b', 'a\\b', './a'])
def test_unsafe_relative_paths_rejected(name):
    with pytest.raises(ValueError, match='unsafe_relative_path'):
        prep.relative(name)


def test_source_escape_rejected(tmp_path):
    outside = tmp_path / 'outside'
    outside.write_text('owned synthetic')
    root = tmp_path / 'root'
    root.mkdir()
    (root / 'link').symlink_to(outside)
    with pytest.raises(ValueError, match='outside_root'):
        prep.existing(root, 'link')


def test_review_patch_does_not_write_canonical_source(tmp_path):
    source = ('def verify_foundation(home=None):\n'
              '    home = Path(home or HOME).resolve()\n'
              'def execute(manifest, registry, *, output=None, release=None):\n'
              '    home = Path(release or HOME).resolve()\n'
              '    output = Path(output or home).resolve()\n')
    p = tmp_path / 'pipeline.py'
    p.write_text(source)
    patch, after = prep.strict_patch(p.read_text())
    assert p.read_text() == source
    assert 'explicit_ingestion_release_required' in patch
    assert 'explicit_ingestion_output_required' in patch
    assert len(after) == 64


def test_patch_rejects_unexpected_source():
    with pytest.raises(ValueError, match='unexpected_canonical_pipeline_base'):
        prep.strict_patch('def verify_foundation():\n    pass\n')


def fixture_rows():
    return [{'logical_key': str(i), **{k: f'owned-{k}-{i}' for k in (
        'source_scope_sha256', 'source_spans_sha256', 'memberships_sha256',
        'qualification_sha256', 'citation_sha256', 'input_text_sha256',
        'token_ids_sha256', 'encoding_sha256', 'vector_sha256')}} for i in range(2)]


def test_reuse_allows_reordered_bijection_and_identity_metadata_change():
    old = fixture_rows()
    new = copy.deepcopy(list(reversed(old)))
    new[0]['future_embedding_id'] = 'proposal-not-a-release'
    result = prep.verify_reuse(old, new)
    assert result['bijection'] == 2 and result['inference'] is False
    assert result['authority'] == 'COMPARISON_ONLY_NOT_AUTHORIZATION'


@pytest.mark.parametrize('key', ['source_scope_sha256', 'source_spans_sha256', 'memberships_sha256',
                               'qualification_sha256', 'citation_sha256', 'input_text_sha256',
                               'token_ids_sha256', 'encoding_sha256', 'vector_sha256'])
def test_each_reuse_invariant_rejects_change(key):
    old = fixture_rows()
    new = copy.deepcopy(old)
    new[0][key] = 'tampered'
    with pytest.raises(ValueError, match='reuse_content_token_scope_or_vector_changed'):
        prep.verify_reuse(old, new)


def test_reuse_rejects_missing_required_proof():
    old = fixture_rows()
    new = copy.deepcopy(old)
    del new[0]['token_ids_sha256']
    with pytest.raises(ValueError, match='incomplete_reuse_evidence'):
        prep.verify_reuse(old, new)


def test_reuse_rejects_duplicated_or_missing_mapping():
    old = fixture_rows()
    with pytest.raises(ValueError, match='duplicate_reuse_key'):
        prep.verify_reuse(old, [old[0], old[0]])
    with pytest.raises(ValueError, match='reuse_row_count_changed'):
        prep.verify_reuse(old, old[:1])


def test_reuse_rejects_unrelated_key():
    old = fixture_rows()
    new = copy.deepcopy(old)
    new[0]['logical_key'] = 'foreign'
    with pytest.raises(ValueError, match='reuse_not_bijective'):
        prep.verify_reuse(old, new)


def test_new_reports_cannot_overwrite(tmp_path):
    p = tmp_path / 'report'
    prep.write_new(p, 'original')
    with pytest.raises(FileExistsError):
        prep.write_new(p, 'replacement')
    assert p.read_text() == 'original'


def dependency_fixture(tmp_path):
    import json

    rows = []
    for i in range(88):
        name = f'workspace/owned/{i}.txt'
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f'owned fixture {i}')
        rows.append({'path': name, 'expected_sha256': prep.digest(p),
                     'size_bytes': p.stat().st_size, 'classification': 'Runtime source evidence',
                     'proposed_durable_destination': f'data/provenance/owned/{i}.txt',
                     'direct_consumers': []})
    ref = tmp_path / 'reference.json'
    ref.write_text(json.dumps({'source': rows[0]['path'], 'sha': rows[0]['expected_sha256']}))
    rows[0]['direct_consumers'] = [
        {'artifact': 'reference.json', 'json_pointer': '/source', 'relationship': 'path value'},
        {'artifact': 'reference.json', 'json_pointer': '/sha', 'relationship': 'key/hash'}]
    return {'count': 88, 'rows': rows}


def test_complete_owned_inventory_and_direct_consumer_bindings(tmp_path):
    matrix = dependency_fixture(tmp_path)
    out = prep.validate_rows(tmp_path, matrix)
    assert len(out) == 88
    assert all(r['status'] == 'PROPOSED_NOT_COPIED_OR_REBOUND' for r in out)
    assert not (tmp_path / 'data').exists()


@pytest.mark.parametrize('mutation,reason', [
    ('missing_row', 'incomplete_dependency_inventory'),
    ('duplicate', 'duplicate_dependency'),
    ('changed_bytes', 'dependency_changed'),
    ('changed_size', 'dependency_size_changed'),
    ('duplicate_target', 'duplicate_destination'),
    ('workspace_target', 'workspace_destination_forbidden'),
    ('wrong_target', 'wrong_destination_role'),
    ('wrong_consumer', 'consumer_reference_changed'),
    ('conflict', 'existing_destination_conflict'),
])
def test_invalid_dependency_plan_fails_closed(tmp_path, mutation, reason):
    matrix = dependency_fixture(tmp_path)
    rows = matrix['rows']
    if mutation == 'missing_row':
        rows.pop()
    elif mutation == 'duplicate':
        rows[1] = copy.deepcopy(rows[0])
    elif mutation == 'changed_bytes':
        (tmp_path / rows[0]['path']).write_text('altered')
    elif mutation == 'changed_size':
        rows[0]['size_bytes'] += 1
    elif mutation == 'duplicate_target':
        rows[1]['proposed_durable_destination'] = rows[0]['proposed_durable_destination']
    elif mutation == 'workspace_target':
        rows[0]['proposed_durable_destination'] = 'workspace/never-active'
    elif mutation == 'wrong_target':
        rows[0]['proposed_durable_destination'] = 'archive/not-source-evidence'
    elif mutation == 'wrong_consumer':
        (tmp_path / 'reference.json').write_text('{"source":"foreign"}')
    elif mutation == 'conflict':
        p = tmp_path / rows[0]['proposed_durable_destination']
        p.parent.mkdir(parents=True)
        p.write_text('conflicting existing durable evidence')
    with pytest.raises(ValueError, match=reason):
        prep.validate_rows(tmp_path, matrix)


def test_identical_existing_durable_witness_is_reused_without_copy(tmp_path):
    import shutil

    matrix = dependency_fixture(tmp_path)
    r = matrix['rows'][0]
    p = tmp_path / r['proposed_durable_destination']
    p.parent.mkdir(parents=True)
    shutil.copyfile(tmp_path / r['path'], p)
    assert prep.validate_rows(tmp_path, matrix)[0]['existing_exact_durable_copy'] is True


@pytest.mark.parametrize('role', ['Build or verification record', 'Temporary working artifact',
                                'Historical release dependency'])
def test_build_working_and_synthetic_records_are_archive_only(tmp_path, role):
    matrix = dependency_fixture(tmp_path)
    matrix['rows'][0]['classification'] = role
    matrix['rows'][0]['proposed_durable_destination'] = 'archive/owned/0.txt'
    assert prep.validate_rows(tmp_path, matrix)[0]['new_active_role'] == 'ARCHIVE_ONLY'
