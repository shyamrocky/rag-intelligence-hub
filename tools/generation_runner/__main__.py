"""Explicit CLI. Dashboard imports never invoke this module."""
import argparse
import json
from pathlib import Path


def main(argv=None):
    import sys
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments[:1] == ['bot']:
        from .bot_cli import main as bot_main
        return bot_main(arguments[1:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['dry-run', 'mock', 'live', 'prepare-authorization'])
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--pending-generation', action='store_true')
    selection.add_argument('--question', nargs='+')
    selection.add_argument('--cohort', nargs='+', choices=list('ABCD'))
    parser.add_argument('--preflight-manifest')
    parser.add_argument('--per-question-cap', default='0.03')
    parser.add_argument('--aggregate-cap', default='1.00')
    parser.add_argument('--scenario', choices=['success', 'api-failure', 'schema-error'], default='success')
    parser.add_argument('--owner-authorization')
    parser.add_argument('--authorization-sha')
    parser.add_argument('--execute-approved-live', action='store_true')
    parser.add_argument('--trust-manifest')
    parser.add_argument('--trust-sha')
    parser.add_argument('--output')
    args = parser.parse_args(argv)
    if args.mode == 'live' and not (args.owner_authorization and args.authorization_sha and args.execute_approved_live):
        parser.error('BUILD ONLY: live requires separately reviewed owner authorization and all opt-ins')
    from .runner import execute
    try:
        root = Path(__file__).resolve().parents[2]
        if args.mode == 'prepare-authorization':
            from .plan import build_plan
            from .trust import prepare
            if not (args.trust_manifest and args.trust_sha and args.output):
                parser.error('Unsigned preparation requires --trust-manifest --trust-sha --output')
            kwargs = {'selected': args.question, 'cohorts': args.cohort,
                      'per_question_cap': args.per_question_cap, 'aggregate_cap': args.aggregate_cap}
            if args.preflight_manifest:
                kwargs['preflight'] = args.preflight_manifest
            plan, _, _ = build_plan(root, **kwargs)
            folder = prepare(root, plan, args.output, trust_manifest=args.trust_manifest,
                             trust_sha=args.trust_sha)
            print(json.dumps({'unsigned_preparation': folder.relative_to(root).as_posix(),
                              'generation_authorized': False}))
            return 0
        run = execute(root, mode=args.mode, selected=args.question, cohorts=args.cohort,
                      preflight=args.preflight_manifest, per_question_cap=args.per_question_cap,
                      aggregate_cap=args.aggregate_cap, scenario=args.scenario,
                      owner_authorization=args.owner_authorization, authorization_sha=args.authorization_sha,
                      execute_approved_live=args.execute_approved_live)
        print(json.dumps({'run': run.relative_to(root).as_posix(), 'mode': args.mode,
                          'live_generation_authorized_by_this_build': False}))
        return 0
    except Exception as error:  # noqa: BLE001 - safe category only
        print(json.dumps({'status': 'BLOCKED', 'error_type': type(error).__name__}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
