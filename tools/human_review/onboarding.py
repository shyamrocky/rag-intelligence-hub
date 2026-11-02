"""Unsigned Q04 onboarding from already recorded decisions; never an approval."""
from pathlib import Path

from tools.quality_dashboard.artifacts import ArtifactError, Store, read_json, sha

from .workflow import prepare

OWNER = 'data/evals/generation-runner-reviews/q04-owner-review-eligibility-v1'
SEMANTIC = 'data/evals/generation-runner-reviews/q04-semantic-review-v1'
VERIFIED = 'data/evals/answer-quality/q04-v2-verified'


def q04(root, trust):
    store = Store(root)
    for base, expected in [(OWNER, 'e4813843f869f329e1eccaaa6dda3b6b867e4926dab126aa6e22665aecdfd0d6'),
        (SEMANTIC, 'caac5457a035151b3b9b9bb91cbda5c0dadb1ac532a6db18f518b0998c4ce693'),
        (VERIFIED, '6f2258c0c8d49d2d49cc867666ceefbb888205c4183001885dfbb0ea86a742ae')]:
        store.manifest(base + '/MANIFEST.json', expected=expected)
    receipt = store.json(OWNER + '/OWNER_DECISION_RECEIPT.json')
    value = store.json(SEMANTIC + '/PROVISIONAL_ASSESSMENT.json')
    if receipt['decisions']['caption_ownership_disclosure']['decision'] != 'NOT_REQUIRED':
        raise ArtifactError('RECORDED_OWNER_DECISION_MISMATCH')
    value['qualifications'] = {'outcome': 'SATISFIED', 'passages': value['qualifications']['passages'],
        'rationale': 'Recorded owner decision for this textual comparison: the absent visual is disclosed; '
        'caption-ownership non-certification does not require additional user-facing disclosure. '
        'No global metadata or source-use rule changes.'}
    value['uncertainty'] = []
    # Still an unsigned assistant draft. Identity/time become human fields ONLY on real confirmation.
    value['reviewer'] = 'UNASSIGNED_OWNER_CONFIRMATION_PENDING'
    value['method'] = 'ASSISTANT_ANALYSIS'
    value['independent_of_generator'] = False
    source = read_json(Path(root) / VERIFIED / 'MANIFEST.json')['response_source']
    layout = store.json(VERIFIED + '/LAYOUT_REVIEWS.json')['records']
    support = dict(store.verified)
    for record in layout:
        name = record['review_id'].split('#')[0]
        support[name] = sha(Path(root) / name)
    return prepare(root, source=source, question=receipt['context']['question'], assessment=value,
                   trust=trust, supporting_artifacts=support, layout_reviews=layout)
