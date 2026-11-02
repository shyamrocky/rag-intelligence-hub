"""Interactive local reviewer CLI. No passphrase argv/env flags or automatic approval."""
import argparse
import getpass
import json
import sys
from pathlib import Path

from tools.quality_dashboard.artifacts import ArtifactError, read_json

from .identity import change_key, default_store, enrollment_confirmation, register, registry
from .workflow import confirmation_text, decide, load_package, prepare, recover, verify_decision


def interactive():
    if not sys.stdin.isatty():
        raise ArtifactError('LOCAL_INTERACTIVE_TERMINAL_REQUIRED')


def main():
    parser = argparse.ArgumentParser(description='Local signed human reviews; never generation authorization')
    sub = parser.add_subparsers(dest='command', required=True)
    enroll = sub.add_parser('register')
    enroll.add_argument('--reviewer-id', required=True)
    enroll.add_argument('--display-name', required=True)
    sub.add_parser('status')
    for name in ('rotate', 'revoke'):
        p = sub.add_parser(name)
        p.add_argument('--reviewer-id', required=True)
    p = sub.add_parser('prepare-q04')
    p.add_argument('--trust-manifest', required=True)
    p.add_argument('--trust-sha256', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--input', required=True, help='Source-free JSON: source, question, assessment, trust, optional supporting_artifacts/layout_reviews')
    for name in ('inspect', 'verify', 'decide'):
        p = sub.add_parser(name)
        p.add_argument('--manifest', required=True)
        if name == 'decide':
            p.add_argument('--sha256', required=True)
            p.add_argument('--reviewer-id', required=True)
            p.add_argument('--decision', choices=['APPROVE', 'REJECT', 'REQUEST_CHANGES'], required=True)
    p = sub.add_parser('recover')
    p.add_argument('--target', required=True)
    p.add_argument('--reviewer-id', required=True)
    args = parser.parse_args()
    root, store = Path.cwd(), default_store()
    if store.is_relative_to(root):
        raise ArtifactError('SIGNING_CREDENTIALS_MUST_BE_OUTSIDE_PROJECT')
    if args.command == 'register':
        interactive()
        phrase = enrollment_confirmation(args.reviewer_id, args.display_name)
        print('This enrolls the explicit local OS operator identity, not a verified legal identity.')
        print('Type exactly: ' + phrase)
        confirmed = input('Enrollment confirmation: ')
        secret = getpass.getpass('New signing-key passphrase (12+ characters): ')
        if secret != getpass.getpass('Repeat passphrase: '):
            raise ArtifactError('PASSPHRASE_CONFIRMATION_MISMATCH')
        result = register(store, args.reviewer_id, args.display_name, secret, confirmed)
        print(json.dumps({k: result[k] for k in ('reviewer_id', 'display_name', 'enrollment_sha256', 'revoked')}))
    elif args.command == 'status':
        result = registry(store)
        print(json.dumps({k: result[k] for k in ('reviewer_id', 'display_name', 'enrollment_sha256', 'revoked')}))
    elif args.command in {'rotate', 'revoke'}:
        interactive()
        operation = args.command.upper()
        print('Type exactly: ' + operation + ' ' + args.reviewer_id)
        confirmed = input('Key change confirmation: ')
        secret = getpass.getpass('Current passphrase: ')
        new = None
        if operation == 'ROTATE':
            new = getpass.getpass('New passphrase: ')
            if new != getpass.getpass('Repeat new passphrase: '):
                raise ArtifactError('PASSPHRASE_CONFIRMATION_MISMATCH')
        change_key(store, args.reviewer_id, secret, operation=operation,
                   confirmation=confirmed, new_passphrase=new)
        print('KEY_CHANGE_RECORDED')
    elif args.command == 'prepare-q04':
        from .onboarding import q04
        print(q04(root, {'path': args.trust_manifest, 'sha256': args.trust_sha256}))
    elif args.command == 'prepare':
        print(prepare(root, **read_json(Path(args.input))))
    elif args.command == 'inspect':
        p, row, h = load_package(root, args.manifest)
        print(json.dumps({'question': p['question'], 'response': row['response'],
            'proposed_assessment': p['assessment_draft'], 'bindings': p['bindings'],
            'manifest_sha256': h, 'status': p['status']}, indent=2))
    elif args.command == 'verify':
        body, result = verify_decision(root, store, args.manifest)
        print(json.dumps({'decision': body['outcome'], 'reviewer_id': body['reviewer_id'],
                          'evaluation_status': result['overall_status']}))
    elif args.command == 'decide':
        interactive()
        p, row, h = load_package(root, args.manifest, expected=args.sha256)
        print(json.dumps({'question': p['question'], 'answer': row['response']['answer'],
                         'assessment': p['assessment_draft']}, indent=2))
        print('Confirm exactly: ' + confirmation_text(args.decision, p['question_id'], h))
        phrase = input('Per-answer confirmation: ')
        secret = getpass.getpass('Signing-key passphrase: ')
        print(decide(root, store, args.manifest, expected_sha=h, reviewer_id=args.reviewer_id,
                     passphrase=secret, decision=args.decision, confirmation=phrase))
    elif args.command == 'recover':
        interactive()
        print('Type exactly: ABORT ' + args.target)
        confirmed = input('Abort unpublished decision: ')
        secret = getpass.getpass('Signing-key passphrase: ')
        print(recover(root, store, args.target, reviewer_id=args.reviewer_id,
                      passphrase=secret, confirmation=confirmed))


if __name__ == '__main__':
    try:
        main()
    except (ArtifactError, OSError, KeyError, TypeError, ValueError):
        print('REVIEW_OPERATION_BLOCKED — credential, confirmation, provenance or freshness check failed.', file=sys.stderr)
        sys.exit(1)
