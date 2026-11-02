"""Read-only H2/H3 preparation. Produces plans, never releases or authorizations.

No application imports, copies, aliases, publication edits or build execution.
"""

import argparse
import ast
import difflib
import hashlib
import json
from collections import Counter
from pathlib import Path, PurePosixPath

MATRIX = 'workspace/rag-implementation/v1/system-hardening-assessment-v1/WORKSPACE_DEPENDENCY_MATRIX.json'
MATRIX_SHA = '2162ca237513f099729a0279edbdee6da8657eefc5ff4b8b8a77ddbbb34c4c4a'
PIPELINE = 'src/rag_hub/shared/pipeline.py'
ARCHIVE_CLASSES = {'Build or verification record', 'Temporary working artifact',
                   'Historical release dependency'}
BULK_INVENTORY = 'workspace/ingestion-freeze/v1/VERIFICATION.json'
EXISTING_WITNESSES = {
    'workspace/rag-implementation/v1/m3-qualified-recovery-v1/FROZEN_BOUNDARIES.json':
        'data/chunking/m3-qualified-v2/FROZEN_BOUNDARIES.json',
    'workspace/rag-implementation/v1/m3-remediation-v1/FROZEN_CASE_REVIEW.json':
        'data/chunking/m3-remediation-v1/FROZEN_CASE_REVIEW.json',
}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def relative(name):
    p = PurePosixPath(name)
    require(bool(name) and not p.is_absolute() and '..' not in p.parts
            and '\\' not in name and str(p) == name, 'unsafe_relative_path')
    return p


def existing(root, name):
    relative(name)
    p = root / name
    require(p.resolve(strict=True).is_relative_to(root.resolve()), 'source_outside_root')
    require(p.is_file() and not p.is_symlink(), 'not_regular_source_file')
    return p


def pointer(document, location):
    require(location.startswith('/'), 'invalid_json_pointer')
    for part in location[1:].split('/'):
        part = part.replace('~1', '/').replace('~0', '~')
        document = document[int(part)] if isinstance(document, list) else document[part]
    return document


def validate_rows(root, matrix):
    rows = matrix['rows']
    require(len(rows) == matrix['count'] == 88, 'incomplete_dependency_inventory')
    require(len({r['path'] for r in rows}) == 88, 'duplicate_dependency')
    result, targets = [], set()
    for row in rows:
        path = existing(root, row['path'])
        require(digest(path) == row['expected_sha256'], 'dependency_changed:' + row['path'])
        require(path.stat().st_size == row['size_bytes'], 'dependency_size_changed')
        archive = row['classification'] in ARCHIVE_CLASSES or row['path'] == BULK_INVENTORY
        target = EXISTING_WITNESSES.get(row['path'], row['proposed_durable_destination'])
        if row['path'] == BULK_INVENTORY:
            target = 'archive/build-history/ingestion-freeze-v1/VERIFICATION.json'
        relative(target)
        require(not target.startswith('workspace/'), 'workspace_destination_forbidden')
        require(target.startswith('archive/' if archive else 'data/'), 'wrong_destination_role')
        require(target not in targets, 'duplicate_destination')
        targets.add(target)
        target_path = root / target
        if target_path.exists():
            require(digest(existing(root, target)) == row['expected_sha256'],
                    'existing_destination_conflict')
        refs = []
        for ref in row['direct_consumers']:
            artifact = existing(root, ref['artifact'])
            value = pointer(json.loads(artifact.read_bytes()), ref['json_pointer'])
            expected = row['path'] if ref['relationship'] == 'path value' else row['expected_sha256']
            require(value == expected, 'consumer_reference_changed:' + ref['artifact'])
            refs.append({**ref, 'artifact_sha256': digest(artifact)})
        result.append({**row, 'actual_sha256': digest(path), 'matches': True,
                       'direct_consumers': refs,
                       'proposed_target': target,
                       'new_active_role': 'ARCHIVE_ONLY' if archive else 'RETAIN_EVIDENCE',
                       'existing_exact_durable_copy': target_path.exists(),
                       'status': 'PROPOSED_NOT_COPIED_OR_REBOUND'})
    return result


def strict_patch(source):
    """Compute a review-only patch in memory; never apply it or mint a release."""
    pairs = [
        ('    home = Path(home or HOME).resolve()',
         ('    if home is None or not str(home).strip():\n'
         '        raise ValueError("explicit_ingestion_release_required")\n'
         '    home = Path(home).resolve()')),
        ('    home = Path(release or HOME).resolve()',
         ('    if release is None or not str(release).strip():\n'
         '        raise ValueError("explicit_ingestion_release_required")\n'
         '    if output is None or not str(output).strip():\n'
         '        raise ValueError("explicit_ingestion_output_required")\n'
         '    home = Path(release).resolve()')),
        ('    output = Path(output or home).resolve()', '    output = Path(output).resolve()'),
    ]
    candidate = source
    for before, after in pairs:
        require(candidate.count(before) == 1, 'unexpected_canonical_pipeline_base')
        candidate = candidate.replace(before, after)
    tree = ast.parse(candidate)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in {'execute', 'verify_foundation'}:
            require(not any(isinstance(n, ast.Name) and n.id == 'HOME' for n in ast.walk(node)),
                    'remaining_HOME_fallback')
    patch = ''.join(difflib.unified_diff(source.splitlines(True), candidate.splitlines(True),
                                       fromfile='a/' + PIPELINE, tofile='b/' + PIPELINE))
    return patch, hashlib.sha256(candidate.encode()).hexdigest()


def verify_reuse(before, candidate):
    """Independent pre-build guard specification, NOT authorization or a producer.

    A future migration must derive both records from verified reader views.
    Matching caller dictionaries alone never establish permission to consume.
    """
    require(len(before) == len(candidate), 'reuse_row_count_changed')
    old = {r['logical_key']: r for r in before}
    new = {r['logical_key']: r for r in candidate}
    require(len(old) == len(before) and len(new) == len(candidate), 'duplicate_reuse_key')
    require(old.keys() == new.keys(), 'reuse_not_bijective')
    protected = {'source_scope_sha256', 'source_spans_sha256', 'memberships_sha256',
                 'qualification_sha256', 'citation_sha256', 'input_text_sha256',
                 'token_ids_sha256', 'encoding_sha256', 'vector_sha256'}
    for key, value in old.items():
        require(protected <= value.keys() and protected <= new[key].keys(),
                'incomplete_reuse_evidence')
        require(all(value[p] == new[key][p] for p in protected),
                'reuse_content_token_scope_or_vector_changed')
    return {'bijection': len(old), 'numerical_reuse_candidate': True,
            'authority': 'COMPARISON_ONLY_NOT_AUTHORIZATION', 'inference': False}


def plan(root):
    root = root.resolve()
    require(digest(existing(root, MATRIX)) == MATRIX_SHA, 'unexpected_dependency_matrix')
    matrix = json.loads(existing(root, MATRIX).read_bytes())
    rows = validate_rows(root, matrix)
    source = existing(root, PIPELINE).read_text()
    patch, after_sha = strict_patch(source)
    recipe = {
        'schema': 'H2-H3-review-only-build-recipe-1.0',
        'authority': 'PROPOSAL_NOT_RELEASE_OR_QA_AUTHORIZATION',
        'state': 'OWNER_CHECKPOINT_REQUIRED_NO_BUILD_OR_ACTIVATION',
        'ingestion': {
            'runtime_root': 'releases/ingestion/strict-v1/root',
            'canonical_base': {'path': PIPELINE, 'sha256': digest(root / PIPELINE)},
            'proposed_after_pipeline_sha256': after_sha,
            'patch_application': 'Only after explicit owner compatibility approval; isolated copy only',
            'foundation_home': 'releases/ingestion/strict-v1/root/data/ingestion/strict-v1',
            'output': 'explicit child of foundation home; no historical HOME writes',
            'lineage': 'canonical source inventory + review-only patch + exact locked dependency versions',
            'qualification': 'real prospective foundation and receipt required; synthetic test identity forbidden',
        },
        'consumer': {
            'retained_evidence_roles': sum(r['new_active_role'] == 'RETAIN_EVIDENCE' for r in rows),
            'archive_only_roles': sum(r['new_active_role'] == 'ARCHIVE_ONLY' for r in rows),
            'new_inventory': 'required native validator inputs and actual component bytes; no build logs or test foundation',
            'minimality_status': 'candidate_set; successor no-workspace native replay still required',
            'authority': 'same shared QA; new native compatibility/publication bindings require approval',
            'originals': 'retain every old path; never alias, delete, edit or rewrite original hashes',
        },
        'vectors': {'reencode': False, 'reuse': 'conditional on verified bijective source/input/token/model equivalence',
                    'new_identity': 'new envelope required if M3 manifest changes; embedding IDs change only if formula inputs change'},
    }
    return {'schema': 'H2-H3-preparation-plan-1.0', 'authority': 'INSPECTION_ONLY_NOT_ADMISSION',
            'count': len(rows), 'classifications': dict(Counter(r['classification'] for r in rows)),
            'role_counts': dict(Counter(r['new_active_role'] for r in rows)),
            'rows': rows, 'recipe': recipe}, patch


def write_new(path, data):
    with path.open('x') as stream:
        stream.write(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output.resolve()
    require(output.is_relative_to((root / 'workspace').resolve()), 'reports_only_in_private_workspace')
    result, patch = plan(root)
    output.mkdir(parents=True, exist_ok=False)
    write_new(output / 'RECONCILED_DEPENDENCIES.json', json.dumps(result, indent=2) + '\n')
    write_new(output / 'PROPOSED_STRICT_PIPELINE.patch', patch)
    write_new(output / 'BUILD_RECIPE.proposed.json', json.dumps(result['recipe'], indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['count', 'classifications', 'role_counts']}))


if __name__ == '__main__':
    main()
