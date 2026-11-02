"""Exact multi-release review readback, separate from paid execution trust."""
import copy

import pytest

from tools.generation_runner import trust
from tools.human_review import workflow
from tools.quality_dashboard.artifacts import ArtifactError


@pytest.mark.parametrize('problem', [None, 'cycle', 'hash', 'edge', 'contract'])
def test_review_transition_chain_cannot_substitute_unreviewed_edges(monkeypatch, problem):
    from tools import generation_trust_anchor as anchor
    refs = [{'path': f'data/owned-v{i}/MANIFEST.json', 'sha256': str(i) * 64} for i in range(3)]
    contract = {'path': 'owned-review-policy', 'sha256': 'a' * 64}
    values = {}
    for i, ref in enumerate(refs):
        base = ref['path'].rsplit('/', 1)[0]
        values[ref['path']] = {'files': {'POLICY.json': 'b' * 64},
            'parent_manifest_sha256': refs[i-1]['sha256'] if i else None}
        values[base + '/POLICY.json'] = {'human_review_contract': contract}
    transitions = {refs[i]['path']: {'parent_sha256': refs[i]['sha256'],
                                    'successor': refs[i+1]} for i in range(2)}
    if problem == 'cycle': transitions[refs[1]['path']]['successor'] = refs[0]
    if problem == 'hash': transitions[refs[0]['path']]['parent_sha256'] = 'f' * 64
    if problem == 'edge': values[refs[1]['path']]['parent_manifest_sha256'] = 'f' * 64
    final_policy = {'human_review_contract': copy.deepcopy(contract)}
    if problem == 'contract': final_policy['human_review_contract']['sha256'] = 'f' * 64
    def bound(root, name, expected):
        return values[name]
    def load(root, path, expected):
        assert (path, expected) == (refs[2]['path'], refs[2]['sha256'])
        return values[path], final_policy, {'blocking_findings': 0}
    monkeypatch.setattr(anchor, 'HUMAN_REVIEW_TRUST_MIGRATIONS', transitions)
    monkeypatch.setattr(trust, 'bound', bound)
    monkeypatch.setattr(trust, 'load_trust', load)
    if problem:
        with pytest.raises(ArtifactError): workflow.trust_check(None, refs[0])
    else:
        _, _, receipt = workflow.trust_check(None, refs[0])
        assert receipt['review_only_trust_transition'] == {'requested': refs[0], 'effective': refs[2]}
