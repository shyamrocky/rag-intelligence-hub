"""Untrusted response observation, independent of the strict grounded contract.

Never repairs output, infers semantics, or places returned text in public receipts.
"""
import json

from tools.answer_quality.fidelity import safe_quote_record
from tools.answer_quality.fidelity_v21 import match_quote
from tools.generation.response_capture import _directory, _write
from tools.quality_dashboard.artifacts import ArtifactError, digest, sha

VERSION = 'generation-response-observation-1.0'


def observe(raw):
    texts, refusals, duplicates = [], [], []
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                duplicates.append(key)
            result[key] = value
        return result
    output = raw.get('output', []) if isinstance(raw, dict) else []
    for item in output if isinstance(output, list) else []:
        if not isinstance(item, dict):
            continue
        content = item.get('content', [])
        for part in content if isinstance(content, list) else []:
            if not isinstance(part, dict):
                continue
            if part.get('type') == 'output_text' and isinstance(part.get('text'), str):
                texts.append(part['text'])
            if part.get('type') == 'refusal' and isinstance(part.get('refusal'), str):
                refusals.append(part['refusal'])
    text = ''.join(texts)
    candidate, state = None, 'NO_TEXT_OUTPUT'
    if texts:
        try:
            candidate = json.loads(text, object_pairs_hook=unique,
                parse_constant=lambda value: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))
            state = 'JSON_CANDIDATE_UNTRUSTED'
        except (ValueError, TypeError, RecursionError):
            state = 'MALFORMED_JSON_TEXT_PRESERVED'
        if duplicates:
            candidate, state = None, 'AMBIGUOUS_DUPLICATE_KEYS'
    return {'schema': VERSION, 'provider_status': raw.get('status') if isinstance(raw, dict) else None,
            'state': state, 'text_parts': texts, 'refusals': refusals, 'candidate': candidate,
            'duplicate_key_count': len(duplicates), 'accepted_contract': False,
            'semantic_status': 'NOT_ASSESSED'}


def field_checks(observation, package):
    """Check usable fields without certifying an invalid candidate as compliant."""
    candidate = observation.get('candidate')
    result = {'schema': 'response-field-checks-1.0', 'semantic_status': 'PENDING_REVIEW',
              'fully_validated': False, 'citations': [], 'quotations': [],
              'qualifications': 'INDETERMINATE', 'completeness': 'NOT_ASSESSED',
              'field_issues': [], 'status': 'PARTIAL_CHECKS_ONLY'}
    if not isinstance(candidate, dict):
        return result | {'status': 'UNAVAILABLE_NO_UNAMBIGUOUS_OBJECT'}
    parents = {p['evidence']['unit_id']: p['evidence']['verified_parent'] for p in package['parents']}
    def refs(value, path):
        if not isinstance(value, list):
            result['field_issues'].append({'path': path, 'code': 'REFERENCE_LIST_REQUIRED'})
            return
        for i, uid in enumerate(value):
            ok = isinstance(uid, str) and uid in parents and not uid.startswith('EXAMPLE-')
            result['citations'].append({'path': path + [i], 'unit_id': uid if isinstance(uid, str) else None,
                                       'status': 'AUTHORIZED' if ok else 'INVALID_CITATION'})
    claims = candidate.get('claims')
    if not isinstance(claims, list):
        result['field_issues'].append({'path': ['claims'], 'code': 'CLAIM_LIST_REQUIRED'})
    else:
        for i, claim in enumerate(claims):
            if not isinstance(claim, dict):
                result['field_issues'].append({'path': ['claims', i], 'code': 'CLAIM_OBJECT_REQUIRED'})
                continue
            refs(claim.get('evidence_unit_ids'), ['claims', i, 'evidence_unit_ids'])
            quotes = claim.get('supporting_quotes')
            if not isinstance(quotes, list):
                result['field_issues'].append({'path': ['claims', i, 'supporting_quotes'], 'code': 'QUOTE_LIST_REQUIRED'})
                continue
            for j, quote in enumerate(quotes):
                if not isinstance(quote, dict) or not isinstance(quote.get('quote'), str):
                    result['field_issues'].append({'path': ['claims', i, 'supporting_quotes', j], 'code': 'QUOTE_OBJECT_INVALID'})
                    continue
                uid = quote.get('evidence_unit_id')
                refs([uid], ['claims', i, 'supporting_quotes', j, 'evidence_unit_id'])
                match = match_quote(quote['quote'], uid if isinstance(uid, str) else '',
                                    parents.get(uid) if isinstance(uid, str) else None)
                result['quotations'].append(safe_quote_record(match) | {'claim_index': i, 'quote_index': j})
    for field in ('requirement_coverage', 'conflicts_detected'):
        items = candidate.get(field)
        if not isinstance(items, list):
            result['field_issues'].append({'path': [field], 'code': 'LIST_REQUIRED'})
        else:
            for i, item in enumerate(items):
                if isinstance(item, dict):
                    refs(item.get('evidence_unit_ids'), [field, i, 'evidence_unit_ids'])
                else:
                    result['field_issues'].append({'path': [field, i], 'code': 'OBJECT_REQUIRED'})
    if (isinstance(claims, list) and all(isinstance(c, dict)
            and isinstance(c.get('evidence_unit_ids'), list)
            and all(isinstance(uid, str) and uid in parents for uid in c['evidence_unit_ids']) for c in claims)
            and isinstance(candidate.get('answer'), str)
            and isinstance(candidate.get('relevant_qualifications'), list)
            and all(isinstance(q, str) for q in candidate['relevant_qualifications'])):
        from tools.generation.qualifications import _assess_metadata
        try:
            result['qualification_checks'] = _assess_metadata(candidate, parents)
            result['qualifications'] = result['qualification_checks']['status']
        except (ValueError, KeyError, TypeError):
            result['qualification_unavailable_reason'] = 'NATIVE_METADATA_NOT_DETERMINATE'
    else:
        result['qualification_unavailable_reason'] = 'REQUIRED_DISCLOSURE_OR_CITATION_FIELDS_INVALID'
    return result


def persist(root, qdir, observation, row, package, *, capture=None):
    """Exact candidate/text private; only hashes/check outcomes in the run seal."""
    relative = 'workspace/generation-observations/' + qdir.parent.parent.name + '/' + row['question_id']
    folder = _directory(root, relative)
    if any(p.stat().st_mode & 0o077 for p in (folder, folder.parent, folder.parent.parent)):
        raise ArtifactError('UNSAFE_OBSERVATION_PERMISSIONS')
    body = json.dumps(observation, ensure_ascii=False, sort_keys=True, indent=2).encode()
    path = folder / 'OBSERVATION.json'
    _write(path, body)
    context = {key: row[key] for key in ('question_id', 'request_sha256', 'M8_package_sha256')}
    context['run_id'] = qdir.parent.parent.name
    return {'schema': VERSION, 'context': context, 'state': observation['state'],
            'identity_sha256': digest({'context': context, 'body_sha256': sha(path)}),
            'raw_body_sha256': (capture or {}).get('artifact', {}).get('sha256') if (capture or {}).get('artifact') else None,
            'artifact': {'path': relative + '/OBSERVATION.json', 'sha256': sha(path)},
            'field_checks': field_checks(observation, package)}
