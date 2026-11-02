"""Quotation fidelity 2.1: bounded sentence-determiner case plus reviewed layout.

No general case folding: only the prose determiner The/the at a true source
sentence boundary is eligible, with a unique same-Unit alignment. All remaining
characters must pass the existing presentation projection unchanged.
"""
import re

from .fidelity import match_quote as legacy_match
from .fidelity import protected_context, source_fields, text_sha, view

VERSION = 'quotation-fidelity-2.1'


def match_quote(quote, unit_id, parent, *, layout_reviews=()):
    result = legacy_match(quote, unit_id, parent, layout_reviews=layout_reviews)
    result['fidelity_policy'] = VERSION
    if result['outcome'] not in {'SUBSTANTIVE_MISMATCH', 'INDETERMINATE'} or parent is None:
        return result
    target, _ = view(quote, typography=True)
    if not re.match(r'^(The|the) [a-z]', target) or protected_context(quote):
        return result
    alternate = ('the' if target.startswith('The ') else 'The') + target[3:]
    matches = []
    for pointer, text in source_fields(parent):
        projected, offsets = view(text, typography=True)
        start = projected.find(alternate)
        while start >= 0:
            end = start + len(alternate)
            raw_start, raw_end = offsets[start], offsets[end - 1] + 1
            before = text[:raw_start].rstrip()
            # Lowercase continuation clauses, headings, token substrings, code,
            # abbreviations and quoted technical identifiers are not guessed.
            boundary = not before or before[-1] in '.!?'
            if (boundary and not protected_context(text[raw_start:raw_end])
                    and (end == len(projected) or not projected[end].isalnum())
                    and not re.search(r'(?:\b[A-Z]|\be\.g|\bi\.e)\.$', before)):
                matches.append((pointer, text, raw_start, raw_end))
            start = projected.find(alternate, start + 1)
    if len(matches) != 1:
        return result
    pointer, text, a, b = matches[0]
    return result | {'outcome': 'PRESENTATION_EQUIVALENT',
        'method': 'UNIQUE_SENTENCE_INITIAL_DETERMINER_CASE', 'layout_review': None,
        'source': {'pointer': pointer, 'field_sha256': text_sha(text), 'start': a, 'end': b,
            'original_text': text[a:b], 'passage_sha256': text_sha(text[a:b]),
            'citation_locators': parent.get('citation_locators', [])}}
