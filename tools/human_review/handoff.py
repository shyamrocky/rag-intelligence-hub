"""Native result → review inbox. Discovery is read-only; synchronization never approves.

Missing semantic assessments stay missing. Package construction reuses workflow.prepare;
fresh M8 and technical checks remain mandatory on an explicit review submission.
"""
import fcntl
import hashlib
import os
from pathlib import Path
from uuid import uuid4

from tools.answer_quality.review import Assessment
from tools.generation_runner.dashboard import discover as generation_runs
from tools.preflight_suite.artifacts import COMPLETION, baseline, now, save
from tools.quality_dashboard.artifacts import (
    ArtifactError,
    Store,
    digest,
    safe_path,
    sha,
)

from . import workflow
from .review_state import target_identity
from .ui import packages

BASE = 'data/evals/human-review/handoffs'
INPUTS = 'data/evals/human-review/assessment-inputs'
SCHEMA = 'generation-human-review-handoff-1.0'
MISSING = ['MATERIAL_CLAIM_INVENTORY_AND_GROUNDING', 'INDEPENDENT_QUESTION_REQUIREMENTS',
           'MATERIAL_QUALIFICATIONS_AND_CONFLICTS', 'RESPONSE_STATUS_APPROPRIATENESS']


def review_trust():
    from tools.generation_trust_anchor import HUMAN_REVIEW_BASELINE, TRUSTED_BASELINES
    path = HUMAN_REVIEW_BASELINE
    return {'path': path, 'sha256': TRUSTED_BASELINES[path]}


def identity(row):
    return digest({'question_id': row['question_id'], 'question_sha256': row['question_sha256'],
        'response_sha256': digest(row['response']), 'request_sha256': row['request_sha256'],
        'package_sha256': row['M8_package_sha256']})


def inventory_context(root):
    """Existing frozen readers only; no retrieval, M8 assembly or label recomputation."""
    store, questions = baseline(root)
    measurements = {r['question_id']: r for r in store.json(COMPLETION + '/RESULTS.json')['questions']}
    reference = store.json('data/evals/expanded-benchmark/v1/EXPANDED_BENCHMARK.json')
    refs = {r['question_id']: r for r in reference['questions']}
    from tools.bot_runtime.projection import discover as bot_inventory
    bot_data = bot_inventory(root, include_native=False)
    if bot_data['rejected']:
        raise ArtifactError('UNVERIFIED_BOT_QUESTION_INVENTORY')
    questions = dict(questions)
    for qid, record in bot_data['records'].items():
        questions[qid] = record['reference']
    return store, questions, measurements, refs


def assessment_candidates(root, source, question, row):
    """Only explicitly sealed assessment inputs, never model requirement_coverage."""
    values, rejected = [], 0
    for file in sorted((Path(root) / INPUTS).glob('*/MANIFEST.json')):
        try:
            store = Store(root)
            manifest = store.manifest(file.relative_to(root).as_posix(),
                                      schema='human-review-assessment-input-1.0')
            base = file.parent.relative_to(root).as_posix()
            info, value = store.json(base + '/INPUT.json'), store.json(base + '/ASSESSMENT.json')
            if info['response_source'] != source:
                continue
            parsed = Assessment.model_validate(value).model_dump()
            expected = {'question_sha256': row['question_sha256'], 'response_sha256': digest(row['response']),
                        'request_sha256': row['request_sha256'], 'package_sha256': row['M8_package_sha256']}
            if info['question'] != question or any(parsed[k] != v for k, v in expected.items()):
                raise ArtifactError('HANDOFF_ASSESSMENT_BINDING_MISMATCH')
            if (sorted(c['claim_index'] for c in parsed['claims']) != list(range(len(row['response']['claims'])))
                    or not parsed['requirements'] or not parsed['answer_claim_inventory_complete']
                    or not parsed['question_requirements_reviewed']):
                raise ArtifactError('INCOMPLETE_HANDOFF_ASSESSMENT')
            for c in parsed['claims']:
                if (c['claim_sha256'] != digest(row['response']['claims'][c['claim_index']])
                        or (c['outcome'] in {'SUPPORTED', 'PARTIALLY_SUPPORTED', 'CONTRADICTED'} and not c['passages'])):
                    raise ArtifactError('UNBOUND_HANDOFF_CLAIM')
            support = info.get('supporting_artifacts', {}) | dict(store.verified)
            for name, fingerprint in support.items():
                store.bind(name, fingerprint)
            for layout in info.get('layout_reviews', []):
                if layout['review_id'].split('#')[0] not in support:
                    raise ArtifactError('UNBOUND_LAYOUT_REVIEW')
            values.append({'assessment': parsed, 'supporting_artifacts': support,
                'layout_reviews': info.get('layout_reviews', []), 'input_manifest': file.relative_to(root).as_posix(),
                'input_manifest_sha256': store.verified[file.relative_to(root).as_posix()],
                'created_at': manifest.get('created_at', '')})
        except (ArtifactError, ValueError, TypeError, KeyError, OSError):
            rejected += 1
    return sorted(values, key=lambda x: (x['created_at'], x['input_manifest'])), rejected


def discover(root, *, prepared=None):
    """Pure projection of sealed results. Refresh creates no files and invokes no pipeline."""
    root = Path(root)
    from tools.answer_quality.current import policy_reference

    from . import local_poc
    from .review_state import latest_answer_decision
    active_policy = policy_reference(root)
    decisions, bad_decisions = local_poc.discover(root)
    runs = generation_runs(root)
    ready, package_errors = packages(root) if prepared is None else (prepared, 0)
    try:
        store, questions, measurements, refs = inventory_context(root)
    except (ArtifactError, ValueError, TypeError, KeyError, OSError):
        store, questions, measurements, refs = None, {}, {}, {}
    entries, rejected = {}, list(runs['rejected'])
    for run in runs['runs']:
        if run['manifest']['mode'] != 'live':
            continue
        base = run['manifest_path'].rsplit('/', 1)[0]
        for row in run['results']['questions']:
            if (row.get('generation_executed') is not True or row.get('fixture_only')
                    or not isinstance(row.get('response'), dict)
                    or row['response'].get('status') not in {'ANSWERED', 'PARTIAL', 'ABSTAINED'}):
                continue
            try:
                source = {'manifest_path': run['manifest_path'],
                    'manifest_sha256': sha(safe_path(root, run['manifest_path'])),
                    'result_path': base + f'/questions/{row["question_id"]}/RESULT.json',
                    'result_sha256': run['manifest']['files'][f'questions/{row["question_id"]}/RESULT.json']}
                verified = workflow.source_record(root, source)
                if verified != row:
                    raise ArtifactError('HANDOFF_RESULT_CHANGED')
                policy = active_policy
                old_decision = latest_answer_decision({'question_id': row['question_id'], 'bindings': {
                    'question_sha256': row['question_sha256'], 'response_sha256': digest(row['response']),
                    'request_sha256': row['request_sha256'], 'package_sha256': row['M8_package_sha256']}}, decisions)
                # An approved/rejected answer remains on its explicitly decided policy.
                # A technical block may be reevaluated, but cannot silently unlock review.
                if old_decision and old_decision[0]['status'] != 'BLOCKED_TECHNICAL':
                    policy = old_decision[0]['evidence_policy']
                q = questions.get(row['question_id'])
                question = q['question'] if q else None
                if question is not None and hashlib.sha256(question.encode()).hexdigest() != row['question_sha256']:
                    raise ArtifactError('HANDOFF_QUESTION_CHANGED')
                compatible = [p for p in ready if identity(p[2]) == identity(row)
                              and p[1]['response_source'] == source and p[1]['policy'] == policy]
                if question is None and compatible:
                    question = compatible[-1][1]['question']
                candidates, bad = assessment_candidates(root, source, question, row) if question else ([], 0)
                coverage = None
                measurement = measurements.get(row['question_id'])
                if measurement and measurement['M7_result_sha256'] == row['M7_result_sha256'] and measurement['m8']['M8_package_sha256'] == row['M8_package_sha256']:
                    from tools.quality_dashboard.completion_adapter import validate_measurement
                    m7 = store.json(COMPLETION + f'/m7/{row["question_id"]}.json')
                    case = store.json(COMPLETION + f'/m8/{row["question_id"]}.json')
                    validate_measurement(refs[row['question_id']], measurement, m7, case)
                    coverage = {'status': 'REUSED_HISTORICAL_KNOWN_POSITIVES_NOT_ANSWER_QUALITY',
                        'groups': measurement['group_outcomes'], 'required': measurement['required_groups'],
                        'delivered': measurement['m8']['delivered_groups'],
                        'source': COMPLETION + '/RESULTS.json', 'source_sha256': store.verified[COMPLETION + '/RESULTS.json']}
                selected = max(compatible, key=lambda p: (p[1]['created_at'], p[0])) if compatible else None
                missing = [] if selected or candidates else list(MISSING)
                if not question:
                    missing.append('ORIGINAL_QUESTION_BINDING')
                logical = target_identity({'question_id': row['question_id'], 'policy': policy,
                    'bindings': {'question_sha256': row['question_sha256'], 'response_sha256': digest(row['response']),
                        'request_sha256': row['request_sha256'], 'package_sha256': row['M8_package_sha256']}})
                value = {'entry_id': digest({'answer': identity(row), 'source': source}),
                    'logical_target_sha256': logical, 'policy': policy,
                    'question_id': row['question_id'], 'question': question,
                    'run_id': run['manifest']['run_id'], 'created_at': run['manifest'].get('created_at', ''),
                    'source': source, 'row': row, 'timing': run['timings'].get(row['question_id']),
                    'coverage': coverage, 'prepared': selected,
                    'assessment_candidate': candidates[-1] if candidates else None,
                    'rejected_assessment_inputs': bad, 'missing_assessments': missing,
                    'status': 'PACKAGE_PREPARED' if selected else 'ASSESSMENT_AVAILABLE' if candidates else 'PENDING_ASSESSMENTS',
                    'independent_semantic_acceptance': False}
                # Same exact answer in multiple sealed sources is one review item.
                # Keep the older source references available without changing handoff receipt IDs.
                prior = entries.get(logical)
                value['source_history'] = (prior.get('source_history', []) + [prior['source']]) if prior else []
                if not prior or (value['created_at'], value['entry_id']) >= (prior['created_at'], prior['entry_id']):
                    entries[logical] = value
                else:
                    prior['source_history'].append(source)
            except (ArtifactError, ValueError, TypeError, KeyError, OSError):
                rejected.append({'run_id': run['manifest']['run_id'], 'status': 'INVALID_REVIEW_SOURCE'})
    return {'entries': sorted(entries.values(), key=lambda e: (e['created_at'], e['question_id'], e['entry_id'])),
            'rejected': rejected, 'package_errors': package_errors + bad_decisions}


def synchronize(root, *, source_manifest=None):
    """Idempotent post-seal hook/backfill. Only unsigned review artifacts can be written."""
    root = Path(root)
    lock = root / 'workspace/review-handoff'
    if any(p.is_symlink() for p in [lock, *lock.parents]):
        raise ArtifactError('UNSAFE_HANDOFF_DIRECTORY')
    lock.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(lock / 'SYNC.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        trust = review_trust()
        workflow.trust_check(root, trust)
        data = discover(root)
        output = []
        for entry in data['entries']:
            if source_manifest and entry['source']['manifest_path'] != source_manifest:
                continue
            old = entry['prepared']
            candidate = entry['assessment_candidate']
            if old and not candidate:
                p = old[1]
                candidate = {'assessment': p['assessment_draft'], 'supporting_artifacts': p['supporting_artifacts'],
                             'layout_reviews': p['layout_reviews']}
            candidate_hash = digest({k: candidate[k] for k in
                ('assessment', 'supporting_artifacts', 'layout_reviews')}) if candidate else None
            key = digest({'entry_id': entry['entry_id'], 'source': entry['source'], 'trust': trust,
                          'candidate': candidate_hash, 'schema': SCHEMA})
            folder = root / BASE / key
            while folder.exists():
                store = Store(root)
                store.manifest((folder / 'MANIFEST.json').relative_to(root).as_posix(), schema=SCHEMA)
                existing = store.json((folder / 'HANDOFF.json').relative_to(root).as_posix())
                if (existing['identity_sha256'] != key or existing['entry_id'] != entry['entry_id']
                        or existing['response_source'] != entry['source'] or existing['trust'] != trust
                        or existing['generation_authorized'] is not False or existing['owner_approval_created'] is not False):
                    raise ArtifactError('HANDOFF_IDENTITY_MISMATCH')
                if existing['package_manifest']:
                    try:
                        workflow.load_package(root, existing['package_manifest'],
                            expected=existing['package_manifest_sha256'])
                    except ArtifactError as error:
                        if str(error) != 'STALE_OR_INVALID_REVIEW_TIMESTAMP':
                            raise
                        workflow.load_package(root, existing['package_manifest'],
                            expected=existing['package_manifest_sha256'], require_fresh=False)
                        key = digest({'renewal_of': key, 'expired_package_sha256': existing['package_manifest_sha256']})
                        folder = root / BASE / key
                        continue
                output.append(existing)
                break
            else:
                existing = None
            if existing is not None and folder.exists():
                continue
            prepared = None
            if candidate and entry['question']:
                if (old and old[1]['trust'] == trust
                        and old[1]['assessment_draft_sha256'] == digest(candidate['assessment'])
                        and old[1]['supporting_artifacts'] == candidate['supporting_artifacts']
                        and old[1]['layout_reviews'] == candidate['layout_reviews']):
                    prepared = old[0]
                else:
                    prepared = workflow.prepare(root, source=entry['source'], question=entry['question'],
                        assessment=candidate['assessment'], trust=trust,
                        supporting_artifacts=candidate['supporting_artifacts'], layout_reviews=candidate['layout_reviews'],
                        validation_policy=entry['policy'])
            value = {'schema': SCHEMA, 'identity_sha256': key, 'entry_id': entry['entry_id'],
                'created_at': now(), 'question_id': entry['question_id'], 'response_source': entry['source'],
                'request_sha256': entry['row']['request_sha256'], 'M8_package_sha256': entry['row']['M8_package_sha256'],
                'response_sha256': digest(entry['row']['response']), 'trust': trust,
                'status': 'PACKAGE_PREPARED' if prepared else 'PENDING_ASSESSMENTS',
                'package_manifest': prepared, 'package_manifest_sha256': sha(safe_path(root, prepared)) if prepared else None,
                'missing_assessments': [] if prepared else entry['missing_assessments'],
                'generation_authorized': False, 'owner_approval_created': False}
            stage = workflow.output_directory(root, 'data/evals/human-review/handoff-pending/' + uuid4().hex)
            save(stage / 'HANDOFF.json', value)
            save(stage / 'MANIFEST.json', {'schema': SCHEMA, 'generation_authorized': False,
                'files': {'HANDOFF.json': sha(stage / 'HANDOFF.json')}})
            folder.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if any(p.is_symlink() for p in [folder, *folder.parents]):
                raise ArtifactError('UNSAFE_HANDOFF_DIRECTORY')
            os.rename(stage, folder)
            output.append(value)
        return output
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def after_generation(root, manifest):
    """Never lose/retry a sealed generation because review preparation was unavailable."""
    try:
        from .preparation import run
        return run(root, source_manifest=manifest)
    except (ArtifactError, ValueError, TypeError, KeyError, OSError, ImportError):
        # Pure discovery still exposes the result as pending. No generation retry.
        return []


if __name__ == '__main__':
    import json
    rows = synchronize(Path(__file__).resolve().parents[2])
    print(json.dumps({'handoffs': len(rows), 'prepared': sum(r['status'] == 'PACKAGE_PREPARED' for r in rows),
                      'generation_authorized': False}))
