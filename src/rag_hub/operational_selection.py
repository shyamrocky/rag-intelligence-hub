"""H4 inspection selections, not an admission registry or a new release default.

Only these exact compatible published stacks can be opened. Native readers
remain the authorization authority. No model or numerical array is imported.
"""

import copy
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from rag_hub.chunk_catalog import ChunkCatalog
from rag_hub.dashboard_data import DashboardData
from rag_hub.qualified_chunk_catalog import QualifiedChunkCatalog
from rag_hub.unified_bindings import BoundFiles
from rag_hub.unified_models import encode, sha

HISTORICAL = 'config/retrieval-chunks-v2.json'
PILOT = 'config/retrieval-chunks-c01-v2.json'
PREMIGRATION = 'config/retrieval-chunks-m3-c14-scope-v2.json'
DURABLE = 'config/retrieval-chunks-m3-durable-v1.json'
MODES = {
    HISTORICAL: {'name': 'Historical full corpus', 'release': 'm3-corpus-v2',
        'loader': 'historical', 'units': 550, 'chunks': 893, 'catalog_units': 550,
        'selector_sha': 'fdeefb6f99c0ed2ff779219442c912a0046ef9f267a307e7b1e058a14fcf1dfd',
        'manifest_sha': 'd3aec5237a145e7b5f033f385aea5428edbda98c3cd7f7cde3cc25d5ae81a211'},
    PILOT: {'name': 'C01 pilot', 'release': 'm3-c01-v2', 'loader': 'historical',
        'units': 550, 'catalog_units': 61, 'chunks': 88,
        'selector_sha': '0211cde0c00177bdff21b67f8194f0b29d222ecab7a6a353a84f6e3490a29475',
        'manifest_sha': '50e72e7f2eb3c6b12ad5667cc1705bf15cef2f80bbd1dc4280e5bc0458d05550'},
    PREMIGRATION: {'name': 'Accepted pre-migration full corpus', 'release': 'm3-c14-scope-v2',
        'loader': 'c14', 'units': 553, 'catalog_units': 553, 'chunks': 992,
        'selector_sha': 'ce8ec2bf179903874e2030475f1b037c00918e51a0d375ed7692ac62c020ed14',
        'manifest_sha': 'f07828feea381507a76ed06e2b7d86f7bd79eab65c8f1188d70ce82cce92653c'},
    DURABLE: {'name': 'Durable full corpus — current operational candidate', 'release': 'm3-durable-v1',
        'loader': 'durable', 'units': 553, 'catalog_units': 553, 'chunks': 992,
        'selector_sha': '8ec4237d894e7c3a045010ca4ad5a767d36d2cd8fdaadef1f9fbbbd6becc9d4a',
        'manifest_sha': '49e254767e3aa4f5b0724cf95ec3ab0d5787d49d74d6bacf5420dc04486dd57c'},
}
# These are UI state keys, never evidence or alias maps. Remove even common IDs
# on release switch so a prior page cannot retain detached source content.
SELECTION_KEYS = {
    'document', 'selected_section', 'selected_unit', 'inspector_mode',
    'chunk_unit_filter', 'chunk_section_filter', 'chunk_document', 'chunk_page',
    'chunk_entered', 'chunk_selected', 'relationship_doc', 'relationship_unit',
    'inspector_entered', 'assembly_document', 'assembly_unit',
}


def switch_release(state, identity):
    if state.get('_operational_identity') == identity:
        return False
    for key in list(state):
        if key in SELECTION_KEYS or str(key).startswith('page:'):
            del state[key]
    state['_operational_identity'] = identity
    return True


@dataclass
class ReleaseSelection:
    selector: str
    spec: dict
    bound: BoundFiles
    manifest: dict
    key: str

    def check(self):
        self.bound.check()


def resolve_selection(root, selector):
    """No arbitrary paths, latest fallback, or caller-selected reader imports."""
    if selector not in MODES:
        raise ValueError('unsupported_operational_release')
    spec = copy.deepcopy(MODES[selector])
    bound = BoundFiles(root)
    selected = json.loads(bound.bind(selector, spec['selector_sha']))
    if (selected.get('schema') != 'chunk-catalog-selection-1.0'
            or selected['manifest_sha256'] != spec['manifest_sha']):
        raise ValueError('incompatible_operational_manifest')
    manifest = json.loads(bound.bind(selected['manifest_path'], spec['manifest_sha']))
    summary = manifest['summary']
    if (summary['units'] != spec['catalog_units'] or summary['chunks'] != spec['chunks']):
        raise ValueError('incompatible_operational_counts')
    key = sha(encode({'schema': 'dashboard-selection-1.0', 'selector': selector,
                      'spec': spec, 'upstream': manifest['upstream_files'],
                      'components': manifest['components']}))
    return ReleaseSelection(selector, spec, bound, manifest, key)


def construct_dashboard(root, selection):
    """Use the accepted native composition for each fixed mode."""
    selection.check()
    if sys.version_info[:2] != (3, 12):
        raise ValueError('dashboard_requires_locked_python_3_12')
    if selection.spec['loader'] == 'durable':
        from rag_hub.durable_unified_selection import load_durable_corpus
        corpus = load_durable_corpus(root)
    elif selection.spec['loader'] == 'c14':
        from rag_hub.c14_unified_selection import load_c14_verified_corpus
        corpus = load_c14_verified_corpus(root)
    else:
        from rag_hub.unified_consumption import load_verified_corpus
        corpus = load_verified_corpus(root)
    data = DashboardData(root, corpus=corpus)
    if data.summary()['units'] != selection.spec['units']:
        raise ValueError('operational_corpus_count_changed')
    return data


def construct_catalog(root, data, selection):
    data.check()
    selection.check()
    # Check before reader construction as well as the native reader's own check.
    if data.binding_fingerprints != selection.manifest['upstream_files']:
        raise ValueError('incompatible_operational_corpus_and_catalog')
    reader = QualifiedChunkCatalog if selection.spec['loader'] in {'c14', 'durable'} else ChunkCatalog
    return reader(root, data.corpus, selector=selection.selector)


class EmbeddingMetadata:
    """Hash-bound metadata only. Does not claim fresh vector/model qualification.

    Verifies complete record-to-catalog identity and artifact byte bindings using
    the original manifest. Hashes vector bytes; never decodes them or loads a
    model. The accepted M4 reader remains the numerical-validation interface.
    """

    SELECTOR = 'config/embedding-artifacts-m4-durable-v1.json'
    SELECTOR_SHA = '6117f3697071bbefbb2ac2c421645846119a37e50073d5665cfed05f952f9a23'
    MANIFEST_SHA = '9b304b4b8be9eb4aa3af22ea3d5fd2625a9b097951564077369943ee239c6ac6'

    def __init__(self, root, catalog):
        self.bound, self.catalog = BoundFiles(root), catalog
        selected = json.loads(self.bound.bind(self.SELECTOR, self.SELECTOR_SHA))
        if selected['manifest_sha256'] != self.MANIFEST_SHA:
            raise ValueError('embedding_metadata_wrong_manifest')
        m = json.loads(self.bound.bind(selected['manifest_path'], self.MANIFEST_SHA))
        if (m['schema'] != 'embedding-manifest-1.0' or m['chunks'] != 992
                or m['dimension'] != 384 or m['dtype'] != 'float32'):
            raise ValueError('unsupported_embedding_metadata')
        ref = m['catalog_selector']
        selected_catalog = json.loads(self.bound.bind(ref['path'], ref['sha256']))
        if (ref['path'] != DURABLE or m['catalog_manifest_sha256'] != MODES[DURABLE]['manifest_sha']
                or selected_catalog['manifest_sha256'] != m['catalog_manifest_sha256']
                or sha(encode(catalog.manifest)) != sha(encode(json.loads(self.bound.bind(
                    selected_catalog['manifest_path'], m['catalog_manifest_sha256']))))):
            raise ValueError('embedding_metadata_wrong_catalog')
        for path, digest in m['files'].items():
            self.bound.bind(path, digest)
        config = json.loads(self.bound.bind(m['model_configuration']['path'],
                                           m['model_configuration']['sha256']))
        for path, digest in config['bound_files'].items():
            self.bound.bind(path, digest)
        records = [json.loads(line) for line in self.bound.path(m['records_path']).read_text().splitlines()]
        rows = catalog.list_chunks(limit=1000)['items']
        if len(records) != 992 or len(rows) != 992:
            raise ValueError('embedding_metadata_incomplete_records')
        for index, (record, row) in enumerate(zip(records, rows, strict=True)):
            if (record['row_index'] != index or record['chunk_id'] != row['chunk_id']
                    or record['chunk_sha256'] != sha(encode(row))
                    or record['unit_id'] != row['unit_id']
                    or record['parent_binding'] != row['parent_binding']):
                raise ValueError('embedding_metadata_row_binding_changed')
        self.value = {'authority': 'INSPECTION_ONLY_HASH_BOUND_METADATA',
            'availability': 'COMPATIBLE_ARTIFACT_PRESENT', 'model': config['model_repo'],
            'revision': config['revision'], 'dimensions': m['dimension'], 'embeddings': len(records),
            'manifest_sha256': self.MANIFEST_SHA, 'selector': self.SELECTOR,
            'pooling': m['pooling'], 'normalization': m['normalization'],
            'qualification': 'M4 owner acceptance pending; provisional baseline, not a retrieval-quality winner. '
                'Metadata validation does not rerun model or numerical correctness checks.'}
        self.check()

    def check(self):
        self.bound.check()
        self.catalog.check()

    def export(self):
        self.check()
        return copy.deepcopy(self.value)


def runtime_description():
    return {'python': sys.version.split()[0], 'prefix': sys.prefix,
            'module_origin': str(Path(__file__).resolve()),
            'required_launch': 'uv run --locked --offline --project apps/ingestion_dashboard '
                               'streamlit run apps/ingestion_dashboard/app.py'}
