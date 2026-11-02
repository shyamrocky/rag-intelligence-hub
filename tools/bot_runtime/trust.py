"""Use the existing allowlisted native preservation gate. Never paid authority."""

def verify_implementation(root):
    from tools.generation_runner.trust import load_trust
    from tools.generation_trust_anchor import BOT_RUNTIME_BASELINE, TRUSTED_BASELINES
    from tools.quality_dashboard.artifacts import ArtifactError
    expected = TRUSTED_BASELINES[BOT_RUNTIME_BASELINE]
    _, policy, result = load_trust(root, BOT_RUNTIME_BASELINE, expected)
    runtime = policy.get('bot_runtime')
    expected_policy = {'schema': 'native-bot-capabilities-2.0',
        'modes': ['local-check','mock','model-preflight','live'],
        'default_provider_calls_allowed': 0, 'generation_authority': False,
        'exact_scoped_owner_consent_required': True, 'benchmark_membership_changes': False}
    if runtime != expected_policy or result['blocking_findings']:
        raise ArtifactError('BOT_NATIVE_POLICY_REQUIRED')
    return {'path': BOT_RUNTIME_BASELINE, 'sha256': expected, 'generation_authority': False}
