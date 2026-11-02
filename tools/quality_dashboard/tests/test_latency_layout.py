"""Layout composition reuses historical code without changing shared globals."""
from types import SimpleNamespace

from tools.quality_dashboard import latency_ui


def pipeline(data, row, attempt):
    data['calls'].append(('historical-pipeline', row['question_id'], attempt))


def layout(data):
    pipeline(data, data, None)


def test_isolated_pipeline_composition_and_historical_behavior(monkeypatch):
    original_globals = dict(layout.__globals__)
    fake = SimpleNamespace(quality=layout, pipeline=pipeline, st=object())
    calls = []
    monkeypatch.setattr(latency_ui, 'coverage_ui', fake)
    monkeypatch.setattr(latency_ui, 'compact_latency',
        lambda st, root, qid: calls.append((st, root, qid)))
    data = {'question_id': 'owned-question', 'calls': []}
    latency_ui.quality(data, root='owned-root')
    assert calls == [(fake.st, 'owned-root', 'owned-question')]
    assert data['calls'] == [('historical-pipeline', 'owned-question', None)]
    assert layout.__globals__ == original_globals
    assert fake.pipeline is pipeline and fake.quality is layout
    layout(data)
    assert len(calls) == 1  # Historical entry still renders without the extension.
    assert len(data['calls']) == 2
