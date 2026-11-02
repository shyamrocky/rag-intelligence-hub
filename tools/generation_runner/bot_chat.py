"""Native single-turn chat consent and orchestration; no new RAG implementation.

An allowlisted owner-reviewed policy plus the exact Send receipt replaces manual
per-question approval paperwork. Existing native preflight and live gates still
verify every request. Importing or inspecting this module never executes work.
"""
import fcntl
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from tools.bot_runtime.store import (
    directory,
    load,
    locked,
    now,
    question_record,
    read,
    reference,
    seal,
    write,
)
from tools.quality_dashboard.artifacts import ArtifactError, digest, sha

BASE = 'data/runtime-chat/v1'
VERSION = 'local-bot-chat-1.0'
SEND_VERSION = 'local-bot-chat-send-2.0'
SEND_AUTHORITY = 'EXPLICIT_SEND_WITHOUT_ENABLEMENT'
DISCLOSURE = ('Send authorizes this question’s verified evidence transfer to OpenAI, '
              'up to two metadata and two token-count checks, and at most one paid answer within the displayed limits. '
              'No automatic retries or fallback. Execution receipts are retained privately.')


def config(policy):
    value = policy.get('bot_chat')
    if (not isinstance(value, dict) or value.get('schema') != VERSION
            or value.get('per_question_cap_usd') != '0.03'
            or type(value.get('generation_calls_per_submission')) is not int
            or value.get('generation_calls_per_submission') != 1
            or type(value.get('retries')) is not int or value.get('retries') != 0
            or value.get('fallback') is not None
            or value.get('budget_scope') != 'ALL_BOT_NATIVE_RESERVATIONS'
            or ('send_authorization' in value and value['send_authorization'] != SEND_AUTHORITY)
            or value.get('disclosure_sha256') != digest(DISCLOSURE)):
        raise ArtifactError('CHAT_POLICY_NOT_CONFIGURED')
    total = value.get('total_bot_cap_usd')
    if not isinstance(total, str) or not Decimal(total).is_finite() or Decimal(total) <= 0:
        raise ArtifactError('CHAT_TOTAL_BUDGET_NOT_CONFIGURED')
    return value


def send_policy(policy):
    """Reviewed default-Chat contract; policy selection still requires native trust.

    This grants no request by itself. Only a fresh explicit Send creates exact
    question consent. Historical enable/revoke events belong to the old contract.
    """
    settings = config(policy)
    if (settings.get('send_authorization') != SEND_AUTHORITY
            or settings['total_bot_cap_usd'] != '1.00'):
        raise ArtifactError('DEFAULT_CHAT_SEND_POLICY_REQUIRED')
    return settings


def verify_send(value, qid, question_ref, policy, trust_ref):
    """Shared current/historical v2 binding check; never issues consent."""
    settings = send_policy(policy)
    if (value.get('schema') != SEND_VERSION or value.get('question_id') != qid
            or value.get('question_reference') != question_ref
            or value.get('trust') != {k: trust_ref[k] for k in ('path', 'sha256')}
            or value.get('config_sha256') != digest(settings)
            or value.get('authority') != SEND_AUTHORITY
            or value.get('disclosure_sha256') != digest(DISCLOSURE)
            or value.get('explicit_send') is not True
            or value.get('allow_source_transfer') is not True
            or value.get('allow_paid_inference') is not True
            or 'activation' in value):
        raise ArtifactError('CHAT_SEND_BINDING_CHANGED_OR_UNAUTHORIZED')


def active(root, *, policy=None, trust_ref=None):
    """Read only; absent/incomplete/revoked or changed control cannot enable chat."""
    root = Path(root)
    folders = sorted((root / BASE / 'control').glob('[0-9]*'))
    if not folders:
        return None
    folder = folders[-1]
    load(folder, 'bot-chat-control-1.0')
    value = read(folder / 'CONTROL.json')
    if value.get('enabled') is False:
        return None
    if trust_ref is None:
        from tools.bot_runtime.trust import verify_implementation
        trust_ref = verify_implementation(root)
    if policy is None:
        from .trust import load_trust
        _, policy, _ = load_trust(root, trust_ref['path'], trust_ref['sha256'])
    from .runner import implementation
    expected = config(policy)
    if (value.get('schema') != VERSION or value.get('enabled') is not True
            or value.get('trust') != {k: trust_ref[k] for k in ('path', 'sha256')}
            or value.get('config') != expected or value.get('implementation') != implementation(root)
            or not value.get('owner_statement') or value.get('explicit_confirmation') is not True):
        raise ArtifactError('CHAT_ENABLEMENT_CHANGED_OR_UNVERIFIED')
    return value | {'reference': {'path': (folder / 'MANIFEST.json').relative_to(root).as_posix(),
                                  'sha256': sha(folder / 'MANIFEST.json')}}


def enable(root, *, owner_statement, confirmed, enabled=True):
    """Explicit local owner operation only. Never called on refresh or installation."""
    from tools.bot_runtime.trust import verify_implementation

    from .runner import implementation
    from .trust import load_trust
    if confirmed is not True or not isinstance(owner_statement, str) or not owner_statement.strip():
        raise ArtifactError('EXPLICIT_CHAT_ENABLEMENT_CONFIRMATION_REQUIRED')
    ref = verify_implementation(root)
    _, policy, _ = load_trust(root, ref['path'], ref['sha256'])
    settings = config(policy) if enabled else None
    if enabled:
        budget_state(root, settings)  # Existing reservations cannot be reset by re-enabling.
    base = directory(root, BASE + '/control')
    with locked(base):
        folders = sorted(base.glob('[0-9]*'))
        folder = base / f'{int(folders[-1].name) + 1 if folders else 1:06d}'
        folder.mkdir(mode=0o700)
        write(folder / 'CONTROL.json', {'schema': VERSION, 'enabled': enabled,
            'created_at': now(), 'owner_statement': owner_statement.strip(),
            'explicit_confirmation': True, 'trust': {k: ref[k] for k in ('path', 'sha256')},
            'config': settings, 'implementation': implementation(root),
            'authority': 'EXPLICIT_LOCAL_OWNER_ENABLEMENT_NOT_CRYPTOGRAPHIC_IDENTITY'})
        seal(folder, 'bot-chat-control-1.0')
    return folder


def submission(root, qid, policy, *, trust_ref=None):
    """Independently verify exact Send, reviewed authority and source framing."""
    root = Path(root)
    folder = root / BASE / 'submissions' / qid
    if not folder.exists():
        return None
    load(folder, 'bot-chat-submission-1.0')
    from tools.bot_runtime.store import read
    value = read(folder / 'SEND.json')
    if value.get('schema') == SEND_VERSION:
        if trust_ref is None:
            from tools.bot_runtime.trust import verify_implementation
            trust_ref = verify_implementation(root)
        verify_send(value, qid, reference(root, qid), policy, trust_ref)
        return value | {'reference': {'path': (folder / 'MANIFEST.json').relative_to(root).as_posix(),
                                      'sha256': sha(folder / 'MANIFEST.json')}}
    owner = active(root, policy=policy, trust_ref=trust_ref)
    if (owner is None or value.get('schema') != VERSION or value.get('question_id') != qid
            or value.get('question_reference') != reference(root, qid)
            or value.get('activation') != owner['reference']
            or value.get('disclosure_sha256') != digest(DISCLOSURE)
            or value.get('explicit_send') is not True
            or value.get('allow_source_transfer') is not True
            or value.get('allow_paid_inference') is not True):
        raise ArtifactError('CHAT_SEND_BINDING_CHANGED_OR_UNAUTHORIZED')
    return value | {'reference': {'path': (folder / 'MANIFEST.json').relative_to(root).as_posix(),
                                  'sha256': sha(folder / 'MANIFEST.json')}}


def budget_state(root, settings, *, additional='0'):
    """Conservative persistent reservations, including earlier exact Bot requests.

    Never resets on a browser session/enablement and never releases failed runs.
    Benchmark ceilings retain their existing independent enforcement.
    """
    from tools.bot_runtime.store import read

    from .trust import history
    history(root, [])  # Includes orphan/unknown native-history safeguards.
    reserved = Decimal(0)
    for start in (Path(root) / 'data/evals/generation-runner').glob('*/START.json'):
        if read(start).get('mode') != 'live':
            continue
        plan = read(start.parent / 'PLAN.json')
        if plan.get('question_source') != 'BOT':
            continue
        reserved += Decimal(plan['aggregate_maximum_estimated_cost_usd'])
        if not (start.parent / 'MANIFEST.json').exists():
            raise ArtifactError('CHAT_PRIOR_BILLING_OR_OUTCOME_UNKNOWN')
        rows = read(start.parent / 'RESULTS.json')['questions']
        if any(r.get('batch_disposition', {}).get('action') == 'STOP_SAFETY' for r in rows):
            raise ArtifactError('CHAT_PRIOR_BILLING_OR_OUTCOME_UNKNOWN')
    cap = Decimal(settings['total_bot_cap_usd'])
    amount = Decimal(additional)
    if not amount.is_finite() or amount < 0:
        raise ArtifactError('CHAT_COST_UNAVAILABLE')
    if reserved + amount > cap or reserved >= cap:
        raise ArtifactError('CHAT_TOTAL_BUDGET_EXCEEDED')
    return {'reserved_usd': str(reserved), 'total_cap_usd': str(cap),
            'remaining_usd': str(cap - reserved)}


def check_context(root, ctx, policy):
    """Dynamic scope is admitted only by an activated reviewed chat policy + Send."""
    value = submission(root, ctx['question_id'], policy)
    if value is None:
        raise ArtifactError('EXACT_BOT_PREFLIGHT_CONTEXT_NOT_ALLOWLISTED')
    if any(ctx.get(k) != v for k, v in config(policy)['configuration_bindings'].items()):
        raise ArtifactError('CHAT_MODEL_PROMPT_OR_PRICE_CHANGED')
    from .bot_preflight import context
    if context(root, ctx['local_manifest'])[0] != ctx:
        raise ArtifactError('CHAT_PREFLIGHT_CONTEXT_CHANGED')
    return value


def historical_context(root, ctx, policy, trust_manifest, trust_sha):
    """Past Send permission is auditable after disable; it is not fresh permission."""
    folder = Path(root) / BASE / 'submissions' / ctx['question_id']
    load(folder, 'bot-chat-submission-1.0')
    send = read(folder / 'SEND.json')
    if send.get('schema') == SEND_VERSION:
        verify_send(send, ctx['question_id'], reference(root, ctx['question_id']), policy,
                    {'path': trust_manifest, 'sha256': trust_sha})
        if (send['question_reference'] != ctx['question_reference']
                or any(ctx.get(k) != v for k, v in config(policy)['configuration_bindings'].items())):
            raise ArtifactError('CHAT_HISTORICAL_CONSENT_UNVERIFIED')
        return
    ref = send['activation']
    from tools.quality_dashboard.artifacts import safe_path
    manifest = safe_path(root, ref['path'], prefix=BASE + '/control')
    if sha(manifest) != ref['sha256']:
        raise ArtifactError('CHAT_HISTORICAL_ENABLEMENT_CHANGED')
    load(manifest.parent, 'bot-chat-control-1.0')
    owner = read(manifest.parent / 'CONTROL.json')
    if (owner.get('enabled') is not True or not owner.get('owner_statement')
            or owner.get('explicit_confirmation') is not True
            or owner.get('trust') != {'path': trust_manifest, 'sha256': trust_sha}
            or owner.get('config') != config(policy)
            or send.get('question_reference') != ctx['question_reference']
            or send.get('question_reference') != reference(root, ctx['question_id'])
            or send.get('question_id') != ctx['question_id']
            or send.get('explicit_send') is not True
            or send.get('disclosure_sha256') != digest(DISCLOSURE)
            or send.get('allow_source_transfer') is not True or send.get('allow_paid_inference') is not True
            or any(ctx.get(k) != v for k, v in config(policy)['configuration_bindings'].items())):
        raise ArtifactError('CHAT_HISTORICAL_CONSENT_UNVERIFIED')


def check_plan(root, plan, policy):
    value = submission(root, plan['questions'][0]['question_id'], policy)
    if value is None or plan.get('chat_submission') != value['reference']:
        raise ArtifactError('CHAT_PLAN_SEND_BINDING_REQUIRED')
    settings = config(policy)
    from .bot_source import build_plan
    expected, _, _ = build_plan(root, selected=[value['question_id']],
        preflight=plan['preflight_manifest'], per_question_cap=settings['per_question_cap_usd'],
        aggregate_cap=settings['per_question_cap_usd'], check_history=False)
    if expected != plan:
        raise ArtifactError('CHAT_PLAN_QUALIFICATION_OR_CONFIGURATION_CHANGED')
    return settings


MESSAGES = {
    'BUDGET_LIMIT_EXCEEDED': 'This request exceeds the configured spending limit. No answer was generated.',
    'CONTEXT_LIMIT_EXCEEDED': 'The prepared evidence exceeds the model’s capacity. No answer was generated.',
    'SOURCE_VALIDATION_FAILED': 'We couldn’t verify the source evidence safely. No answer was generated.',
    'INSUFFICIENT_EVIDENCE': 'There isn’t enough verified information to prepare an answer.',
    'PROVIDER_UNAVAILABLE': 'The service couldn’t complete this request. It won’t be retried automatically.',
    'DUPLICATE_SUBMISSION': 'This request is already processing or has completed. It won’t be submitted again.',
    'RESPONSE_REVIEW_REQUIRED': 'A response was received but needs review. Its available output and diagnostics are retained.',
    'RAW_RESPONSE_CAPTURE_FAILED': 'The response could not be saved safely. Raw response unavailable; no automatic retry.',
    'PRICING_OR_COST_UNAVAILABLE': 'We couldn’t verify the request cost. Generation has been stopped.',
    'BILLING_STATUS_UNKNOWN': 'A previous request has an unresolved outcome or cost. New paid requests are paused for review.',
    'CHAT_DISABLED': 'Live answering is off. Enable it explicitly before sending a paid request.',
    'EXECUTION_BLOCKED': 'This request stopped at a safety check. Its diagnostics are retained; no automatic retry.',
}


def finding(code, *, stage, generation_attempted=False, cost=None, limit=None):
    message = MESSAGES[code]
    if code == 'BUDGET_LIMIT_EXCEEDED' and cost is not None and limit is not None:
        message = (f'This request’s estimated maximum cost is ${cost}, above the applicable '
                   f'${limit} spending limit. No answer was generated. Try a more focused question.')
    return {'code': code, 'message': message, 'stage': stage,
            'generation_attempted': generation_attempted, 'estimated_maximum_cost_usd': cost,
            'applicable_limit_usd': limit, 'cost_status': 'UNKNOWN' if generation_attempted else 'GENERATION_NOT_ATTEMPTED'}


def error_code(error):
    # Classify known codes only; arbitrary source/provider exception text is private.
    value = str(error)
    if 'BILLING' in value or 'OUTCOME_UNKNOWN' in value:
        return 'BILLING_STATUS_UNKNOWN'
    if 'BUDGET' in value or 'COST_CAP' in value:
        return 'BUDGET_LIMIT_EXCEEDED'
    if 'CONTEXT' in value or 'OVERSIZED' in value:
        return 'CONTEXT_LIMIT_EXCEEDED'
    if 'PRICE' in value or 'PRICING' in value or 'COST_UNAVAILABLE' in value:
        return 'PRICING_OR_COST_UNAVAILABLE'
    if 'DUPLICATE' in value or 'ALREADY' in value or 'PRIOR_LIVE' in value:
        return 'DUPLICATE_SUBMISSION'
    if 'SOURCE' in value or value.startswith(('m8_', 'M8_')):
        return 'SOURCE_VALIDATION_FAILED'
    if 'CAPTURE_FAILED' in value:
        return 'RAW_RESPONSE_CAPTURE_FAILED'
    return 'EXECUTION_BLOCKED'


def observe_native_result(root, qid, outcome):
    """Retain honest attempted/unknown billing state even if sealing/handoff fails."""
    from tools.bot_runtime.projection import discover
    values = discover(root)['records'].get(qid, {}).get('attempts', [])
    native = [a for a in values if a['mode'] == 'live']
    if native:
        row = native[-1]
        outcome['generation_attempted'] = row.get('generation_attempted', row.get('generation_executed'))
        outcome['cost_usd'] = row.get('cost_usd')
    else:
        markers = list((Path(root) / 'data/evals/generation-runner').glob(
            '*/questions/' + qid + '/GENERATION_HTTP_ATTEMPT.json'))
        outcome['generation_attempted'] = bool(markers)


def execute(root, qid, *, confirmed):
    """Send -> existing local/preflight/live APIs, one immutable controller receipt.

    No retries, no alternate provider, no automatic source/prompt repair. The same
    command serves UI and terminal; native stages retain their own sealed records.
    """
    from tools.bot_runtime.store import read
    from tools.bot_runtime.trust import verify_implementation

    from . import bot_consent, bot_preflight, bot_runtime, bot_source, runner, trust
    root = Path(root)
    ref = verify_implementation(root)
    _, policy, _ = trust.load_trust(root, ref['path'], ref['sha256'])
    settings = config(policy)
    default_chat = settings.get('send_authorization') == SEND_AUTHORITY
    owner = None
    if default_chat:
        send_policy(policy)
        if confirmed is not True:
            raise ArtifactError('EXPLICIT_CHAT_SEND_REQUIRED')
    else:  # Historical allowlisted contracts retain their original controls.
        owner = active(root, policy=policy, trust_ref=ref)
        if owner is None or confirmed is not True:
            raise ArtifactError('EXPLICIT_ENABLED_CHAT_SEND_REQUIRED')
    question_record(root, qid)
    # Lock survives multiple browser sessions; exclusive claim survives crashes.
    base = directory(root, BASE)
    fd = (base / 'EXECUTION.lock').open('a')
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fd.close()
        raise ArtifactError('CHAT_ALREADY_PROCESSING_NO_RETRY') from None
    try:
        folder = root / BASE / 'submissions' / qid
        if folder.exists():
            raise ArtifactError('CHAT_DUPLICATE_SUBMISSION_NO_RETRY')
        folder.mkdir(parents=True, mode=0o700, exist_ok=False)
        authority = ({'trust': {k: ref[k] for k in ('path', 'sha256')},
                      'config_sha256': digest(settings), 'authority': SEND_AUTHORITY}
                     if default_chat else {'activation': owner['reference']})
        write(folder / 'SEND.json', {'schema': SEND_VERSION if default_chat else VERSION, 'question_id': qid,
            'question_reference': reference(root, qid), **authority,
            'created_at': now(), 'explicit_send': True, 'disclosure_sha256': digest(DISCLOSURE),
            'allow_source_transfer': True, 'allow_paid_inference': True})
        seal(folder, 'bot-chat-submission-1.0')
        run = directory(root, BASE + '/runs/' + qid)
        write(run / 'START.json', {'question_id': qid, 'question_reference': reference(root, qid),
            'created_at': now(), 'send': {'path': (folder / 'MANIFEST.json').relative_to(root).as_posix(),
                                        'sha256': sha(folder / 'MANIFEST.json')}})
        outcome = {'question_id': qid, 'question_reference': reference(root, qid),
                   'status': 'BLOCKED', 'stage': 'BUDGET_ADMISSION', 'references': {},
                   'finding': None, 'generation_attempted': False, 'cost_usd': None}
        try:
            budget_state(root, settings)
            trust.history(root, [qid])
            outcome['stage'] = 'LOCAL_EVIDENCE_PREPARATION'
            local = bot_runtime.execute(root, qid, mode='local-check')
            outcome['references']['local'] = (local / 'MANIFEST.json').relative_to(root).as_posix()
            local_result = read(local / 'RESULT.json')
            if local_result['application_outcome'] != 'LOCAL_ASSEMBLED_NOT_MODEL_QUALIFIED':
                code = 'INSUFFICIENT_EVIDENCE' if local_result.get('application_outcome') == 'INSUFFICIENT_EVIDENCE' else 'SOURCE_VALIDATION_FAILED'
                outcome['finding'] = finding(code, stage=outcome['stage'])
            else:
                outcome['stage'] = 'MODEL_PREFLIGHT'
                output = 'workspace/bot-chat-preparations/' + qid + '-' + uuid4().hex
                prepared = bot_preflight.prepare(root, outcome['references']['local'], output,
                    trust_manifest=ref['path'], trust_sha=ref['sha256'])
                # Attribute permission to the actual Send, never an invented enablement.
                provenance = f'trust {ref["sha256"]}' if default_chat else f'activation {owner["reference"]["sha256"]}'
                statement = f'Explicit Send for {qid}; {provenance}; submission {sha(folder / "MANIFEST.json")}; within the reviewed limits.'
                auth = bot_consent.issue(root, (prepared / 'MANIFEST.json').relative_to(root).as_posix(),
                    sha(prepared / 'MANIFEST.json'), operation='model-preflight', owner_statement=statement, confirmed=True)
                qualified = bot_preflight.execute(root, outcome['references']['local'],
                    auth.relative_to(root).as_posix(), sha(auth))
                outcome['references']['qualification'] = (qualified / 'MANIFEST.json').relative_to(root).as_posix()
                observation = read(qualified / 'RESULT.json')
                if observation['status'] != 'MODEL_QUALIFIED':
                    reasons = read(qualified / 'MODEL_PREFLIGHT.json').get('blocking_reasons', [])
                    code = error_code(ArtifactError(' '.join(reasons)))
                    outcome['finding'] = finding(code if code != 'EXECUTION_BLOCKED' else 'PROVIDER_UNAVAILABLE', stage=outcome['stage'])
                else:
                    maximum = observation['maximum_cost_usd']
                    state = budget_state(root, settings)
                    cap = min(Decimal(settings['per_question_cap_usd']), Decimal(state['remaining_usd']))
                    if Decimal(maximum) > cap:
                        outcome['finding'] = finding('BUDGET_LIMIT_EXCEEDED', stage=outcome['stage'], cost=maximum, limit=str(cap))
                    else:
                        outcome['stage'] = 'GENERATION'
                        plan, _, _ = bot_source.build_plan(root, selected=[qid], preflight=outcome['references']['qualification'],
                            per_question_cap='0.03', aggregate_cap='0.03')
                        prepared = trust.prepare(root, plan, 'workspace/bot-chat-preparations/' + qid + '-live-' + uuid4().hex,
                            trust_manifest=ref['path'], trust_sha=ref['sha256'])
                        auth = bot_consent.issue(root, (prepared / 'MANIFEST.json').relative_to(root).as_posix(),
                            sha(prepared / 'MANIFEST.json'), operation='live', owner_statement=statement, confirmed=True)
                        native = runner.execute(root, mode='live', selected=[qid], preflight=outcome['references']['qualification'],
                            per_question_cap='0.03', aggregate_cap='0.03', owner_authorization=auth.relative_to(root).as_posix(),
                            authorization_sha=sha(auth), execute_approved_live=True, progress=lambda *a, **kw: None)
                        outcome['references']['generation'] = (native / 'MANIFEST.json').relative_to(root).as_posix()
                        row = read(native / 'RESULTS.json')['questions'][0]
                        outcome['generation_attempted'] = bool(row.get('generation_attempted'))
                        outcome['cost_usd'] = row.get('audit', {}).get('usage', {}).get('total_estimated_cost_usd')
                        outcome['status'] = 'COMPLETED' if row.get('response') else 'REVIEW_REQUIRED'
                        if not row.get('response'):
                            reasons = row.get('audit', {}).get('blocking_reasons', [])
                            capture = row.get('audit', {}).get('raw_response_capture', {})
                            code = ('RAW_RESPONSE_CAPTURE_FAILED' if 'RAW_RESPONSE_CAPTURE_FAILED' in reasons
                                else 'RESPONSE_REVIEW_REQUIRED' if capture.get('status') == 'RAW_RESPONSE_CAPTURED'
                                else 'PROVIDER_UNAVAILABLE')
                            outcome['finding'] = finding(code,
                                stage=outcome['stage'], generation_attempted=outcome['generation_attempted'])
                            if code != 'RESPONSE_REVIEW_REQUIRED':
                                outcome['status'] = 'FAILED'
        except Exception as error:  # noqa: BLE001 - preserve source-free findings; never retry
            observe_native_result(root, qid, outcome)
            outcome['finding'] = finding(error_code(error), stage=outcome['stage'],
                                         generation_attempted=outcome['generation_attempted'])
        if outcome['finding']:
            outcome['finding']['cost_status'] = ('ACTUAL_USAGE_ESTIMATE_RECORDED' if outcome['cost_usd'] is not None
                else 'UNKNOWN' if outcome['generation_attempted'] else 'GENERATION_NOT_ATTEMPTED')
        write(run / 'RESULT.json', outcome)
        seal(run, 'bot-chat-execution-1.0')
        return run
    finally:
        fd.close()
