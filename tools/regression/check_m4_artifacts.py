"""Existing read-only current-stack gate: no model construction, inference or generation."""

import argparse
import copy
import importlib.metadata
import json
import resource
import time
from pathlib import Path

from rag_hub.c14_unified_selection import load_c14_verified_corpus
from rag_hub.embedding_artifacts import EmbeddingArtifacts
from rag_hub.m2_tokenizer import PinnedBgeTokenizer
from rag_hub.qualified_chunk_catalog import QualifiedChunkCatalog
from rag_hub.unified_models import encode, sha

SELECTIONS = {
    'config/unified-c14-scope-selection-v1.json':
        '382c87b298fd94034910128ae7ceda3ac8730287d1ec1e505fd632874baf3c5e',
    'config/retrieval-chunks-m3-c14-scope-v2.json':
        'ce8ec2bf179903874e2030475f1b037c00918e51a0d375ed7692ac62c020ed14',
    'config/embedding-artifacts-m4-v1.json':
        '3b98da33894debfecd532b3fabf62b76b2d0fa364d5a1bad76d132532f377cfc',
}
M3_MANIFEST = 'f07828feea381507a76ed06e2b7d86f7bd79eab65c8f1188d70ce82cce92653c'
M4_MANIFEST = 'e9e1a5edb83db723384ce8583f053b31d65d93a7318a21d5948fb4f0e71e4baa'


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def verify_selections(root, selections=None):
    """Gate only the explicitly authorized stack; no latest-version discovery."""
    from rag_hub.unified_bindings import BoundFiles

    bound = BoundFiles(root)
    selected = SELECTIONS if selections is None else selections
    require(selected == SELECTIONS, 'wrong_release_selection')
    documents = {name: json.loads(bound.bind(name, digest)) for name, digest in selected.items()}
    for name, expected in [(list(SELECTIONS)[1], M3_MANIFEST),
                           (list(SELECTIONS)[2], M4_MANIFEST)]:
        require(documents[name]['manifest_sha256'] == expected, 'wrong_catalog_or_model_binding')
        bound.bind(documents[name]['manifest_path'], expected)
    bound.check()
    return documents


def verify_c10_context(parent, qualified_native_id):
    """Apply the published C10 delta qualification, not a document-wide table rule."""
    if parent['native_unit_id'] != qualified_native_id:
        return False
    require(parent['document_id'] == 'C10', 'wrong_C10_delta_document')
    context = parent['consumer']['llm_context']
    require(any(o.get('issue_id') == 'HTML-SRC-SCORE-STAGE'
                and o.get('kind') == 'QA_OBSERVATION'
                and o.get('origin') == 'ingestion_QA_not_publisher'
                and o.get('must_accompany') for o in context['qa_observations']),
            'missing_C10_scoring_observation')
    require(any(c.get('relationship_type') == 'documented_RRF_context_not_numerical_equivalence'
                and c.get('required') and c.get('unit_id')
                for c in context['required_context']), 'missing_C10_RRF_context')
    return True


def verify(root, *, depth='full'):
    require(depth in {'fast', 'full'}, 'invalid_artifact_gate_depth')
    started = time.perf_counter()
    root = Path(root).resolve()
    selections = verify_selections(root)
    corpus = load_c14_verified_corpus(root)
    summary = corpus.catalog.get_corpus_summary()
    expected = {'documents': 16, 'sections': 3040, 'admitted': 2572, 'excluded': 110,
                'HOLD': 358, 'units': 553, 'membership_edges': 3727}
    require(all(summary[k] == v for k, v in expected.items()), 'wrong_current_corpus_scope')
    catalog = QualifiedChunkCatalog(root, corpus, selector=list(SELECTIONS)[1])
    artifacts = EmbeddingArtifacts(root, catalog, selector=list(SELECTIONS)[2])
    rows = catalog.list_chunks(limit=1000)['items']
    require(len(rows) == len(artifacts.records) == 992 and artifacts.vectors.shape == (992, 384),
            'wrong_current_artifact_counts')
    config = json.loads(artifacts.bound.path(
        artifacts.manifest['model_configuration']['path']).read_bytes())
    runtime = {name: importlib.metadata.version(name) for name in config['runtime_versions']}
    require(runtime == config['runtime_versions'], 'wrong_embedding_runtime_versions')
    require(config['model_repo'] == 'BAAI/bge-small-en-v1.5'
            and config['revision'] == '5c38ec7c405ec4b44b94cc5a9bb96e735b38267a'
            and config['encoding']['pooling'] == 'CLS'
            and config['encoding']['normalize_embeddings'], 'wrong_pinned_model_configuration')
    inputs = {r['chunk_id']: r['text'] for r in map(json.loads,
        artifacts.bound.path(artifacts.manifest['inputs_path']).read_text().splitlines())}
    tokenizer = PinnedBgeTokenizer(root)
    units = {r['unit_id']: r for r in corpus.catalog.list_units()}
    html_selection = json.loads((root / 'config/html-c10-admission-publication.json').read_bytes())
    html_manifest = json.loads((root / html_selection['manifest_path']).read_bytes())
    c10_native_id = html_manifest['delta_unit_id']
    require(sum(u['native_unit_id'] == c10_native_id for u in units.values()) == 1,
            'missing_or_duplicate_C10_delta_unit')
    memberships = {uid: corpus.catalog.get_unit_sections(uid) for uid in units}
    links = sum(map(len, memberships.values()))
    require({r['unit_id'] for r in rows} == set(units), 'unrepresented_current_unit')
    require(links == 3727 and {o['unit_id'] for o in catalog.outcomes()} == set(units),
            'incomplete_parent_or_membership_accounting')
    for status, count in [('HOLD', 358), ('EXCLUDED', 110)]:
        page = corpus.catalog.list_sections(filters={'admission_status': status}, limit=1000)
        require(page['total'] == count, 'wrong_nonadmitted_scope')
        for section in page['items']:
            require(not section['unit_ids'] and not catalog.get_section_chunks(section['section_id']),
                    'nonadmitted_section_exposed')
    for row in rows:
        cid = row['chunk_id']
        record = artifacts.records[cid]
        token_ids = tokenizer.encode(inputs[cid]).ids
        require(sha(inputs[cid].encode()) == record['input_text_sha256']
                and sha(encode(token_ids)) == record['token_ids_sha256']
                and len(token_ids) == row['token_count'] <= record['total_token_limit'],
                'source_input_or_tokenizer_binding_changed')
        members = {edge['section_id']: edge for edge in memberships[row['unit_id']]}
        require(set(row['lineage']['section_ids']) <= set(members), 'chunk_section_lineage_missing')
        require(all(members[s]['role'] in {'content', 'projection'}
                    for s in row['lineage']['section_ids']), 'context_only_used_as_source')
    opened, negative = 0, []
    opened_units, c10_checked = set(), False
    protected, expired = set(), set()
    selected_rows = rows if depth == 'full' else [rows[0]]
    for row in selected_rows:
        view = artifacts.open_bound_chunk(row['chunk_id'])
        parent = view['verified_parent']
        require(parent['consumer']['llm_context']['qualification']['mandatory'],
                'missing_mandatory_qualification')
        require(encode(parent['citation_locators']) == encode(
            units[row['unit_id']]['citation_locators']), 'parent_citation_binding_changed')
        opened += 1
        opened_units.add(row['unit_id'])
        context = parent['consumer']['llm_context']
        c10_checked = verify_c10_context(parent, c10_native_id) or c10_checked
        if row['document_id'] == 'C04' and 'restricted_projection' in row['source']['pointer']:
            protected.add(row['unit_id'])
        if parent['consumer'].get('publication_expiration', {}).get('status') == 'EXPIRED':
            require(parent['consumer']['publication_expiration']['warning']
                    and any(o.get('issue_id') == 'PDF_PUBLICATION_EXPIRED'
                            and o.get('display_to_user_when_used')
                            for o in context['qa_observations']), 'missing_expiry_warning')
            expired.add(row['unit_id'])
        if opened == 1:
            bad = copy.deepcopy(view)
            del bad['verified_parent']['consumer']['llm_context']['qualification']
            try:
                catalog.validate_view(bad)
            except ValueError:
                negative.append('qualification_removal_rejected')
            else:
                raise ValueError('qualification_removal_accepted')
        if opened % 100 == 0:
            print(f'Validated {opened}/992 live chunk-parent bindings', flush=True)
    if depth == 'full':
        require(len(protected) == 4, 'protected_markdown_parent_missing')
        require(opened_units == set(units), 'unverified_current_parent')
        require(c10_checked, 'C10_qualification_not_checked')
        pdf = json.loads((root / 'config/pdf-c14-scope-admission-publication-v1.json').read_bytes())
        publication = json.loads((root / pdf['manifest_path']).read_bytes())
        expected_expiry = set()
        for descriptor in publication['publications']:
            for unit in json.loads((root / descriptor['path']).read_bytes())['qa']['pdf_text_support']['units']:
                if unit.get('historical_publication_interval'):
                    expected_expiry.add(unit['id'])
        native = {unit['native_unit_id']: uid for uid, unit in units.items() if unit['format'] == 'pdf'}
        require(expired == {native[uid] for uid in expected_expiry}, 'expiry_qualification_scope_changed')
    artifacts.check()
    return {'schema': 'current-artifact-gate-2.0', 'result': 'PASS', 'depth': depth,
            'corpus': expected, 'shape': list(artifacts.vectors.shape), 'records': len(rows),
            'all992_saved_input_token_vector_and_catalog_lineage_bindings': True,
            'all992_live_parent_input_bindings': depth == 'full',
            'live_complete_parent_rehydrations': opened,
            'unique_live_parents_checked': len(opened_units),
            'C10_required_context_and_QA_observation_checked': c10_checked,
            'protected_markdown_parents_checked': len(protected),
            'negative_controls': negative, 'selections': selections, 'runtime_versions': runtime,
            'inference': False, 'authority': 'VERIFICATION_ONLY_NOT_ADMISSION',
            'seconds': time.perf_counter() - started,
            'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--depth', choices=['fast', 'full'], default='full')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = verify(Path.cwd(), depth=args.depth)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
