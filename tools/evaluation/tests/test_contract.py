"""Actual frozen owner-approved packet and disposable adversarial copies."""

import json
import shutil
from pathlib import Path

import pytest

from tools.evaluation.contract import APPROVAL, BENCHMARK, benchmark

ROOT = Path(__file__).resolve().parents[3]


def test_real_owner_receipt_and_frozen_alternatives():
    _, questions, labels = benchmark(ROOT)
    assert len(questions) == 29
    assert sum(bool(x['required_evidence_groups']) for x in labels.values()) == 26
    assert len(labels['M9-Q06']['required_evidence_groups'][0]['alternatives']) == 8
    assert len(labels['M9-Q20']['required_evidence_groups'][0]['alternatives']) == 2
    assert len(labels['M9-Q17']['required_evidence_groups']) == 1
    assert [len(labels['M9-Q'+i]['required_evidence_groups']) for i in ('02','04','13','26')] == [2,3,2,2]


@pytest.mark.parametrize('name', ['BENCHMARK_MANIFEST.json', 'QUESTION_SET.json',
                                 'PROPOSED_EVIDENCE_LABELS.json', 'REVIEW_PACKET.html',
                                 'REVIEW_EVIDENCE.json', 'OWNER_REVIEW_TEMPLATE.json', 'approval'])
def test_altered_reviewed_bytes_or_approval_fail(tmp_path, name):
    base = Path(BENCHMARK).parent
    shutil.copytree(ROOT / base, tmp_path / base)
    (tmp_path / APPROVAL).parent.mkdir(parents=True)
    shutil.copy2(ROOT / APPROVAL, tmp_path / APPROVAL)
    p = tmp_path / APPROVAL if name == 'approval' else tmp_path / base / name
    p.write_bytes(p.read_bytes() + b' ')
    with pytest.raises(ValueError):
        benchmark(tmp_path)


def test_missing_owner_approval_is_not_machine_ground_truth(tmp_path):
    base = Path(BENCHMARK).parent
    shutil.copytree(ROOT / base, tmp_path / base)
    with pytest.raises((ValueError, OSError)):
        benchmark(tmp_path)


def test_original_machine_labels_not_rewritten_as_signed_rows():
    q = json.loads((ROOT / Path(BENCHMARK).parent / 'PROPOSED_EVIDENCE_LABELS.json').read_bytes())
    assert all(x['owner_decision'] is None for x in q['labels'])
    receipt = json.loads((ROOT / APPROVAL).read_bytes())
    assert receipt['status'] == 'OWNER_APPROVED_GROUND_TRUTH'
    assert receipt['no_revisions_or_rejections']
