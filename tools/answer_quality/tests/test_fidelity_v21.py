"""Bounded successor controls; owned prose is never real source authority."""
import copy

import pytest

from tools.answer_quality.fidelity import match_quote as legacy
from tools.answer_quality.fidelity import source_fields, text_sha
from tools.answer_quality.fidelity_v21 import match_quote


def parent(text):
    return {'consumer': {'llm_context': {'source_content': [{'text': text}]}},
        'citation_locators': [{'page': 1}]}


@pytest.mark.parametrize('source,quote', [
    ('The retrieval phase returns passages.', 'the retrieval phase returns passages.'),
    ('Prose ends. The retrieval phase returns passages.', 'the retrieval phase returns passages.'),
    ('The retrieval\nphase returns passages.', 'the retrieval phase returns passages.'),
])
def test_unique_initial_determiner_only(source, quote):
    p = parent(source)
    before = copy.deepcopy(p)
    r = match_quote(quote, 'owned', p)
    assert r['outcome'] == 'PRESENTATION_EQUIVALENT'
    assert r['source']['original_text'] == source[r['source']['start']:r['source']['end']]
    assert not r['raw_exact_match'] and p == before
    assert legacy(quote, 'owned', p)['outcome'] == 'SUBSTANTIVE_MISMATCH'


@pytest.mark.parametrize('source,quote', [
    ('The Model uses IndexA.', 'the Model uses IndexA.'),
    ('The index uses ModelA.', 'the index uses modelA.'),
    ('We use The retrieval layer.', 'the retrieval layer.'),
    ('The retrieval returns 10 ms.', 'the retrieval returns 10 s.'),
    ('The retrieval returns 10 ms.', 'the retrieval returns 11 ms.'),
    ('The retrieval is not exact.', 'the retrieval is exact.'),
    ('The retrieval uses pre-retrieval.', 'the retrieval uses preretrieval.'),
    ('The retrieval uses x >= 2.', 'the retrieval uses x > 2.'),
    ('The retrieval returns passages.', 'the retrieval produces passages.'),
    ('The retrieval returns passages. The retrieval returns passages.', 'the retrieval returns passages.'),
    ('C. The retrieval returns passages.', 'the retrieval returns passages.'),
])
def test_meaningful_or_ambiguous_changes_never_pass(source, quote):
    assert match_quote(quote, 'owned', parent(source))['outcome'] != 'PRESENTATION_EQUIVALENT'


def test_reviewed_pdf_split_requires_exact_trusted_span():
    p = parent('By intro-\nducing questions, retrieval narrows the gap.')
    pointer, text = source_fields(p)[0]
    quote = 'By introducing questions, retrieval narrows the gap.'
    record = {'unit_id': 'owned', 'quote_sha256': text_sha(quote),
        'field_sha256': text_sha(text), 'pointer': pointer, 'start': 0, 'end': len(text),
        'operation': 'PDF_LINE_END_WORD_REJOIN', 'review_id': 'trusted-layout-fixture'}
    assert match_quote(quote, 'owned', p)['outcome'] == 'INDETERMINATE'
    assert match_quote(quote, 'owned', p, layout_reviews=[record])['outcome'] == 'PRESENTATION_EQUIVALENT'
    for change in [{'unit_id':'another'}, {'field_sha256':'0'*64}, {'end':len(text)-1}]:
        assert match_quote(quote, 'owned', p, layout_reviews=[record | change])['outcome'] != 'PRESENTATION_EQUIVALENT'
    assert match_quote(quote, 'owned', None)['outcome'] == 'SOURCE_NOT_FOUND'
    assert match_quote('By pre-retrieval matching.', 'owned', parent('By preretrieval matching.'),
        layout_reviews=[record])['outcome'] == 'SUBSTANTIVE_MISMATCH'
