"""Isolated worker: imports must originate solely in the explicit strict image."""

import argparse
import copy
import dataclasses
import importlib
import json
import sys
from pathlib import Path


def run(root, manifest, release, output):
    from rag_hub.shared.builtins import entries
    from rag_hub.shared.pipeline import execute
    from rag_hub.shared.registry import Registry

    home = root / 'data/ingestion/strict-v1'
    options = json.loads((home / 'ADAPTER_OPTIONS.json').read_bytes())
    adapter = dataclasses.replace(entries()[0], options=options,
        assets=(home / 'classification-input.json', home / 'reviewed-c06-split.json'))
    return execute(manifest, Registry((adapter,)), release=release, output=output)


def origin_check(root):
    for name, module in tuple(sys.modules.items()):
        if name == 'rag_hub' or name.startswith('rag_hub.'):
            p = getattr(module, '__file__', None)
            if p and not Path(p).resolve().is_relative_to(root / 'src/rag_hub'):
                raise ValueError('mixed_strict_runtime_import:' + name)


def qualify(root):
    from rag_hub.acquire import digest
    from rag_hub.shared import pipeline

    home = root / 'data/ingestion/strict-v1'
    pipeline.verify_foundation(home)
    controls = []
    for value in [None, '', '   ']:
        for function in ['verify_foundation', 'execute']:
            try:
                if function == 'verify_foundation':
                    pipeline.verify_foundation(value)
                else:
                    pipeline.execute({}, None, release=value, output=home / 'must-not-write')
            except ValueError as exc:
                if str(exc) != 'explicit_ingestion_release_required':
                    raise
                controls.append(function + ':missing_release:' + repr(value))
            else:
                raise ValueError('omitted_release_accepted')
        try:
            pipeline.execute({}, None, release=home, output=value)
        except ValueError as exc:
            if str(exc) != 'explicit_ingestion_output_required':
                raise
            controls.append('execute:missing_output:' + repr(value))
        else:
            raise ValueError('omitted_output_accepted')
    old_home = pipeline.HOME
    pipeline.HOME = home / 'forbidden-HOME'
    try:
        try:
            pipeline.execute({}, None, output=home / 'must-not-write')
        except ValueError as exc:
            if str(exc) != 'explicit_ingestion_release_required':
                raise
            controls.append('HOME_assignment_cannot_restore_fallback')
        else:
            raise ValueError('HOME_fallback_restored')
    finally:
        pipeline.HOME = old_home
    if (home / 'must-not-write').exists() or (home / 'forbidden-HOME').exists():
        raise ValueError('rejected_omission_wrote_artifact')
    # Real manifests/bytes, current native parser and maintained structural assets.
    docs = {}
    for doc in ['C01', 'C02', 'C06', 'C14']:
        source = json.loads((home / f'sources/{doc}.json').read_bytes())
        record = run(root, source, home, home / 'qualification' / doc)
        if record['program_status'] != 'completed':
            raise ValueError('real_strict_ingestion_failed:' + doc + ':' + str(record['diagnostics']))
        raw = home / 'qualification' / doc / 'runs' / record['run_id']
        blocks = json.loads((raw / 'blocks.json').read_bytes())
        expected = json.loads((home / f'expected/{doc}/blocks.json').read_bytes())
        if blocks != expected:
            raise ValueError('strict_parser_source_observations_changed:' + doc)
        qa = json.loads((raw / 'qa.json').read_bytes())
        if any(d['status'] != 'hold' for d in qa['quality_decisions']):
            raise ValueError('strict_foundation_promoted_unqualified_content')
        stages = record['stages']
        if len({(s['source_id'], s['stage'], s['attempt_id']) for s in stages}) != len(stages):
            raise ValueError('competing_strict_stage_owner')
        facets = json.loads((raw / 'review-facets.json').read_bytes()) if doc == 'C06' else None
        parents = json.loads((raw / 'parents.json').read_bytes())
        if doc == 'C06':
            pair = [p for p in parents if p.get('source_review_case') == 'P3-RP2-C06-049']
            if len(pair) != 2 or facets['mathematical_completeness'] != 'FAIL/HOLD':
                raise ValueError('strict_C06_split_or_math_HOLD_changed')
        docs[doc] = {'program_status': record['program_status'], 'blocks': len(blocks),
                     'original_blocks_identical': True, 'all_content_HOLD': True,
                     'stages': {s['stage']: s['status'] for s in stages},
                     'source_sha256': source['raw_sha256'], 'run_id': record['run_id']}
    # Altered real source must fail, never be silently excluded or admitted.
    source = copy.deepcopy(json.loads((home / 'sources/C06.json').read_bytes()))
    source['raw_sha256'] = '0' * 64
    bad = run(root, source, home, home / 'negative-source')
    if bad['program_status'] != 'failed' or bad['stages'][0]['status'] != 'failure':
        raise ValueError('corrupt_strict_source_accepted')
    controls.append('altered_real_source_rejected')
    origin_check(root)
    return {'status': 'PASS', 'real_PDFs': docs, 'negative_controls': controls,
            'foundation_sha256': digest((home / 'foundation-freeze.json').read_bytes()),
            'real_execution_foundation_qualified': True, 'source_readiness_granted': False,
            'QA_admission_authority_changed': False, 'mathematical_completeness': 'FAIL/HOLD'}


def rich_guards(root):
    import tempfile

    import rag_hub
    from rag_hub.shared import pipeline
    from rag_hub.shared.registry import Registry
    from rag_hub.unified_models import encode, sha

    home = root / 'data/ingestion/strict-v1'
    original = json.loads((home / 'foundation-freeze.json').read_bytes())
    controls = []
    for kind in ['fingerprint', 'receipt', 'dependencies', 'file_set', 'missing_file']:
        with tempfile.TemporaryDirectory(prefix='rag-strict-control-') as temporary:
            path = Path(temporary)
            freeze = copy.deepcopy(original)
            if kind == 'fingerprint':
                freeze['files']['src/rag_hub/schemas.py'] = '0' * 64
            elif kind == 'dependencies':
                freeze['dependencies']['pymupdf'] = '0.0.0'
            elif kind == 'file_set':
                del freeze['files']['src/rag_hub/shared/registry.py']
            elif kind == 'missing_file':
                freeze['files']['data/missing-owned-control'] = '0' * 64
            (path / 'foundation-freeze.json').write_bytes(encode(freeze))
            (path / 'foundation-freeze-receipt.json').write_bytes(encode({
                'foundation_manifest_sha256': '0' * 64 if kind == 'receipt' else sha(encode(freeze))}))
            try:
                pipeline.verify_foundation(path)
            except (ValueError, FileNotFoundError) as exc:
                controls.append({'case': kind, 'rejected': True, 'reason': str(exc)})
            else:
                raise ValueError('forged_strict_foundation_accepted:' + kind)
    previous = rag_hub.__file__
    try:
        rag_hub.__file__ = str(root / 'forged/rag_hub/__init__.py')
        try:
            pipeline.verify_foundation(home)
        except ValueError as exc:
            controls.append({'case': 'wrong_import_origin', 'rejected': True, 'reason': str(exc)})
        else:
            raise ValueError('wrong_strict_origin_accepted')
    finally:
        rag_hub.__file__ = previous
    source = json.loads((home / 'sources/C06.json').read_bytes())
    failed = pipeline.execute(source, Registry(()), release=home, output=home / 'negative-unsupported-format')
    if failed['program_status'] != 'failed' or failed['stages'][1]['status'] != 'failure':
        raise ValueError('unsupported_strict_parser_accepted')
    controls.append({'case': 'unsupported_parser', 'rejected': True,
                     'stage_evidence': {s['stage']: s['status'] for s in failed['stages']}})
    from rag_hub.shared.builtins import entries

    options = json.loads((home / 'ADAPTER_OPTIONS.json').read_bytes())
    options['reviewed_split']['constraint']['groups'][0][0]['end'] += 1000000
    adapter = dataclasses.replace(entries()[0], options=options)
    failed = pipeline.execute(source, Registry((adapter,)), release=home, output=home / 'negative-span')
    if failed['program_status'] != 'failed':
        raise ValueError('invalid_strict_span_accepted')
    controls.append({'case': 'invalid_source_span', 'rejected': True,
                     'stage_evidence': {s['stage']: s['status'] for s in failed['stages']}})
    origin_check(root)
    return {'status': 'PASS', 'controls': controls, 'authority': 'NEGATIVE_EXECUTION_EVIDENCE_NOT_QA'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime-root', type=Path, required=True)
    p.add_argument('--qualify', action='store_true')
    p.add_argument('--guards-only', action='store_true')
    p.add_argument('--deny-original-evidence', action='store_true')
    p.add_argument('--source-manifest', type=Path)
    p.add_argument('--release', type=Path)
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    root = args.runtime_root.resolve()
    import tempfile

    bytecode = tempfile.TemporaryDirectory(prefix='rag-strict-bytecode-')
    sys.dont_write_bytecode = True
    sys.pycache_prefix = bytecode.name
    sys.path.insert(0, str(root / 'src'))
    importlib.invalidate_caches()
    denied_controls = []
    if args.deny_original_evidence:
        original = Path(__file__).resolve().parents[2]
        def audit(event, values):
            if event in {'socket.connect', 'socket.getaddrinfo'}:
                raise PermissionError('strict_network_access_forbidden')
            if event == 'open' and values and isinstance(values[0], str):
                path = Path(values[0])
                path = path if path.is_absolute() else root / path
                if any(path.is_relative_to(original / name)
                       for name in ['workspace', 'src', 'data', 'config']):
                    raise PermissionError('strict_original_evidence_read_forbidden')
        sys.addaudithook(audit)
        for name in ['workspace', 'src', 'data', 'config']:
            try:
                (original / name / 'owned-denial-control').read_bytes()
            except PermissionError:
                denied_controls.append(name)
            else:
                raise ValueError('original_evidence_denial_not_active')
    if args.qualify:
        result = qualify(root)
    elif args.guards_only:
        result = rich_guards(root)
    else:
        if args.release is None or args.output is None or args.source_manifest is None:
            p.error('explicit source-manifest, release and output are required')
        result = run(root, json.loads(args.source_manifest.read_bytes()), args.release, args.output)
        origin_check(root)
    result['original_evidence_denial_controls'] = denied_controls
    result['denial_method'] = 'trusted Python audit; OS sandbox unavailable' if args.deny_original_evidence else 'not_requested'
    print(json.dumps(result))
    if not args.qualify and not args.guards_only and result['program_status'] != 'completed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
