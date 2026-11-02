"""Local-only next-step preparation. Never selects trust or grants itself authority."""
from decimal import Decimal
from pathlib import Path

from tools.bot_runtime.projection import discover
from tools.preflight_suite.artifacts import sha
from tools.quality_dashboard.artifacts import ArtifactError


def prepare_next(root, qid, output):
    """Explicit submission/click only; existing exact native policy must admit it."""
    from tools.bot_runtime.trust import verify_implementation

    from . import bot_preflight, bot_source, trust
    root=Path(root)
    ref=verify_implementation(root)
    data=discover(root)
    if data['rejected'] or qid not in data['records']:
        raise ArtifactError('UNVERIFIED_BOT_HISTORY')
    if data['records'][qid].get('disposition')=='DISCARDED':
        return {'status':'DISCARDED','stage':'none'}
    attempts=data['records'][qid]['attempts']
    if any(a.get('native_attempt') or a.get('mode')=='live' for a in attempts):
        return {'status':'EXECUTION_ALREADY_RECORDED','stage':'human-review'}
    locals_=[a for a in attempts if a['mode']=='local-check']
    if not locals_:
        return {'status':'LOCAL_CHECK_REQUIRED','stage':'local-check'}
    local=locals_[-1]
    if local.get('application_outcome')!='LOCAL_ASSEMBLED_NOT_MODEL_QUALIFIED':
        return {'status':'LOCAL_PREPARATION_BLOCKED','stage':'local-check'}
    _,policy,_=trust.load_trust(root,ref['path'],ref['sha256'])
    observations=[a for a in attempts if a['mode']=='model-preflight']
    claims=root/bot_source.QUALIFICATIONS/'claims'/f'{qid}.json'
    if observations or claims.exists():
        qualified=[a for a in observations if a.get('execution_status')=='MODEL_QUALIFIED']
        if not qualified:
            return {'status':'PREFLIGHT_RECORDED_NO_AUTOMATIC_RETRY','stage':'model-preflight'}
        scope=policy.get('bot_live_scope') or {}
        if scope.get('question_ids')!=[qid]:
            return {'status':'POLICY_REVIEW_REQUIRED','stage':'live'}
        # Caps come from the reviewed native policy, never a UI default or an
        # inferred allowance from another question. Exact plan binding still wins.
        plan,_,_=bot_source.build_plan(root,selected=[qid],
            preflight=qualified[-1]['manifest_path'],
            per_question_cap=policy['maximum_question_cap_usd'],
            aggregate_cap=min(policy['maximum_stage_cap_usd'],policy['maximum_question_cap_usd'],key=Decimal))
        folder=trust.prepare(root,plan,output,trust_manifest=ref['path'],trust_sha=ref['sha256'])
        stage='live'
    else:
        ctx,_,_=bot_preflight.context(root,local['manifest_path'])
        if ctx not in policy.get('bot_provider_preflight_allowlist',[]):
            return {'status':'POLICY_REVIEW_REQUIRED','stage':'model-preflight'}
        folder=bot_preflight.prepare(root,local['manifest_path'],output,
            trust_manifest=ref['path'],trust_sha=ref['sha256'])
        stage='model-preflight'
    manifest=folder/'MANIFEST.json'
    return {'status':'AWAITING_OWNER_CONSENT','stage':stage,
            'manifest':manifest.relative_to(root).as_posix(),'sha256':sha(manifest)}
