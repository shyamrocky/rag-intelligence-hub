"""Explicit owner confirmation of sealed templates; never called on refresh.

These local attestations use the existing native trust mechanisms. They do not
claim cryptographic identity and cannot admit a plan outside the native allowlist.
"""
import os
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from tools.bot_runtime.store import directory, read, write
from tools.preflight_suite.artifacts import sha
from tools.quality_dashboard.artifacts import ArtifactError, digest, safe_path

from .trust import MAX_AGE_SECONDS


def preparation(root, manifest_path, expected):
    path=safe_path(root,manifest_path,prefix='workspace')
    if sha(path)!=expected:
        raise ArtifactError('DISPLAYED_CONSENT_PREPARATION_CHANGED')
    m=read(path)
    if m.get('generation_authorized',False) or m.get('generation_authority',False):
        raise ArtifactError('UNSIGNED_PREPARATION_REQUIRED')
    folder=path.parent
    for name,h in m['files'].items():
        if Path(name).name!=name or sha(safe_path(root,(folder/name).relative_to(root).as_posix(),prefix='workspace'))!=h:
            raise ArtifactError('CONSENT_PREPARATION_ARTIFACT_CHANGED')
    return folder,m


def issue(root, manifest_path, expected, *, operation, owner_statement, confirmed):
    """A fresh explicit click/CLI opt-in for this displayed exact hash-bound target."""
    if (confirmed is not True or operation not in {'model-preflight','live'}
            or not isinstance(owner_statement,str) or not owner_statement.strip()
            or len(owner_statement)>5000):
        raise ArtifactError('EXPLICIT_EXACT_REQUEST_OWNER_CONFIRMATION_REQUIRED')
    folder,m=preparation(root,manifest_path,expected)
    from tools.preflight_suite.artifacts import now

    from .runner import implementation
    expires=(datetime.fromisoformat(now())+timedelta(seconds=MAX_AGE_SECONDS)).isoformat()
    if operation=='model-preflight':
        from .bot_preflight import AUTH_SCHEMA, validate_value
        if m['schema']!='bot-unsigned-preflight-preparation-1.0':
            raise ArtifactError('BOT_PREFLIGHT_TEMPLATE_REQUIRED')
        value=read(folder/'PREFLIGHT_CONSENT_TEMPLATE.json')
        if value['schema']!=AUTH_SCHEMA or value['allow_paid_inference'] is not False:
            raise ArtifactError('PREFLIGHT_CANNOT_AUTHORIZE_PAID_INFERENCE')
        value=value|{'owner_statement':owner_statement.strip(),'allow_source_transfer':True,
                     'allow_provider_preflight':True,'expires_at':expires}
        # Validate through the actual native preflight path BEFORE publication.
        from .bot_preflight import context, policy_check
        ctx,_,_=context(root,value['context']['local_manifest'])
        if ctx!=value['context'] or implementation(root)!=value['implementation_bindings']:
            raise ArtifactError('BOT_PREFLIGHT_TEMPLATE_CONTEXT_CHANGED')
        policy_check(root,ctx,value['trust_manifest'],value['trust_sha256'])
        validator=lambda:validate_value(root,ctx['local_manifest'],value)
    else:
        if m['schema']!='generation-unsigned-preparation-1.0':
            raise ArtifactError('NATIVE_UNSIGNED_LIVE_TEMPLATE_REQUIRED')
        from .runner import validate_authorization_fields
        value=read(folder/'AUTHORIZATION_TEMPLATE.json')
        plan=read(folder/'PLAN.json')
        if plan.get('question_source')!='BOT' or len(plan['questions'])!=1:
            raise ArtifactError('EXACT_SINGLE_BOT_PLAN_REQUIRED')
        value=value|{'owner_statement':owner_statement.strip(),'allow_source_transfer':True,
                     'allow_paid_inference':True,'expires_at':expires}
        validator=lambda:validate_authorization_fields(root,plan,value)
    # Validate before writing owner permission; publish atomically into the only
    # namespace accepted by execute/authorize. Interrupted pending records cannot run.
    validator()
    identity = uuid4().hex
    pending=directory(root,'workspace/bot-consents/pending/'+identity)
    write(pending/'CONSENT.json',value)
    write(pending/'MANIFEST.json',{'schema':'bot-owner-consent-1.0','operation':operation,
        'explicit_owner_confirmation':True,'publication_status':'ACCEPTED_OWNER_ATTESTATION',
        'question_ids':([value['context']['question_id']]
          if operation=='model-preflight' else value['question_ids']),
        'files':{'CONSENT.json':sha(pending/'CONSENT.json')},'consent_sha256':digest(value)})
    approved=directory(root,'workspace/bot-consents/approved')
    final=approved/identity
    os.rename(pending,final)
    fd=os.open(approved,os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return final/'CONSENT.json'


def verify_publication(root, consent_path, expected, *, operation):
    path=safe_path(root,consent_path,prefix='workspace/bot-consents/approved')
    if path.name!='CONSENT.json' or sha(path)!=expected:
        raise ArtifactError('PUBLISHED_OWNER_CONSENT_REQUIRED')
    m=read(path.parent/'MANIFEST.json')
    value=read(path)
    if (m.get('schema')!='bot-owner-consent-1.0' or m.get('operation')!=operation
            or m.get('explicit_owner_confirmation') is not True
            or m.get('publication_status')!='ACCEPTED_OWNER_ATTESTATION'
            or m.get('files')!={'CONSENT.json':expected}
            or m.get('consent_sha256')!=digest(value)
            or m.get('question_ids')!=([value['context']['question_id']] if operation=='model-preflight' else value['question_ids'])):
        raise ArtifactError('OWNER_CONSENT_PUBLICATION_CHANGED')
    return value
