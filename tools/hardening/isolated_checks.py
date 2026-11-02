"""Independent copied-root native positive and tamper controls; originals never mutated."""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from rag_hub.unified_models import encode, sha


def build_and_check(root, copy_root=None):
    os.umask(0o077)
    if copy_root is None:
        copy_root = Path(tempfile.mkdtemp(prefix='rag-h2-native-restore-')) / 'project'
        copy_root.mkdir()
    else:
        copy_root = copy_root.resolve(strict=True)
        if (not copy_root.is_relative_to(Path(tempfile.gettempdir()).resolve())
                or not copy_root.parent.name.startswith('rag-h2-native-restore-')
                or copy_root.name != 'project'):
            raise ValueError('not_an_owned_disposable_restore_root')
    descriptor = json.loads((root / 'data/validation/provenance/durable-consumer-v1/BINDINGS.json').read_bytes())
    names = set(descriptor['files']) | {
        'config/unified-durable-selection-v1.json',
        'data/validation/provenance/durable-consumer-v1/BINDINGS.json'}
    for prefix in ['src/rag_hub', 'config', 'data/manifests', 'data/normalized/html',
                   'data/validation', 'data/ingestion', 'data/raw', 'data/snapshots']:
        names.update(str(p.relative_to(root)) for p in (root / prefix).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts)
    inventory = []
    for name in sorted(names):
        source, target = root / name, copy_root / name
        if source.is_symlink() or not source.resolve().is_relative_to(root):
            raise ValueError('unsupported_copy_source_alias')
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if source.read_bytes() != target.read_bytes():
                raise ValueError('existing_disposable_copy_changed')
        else:
            shutil.copyfile(source, target)
        if source.read_bytes() != target.read_bytes():
            raise ValueError('independent_copy_mismatch')
        inventory.append({'path': name, 'sha256': sha(target.read_bytes())})
    code = '''
import json,sys
from pathlib import Path
original=Path(sys.argv[2]); root=Path(sys.argv[1]); denied=[]
def audit(event,values):
 if event=='open' and values and isinstance(values[0],str):
  p=Path(values[0]); p=p if p.is_absolute() else root/p
  if any(p.is_relative_to(original/s)for s in ['src','config','data','workspace','archive','releases']):
   denied.append(str(p)); raise PermissionError('original_project_evidence_access_denied')
sys.addaudithook(audit)
sys.path.insert(0,str(root/'src'))
from rag_hub.durable_unified_selection import load_durable_corpus
corpus=load_durable_corpus(root)
summary=corpus.catalog.get_corpus_summary()
assert summary['units']==553 and summary['sections']==3040 and not denied
print(json.dumps({'status':'PASS','summary':summary,'original_evidence_read_attempts':denied}))
'''
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    def load():
        return subprocess.run([str(root / '.venv/bin/python'), '-I', '-c', code,
            str(copy_root), str(root)], cwd=copy_root, env=env, text=True,
            capture_output=True, check=False)
    baseline = load()
    if baseline.returncode:
        raise ValueError('isolated_native_baseline_failed:' + baseline.stderr[-2500:])
    witness = json.loads((root / 'config/pdf-durable-qualification-policy-v1.json').read_bytes())['source_scope_witness']
    source = json.loads((root / 'data/parsed/pdf/four-pdf-poc-v1/C06/source.json').read_bytes())['snapshot_path']
    selected = json.loads((root / 'config/pdf-durable-admission-publication-v1.json').read_bytes())
    cases = [('selector', 'config/unified-durable-selection-v1.json'),
             ('descriptor', 'data/validation/provenance/durable-consumer-v1/BINDINGS.json'),
             ('source_snapshot', source), ('source_witness', witness),
             ('policy', 'config/pdf-durable-qualification-policy-v1.json'),
             ('publication', selected['manifest_path']),
             ('implementation', 'src/rag_hub/shared/pipeline.py')]
    results = []
    for case, name in cases:
        p = copy_root / name
        raw = p.read_bytes()
        p.write_bytes(raw + b' altered-owned-copy')
        try:
            result = load()
            if not result.returncode:
                raise ValueError('isolated_corruption_accepted:' + case)
            results.append({'case': case, 'rejected': True, 'exit_code': result.returncode,
                            'last_error': result.stderr.strip().splitlines()[-1]})
        finally:
            p.write_bytes(raw)
    p = copy_root / witness
    raw = p.read_bytes()
    p.unlink()
    try:
        result = load()
        if not result.returncode:
            raise ValueError('isolated_missing_witness_accepted')
        results.append({'case': 'missing_witness', 'rejected': True, 'exit_code': result.returncode})
    finally:
        p.write_bytes(raw)
    rollback = load()
    if rollback.returncode:
        raise ValueError('copied_root_restoration_failed:' + rollback.stderr[-2000:])
    return {'status': 'PASS', 'authority': 'DISPOSABLE_COPY_TEST_NOT_QA', 'copy_root': str(copy_root),
            'copied_files': len(inventory), 'inventory': inventory,
            'baseline': json.loads(baseline.stdout), 'negative_controls': results,
            'restored_copy_replay': json.loads(rollback.stdout),
            'original_source_and_venv_not_copied': 'Original implementation/evidence denied; pinned host Python/site-packages reused, not cross-host qualification',
            'original_files_modified': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--reuse-copy-root', type=Path)
    args = p.parse_args()
    result = build_and_check(args.root.resolve(), args.reuse_copy_root)
    with args.output.open('xb') as stream:
        stream.write(encode(result))
    print(json.dumps({k: result[k] for k in ['status', 'copy_root', 'copied_files']}))
