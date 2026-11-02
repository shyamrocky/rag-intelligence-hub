"""Build explicit H2 evidence/QA successors; no defaults, new admission or inference."""

import argparse
import copy
import json
import os
import shutil
from pathlib import Path

from rag_hub.chunk_preparation import write_once
from rag_hub.pdf_corpus import encoded, load_corpus
from rag_hub.unified_models import sha

PREPARATION = 'workspace/rag-implementation/v1/h2-h3-preparation-v1'
HOME = 'data/validation/provenance/durable-consumer-v1'
POLICY = 'config/pdf-durable-qualification-policy-v1.json'
RELEASE = 'config/pdf-durable-qa-successor-v1.json'
PDF_SELECTION = 'config/pdf-durable-admission-publication-v1.json'


def read(root, path):
    return json.loads((root / path).read_bytes())


def save(root, path, value):
    write_once(root / path, encoded(value))


def evidence(root):
    plan = read(root, PREPARATION + '/plan-v1/RECONCILED_DEPENDENCIES.json')
    rows = plan['rows']
    if len(rows) != 88 or sum(r['new_active_role'] == 'RETAIN_EVIDENCE' for r in rows) != 50:
        raise ValueError('unexpected_approved_evidence_plan')
    receipt = read(root, 'workspace/rag-implementation/v1/h2-h3-implementation-v1/OWNER_AUTHORIZATION.json')
    save(root, HOME + '/OWNER_AUTHORIZATION.json', receipt)
    copied = []
    for row in rows:
        old, new = root / row['path'], root / row['proposed_target']
        if sha(old.read_bytes()) != row['expected_sha256']:
            raise ValueError('original_workspace_evidence_changed')
        if not new.resolve().is_relative_to(root.resolve()) or new.is_symlink():
            raise ValueError('invalid_durable_evidence_destination')
        new.parent.mkdir(parents=True, exist_ok=True)
        if new.exists():
            if sha(new.read_bytes()) != row['expected_sha256']:
                raise ValueError('durable_evidence_conflict')
        else:
            with new.open('xb') as stream, old.open('rb') as original:
                shutil.copyfileobj(original, stream)
            new.chmod(0o400)
        copied.append({k: row[k] for k in ['path', 'proposed_target', 'expected_sha256',
                                          'new_active_role', 'existing_exact_durable_copy']})
    save(root, HOME + '/EVIDENCE_MIGRATION.json', {
        'schema': 'durable-evidence-migration-1.0',
        'authority': 'PROVENANCE_MAPPING_NOT_QA_ADMISSION', 'rows': copied,
        'originals_preserved': True, 'runtime_roles': 50, 'archive_roles': 38,
        'owner_authorization_sha256': sha(encoded(receipt))})
    return copied


def qa(root):
    from rag_hub.c14_scope_correction import verify_corrected_evidence
    from rag_hub.pdf_text_handoff import load_units, publish
    from rag_hub.pdf_text_recovery import verify_release

    mappings = read(root, HOME + '/EVIDENCE_MIGRATION.json')['rows']
    remap = {r['path']: r['proposed_target'] for r in mappings if r['new_active_role'] == 'RETAIN_EVIDENCE'}
    old_selection = read(root, 'config/pdf-c14-scope-admission-publication-v1.json')
    old_release = read(root, old_selection['release_path'])
    old_policy_path = old_release['qualification_policy_path']
    old_policy = read(root, old_policy_path)
    policy = copy.deepcopy(old_policy)
    policy['source_scope_witness'] = remap[policy['source_scope_witness']]
    policy['frozen_bindings'] = {remap.get(p, p): h for p, h in policy['frozen_bindings'].items()}
    policy['packaging_predecessor_policy_sha256'] = sha(encoded(old_policy))
    policy['packaging_owner_authorization'] = HOME + '/OWNER_AUTHORIZATION.json'
    save(root, POLICY, policy)
    release = copy.deepcopy(old_release)
    release.update(release_id='combined-pdf-durable-qa-1.0',
                   predecessor_release_sha256=old_selection['expected_release_sha256'],
                   predecessor_publication=old_selection,
                   qualification_policy_path=POLICY, changed_document_scope=[],
                   packaging_only_successor=True)
    release['files'] = {remap.get(p, p): h for p, h in release['files'].items()
                        if p != old_policy_path}
    release['files'][POLICY] = sha(encoded(policy))
    if any(p.startswith('workspace/') for p in release['files']):
        raise ValueError('unmigrated_native_release_evidence')
    save(root, RELEASE, release)
    auth = {
        'schema': 'pdf-text-execution-authorization-1.0',
        'authority': 'Explicit owner H2/H3 compatibility approval; packaging-only replay, no source requalification or identity attestation',
        'scope': ['C01', 'C02', 'C06', 'C14'], 'changed_document_scope': [],
        'release_sha256': sha(encoded(release)), 'policy_sha256': sha(encoded(policy)),
        'source_witness_sha256': sha((root / policy['source_scope_witness']).read_bytes()),
        'packaging_owner_authorization_sha256': sha((root / HOME / 'OWNER_AUTHORIZATION.json').read_bytes()),
        'authorization': 'Rebind exact existing scopes through unchanged shared QA; no eligibility expansion',
        'owner_acceptance_of_candidate_results': False}
    ap = 'data/validation/pdf/durable-consumer-v1/authorizations/' + sha(encoded(auth)) + '.json'
    save(root, ap, auth)
    args = {'release_path': RELEASE, 'expected_release_sha256': sha(encoded(release)),
            'authorization_path': ap, 'authorization_sha256': sha(encoded(auth))}
    save(root, HOME + '/PDF_PUBLICATION_ARGS.json', args)
    # Real relocated witness through the actual native release and source verifier.
    verify_release(root, RELEASE, args['expected_release_sha256'])
    witness = read(root, policy['source_scope_witness'])
    predecessor = read(root, witness['predecessor_evidence']['path'])
    verify_corrected_evidence(load_corpus(root)['documents']['C14'], predecessor, witness,
                              read(root, policy['recovery_evidence']['C14']))
    save(root, HOME + '/NATIVE_WITNESS_VERIFICATION.json', {
        'status': 'PASS', 'source': 'C14', 'witness_path': policy['source_scope_witness'],
        'witness_sha256': auth['source_witness_sha256'], 'release_sha256': args['expected_release_sha256'],
        'verification': 'native verify_release + verify_corrected_evidence',
        'source_scope_changed': False})
    dest = 'data/validation/pdf/durable-consumer-v1/publications/' + args['authorization_sha256']
    manifest = publish(root, **args, destination=dest)
    selection = {k: args[k] for k in ['release_path', 'expected_release_sha256', 'authorization_sha256']}
    selection.update(manifest_path=dest + '/manifest.json', expected_manifest_sha256=sha(encoded(manifest)))
    views = load_units(root, **selection)
    old_manifest = read(root, old_selection['manifest_path'])
    by_doc = {}
    for desc in manifest['publications']:
        record = read(root, desc['path'])
        old_desc = next(d for d in old_manifest['publications'] if d['path'].endswith('/' + record['doc_id'] + '.json'))
        previous = read(root, old_desc['path'])
        if previous['qa']['pdf_text_support'] != record['qa']['pdf_text_support']:
            raise ValueError('packaging_changed_source_scope')
        old_decisions = previous['qa']['quality_decisions']
        new_decisions = record['qa']['quality_decisions']
        if [(d['section_id'], d['status']) for d in old_decisions] != [
                (d['section_id'], d['status']) for d in new_decisions]:
            raise ValueError('packaging_changed_admission')
        by_doc[record['doc_id']] = {'sections': len(new_decisions),
            'approved': sum(d['status'] == 'approved_for_index' for d in new_decisions),
            'native_units': len(record['qa']['pdf_text_support']['units'])}
    if len(views) != 312:
        raise ValueError('wrong_durable_pdf_scope')
    save(root, PDF_SELECTION, selection)
    save(root, HOME + '/PDF_QA_RECONCILIATION.json', {
        'authority': 'INSPECTION_OF_SHARED_QA_OUTPUT_NOT_NEW_ENGINE',
        'status': 'PASS', 'documents': by_doc, 'native_units': len(views),
        'original_admissions_and_source_scopes_unchanged': True, 'selection': selection})
    return selection


def unified(root):
    import re

    from rag_hub.unified_bindings import FREEZE, INDEX

    current = read(root, 'data/chunking/m3-c14-scope-v2/manifest.json')
    files = {p: h for p, h in current['upstream_files'].items() if not p.startswith('workspace/')}
    migrations = read(root, HOME + '/EVIDENCE_MIGRATION.json')['rows']
    for r in migrations:
        if r['new_active_role'] == 'RETAIN_EVIDENCE':
            files[r['proposed_target']] = r['expected_sha256']
    selection = read(root, PDF_SELECTION)
    release = read(root, RELEASE)
    manifest = read(root, selection['manifest_path'])
    files.update(release['files'])
    for p in [RELEASE, PDF_SELECTION, selection['manifest_path'],
              HOME + '/OWNER_AUTHORIZATION.json', manifest['admission']['authorization_path']]:
        files[p] = sha((root / p).read_bytes())
    for desc in manifest['publications']:
        files[desc['path']] = desc['sha256']
    issues = read(root, 'data/validation/pdf/c14-scope-correction-v1/PDF_QA_ISSUES.json')
    issues['publication_selection'] = selection
    issuepath = 'data/validation/pdf/durable-consumer-v1/PDF_QA_ISSUES.json'
    save(root, issuepath, issues)
    files[issuepath] = sha(encoded(issues))
    descriptor = {'schema': 'durable-unified-bindings-1.0',
        'authority': 'NATIVE_PUBLICATIONS_NOT_NEW_ADMISSION', 'files': files,
        'selectors': {'html': 'config/html-c10-admission-publication.json',
                      'markdown': 'config/markdown-admission-publication-v1-1.json',
                      'pdf': PDF_SELECTION},
        'source_freeze': FREEZE, 'html_markdown_index': INDEX, 'pdf_issues': issuepath,
        'expected_counts': {'documents': 16, 'sections': 3040, 'units': 553,
                            'admitted': 2572, 'excluded': 110, 'HOLD': 358},
        'predecessor': {'path': 'config/unified-c14-scope-selection-v1.json',
                        'sha256': sha((root / 'config/unified-c14-scope-selection-v1.json').read_bytes())},
        'archive_roles_not_runtime_inputs': 38}
    dp = HOME + '/BINDINGS.json'
    save(root, dp, descriptor)
    selected = {'schema': 'durable-unified-selection-1.0', 'descriptor_path': dp,
                'descriptor_sha256': sha(encoded(descriptor))}
    sp = 'config/unified-durable-selection-v1.json'
    save(root, sp, selected)
    source_path = root / 'src/rag_hub/durable_unified_selection.py'
    source = source_path.read_text()
    new = re.sub(r"SELECTOR_SHA = '[^']+'", "SELECTOR_SHA = '" + sha(encoded(selected)) + "'", source)
    if new != source:
        if "SELECTOR_SHA = 'AWAITING_QUALIFIED_BUILD'" not in source:
            raise ValueError('immutable_durable_composition_identity_changed')
        source_path.write_text(new)
    from rag_hub.durable_unified_selection import load_durable_corpus

    corpus = load_durable_corpus(root)
    summary = corpus.catalog.get_corpus_summary()
    if summary['membership_edges'] != 3727 or summary['units'] != 553:
        raise ValueError('durable_graph_scope_changed')
    if any(p.startswith(('workspace/', 'archive/', 'releases/'))
           for p in corpus.binding_manifest()['files']):
        raise ValueError('durable_snapshot_still_has_working_dependencies')
    save(root, HOME + '/UNIFIED_VERIFICATION.json', {
        'status': 'PASS', 'summary': summary, 'selector': sp,
        'selector_sha256': sha(encoded(selected)),
        'descriptor_sha256': sha(encoded(descriptor)),
        'bindings': corpus.binding_manifest()['files']})
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--stage', choices=['evidence', 'qa', 'unified'], required=True)
    args = parser.parse_args()
    os.umask(0o077)
    root = args.root.resolve()
    result = {'evidence': evidence, 'qa': qa, 'unified': unified}[args.stage](root)
    print(json.dumps({'stage': args.stage, 'result': result if isinstance(result, dict) else len(result)}))


if __name__ == '__main__':
    main()
