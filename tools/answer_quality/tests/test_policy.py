"""Owned labeled controls, not real answer-quality benchmark judgments."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from tools.answer_quality.fidelity import match_quote, safe_quote_record, source_fields, text_sha
from tools.answer_quality.review import Assessment, HumanReview
from tools.answer_quality.validator import PostGenerationValidator, evaluate_dimensions
from tools.quality_dashboard.artifacts import ArtifactError, digest, sha


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def denied(*a, **kw):
        pytest.fail('NO_PROVIDER_OR_NETWORK_AUTHORIZED')
    for name in ('socket.socket.connect', 'socket.create_connection', 'socket.getaddrinfo',
                 'tools.preflight_suite.provider.load_key'):
        monkeypatch.setattr(name, denied)


@pytest.fixture
def owned():
    text = 'Atlas supports keyword search and semantic search. It does not cause errors. The limit is 10 ms.'
    parent = {'citation_locators': [{'page': 1}], 'consumer': {'llm_context': {
        'source_content': [{'text': text}], 'qualification': {'mandatory': False}}}}
    response = {'status': 'ANSWERED', 'answer': 'Atlas supports two search methods.',
        'claims': [{'claim_text': 'Atlas supports two search methods.', 'evidence_unit_ids': ['OWNED'],
            'supporting_quotes': [{'evidence_unit_id': 'OWNED', 'quote': 'Atlas supports keyword search and semantic search.'}]}],
        'missing_information': [], 'relevant_qualifications': [],
        'requirement_coverage': [{'requirement': 'Methods', 'status': 'SUPPORTED', 'evidence_unit_ids': ['OWNED']}],
        'conflicts_detected': []}
    return {'question': 'Which methods does Atlas support?', 'response': response,
        'package': {'parents': [{'evidence': {'unit_id': 'OWNED', 'verified_parent': parent}}]},
        'request_sha256': 'a' * 64, 'qualification': {'status': 'QUALIFICATIONS_VALID'}}


def review(data, **updates):
    parent = data['package']['parents'][0]['evidence']['verified_parent']
    pointer, text = source_fields(parent)[0]
    passage = {'unit_id': 'OWNED', 'pointer': pointer, 'field_sha256': text_sha(text), 'start': 0, 'end': len(text)}
    value = {'schema_version': 'answer-quality-assessment-2.0', 'method': 'HUMAN_REVIEW',
        'reviewer': 'OWNED-SYNTHETIC-NOT-A-REAL-HUMAN-APPROVAL', 'assessed_at': '2026-10-29',
        'question_sha256': hashlib.sha256(data['question'].encode()).hexdigest(),
        'response_sha256': digest(data['response']), 'package_sha256': digest(data['package']),
        'request_sha256': data['request_sha256'], 'independent_of_generator': True,
        'answer_claim_inventory_complete': True, 'question_requirements_reviewed': True,
        'response_status_appropriate': True, 'uncertainty': [],
        'claims': [{'claim_index': 0, 'claim_sha256': digest(data['response']['claims'][0]),
            'outcome': 'SUPPORTED', 'rationale': 'Owned labeled fixture supports both methods.', 'passages': [passage]}],
        'requirements': [{'requirement_id': 'OWNED-R1', 'requirement': 'Name the supported methods',
            'outcome': 'COMPLETE', 'rationale': 'Both methods are in the answer.', 'claim_indices': [0], 'passages': [passage]}],
        'qualifications': {'outcome': 'SATISFIED', 'rationale': 'No disclosure in owned fixture.', 'passages': []},
        'conflicts': {'outcome': 'SATISFIED', 'rationale': 'Owned source has no conflict.', 'passages': []}}
    return value | updates


def test_default_is_review_not_false_semantic_success(owned):
    result = evaluate_dimensions(**owned)
    assert result['citation_validity'] == 'PASS'
    assert result['raw_exact_matches'] == {'numerator': 1, 'denominator': 1}
    assert result['overall_status'] == 'REVIEW_REQUIRED'
    assert not result['fully_validated']


def test_qualifying_review_and_no_mutation(owned):
    before = copy.deepcopy(owned)
    result = evaluate_dimensions(**owned, assessment=review(owned), human_review_qualified=True)
    assert result['overall_status'] == 'VALIDATED'
    assert owned == before


@pytest.mark.parametrize('method', ['HUMAN_REVIEW', 'LLM_JUDGE', 'ASSISTANT_ANALYSIS', 'OFFLINE_FIXTURE'])
def test_self_asserted_or_model_judgment_not_independent_approval(owned, method):
    result = evaluate_dimensions(**owned, assessment=review(owned, method=method))
    assert result['overall_status'] == 'REVIEW_REQUIRED'
    assert not result['fully_validated']


@pytest.mark.parametrize('outcome,expected', [('CONTRADICTED', 'VALIDATION_FAILED'),
    ('UNSUPPORTED', 'VALIDATION_FAILED'), ('PARTIALLY_SUPPORTED', 'REVIEW_REQUIRED'),
    ('INDETERMINATE', 'REVIEW_REQUIRED')])
def test_claim_meaning_not_quote_similarity(owned, outcome, expected):
    value = review(owned); value['claims'][0]['outcome'] = outcome
    value['claims'][0]['rationale'] = 'Owned labeled causal/comparative claim control.'
    result = evaluate_dimensions(**owned, assessment=value, human_review_qualified=True)
    assert result['overall_status'] == expected
    assert result['citation_validity'] == 'PASS'


@pytest.mark.parametrize('mutation', ['request', 'source', 'claim', 'duplicate', 'pointer', 'unit', 'question'])
def test_review_bindings_fail_closed(owned, mutation):
    value = review(owned)
    if mutation == 'request': value['request_sha256'] = 'b' * 64
    if mutation == 'source': value['claims'][0]['passages'][0]['field_sha256'] = 'b' * 64
    if mutation == 'claim': value['claims'][0]['claim_sha256'] = 'b' * 64
    if mutation == 'duplicate': value['claims'].append(value['claims'][0])
    if mutation == 'pointer': value['claims'][0]['passages'][0]['end'] = 1000000
    if mutation == 'unit': value['claims'][0]['passages'][0]['unit_id'] = 'OTHER'
    if mutation == 'question': value['question_sha256'] = 'b' * 64
    with pytest.raises(ArtifactError):
        evaluate_dimensions(**owned, assessment=value, human_review_qualified=True)


@pytest.mark.parametrize('which', ['requirements', 'qualifications', 'conflicts'])
def test_missing_requirements_and_material_disclosure(owned, which):
    value = review(owned)
    if which == 'requirements': value[which][0]['outcome'] = 'INCOMPLETE'
    else: value[which]['outcome'] = 'MISSING'
    assert evaluate_dimensions(**owned, assessment=value, human_review_qualified=True)['overall_status'] == 'VALIDATION_FAILED'


def test_qualification_uncertainty_is_not_pass(owned):
    owned['qualification']['status'] = 'QUALIFICATION_APPLICABILITY_UNDETERMINED'
    value = review(owned); value['qualifications']['outcome'] = 'INDETERMINATE'
    assert evaluate_dimensions(**owned, assessment=value, human_review_qualified=True)['overall_status'] == 'REVIEW_REQUIRED'


def test_appropriate_unsupported_abstention_needs_real_assessment(owned):
    owned['response'].update(status='ABSTAINED', answer='', claims=[], missing_information=['Evidence does not supply the requested fact.'], requirement_coverage=[])
    assert evaluate_dimensions(**owned)['overall_status'] == 'REVIEW_REQUIRED'
    # Offline controls can supply a true independent full-answer review even when
    # there are no positive claims. No synthetic status is scored as real correctness.
    template = copy.deepcopy(owned)
    template['response']['claims'] = [{'claim_text': 'temporary', 'evidence_unit_ids': ['OWNED'], 'supporting_quotes': []}]
    value = review(template)
    value.update(response_sha256=digest(owned['response']), claims=[])
    value['requirements'][0].update(outcome='INCOMPLETE', claim_indices=[], passages=[], rationale='Requested fact unavailable; abstention is appropriate.')
    assert evaluate_dimensions(**owned, assessment=value, human_review_qualified=True)['overall_status'] == 'VALIDATED'


@pytest.mark.parametrize('unit', ['FABRICATED', 'EXAMPLE-UNIT-001'])
def test_favorable_semantics_never_overrides_bad_citation(owned, unit):
    owned['response']['claims'][0]['evidence_unit_ids'] = [unit]
    result = evaluate_dimensions(**owned, assessment=review(owned), human_review_qualified=True)
    assert result['citation_validity'] == 'FAIL' and result['overall_status'] == 'VALIDATION_FAILED'


def test_paraphrase_can_support_claim_but_not_be_verbatim(owned):
    owned['response']['claims'][0]['supporting_quotes'][0]['quote'] = 'Atlas offers lexical and meaning-based retrieval.'
    result = evaluate_dimensions(**owned, assessment=review(owned), human_review_qualified=True)
    assert result['claim_grounding'][0]['outcome'] == 'SUPPORTED'
    assert result['quotation_fidelity'][0]['outcome'] == 'SUBSTANTIVE_MISMATCH'
    assert result['overall_status'] == 'VALIDATION_FAILED'
    assert 'INVALID_CITATION' not in result['diagnoses']


def parent(text):
    return {'consumer': {'llm_context': {'source_content': [{'text': text}]}}, 'citation_locators': [{'page': 1}]}


@pytest.mark.parametrize('source,quote', [
    ('A source\n names two methods.', 'A source names two methods.'),
    ('Atlas uses “keyword search”.', 'Atlas uses "keyword search".'),
    ('Atlas doesn’t retrieve.', "Atlas doesn't retrieve.")])
def test_limited_presentation_matching(source, quote):
    result = match_quote(quote, 'OWNED', parent(source))
    assert result['outcome'] == 'PRESENTATION_EQUIVALENT'
    assert not result['raw_exact_match']
    assert source[result['source']['start']:result['source']['end']] == result['source']['original_text']
    assert 'original_text' not in safe_quote_record(result)['source']


@pytest.mark.parametrize('source,quote', [
    ('The source does not retrieve.', 'The source does retrieve.'),
    ('The limit is 10 ms.', 'The limit is 100 ms.'),
    ('The limit is 10 ms.', 'The limit is 10 s.'),
    ('Use pre-retrieval.', 'Use preretrieval.'),
    ('Use x < y.', 'Use x > y.'),
    ('Use -1.', 'Use 1.'),
    ('Use A+B.', 'Use AB.'),
    ('Atlas works.', 'Invented quotation.')])
def test_substantive_differences_not_erased(source, quote):
    assert match_quote(quote, 'OWNED', parent(source))['outcome'] == 'SUBSTANTIVE_MISMATCH'


def test_line_hyphen_needs_hash_bound_review():
    source = 'An adapt-\nability test preserves pre-retrieval.'
    quote = 'An adaptability test preserves pre-retrieval.'
    p = parent(source); pointer, text = source_fields(p)[0]
    assert match_quote(quote, 'OWNED', p)['outcome'] == 'INDETERMINATE'
    item = {'unit_id': 'OWNED', 'quote_sha256': text_sha(quote), 'field_sha256': text_sha(text),
        'pointer': pointer, 'start': 0, 'end': len(text), 'operation': 'PDF_LINE_END_WORD_REJOIN', 'review_id': 'OWNED-REVIEW'}
    assert match_quote(quote, 'OWNED', p, layout_reviews=[item])['outcome'] == 'PRESENTATION_EQUIVALENT'
    item['field_sha256'] = 'b' * 64
    assert match_quote(quote, 'OWNED', p, layout_reviews=[item])['outcome'] == 'INDETERMINATE'
    assert match_quote(quote, 'MISSING', None)['outcome'] == 'SOURCE_NOT_FOUND'


def test_source_location_cannot_move_to_other_unit():
    assert match_quote('Atlas works.', 'WRONG', parent('Another source.'))['outcome'] == 'SUBSTANTIVE_MISMATCH'


def test_code_reflow_is_not_certified():
    assert match_quote('`x = 1`', 'OWNED', parent('`x  = 1`'))['outcome'] == 'INDETERMINATE'


def test_human_review_import_requires_external_hash_and_trusted_identity(owned, tmp_path):
    path = tmp_path / 'review.json'; path.write_text(json.dumps(review(owned)))
    with pytest.raises(ArtifactError): HumanReview(tmp_path, 'review.json', 'b' * 64, approved_reviewers=set())
    with pytest.raises(ArtifactError): HumanReview(tmp_path, 'review.json', sha(path), approved_reviewers=set())
    assessor = HumanReview(tmp_path, 'review.json', sha(path), approved_reviewers={review(owned)['reviewer']})
    assert isinstance(assessor.assess(), Assessment)


def test_native_validator_rejects_source_before_assessor(owned):
    validator = PostGenerationValidator.__new__(PostGenerationValidator)
    class Source:
        def validate(self, *args): raise ValueError('TAMPERED')
    validator.service = Source()
    result = validator.validate(owned['response'], owned['package'], {}, question=owned['question'], request_binding={})
    assert result['overall_status'] == 'VALIDATION_FAILED'
    assert result['semantic_status'] == 'NOT_ASSESSED'


def test_historical_validators_and_prompt_are_unchanged():
    root = Path(__file__).resolve().parents[3]
    critical = json.loads((root / 'data/evals/generation-trust/v1/BASELINE_BINDINGS.json').read_bytes())
    for name in ['tools/quality_dashboard/post_generation.py', 'tools/pre_generation_gate/current.py',
                 'tools/pre_generation_gate/response_v2.py']:
        # The old current.py implementation is now explicitly versioned; its
        # original bytes remain pinned while current.py selects the successor.
        selected = ('tools/pre_generation_gate/prompt_v21.py'
                    if name == 'tools/pre_generation_gate/current.py' else name)
        assert sha(root / selected) == critical[name]

@pytest.mark.parametrize('claim,rationale', [
    ('Keyword search causes semantic search.', 'Source lists methods and establishes no causal relationship.'),
    ('Keyword search always performs better than semantic search.', 'Source supplies no comparative performance result.')])
def test_labeled_causal_and_comparative_additions_block(owned, claim, rationale):
    owned['response']['claims'][0]['claim_text'] = claim
    owned['response']['answer'] = claim
    value = review(owned)
    value['claims'][0].update(outcome='UNSUPPORTED', rationale=rationale)
    result = evaluate_dimensions(**owned, assessment=value, human_review_qualified=True)
    assert result['overall_status'] == 'VALIDATION_FAILED'
    assert result['raw_exact_matches']['numerator'] == 1


def test_support_elsewhere_in_cited_parent_is_not_quote_coverage_failure(owned):
    owned['response']['claims'][0]['supporting_quotes'][0]['quote'] = 'Atlas supports keyword search'
    value = review(owned)
    value['claims'][0]['quotation_coverage_gap'] = 'Selected quote omits semantic search; complete cited source supports it.'
    result = evaluate_dimensions(**owned, assessment=value, human_review_qualified=True)
    assert result['overall_status'] == 'VALIDATED'
    assert result['claim_grounding'][0]['quotation_coverage_gap']


def test_bounded_partial_requires_independent_status_review(owned):
    owned['response'].update(status='PARTIAL', missing_information=['Third-party ranking measurements are unavailable.'])
    value = review(owned)
    value['requirements'][0].update(outcome='PARTIAL', rationale='Known methods supplied; requested measurements disclosed as missing.')
    assert evaluate_dimensions(**owned, assessment=value, human_review_qualified=True)['overall_status'] == 'VALIDATED'
    value['response_status_appropriate'] = None
    assert evaluate_dimensions(**owned, assessment=value, human_review_qualified=True)['overall_status'] == 'REVIEW_REQUIRED'


def test_ambiguous_punctuation_needs_meaning_review_not_false_error():
    source, quote = 'Atlas, however, works.', 'Atlas however works'
    p = parent(source); pointer, text = source_fields(p)[0]
    result = match_quote(quote, 'OWNED', p)
    assert result['outcome'] == 'INDETERMINATE'
    item = {'operation': 'LIMITED_PUNCTUATION_REVIEW', 'review_method': 'HUMAN_REVIEW',
        'meaning_preserving': True, 'unit_id': 'OWNED', 'quote_sha256': text_sha(quote),
        'pointer': pointer, 'field_sha256': text_sha(text), 'start': 0, 'end': len(text), 'review_id': 'OWNED-PUNCTUATION'}
    assert match_quote(quote, 'OWNED', p, layout_reviews=[item])['outcome'] == 'PRESENTATION_EQUIVALENT'
    item['meaning_preserving'] = False
    assert match_quote(quote, 'OWNED', p, layout_reviews=[item])['outcome'] == 'INDETERMINATE'


@pytest.mark.parametrize('source,quote', [('The count is 1,000.', 'The count is 1000.'),
    ('Use A.B.', 'Use AB.'), ('Use C++.', 'Use C.')])
def test_punctuation_probe_never_certifies_numbers_or_technical_changes(source, quote):
    assert match_quote(quote, 'OWNED', parent(source))['outcome'] == 'SUBSTANTIVE_MISMATCH'
