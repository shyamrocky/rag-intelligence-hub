"""Owned offline boundaries only. Never corpus authority, provider access or live mode.

The real prompt gate, GenerationService, parser, capture, budget and validator are
exercised. Retrieval, native source reconstruction and input counts are SYNTHETIC.
This module cannot be selected by a live execution path.
"""
import copy
import json
from types import MethodType

from tools.bot_runtime.store import text_sha
from tools.quality_dashboard.artifacts import digest

TEXT = 'This is an owned simulation of evidence-grounded retrieval.'
UID = 'owned-bot-fixture:unit-1'
SCENARIOS = ('abstained', 'answered', 'partial', 'schema-error', 'api-failure', 'empty-evidence')


def boundaries(question, scenario):
    from tools.evidence.service import EvidenceService
    from tools.pre_generation_gate.gate import M8_SELECTOR, M8_SHA

    if scenario not in SCENARIOS:
        raise ValueError('UNKNOWN_MOCK_SCENARIO')
    result = {'schema': 'm7-candidates-1.0', 'query_sha256': text_sha(question),
        'retrieval_mode': 'hybrid', 'release_identity': 'OWNED_SYNTHETIC_NOT_PUBLISHED',
        'index_release_bindings': {}, 'parameters': {'top_k': 30, 'candidate_depth': 50, 'rrf_k': 60, 'filters': {}},
        'candidates': [] if scenario == 'empty-evidence' else [{'chunk_id': 'owned-bot-fixture:chunk-1',
            'unit_id': UID, 'document_id': 'OWNED_FIXTURE', 'rank': 1}],
        'diagnostics': {'quality': 'NOT_EVALUATED', 'fixture_only': True}}
    parent = {'unit_id': UID, 'document_id': 'OWNED_FIXTURE', 'admission_status': 'ADMITTED',
        'citation_locators': [{'source': 'Owned synthetic test data'}],
        'consumer': {'llm_context': {'source_content': {'text': TEXT},
            'qualification': {'mandatory': False}, 'qa_observations': []}}}
    package = {'release_identity': 'OWNED_SYNTHETIC_NOT_PUBLISHED',
        'retrieval': {'query_sha256': text_sha(question), 'candidate_result_sha256': digest(result)},
        'parents': [] if scenario == 'empty-evidence' else [{'evidence': {'unit_id': UID, 'verified_parent': parent}}],
        'counts': {'selected_parents': 0 if scenario == 'empty-evidence' else 1, 'omitted_parents': 0},
        'budget': {'limit': 128000, 'exact_llm_evidence_tokens': None},
        'llm_evidence': '' if scenario == 'empty-evidence' else json.dumps(parent)}
    service = EvidenceService.__new__(EvidenceService)
    service.selector, service.selector_sha256 = M8_SELECTOR, M8_SHA
    service.inventory, service.files = {}, {}

    def check(_self):
        return None

    def validate(_self, actual, candidates):
        if actual != package or candidates != result:
            raise ValueError('OWNED_FIXTURE_CHANGED')
        return True

    def assemble(_self, candidates, *, token_budget):
        if candidates != result or token_budget != 128000:
            raise ValueError('OWNED_FIXTURE_CONFIGURATION_CHANGED')
        return copy.deepcopy(package)

    service.check = MethodType(check, service)
    service.validate = MethodType(validate, service)
    service.assemble = MethodType(assemble, service)
    return result, service


def answer(scenario):
    if scenario not in {'answered', 'partial'}:
        return None  # Reuse OfflineAdapter's existing explicit abstention control.
    partial = scenario == 'partial'
    return {'status': 'PARTIAL' if partial else 'ANSWERED', 'answer': TEXT,
        'claims': [{'claim_text': TEXT, 'evidence_unit_ids': [UID],
            'supporting_quotes': [{'evidence_unit_id': UID, 'quote': TEXT}]}],
        'missing_information': ['This owned fixture does not answer the remaining requirement.'] if partial else [],
        'relevant_qualifications': [], 'conflicts_detected': [],
        'requirement_coverage': [{'requirement': 'Owned fixture requirement',
            'status': 'PARTIAL' if partial else 'SUPPORTED', 'evidence_unit_ids': [UID]}]}
