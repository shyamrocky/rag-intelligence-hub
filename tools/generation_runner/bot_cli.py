"""One Bot backend for local preparation, native qualification/consent and execution."""
import argparse
import json
from pathlib import Path
from uuid import uuid4


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['register','local-check','mock','inspect','prepare-next','prepare-model-preflight',
        'model-preflight','prepare-live','issue-preflight-consent','issue-live-consent','live',
        'chat','activate-chat','disable-chat','chat-status'])
    group=parser.add_mutually_exclusive_group(required=False)
    group.add_argument('--question-file',type=Path)
    group.add_argument('--question-id')
    parser.add_argument('--submission-id')
    parser.add_argument('--scenario',choices=['abstained','answered','partial','schema-error','api-failure','empty-evidence'],default='abstained')
    for field in ['local-manifest','preflight-manifest','trust-manifest','trust-sha','output',
        'preflight-consent','preflight-consent-sha','owner-authorization','authorization-sha',
        'preparation-manifest','preparation-sha','per-question-cap','aggregate-cap']:
        parser.add_argument('--'+field)
    parser.add_argument('--owner-statement-file',type=Path)
    parser.add_argument('--confirm-exact-request',action='store_true')
    parser.add_argument('--execute-approved-live',action='store_true')
    args=parser.parse_args(argv)
    root=Path(__file__).resolve().parents[2]
    def require(*fields):
        if any(not getattr(args,k) for k in fields):
            raise ValueError('EXPLICIT_REQUIRED_BOT_ARGUMENT_MISSING')
    try:
        from tools.bot_runtime.store import question_record, register
        from tools.bot_runtime.trust import verify_implementation
        verify_implementation(root)
        if args.mode in {'activate-chat','disable-chat','chat-status'}:
            if args.question_id or args.question_file:
                raise ValueError('CHAT_CONTROL_DOES_NOT_SELECT_A_QUESTION')
            from .bot_chat import SEND_AUTHORITY, active, config, enable, send_policy
            if args.mode == 'chat-status':
                from .trust import load_trust
                ref = verify_implementation(root)
                _, policy, _ = load_trust(root, ref['path'], ref['sha256'])
                if config(policy).get('send_authorization') == SEND_AUTHORITY:
                    print(json.dumps({'mode': args.mode, 'enabled': True,
                                      'authority': SEND_AUTHORITY, 'config': send_policy(policy)}))
                else:
                    value = active(root)
                    print(json.dumps({'mode': args.mode, 'enabled': bool(value),
                                      'config': value['config'] if value else None}))
            else:
                require('owner_statement_file','confirm_exact_request')
                from tools.bot_runtime.store import read
                from tools.quality_dashboard.artifacts import safe_path
                path = safe_path(root, args.owner_statement_file.as_posix(), prefix='workspace')
                statement = read(path)['statement'] if path.suffix == '.json' else path.read_text()
                folder = enable(root, owner_statement=statement, confirmed=True,
                                enabled=args.mode == 'activate-chat')
                print(json.dumps({'mode': args.mode, 'enabled': args.mode == 'activate-chat',
                                  'manifest': (folder/'MANIFEST.json').relative_to(root).as_posix()}))
            return 0
        if not (args.question_id or args.question_file):
            raise ValueError('EXPLICIT_BOT_QUESTION_REQUIRED')
        if args.mode!='mock' and args.scenario!='abstained':
            raise ValueError('MOCK_SCENARIO_REQUIRES_MOCK_MODE')
        if args.question_file and args.mode not in {'register','local-check','mock'}:
            raise ValueError('EXISTING_EXACT_BOT_ID_REQUIRED')
        question=register(root,args.question_file.read_text(),args.submission_id or uuid4().hex) if args.question_file else question_record(root,args.question_id)
        qid=question['question_id']; output={'question_id':qid,'mode':args.mode}
        if args.mode == 'chat':
            from .bot_chat import execute
            require('confirm_exact_request')
            output['run'] = execute(root, qid, confirmed=True).relative_to(root).as_posix()
        elif args.mode in {'mock','local-check'}:
            from .bot_runtime import execute
            output['run']=execute(root,qid,mode=args.mode,scenario=args.scenario).relative_to(root).as_posix()
        elif args.mode=='prepare-next':
            from .bot_flow import prepare_next
            require('output')
            output.update(prepare_next(root,qid,args.output))
        elif args.mode in {'prepare-model-preflight','model-preflight'}:
            from .bot_preflight import context, execute, prepare
            require('local_manifest')
            if context(root,args.local_manifest)[0]['question_id']!=qid:
                raise ValueError('BOT_PREFLIGHT_SELECTION_CHANGED')
            if args.mode=='prepare-model-preflight':
                require('trust_manifest','trust_sha','output')
                folder=prepare(root,args.local_manifest,args.output,trust_manifest=args.trust_manifest,trust_sha=args.trust_sha)
            else:
                require('preflight_consent','preflight_consent_sha')
                folder=execute(root,args.local_manifest,args.preflight_consent,args.preflight_consent_sha)
            output['run']=folder.relative_to(root).as_posix()
        elif args.mode in {'prepare-live','live'}:
            from .bot_source import build_plan
            require('preflight_manifest','per_question_cap','aggregate_cap')
            kwargs={'selected':[qid],'preflight':args.preflight_manifest,'per_question_cap':args.per_question_cap,'aggregate_cap':args.aggregate_cap}
            if args.mode=='prepare-live':
                from .trust import prepare
                require('trust_manifest','trust_sha','output')
                plan,_,_=build_plan(root,**kwargs)
                folder=prepare(root,plan,args.output,trust_manifest=args.trust_manifest,trust_sha=args.trust_sha)
            else:
                from .runner import execute
                require('owner_authorization','authorization_sha','execute_approved_live')
                folder=execute(root,mode='live',**kwargs,owner_authorization=args.owner_authorization,
                    authorization_sha=args.authorization_sha,execute_approved_live=True)
            output['run']=folder.relative_to(root).as_posix()
        elif args.mode in {'issue-live-consent','issue-preflight-consent'}:
            from .bot_consent import issue, preparation
            require('preparation_manifest','preparation_sha','owner_statement_file','confirm_exact_request')
            folder,_=preparation(root,args.preparation_manifest,args.preparation_sha)
            from tools.bot_runtime.store import read
            template=read(folder/('AUTHORIZATION_TEMPLATE.json' if args.mode=='issue-live-consent' else 'PREFLIGHT_CONSENT_TEMPLATE.json'))
            ids=template['question_ids'] if args.mode=='issue-live-consent' else [template['context']['question_id']]
            if ids!=[qid]:
                raise ValueError('BOT_CONSENT_SELECTION_CHANGED')
            from tools.quality_dashboard.artifacts import safe_path
            statement_path=safe_path(root,args.owner_statement_file.as_posix(),prefix='workspace')
            statement=statement_path.read_text()
            if args.owner_statement_file.suffix=='.json':
                statement=json.loads(statement)['statement']
            file=issue(root,args.preparation_manifest,args.preparation_sha,
                operation='live' if args.mode=='issue-live-consent' else 'model-preflight',
                owner_statement=statement,confirmed=True)
            from tools.preflight_suite.artifacts import sha
            output.update(consent=file.relative_to(root).as_posix(),consent_sha256=sha(file))
        elif args.mode=='inspect':
            from tools.bot_runtime.projection import discover
            record=discover(root)['records'][qid]
            output['attempts']=[{k:a.get(k) for k in ('run_id','mode','execution_status','model_status','validation_status')} for a in record['attempts']]
        else:
            output['registered']=True
        print(json.dumps(output))
        return 0
    except Exception as error:  # noqa: BLE001 - source-free diagnostic category
        output = {'status':'BLOCKED','error_type':type(error).__name__}
        if args.mode == 'chat':
            from .bot_chat import error_code, finding
            output.update(question_id=args.question_id, mode='chat',
                          finding=finding(error_code(error), stage='ADMISSION'))
        print(json.dumps(output))
        return 2
