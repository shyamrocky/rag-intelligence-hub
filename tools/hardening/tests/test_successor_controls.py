"""Actual public-view reuse negatives and standalone strict-selection controls."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


@pytest.fixture(scope='module')
def reuse():
    from rag_hub.c14_unified_selection import load_c14_verified_corpus
    from rag_hub.durable_unified_selection import load_durable_corpus
    from rag_hub.embedding_artifacts import EmbeddingArtifacts
    from rag_hub.m2_tokenizer import PinnedBgeTokenizer
    from rag_hub.qualified_chunk_catalog import QualifiedChunkCatalog

    producer = module('reuse_producer', 'tools/embeddings/rebind_artifacts.py')
    before = load_c14_verified_corpus(ROOT)
    old_catalog = QualifiedChunkCatalog(ROOT, before, selector='config/retrieval-chunks-m3-c14-scope-v2.json')
    old = EmbeddingArtifacts(ROOT, old_catalog, selector='config/embedding-artifacts-m4-v1.json')
    after = load_durable_corpus(ROOT)
    catalog = QualifiedChunkCatalog(ROOT, after, selector='config/retrieval-chunks-m3-durable-v1.json')
    mapping = json.loads((ROOT / 'data/chunking/m3-durable-v1/CHUNK_ID_RECONCILIATION.json').read_bytes())[0]
    cid = mapping['old_chunk_id']
    original = old.open_bound_chunk(cid)
    candidate = catalog.open_chunk(mapping['new_chunk_id'])
    text = next(x['text'] for x in map(json.loads,
        (ROOT / old.manifest['inputs_path']).read_text().splitlines()) if x['chunk_id'] == cid)
    return producer, original, candidate, old.records[cid], text, PinnedBgeTokenizer(ROOT)


def test_actual_source_token_scope_bijection_sample(reuse):
    producer, old, new, record, text, tokenizer = reuse
    output, _, ids = producer.equivalent(old, new, record, text, tokenizer)
    assert output == text and len(ids) == record['tokens_including_specials']


@pytest.mark.parametrize('defect', ['input', 'source', 'heading', 'qualification', 'context',
                                   'citation', 'membership', 'token_record', 'scope'])
def test_reuse_rejects_adversarial_view_or_saved_binding(reuse, defect):
    producer, old, new, record, text, tokenizer = reuse
    new, record = copy.deepcopy(new), copy.deepcopy(record)
    if defect == 'input':
        text += ' forged'
    elif defect == 'source':
        new['source_slice'] += ' forged'
    elif defect == 'heading':
        new['heading_context'].append({'text': 'forged heading'})
    elif defect == 'qualification':
        new['verified_parent']['consumer']['llm_context']['qualification']['mandatory'] = False
    elif defect == 'context':
        new['verified_parent']['consumer']['llm_context']['required_context'] = [{'forged': True}]
    elif defect == 'citation':
        new['verified_parent']['citation_locators'] = []
    elif defect == 'membership':
        new['verified_parent']['memberships'] = []
    elif defect == 'token_record':
        record['token_ids_sha256'] = '0' * 64
    else:
        new['chunk']['mandatory_evidence_refs']['scope'] = 'detached_fragment'
    with pytest.raises((ValueError, KeyError)):
        producer.equivalent(old, new, record, text, tokenizer)


def test_actual_strict_selection_hashes_the_qualified_foundation():
    launcher = module('strict_launcher', 'tools/ingestion/run.py')
    runtime, foundation = launcher.load_selection(ROOT, 'config/ingestion-strict-v1.json')
    assert runtime == ROOT / 'releases/ingestion/strict-v1/root'
    assert foundation.is_relative_to(runtime)


@pytest.mark.parametrize('defect', ['source', 'foundation', 'build', 'wrong_path'])
def test_owned_strict_selector_fixture_rejects_tampering(tmp_path, defect):
    from rag_hub.unified_models import encode, sha

    launcher = module('strict_launcher_fixture', 'tools/ingestion/run.py')
    runtime = tmp_path / 'releases/ingestion/strict-v1/root'
    foundation = runtime / 'data/ingestion/strict-v1'
    foundation.mkdir(parents=True)
    (foundation / 'foundation-freeze.json').write_bytes(b'owned foundation')
    source = runtime / 'owned.txt'
    source.write_bytes(b'owned source')
    build = {'runtime_root': 'releases/ingestion/strict-v1/root',
             'foundation_path': 'data/ingestion/strict-v1',
             'foundation_sha256': sha(b'owned foundation'),
             'actual_image_files': {'owned.txt': sha(b'owned source')}}
    (tmp_path / 'build.json').write_bytes(encode(build))
    selection = {'schema': 'strict-ingestion-selection-1.0', 'runtime_root': build['runtime_root'],
                 'foundation_path': build['foundation_path'], 'foundation_sha256': build['foundation_sha256'],
                 'build_path': 'build.json', 'build_sha256': sha(encode(build))}
    (tmp_path / 'selection.json').write_bytes(encode(selection))
    assert launcher.load_selection(tmp_path, 'selection.json')[0] == runtime
    if defect == 'source':
        source.write_bytes(b'corrupt')
    elif defect == 'foundation':
        (foundation / 'foundation-freeze.json').write_bytes(b'forged self-receipted foundation')
    elif defect == 'build':
        (tmp_path / 'build.json').write_bytes(b'{}')
    else:
        selection['runtime_root'] = '../escape'
        (tmp_path / 'selection.json').write_bytes(encode(selection))
    with pytest.raises((ValueError, FileNotFoundError)):
        launcher.load_selection(tmp_path, 'selection.json')


@pytest.fixture(scope='module')
def successor_artifacts():
    from rag_hub.durable_unified_selection import load_durable_corpus
    from rag_hub.embedding_artifacts import EmbeddingArtifacts
    from rag_hub.qualified_chunk_catalog import QualifiedChunkCatalog

    corpus = load_durable_corpus(ROOT)
    catalog = QualifiedChunkCatalog(ROOT, corpus, selector='config/retrieval-chunks-m3-durable-v1.json')
    artifacts = EmbeddingArtifacts(ROOT, catalog, selector='config/embedding-artifacts-m4-durable-v1.json')
    return corpus, catalog, artifacts


def test_prior_publication_IDs_are_not_aliased(successor_artifacts):
    corpus, catalog, artifacts = successor_artifacts
    mapping = next(m for m in json.loads((ROOT / 'data/chunking/m3-durable-v1/CHUNK_ID_RECONCILIATION.json').read_bytes())
                   if m['old_unit_id'] != m['new_unit_id'])
    with pytest.raises(ValueError):
        corpus.evidence.get_verified_unit(mapping['old_unit_id'])
    with pytest.raises(ValueError):
        catalog.open_chunk(mapping['old_chunk_id'])
    with pytest.raises(ValueError):
        artifacts.get_vector(mapping['old_chunk_id'])


def test_old_vector_envelope_cannot_authorize_new_catalog(successor_artifacts):
    from rag_hub.embedding_artifacts import EmbeddingArtifacts

    _, catalog, _ = successor_artifacts
    with pytest.raises(ValueError, match='embedding_wrong_chunk_catalog'):
        EmbeddingArtifacts(ROOT, catalog, selector='config/embedding-artifacts-m4-v1.json')
