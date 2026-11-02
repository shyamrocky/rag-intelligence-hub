"""Private, bounded forensic excerpts; component probes, not M8 source authority."""
import json
from pathlib import Path

import pytest

from tools.answer_quality.fidelity import match_quote, source_fields, text_sha
from tools.quality_dashboard.artifacts import sha

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'data/evals/generation-runner-reviews/q04-quotation-investigation-v1'


@pytest.mark.parametrize('index', range(8))
def test_all_eight_sealed_q04_presentation_cases(index):
    if not BASE.is_dir():
        pytest.skip('Private forensic input unavailable; no replacement labels invented.')
    assert sha(BASE / 'MANIFEST.json') == 'e47ce47b390eeb6261571724a9afc54fbff29189db1a15c9747104486693df63'
    manifest = json.loads((BASE / 'MANIFEST.json').read_bytes())
    assert sha(BASE / 'QUOTATION_MATRIX.json') == manifest['files']['QUOTATION_MATRIX.json']
    item = json.loads((BASE / 'QUOTATION_MATRIX.json').read_bytes())['quotes'][index]
    # Deliberately bounded excerpt fixture, not a reconstructed parent/package.
    parent = {'consumer': {'llm_context': {'source_content': [{'text': item['source_excerpt_exact']}]}},
              'citation_locators': item['citation_locators']}
    pointer, text = source_fields(parent)[0]
    layout = []
    if not item['whitespace_only_match']:
        layout = [{'unit_id': item['unit_id'], 'quote_sha256': item['generated_quote_sha256'],
            'field_sha256': text_sha(text), 'pointer': pointer, 'start': 0, 'end': len(text),
            'operation': 'PDF_LINE_END_WORD_REJOIN', 'review_id': 'BOUNDED_EXCERPT_COMPONENT_' + item['quote_id']}]
        assert match_quote(item['generated_quote'], item['unit_id'], parent)['outcome'] == 'INDETERMINATE'
    result = match_quote(item['generated_quote'], item['unit_id'], parent, layout_reviews=layout)
    assert result['outcome'] == 'PRESENTATION_EQUIVALENT'
    assert result['raw_exact_match'] is False
