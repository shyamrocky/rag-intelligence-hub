"""Reproducibly build the opt-in actual strict APIs from canonical source + patch."""

import argparse
import importlib.metadata
import json
import os
from pathlib import Path

from rag_hub.chunk_preparation import write_once
from rag_hub.unified_models import encode, sha

RUNTIME = 'releases/ingestion/strict-v1/root'
HOME = 'data/ingestion/strict-v1'


def strict_source(source):
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
        ('    output = Path(output or home).resolve()', '    output = Path(output).resolve()')]
    for before, after in pairs:
        if source.count(before) != 1:
            raise ValueError('unapproved_strict_source_base')
        source = source.replace(before, after)
    return source


def build(root):
    from rag_hub.pdf_classification import load_evidence

    os.umask(0o077)
    target = root / RUNTIME
    base, actual = {}, {}
    def save(name, raw):
        write_once(target / name, raw)
        actual[name] = sha(raw)
    for p in sorted((root / 'src/rag_hub').rglob('*.py')):
        name = str(p.relative_to(root))
        raw = p.read_bytes()
        base[name] = sha(raw)
        if name == 'src/rag_hub/shared/pipeline.py':
            raw = strict_source(raw.decode()).encode()
        save(name, raw)
    for name in ['uv.lock', 'pyproject.toml']:
        base[name] = sha((root / name).read_bytes())
        save(name, (root / name).read_bytes())
    # Reuse the currently recorded structural evidence, with exact leaf bytes.
    # Only the descriptor's source-bound locations change; no new review/type assertion.
    component = json.loads((root / 'data/parsed/pdf/four-pdf-poc-v1/C06/component.json').read_bytes())
    old_bundle_path = component['options']['classification_evidence']['bundle_path']
    original = json.loads((root / old_bundle_path).read_bytes())
    mapping = {p: HOME + '/evidence/' + str(i) + '-' + Path(p).name
               for i, p in enumerate(sorted(original['files']))}
    for old, new in mapping.items():
        raw = (root / old).read_bytes()
        if sha(raw) != original['files'][old]:
            raise ValueError('classification_leaf_evidence_changed')
        save(new, raw)
    def relocated(value):
        if isinstance(value, dict):
            return {mapping.get(k, k): relocated(v) for k, v in value.items()}
        if isinstance(value, list):
            return [relocated(v) for v in value]
        return mapping.get(value, value) if isinstance(value, str) else value
    bundle = relocated(original)
    bp = HOME + '/classification-input.json'
    save(bp, encode(bundle))
    split_path = HOME + '/reviewed-c06-split.json'
    save(split_path, encode(component['options']['reviewed_split']))
    # Actual existing native loader must accept the relocated descriptor.
    expected, _ = load_evidence(root, old_bundle_path)
    relocated_evidence, _ = load_evidence(target, bp)
    for key in ['parents', 'inactive_parent_ids', 'phase1d_reviews', 'owner_reviews']:
        if expected[key] != relocated_evidence[key]:
            raise ValueError('relocation_changed_classification_scope')
    options = {'classification_evidence': {'bundle_path': bp, 'bundle_sha256': sha(encode(bundle))},
               'reviewed_split': component['options']['reviewed_split']}
    save(HOME + '/ADAPTER_OPTIONS.json', encode(options))
    for doc in ['C01', 'C02', 'C06', 'C14']:
        source = json.loads((root / f'data/parsed/pdf/four-pdf-poc-v1/{doc}/source.json').read_bytes())
        for name in {source['raw_path'], source['snapshot_path']}:
            raw = (root / name).read_bytes()
            if sha(raw) != source['raw_sha256']:
                raise ValueError('strict_fixture_source_changed')
            save(name, raw)
        save(HOME + f'/sources/{doc}.json', encode(source))
        for name in ['blocks.json', 'pdf-classification.json']:
            save(HOME + f'/expected/{doc}/{name}',
                 (root / f'data/parsed/pdf/four-pdf-poc-v1/{doc}/{name}').read_bytes())
    dependencies = {n: importlib.metadata.version(n) for n in ['pydantic', 'pymupdf', 'markdown-it-py']}
    freeze = {'schema': 'strict-ingestion-foundation-1.0', 'version': 'ingestion-strict-v1',
              'authority': 'EXECUTION_FOUNDATION_NOT_CONTENT_ADMISSION', 'files': actual,
              'dependencies': dependencies, 'canonical_source_base': base,
              'proposed_patch_sha256': sha((root / 'workspace/rag-implementation/v1/h2-h3-preparation-v1/plan-v1/PROPOSED_STRICT_PIPELINE.patch').read_bytes()),
              'synthetic_test_foundation': False}
    write_once(target / HOME / 'foundation-freeze.json', encode(freeze))
    write_once(target / HOME / 'foundation-freeze-receipt.json', encode({
        'foundation_manifest_sha256': sha(encode(freeze)),
        'authority': 'PROSPECTIVE_REAL_EXECUTION_RELEASE_NOT_QA_OR_OWNER_ACCEPTANCE'}))
    recipe = {'schema': 'canonical-strict-ingestion-build-1.0', 'runtime_root': RUNTIME,
        'source_base': base, 'actual_image_files': actual, 'foundation_path': HOME,
        'foundation_sha256': sha(encode(freeze)), 'dependencies': dependencies,
        'only_modified_application_source': 'src/rag_hub/shared/pipeline.py',
        'original_pipeline_sha256': base['src/rag_hub/shared/pipeline.py'],
        'actual_pipeline_sha256': actual['src/rag_hub/shared/pipeline.py'],
        'model_inference': False, 'default_activation': False,
        'classification_evidence_migration': mapping}
    write_once(root / 'releases/ingestion/strict-v1/BUILD.json', encode(recipe))
    write_once(root / 'config/ingestion-strict-v1.json', encode({
        'schema': 'strict-ingestion-selection-1.0', 'runtime_root': RUNTIME,
        'build_path': 'releases/ingestion/strict-v1/BUILD.json', 'build_sha256': sha(encode(recipe)),
        'foundation_path': HOME, 'foundation_sha256': sha(encode(freeze))}))
    patch = root / 'workspace/rag-implementation/v1/h2-h3-preparation-v1/plan-v1/PROPOSED_STRICT_PIPELINE.patch'
    write_once(root / 'tools/ingestion/successors/strict-v1/explicit-release.patch', patch.read_bytes())
    write_once(root / 'tools/ingestion/successors/strict-v1/build.json', encode({
        'schema': 'strict-ingestion-source-recipe-1.0', 'builder': 'tools/ingestion/build_strict.py',
        'builder_sha256': sha(Path(__file__).read_bytes()),
        'private_build_manifest': 'releases/ingestion/strict-v1/BUILD.json',
        'private_build_manifest_sha256': sha(encode(recipe)),
        'patch_sha256': sha(patch.read_bytes()),
        'qualification': 'not established by a synthetic foundation; real PDF qualification required'}))
    return {'runtime_root': RUNTIME, 'files': len(actual), 'foundation_sha256': sha(encode(freeze))}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    print(json.dumps(build(p.parse_args().root.resolve())))
