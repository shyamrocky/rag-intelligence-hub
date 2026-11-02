"""Explicit policy selection. Historical packages never inherit newer policy bytes."""
from pathlib import Path

from tools.quality_dashboard.artifacts import ArtifactError, sha

LEGACY = 'tools/answer_quality/POLICY.json'
CURRENT = 'tools/answer_quality/POLICY_2_1.json'


def policy_reference(root):
    return {'path': CURRENT, 'sha256': sha(Path(root) / CURRENT)}


def validator_for(root, reference):
    if reference['path'] not in {LEGACY, CURRENT} or sha(Path(root) / reference['path']) != reference['sha256']:
        raise ArtifactError('UNSUPPORTED_OR_CHANGED_VALIDATION_POLICY')
    if reference['path'] == CURRENT:
        from .validator_v21 import PostGenerationValidator
    else:
        from .validator import PostGenerationValidator
    return PostGenerationValidator
