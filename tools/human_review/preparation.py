"""Bounded, idempotent local evidence-to-review preparation; never a semantic oracle.

Called after native generation seals or by an explicit local preparation action.
Discovery reads receipts only. Full cited source context is private, not telemetry.
"""
import argparse
import fcntl
import os
from pathlib import Path
from uuid import uuid4

from tools.answer_quality.fidelity import source_fields, text_sha
from tools.answer_quality.review import Assessment, bound_assessment
from tools.preflight_suite.artifacts import now, save
from tools.quality_dashboard.artifacts import ArtifactError, Store, digest, safe_path, sha

from . import workflow
from .review_state import current_decision

BASE = 'data/evals/human-review/preparations'
SCHEMA = 'human-review-preparation-1.0'
PRIVATE = 'workspace/human-review-evidence'


def metadata_fields(parent):
    """QA/use metadata stays distinct from publisher passages."""
    output = {}
    def visit(value, pointer):
        if isinstance(value, str):
            output[pointer] = value
        elif isinstance(value, list):
            for i, item in enumerate(value):
                visit(item, f'{pointer}/{i}')
        elif isinstance(value, dict):
            for key, item in value.items():
                if key != 'source_content':
                    visit(item, pointer + '/' + key)
    visit(parent['consumer'], '/consumer')
    return output


def bindings(row):
    return {'question_sha256': row['question_sha256'], 'response_sha256': digest(row['response']),
            'package_sha256': row['M8_package_sha256'], 'request_sha256': row['request_sha256']}


def unassessed(entry):
    row = entry['row']
    return {'schema_version': 'answer-quality-assessment-2.0', 'method': 'ASSISTANT_ANALYSIS',
        'reviewer': 'LOCAL_PREPARATION_NO_SEMANTIC_ASSESSOR', 'assessed_at': now(),
        **bindings(row), 'independent_of_generator': False, 'answer_claim_inventory_complete': False,
        'question_requirements_reviewed': False,
        'uncertainty': ['No semantic assessor was executed. Owner must inspect the evidence, inventory all assertions and decompose the question.'],
        'response_status_appropriate': None,
        'claims': [{'claim_index': i, 'claim_sha256': digest(c), 'outcome': 'INDETERMINATE',
            'rationale': 'Unassessed. Citation and quotation checks do not establish support.', 'passages': []}
            for i, c in enumerate(row['response']['claims'])],
        'requirements': [{'requirement_id': 'QUESTION', 'requirement': entry['question'],
            'outcome': 'INDETERMINATE', 'rationale': 'Exact question provided for owner decomposition; no completeness judgment.',
            'claim_indices': [], 'passages': []}],
        'qualifications': {'outcome': 'INDETERMINATE', 'rationale': 'Owner applicability and disclosure judgment required.', 'passages': []},
        'conflicts': {'outcome': 'INDETERMINATE', 'rationale': 'No independent conflict assessment executed.', 'passages': []}}


def approval_ready(assessment, response):
    """Declared review completeness only, not automatic entailment or authentication."""
    a = Assessment.model_validate(assessment)
    return (a.answer_claim_inventory_complete and a.question_requirements_reviewed
        and a.response_status_appropriate is True and not a.uncertainty
        and all(c.outcome == 'SUPPORTED' for c in a.claims)
        and bool(a.requirements) and all(r.outcome != 'INDETERMINATE' for r in a.requirements)
        and (response['status'] != 'ANSWERED' or all(r.outcome == 'COMPLETE' for r in a.requirements))
        and a.qualifications.outcome == a.conflicts.outcome == 'SATISFIED')


def read(root, manifest, *, entry=None):
    store = Store(root)
    m = store.manifest(manifest, schema=SCHEMA)
    base = manifest.rsplit('/', 1)[0]
    value = store.json(base + '/PREPARATION.json')
    materials = store.json(base + '/MATERIALS.json')
    p, row, fingerprint = workflow.load_package(root, value['package_manifest'],
        expected=value['package_manifest_sha256'], require_fresh=False)
    if (value['bindings'] != bindings(row) or materials['bindings'] != bindings(row)
            or value['policy'] != p['policy'] or materials['response_source'] != p['response_source']
            or value['generation_authorized'] is not False or value['owner_approval_created'] is not False
            or (entry and (entry['source'] != materials['response_source'] or bindings(entry['row']) != value['bindings']))):
        raise ArtifactError('PREPARATION_BINDING_MISMATCH')
    private = safe_path(root, value['protected_evidence']['path'], prefix=PRIVATE)
    if (sha(private) != value['protected_evidence']['sha256'] or private.stat().st_mode & 0o077
            or any(parent.stat().st_mode & 0o077 for parent in [private.parent, private.parent.parent])):
        raise ArtifactError('PROTECTED_REVIEW_EVIDENCE_UNAVAILABLE_OR_UNSAFE')
    # Publisher content is read only when the selected review is rendered, not by discovery.
    return value | {'materials': materials, 'prepared': (value['package_manifest'], p, row, fingerprint),
                    'manifest': manifest, 'manifest_sha256': sha(safe_path(root, manifest)), 'created_at': m['created_at']}


def discover(root, entry):
    rows, rejected = [], 0
    for p in sorted((Path(root) / BASE).glob('*/MANIFEST.json')):
        try:
            store = Store(root)
            manifest = store.manifest(p.relative_to(root).as_posix(), schema=SCHEMA)
            if 'FAILURE.json' in manifest['files']:
                continue
            value = read(root, p.relative_to(root).as_posix())
            if (value['materials']['response_source'] == entry['source']
                    and value['bindings'] == bindings(entry['row']) and value['policy'] == entry['policy']):
                rows.append(value)
        except (ArtifactError, ValueError, KeyError, TypeError, OSError):
            rejected += 1
    return sorted(rows, key=lambda r: (r['created_at'], r['manifest'])), rejected


def failures(root, entry):
    values = []
    for file in sorted((Path(root) / BASE).glob('*/MANIFEST.json')):
        try:
            store = Store(root)
            m = store.manifest(file.relative_to(root).as_posix(), schema=SCHEMA)
            if 'FAILURE.json' not in m['files']:
                continue
            row = store.json(file.parent.relative_to(root).as_posix() + '/FAILURE.json')
            if row['response_source'] == entry['source'] and row['bindings'] == bindings(entry['row']):
                values.append(row | {'manifest': file.relative_to(root).as_posix()})
        except (ArtifactError, ValueError, KeyError, TypeError, OSError):
            continue
    return sorted(values, key=lambda r: (r['created_at'], r['manifest']))


def source_context(root, receipt):
    from tools.quality_dashboard.artifacts import read_json
    ref = receipt['protected_evidence']
    path = safe_path(root, ref['path'], prefix=PRIVATE)
    if sha(path) != ref['sha256'] or path.stat().st_mode & 0o077:
        raise ArtifactError('PROTECTED_REVIEW_EVIDENCE_CHANGED')
    value = read_json(path)
    if value['bindings'] != receipt['bindings']:
        raise ArtifactError('PROTECTED_REVIEW_EVIDENCE_BINDING_MISMATCH')
    return value


def prepare_one(root, entry, trust):
    workflow.trust_check(root, trust)
    if not entry['question']:
        raise ArtifactError('ORIGINAL_QUESTION_BINDING_UNAVAILABLE')
    candidate = entry.get('assessment_candidate')
    assessment = candidate['assessment'] if candidate else unassessed(entry)
    stable = digest({'source': entry['source'], 'bindings': bindings(entry['row']), 'trust': trust,
                     'candidate': candidate, 'schema': SCHEMA, 'policy': entry['policy']})
    prior, rejected = discover(root, entry)
    if rejected:
        raise ArtifactError('UNVERIFIED_PREPARATION_HISTORY')
    for old in reversed(prior):
        if old['preparation_key'] == stable:
            try:
                workflow.load_package(root, old['package_manifest'], expected=old['package_manifest_sha256'])
                return old
            except ArtifactError as error:
                if str(error) != 'STALE_OR_INVALID_REVIEW_TIMESTAMP':
                    raise
    row = workflow.source_record(root, entry['source'])
    service, evidence, m7 = workflow.live_context(root, {'question_id': entry['question_id'], 'question': entry['question']}, row)
    if service.validate(evidence, m7) is not True:
        raise ArtifactError('M8_VALIDATION_NOT_CONFIRMED')
    cited = {u for c in row['response']['claims'] for u in c['evidence_unit_ids']}
    parents = {p['evidence']['unit_id']: p['evidence']['verified_parent'] for p in evidence['parents']}
    if not cited <= parents.keys():
        raise ArtifactError('UNAUTHORIZED_CITED_UNIT')
    fields = {(uid, pointer): text for uid in parents for pointer, text in source_fields(parents[uid])}
    bound_assessment(assessment, question=entry['question'], response=row['response'], package=evidence,
                     request_sha256=row['request_sha256'], fields=fields)
    layout = candidate.get('layout_reviews', []) if candidate else []
    from tools.answer_quality.current import validator_for
    technical = validator_for(root, entry['policy'])(service, layout_reviews=layout).validate(row['response'], evidence, m7,
        question=entry['question'], request_binding=row)
    service.check()
    identity = stable + '-' + uuid4().hex[:10]
    private_base = Path(root) / PRIVATE
    if not private_base.exists():
        workflow.output_directory(root, PRIVATE)
    if private_base.is_symlink() or private_base.stat().st_mode & 0o077:
        raise ArtifactError('UNSAFE_PRIVATE_REVIEW_STORAGE')
    private = workflow.output_directory(root, PRIVATE + '/' + identity)
    protected = {'bindings': bindings(row), 'parents': [{'unit_id': uid,
        'source_fields': dict(source_fields(parents[uid])), 'citation_locators': parents[uid].get('citation_locators', []),
        'metadata_fields': metadata_fields(parents[uid]),
        'consumer_metadata': {k: v for k, v in parents[uid]['consumer'].items() if k != 'llm_context'},
        'source_obligations': {k: v for k, v in parents[uid]['consumer']['llm_context'].items() if k != 'source_content'}}
        for uid in sorted(parents)]}
    save(private / 'EVIDENCE.json', protected)
    folder = workflow.output_directory(root, BASE + '/' + identity)
    materials = {'schema': SCHEMA, 'bindings': bindings(row), 'response_source': entry['source'],
        'question_id': entry['question_id'], 'question': entry['question'],
        'status': 'ASSESSMENT_READY' if candidate else 'OWNER_REVIEW_NEEDED',
        'semantic_assessor_executed': bool(candidate), 'independent_human_acceptance': False,
        'assessment_method': assessment['method'] if candidate else 'DETERMINISTIC_PREPARATION_ONLY',
        'additional_assertion_inventory': 'OWNER_MUST_REVIEW_FULL_ANSWER_INCLUDING_UNLISTED_ASSERTIONS',
        'known_positive_coverage': entry.get('coverage'), 'native_validation': row.get('post_validation'),
        'fresh_technical_validation': technical,
        'source_field_references': [{'unit_id': uid, 'pointer': pointer, 'field_sha256': text_sha(text),
            'start': 0, 'end': len(text)} for (uid, pointer), text in fields.items() if text],
        'metadata_field_references': [{'unit_id': uid, 'pointer': pointer, 'field_sha256': text_sha(text),
            'start': 0, 'end': len(text)} for uid in sorted(parents)
            for pointer, text in metadata_fields(parents[uid]).items() if text],
        'assessment_uncertainty': assessment['uncertainty'],
        'notes': ['A prepared package is not owner approval.', 'No model judge or provider call executed.']}
    save(folder / 'MATERIALS.json', materials)
    support = (candidate.get('supporting_artifacts', {}) if candidate else {}) | {
        (folder / 'MATERIALS.json').relative_to(root).as_posix(): sha(folder / 'MATERIALS.json')}
    package = workflow.prepare(root, source=entry['source'], question=entry['question'], assessment=assessment,
        trust=trust, supporting_artifacts=support, layout_reviews=layout, validation_policy=entry['policy'])
    value = {'schema': SCHEMA, 'preparation_key': stable, 'bindings': bindings(row), 'policy': entry['policy'],
        'created_at': now(), 'status': materials['status'], 'package_manifest': package,
        'package_manifest_sha256': sha(safe_path(root, package)), 'generation_authorized': False,
        'owner_approval_created': False, 'protected_evidence': {
            'path': (private / 'EVIDENCE.json').relative_to(root).as_posix(), 'sha256': sha(private / 'EVIDENCE.json')}}
    save(folder / 'PREPARATION.json', value)
    save(folder / 'MANIFEST.json', {'schema': SCHEMA, 'created_at': value['created_at'],
        'files': {p.name: sha(p) for p in folder.iterdir()}})
    return read(root, (folder / 'MANIFEST.json').relative_to(root).as_posix(), entry=entry)


def run(root, *, question_ids=None, source_manifest=None):
    from . import local_poc
    from .handoff import discover as entries
    from .handoff import review_trust
    root = Path(root)
    lock = root / 'workspace/review-preparation'
    if any(p.is_symlink() for p in [lock, *lock.parents]):
        raise ArtifactError('UNSAFE_REVIEW_OUTPUT_PATH')
    lock.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(lock / 'PREPARE.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    results = []
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        trust = review_trust()
        workflow.trust_check(root, trust)
        history, bad = local_poc.discover(root)
        if bad:
            raise ArtifactError('UNVERIFIED_LOCAL_POC_HISTORY')
        found = entries(root)['entries']
        if question_ids and set(question_ids) - {e['question_id'] for e in found}:
            raise ArtifactError('COMPLETED_NATIVE_QUESTION_NOT_FOUND')
        for entry in found:
            if question_ids and entry['question_id'] not in question_ids:
                continue
            if source_manifest and entry['source']['manifest_path'] != source_manifest:
                continue
            target = {'question_id': entry['question_id'], 'bindings': bindings(entry['row']), 'policy': entry['policy']}
            if current_decision(target, history):
                results.append({'question_id': entry['question_id'], 'status': 'REVIEW_ALREADY_COMPLETED'})
                continue
            try:
                prepared = prepare_one(root, entry, trust)
                results.append({'question_id': entry['question_id'], 'status': prepared['status'], 'manifest': prepared['manifest']})
            except (ArtifactError, ValueError, TypeError, KeyError, OSError) as error:
                # A failure is separate and auditable; original generation remains sealed.
                folder = workflow.output_directory(root, BASE + '/failed-' + uuid4().hex)
                failure = {'schema': SCHEMA, 'question_id': entry['question_id'], 'response_source': entry['source'],
                    'bindings': bindings(entry['row']), 'status': 'ASSESSMENT_UNAVAILABLE',
                    'reason': str(error) if isinstance(error, ArtifactError) and str(error).isupper()
                        and str(error).replace('_', '').isalnum() else 'LOCAL_SOURCE_ASSESSMENT_PREPARATION_FAILED',
                    'error_type': type(error).__name__, 'created_at': now(),
                    'generation_authorized': False, 'owner_approval_created': False}
                save(folder / 'FAILURE.json', failure)
                save(folder / 'MANIFEST.json', {'schema': SCHEMA, 'created_at': failure['created_at'],
                    'files': {'FAILURE.json': sha(folder / 'FAILURE.json')}})
                results.append(failure)
        return results
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def owner_decide(root, manifest, *, expected_sha, reviewer_label, decision, confirmed, assessment,
                 additional_assertions, notes='', revision_of=None, revision_reason=''):
    """Explicit owner judgments, unsigned POC only. No authenticated HumanReview import."""
    from . import local_poc
    local_poc.require_localhost()
    if not confirmed or not reviewer_label.strip():
        raise ArtifactError('EXPLICIT_OWNER_CONFIRMATION_REQUIRED')
    if sha(safe_path(root, manifest)) != expected_sha:
        raise ArtifactError('DISPLAYED_REVIEW_MATERIALS_CHANGED')
    receipt = read(root, manifest)
    _, p, row, _ = receipt['prepared']
    history, rejected = local_poc.discover(root)
    from .review_state import latest_answer_decision
    current = latest_answer_decision(p, history)
    if rejected or (current and revision_of is None):
        raise ArtifactError('UNVERIFIED_OR_ALREADY_COMPLETED_REVIEW')
    if revision_of is not None and (not current or revision_of != {
            'path': current[1], 'sha256': sha(Path(root) / current[1])} or not revision_reason.strip()):
        raise ArtifactError('EXPLICIT_CURRENT_REVIEW_REVISION_AND_REASON_REQUIRED')
    workflow.trust_check(root, p['trust'])
    context = source_context(root, receipt)
    fields = {(v['unit_id'], pointer): text for v in context['parents'] for pointer, text in v['source_fields'].items()}
    metadata = {(v['unit_id'], pointer): text for v in context['parents'] for pointer, text in v['metadata_fields'].items()}
    value = Assessment.model_validate(assessment).model_dump()
    if any(value[k] != p['bindings'][k] for k in p['bindings']):
        raise ArtifactError('OWNER_ASSESSMENT_BINDING_MISMATCH')
    for extra in additional_assertions:
        if (not isinstance(extra.get('assertion'), str) or not extra['assertion'].strip()
                or not isinstance(extra.get('rationale'), str) or not extra['rationale'].strip()
                or extra.get('outcome') not in {'SUPPORTED', 'PARTIALLY_SUPPORTED', 'UNSUPPORTED', 'CONTRADICTED', 'INDETERMINATE'}
                or not isinstance(extra.get('passages'), list)):
            raise ArtifactError('INVALID_ADDITIONAL_ASSERTION_JUDGMENT')
    # All owner-selected evidence references must be actual prepared publisher fields.
    for item in [*value['claims'], *value['requirements'], value['qualifications'], value['conflicts'], *additional_assertions]:
        for ref in item['passages']:
            allowed = fields | metadata if item in additional_assertions else fields
            text = allowed.get((ref['unit_id'], ref['pointer']))
            if (text is None or text_sha(text) != ref['field_sha256'] or not 0 <= ref['start'] < ref['end'] <= len(text)):
                raise ArtifactError('OWNER_PASSAGE_NOT_IN_SUPPLIED_EVIDENCE')
    if decision == 'APPROVE' and (not approval_ready(value, row['response']) or any(
            a['outcome'] != 'SUPPORTED' or not a['rationale'].strip() or not a['passages'] for a in additional_assertions)):
        raise ArtifactError('UNRESOLVED_OWNER_JUDGMENTS_PREVENT_APPROVAL')
    value.update(method='HUMAN_REVIEW', reviewer=reviewer_label, assessed_at=now(), independent_of_generator=True)
    folder = workflow.output_directory(root, 'data/evals/human-review/owner-judgments/' + uuid4().hex)
    save(folder / 'OWNER_JUDGMENTS.json', {'schema': 'local-poc-owner-judgments-1.0', 'assessment': value,
        'additional_assertions': additional_assertions, 'original_preparation': manifest,
        'preparation_sha256': expected_sha, 'authenticated': False, 'owner_decision_created': False})
    support = p['supporting_artifacts'] | {(folder / 'OWNER_JUDGMENTS.json').relative_to(root).as_posix(): sha(folder / 'OWNER_JUDGMENTS.json')}
    package = workflow.prepare(root, source=p['response_source'], question=p['question'], assessment=value,
        trust=p['trust'], supporting_artifacts=support, layout_reviews=p['layout_reviews'], validation_policy=p['policy'])
    return local_poc.decide(root, package, expected_sha=sha(safe_path(root, package)), reviewer_label=reviewer_label,
        decision=decision, confirmed=confirmed, notes=notes, revision_of=revision_of, revision_reason=revision_reason)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--question', action='append', dest='question_ids')
    args = parser.parse_args()
    import json
    print(json.dumps(run(Path.cwd(), question_ids=args.question_ids)))
