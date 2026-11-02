"""Explicit CLI only: no stages execute through imports or dashboard refresh."""
import argparse
import json
from pathlib import Path

from .artifacts import baseline
from .runner import completed_questions, execute, select


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['local-check', 'model-preflight'])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--all', action='store_true')
    group.add_argument('--question', nargs='+')
    group.add_argument('--cohort', nargs='+', choices=list('ABCD'))
    group.add_argument('--pending-generation', action='store_true')
    parser.add_argument('--local-manifest')
    parser.add_argument('--authorize-transfer', help='Explicit owner authorization reference for this question set')
    args = parser.parse_args(argv)
    if args.mode == 'model-preflight' and not (args.local_manifest and args.authorize_transfer):
        parser.error('model-preflight requires --local-manifest and --authorize-transfer; no generation is permitted')
    root = Path(__file__).resolve().parents[2]
    try:
        _, questions = baseline(root)
        selected = select(questions, ids=args.question, cohorts=args.cohort,
                          pending=args.pending_generation,
                          completed=completed_questions(root) if args.pending_generation else ())
        run, _ = execute(root, mode=args.mode, selected=selected,
                         authorization=args.authorize_transfer, local_manifest=args.local_manifest)
        print(json.dumps({'sealed_run': run.relative_to(root).as_posix(), 'generation_executed': False}))
        return 0
    except Exception as error:  # noqa: BLE001 - redact arbitrary source/provider exception bodies
        print(json.dumps({'status': 'BLOCKED', 'error_type': type(error).__name__,
                          'source_and_credentials_omitted': True, 'generation_executed': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
