"""Explicit strict-ingestion launcher; no historical/default/latest fallback."""

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

WORKER_SHA = '00cc7f0790e8c6e87430d7c03e400dac1572b5a6ef799d1e28209133d3a9be8a'

def load_selection(root, path):
    selected_path = (root / path).resolve(strict=True)
    if not selected_path.is_relative_to(root) or selected_path.is_symlink():
        raise ValueError('ingestion_selection_outside_project')
    selected = json.loads(selected_path.read_bytes())
    build_path = root / selected['build_path']
    raw = build_path.read_bytes()
    if (selected['schema'] != 'strict-ingestion-selection-1.0'
            or hashlib.sha256(raw).hexdigest() != selected['build_sha256']):
        raise ValueError('strict_build_identity_changed')
    build = json.loads(raw)
    runtime = (root / selected['runtime_root']).resolve(strict=True)
    if not runtime.is_relative_to(root / 'releases/ingestion'):
        raise ValueError('invalid_strict_runtime_root')
    if build['runtime_root'] != selected['runtime_root'] or build['foundation_sha256'] != selected['foundation_sha256']:
        raise ValueError('strict_selection_mismatch')
    foundation = (runtime / selected['foundation_path']).resolve(strict=True)
    if (not foundation.is_relative_to(runtime)
            or selected['foundation_path'] != build['foundation_path']
            or hashlib.sha256((foundation / 'foundation-freeze.json').read_bytes()).hexdigest()
            != selected['foundation_sha256']):
        raise ValueError('strict_foundation_identity_changed')
    for name, expected in build['actual_image_files'].items():
        p = (runtime / name).resolve(strict=True)
        if not p.is_relative_to(runtime) or hashlib.sha256(p.read_bytes()).hexdigest() != expected:
            raise ValueError('strict_runtime_component_changed:' + name)
    return runtime, foundation


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--selector', required=True)
    p.add_argument('--source-manifest', required=True, type=Path)
    p.add_argument('--release', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    root = args.root.resolve()
    runtime, foundation = load_selection(root, args.selector)
    manifest, release, output = [x.resolve() for x in [args.source_manifest, args.release, args.output]]
    if not all(x.is_relative_to(runtime) for x in [manifest, release, output]):
        p.error('source-manifest, release and output must belong to the explicit isolated runtime')
    if release != foundation:
        p.error('release must equal the exact qualified foundation from the explicit selector')
    worker = root / 'tools/ingestion/strict_worker.py'
    if hashlib.sha256(worker.read_bytes()).hexdigest() != WORKER_SHA:
        p.error('strict worker implementation fingerprint changed')
    env = os.environ.copy()
    for key in ['PYTHONPATH', 'PYTHONHOME', 'RAG_TEST_QA_RELEASE', 'PYTEST_PLUGINS']:
        env.pop(key, None)
    env.update(PYTHONDONTWRITEBYTECODE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    command = [str(root / '.venv/bin/python'), '-I', str(worker),
        '--runtime-root', str(runtime), '--source-manifest', str(manifest),
        '--release', str(release), '--output', str(output)]
    raise SystemExit(subprocess.run(command, env=env, cwd=runtime, check=False).returncode)


if __name__ == '__main__':
    main()
