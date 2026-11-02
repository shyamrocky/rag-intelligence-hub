"""Bounded presentation matching with original decoded-source offsets.

No fuzzy matching, punctuation stripping, numeric coercion or semantic entailment.
PDF word rejoins require a separately reviewed, hash-bound source span. The normal
runtime path never guesses whether a line-end hyphen is a compound or word split.
"""
import hashlib
import re

QUOTE_MARKS = str.maketrans({'“': '"', '”': '"', '‘': "'", '’': "'"})
SPLIT = re.compile(r'(?<=[a-z])-[ \t]*\r?\n[ \t]*(?=[a-z])')


def text_sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def source_fields(parent):
    """Only publisher source content, never QA text or citation metadata."""
    fields = []

    def visit(value, pointer):
        if isinstance(value, str):
            fields.append((pointer, value))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                visit(item, f'{pointer}/{i}')
        elif isinstance(value, dict):
            for key, item in value.items():
                if key in {'text', 'markdown', 'rendered_markdown', 'content'}:
                    visit(item, pointer + '/' + key)
    visit(parent['consumer']['llm_context']['source_content'], '/consumer/llm_context/source_content')
    return fields


def view(value, *, typography=False, rejoins=False, punctuation_probe=False):
    chars, offsets = [], []
    removed = set()
    if rejoins:
        for match in SPLIT.finditer(value):
            removed.update(range(match.start(), match.end()))
    if punctuation_probe:
        # Diagnostic/review-only: commas after letters before whitespace, and
        # terminal periods after letters. Never numbers, decimals, compounds,
        # abbreviations within tokens, operators or arbitrary punctuation.
        for match in re.finditer(r'(?<=[A-Za-z])[,\.](?=\s|$)', value):
            removed.add(match.start())
    for i, char in enumerate(value):
        if i in removed:
            continue
        char = char.translate(QUOTE_MARKS) if typography else char
        if char.isspace():
            if chars and chars[-1] != ' ':
                chars.append(' '); offsets.append(i)
        else:
            chars.append(char); offsets.append(i)
    if chars and chars[-1] == ' ':
        chars.pop(); offsets.pop()
    return ''.join(chars), offsets


def protected_context(text):
    # Reflow may change code, tables, formulas or technical prime notation. Exact
    # matching still works. Nonexact examples of these require separate review.
    return ('`' in text or '|' in text or any(c in text for c in '≤≥≠=<>')
            or bool(re.search(r'^ {4}\S', text, re.MULTILINE)))


def locate(quote, fields, *, typography=False, rejoins=False, punctuation_probe=False):
    target, _ = view(quote, typography=typography, punctuation_probe=punctuation_probe)
    if not target:
        return None
    for pointer, text in fields:
        projected, offsets = view(text, typography=typography, rejoins=rejoins, punctuation_probe=punctuation_probe)
        position = projected.find(target)
        while position >= 0:
            end = position + len(target)
            left = projected[position - 1] if position else ''
            right = projected[end] if end < len(projected) else ''
            # Never normalize a partial technical token (C versus C++, two
            # versus twofold). Exact raw substrings retain their raw diagnostic.
            left_ok = not (target[0].isalnum() and left and (left.isalnum() or left in '_+-/'))
            right_ok = not (target[-1].isalnum() and right and (right.isalnum() or right in '_+-/'))
            if left_ok and right_ok:
                a, b = offsets[position], offsets[end - 1] + 1
                return pointer, text, a, b
            position = projected.find(target, position + 1)
    return None


def match_quote(quote, unit_id, parent, *, layout_reviews=()):
    """Layout reviews must be supplied by a trusted external review reader.

    Each review binds one exact quote and raw source field/span; permits only
    the declared line-end word-rejoin operation. It cannot change any other byte.
    Original text is returned in memory for protected inspection, not audit logs.
    """
    base = {'unit_id': unit_id, 'quote_sha256': text_sha(quote), 'raw_exact_match': False,
            'semantic_support': 'NOT_ASSESSED', 'source': None}
    if parent is None:
        return base | {'outcome': 'SOURCE_NOT_FOUND'}
    fields = source_fields(parent)

    def result(found, outcome, method, review=None):
        pointer, text, a, b = found
        return base | {'outcome': outcome, 'method': method,
            'raw_exact_match': outcome == 'EXACT_MATCH', 'layout_review': review,
            'source': {'pointer': pointer, 'field_sha256': text_sha(text),
                       'start': a, 'end': b, 'original_text': text[a:b],
                       'passage_sha256': text_sha(text[a:b]),
                       'citation_locators': parent.get('citation_locators', [])}}

    for pointer, text in fields:
        a = text.find(quote)
        if quote and a >= 0:
            return result((pointer, text, a, a + len(quote)), 'EXACT_MATCH', 'RAW_SUBSTRING')
    for typography in (False, True):
        found = locate(quote, fields, typography=typography)
        if found:
            if protected_context(found[1][found[2]:found[3]]) or protected_context(quote):
                return result(found, 'INDETERMINATE', 'PRESENTATION_IN_TECHNICAL_CONTEXT')
            return result(found, 'PRESENTATION_EQUIVALENT',
                          'WHITESPACE_AND_UNICODE_QUOTES' if typography else 'WHITESPACE_REFLOW')
    # No dictionary/ID-specific logic. Reviewed spans permit only the exact
    # layout edit; meaningful normal compound hyphens remain untouched.
    for review in layout_reviews:
        if (review['unit_id'] != unit_id or review['quote_sha256'] != text_sha(quote)
                or review['operation'] != 'PDF_LINE_END_WORD_REJOIN'):
            continue
        for pointer, text in fields:
            a, b = review['start'], review['end']
            if (pointer != review['pointer'] or text_sha(text) != review['field_sha256']
                    or type(a) is not int or type(b) is not int or not 0 <= a < b <= len(text)):
                continue
            raw = text[a:b]
            if (not protected_context(raw) and SPLIT.search(raw)
                    and view(raw, typography=True, rejoins=True)[0] == view(quote, typography=True)[0]):
                return result((pointer, text, a, b), 'PRESENTATION_EQUIVALENT',
                              'REVIEWED_PDF_WORD_REJOIN', review['review_id'])
    found = locate(quote, fields, typography=True, rejoins=True)
    if found:
        return result(found, 'INDETERMINATE', 'AMBIGUOUS_UNREVIEWED_LINE_END_HYPHEN')
    # Limited punctuation differences require an actual independent meaning
    # review. A candidate match alone is never a presentation-equivalence pass.
    for review in layout_reviews:
        if (review.get('operation') != 'LIMITED_PUNCTUATION_REVIEW'
                or review.get('review_method') != 'HUMAN_REVIEW'
                or review.get('meaning_preserving') is not True
                or review['unit_id'] != unit_id or review['quote_sha256'] != text_sha(quote)):
            continue
        for pointer, text in fields:
            a, b = review['start'], review['end']
            if (pointer == review['pointer'] and text_sha(text) == review['field_sha256']
                    and type(a) is int and type(b) is int and 0 <= a < b <= len(text)
                    and not protected_context(text[a:b]) and not protected_context(quote)
                    and view(text[a:b], typography=True, punctuation_probe=True)[0]
                    == view(quote, typography=True, punctuation_probe=True)[0]):
                return result((pointer, text, a, b), 'PRESENTATION_EQUIVALENT',
                              'INDEPENDENTLY_REVIEWED_LIMITED_PUNCTUATION', review['review_id'])
    found = locate(quote, fields, typography=True, punctuation_probe=True)
    if found:
        return result(found, 'INDETERMINATE', 'LIMITED_PUNCTUATION_MEANING_REVIEW_REQUIRED')
    return base | {'outcome': 'SUBSTANTIVE_MISMATCH', 'method': 'NO_PERMITTED_SOURCE_ALIGNMENT',
                   'scope': 'Not certified as quotation; paraphrase/entailment requires independent assessment'}


def safe_quote_record(record):
    """Source-free persisted receipt; raw source text remains protected/in-memory."""
    return record | {'source': ({k: v for k, v in record['source'].items() if k != 'original_text'}
                              if record['source'] else None)}
