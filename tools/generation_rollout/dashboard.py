"""Sealed planning observations only. No provider, prompt or runner execution imports."""
from pathlib import Path

from tools.generation_runner.dashboard import discover
from tools.quality_dashboard.artifacts import ArtifactError, Store, digest

BASE = 'data/evals/generation-rollout'


def read_rollout(root):
    paths = sorted((Path(root) / BASE).glob('*/MANIFEST.json'))
    if not paths:
        return None
    path = paths[-1].relative_to(root).as_posix()
    store = Store(root)
    store.manifest(path, schema='grounded-generation-rollout-1.0')
    base = path.rsplit('/', 1)[0]
    summary = store.json(base + '/ROLLOUT.json')
    if (summary.get('generation_authorized') is not False
            or [s['name'] for s in summary['stages']] != ['canary', 'pilot', 'remaining']
            or [len(s['question_ids']) for s in summary['stages']] != [1, 4, 28]
            or len({q for s in summary['stages'] for q in s['question_ids']}) != 33
            or any('M9-Q05' in s['question_ids'] for s in summary['stages'])):
        raise ArtifactError('ROLLOUT_INVENTORY_INVALID')
    for stage in summary['stages']:
        plan = store.json(base + '/' + stage['name'] + '/PLAN.json')
        if (plan['plan_sha256'] != digest({k: v for k, v in plan.items() if k != 'plan_sha256'})
                or stage['plan_sha256'] != plan['plan_sha256']
                or stage['question_ids'] != [q['question_id'] for q in plan['questions']]):
            raise ArtifactError('ROLLOUT_PLAN_BINDING_FAILED')
    return summary, path


def render(st, root):
    st.subheader('Controlled generation rollout — preparation only')
    try:
        result = read_rollout(root)
        if result is None:
            st.info('NOT_RUN — no sealed rollout plan.')
            return
        summary, path = result
        history = discover(root)
        if history['rejected']:
            raise ArtifactError('GENERATION_HISTORY_REQUIRES_REVIEW')
        live = {}
        for run in history['runs']:
            if run['manifest']['mode'] == 'live':
                for row in run['results']['questions']:
                    live[row['question_id']] = row
        rows = []
        for stage in summary['stages']:
            observations = [live.get(q) for q in stage['question_ids']]
            completed = sum(bool(r and r.get('generation_executed') and r.get('response'))
                            for r in observations)
            status = ('COMPLETED_PENDING_REVIEW' if completed == len(observations) else
                      'BLOCKED_OR_PARTIAL' if any(observations) else 'PENDING_OWNER_APPROVAL')
            rows.append({'Stage': stage['name'], 'Questions': len(observations),
                         'Status': status, 'Completed real responses': completed,
                         'Maximum projected USD': stage['maximum_cost_usd']})
        st.dataframe(rows, hide_index=True)
        st.caption('Historical token/cost observations; fresh provider qualification NOT RUN. '
                   'Each stage needs a separate owner decision and completion/spend reconciliation. '
                   'Mock outcomes never authorize or count as live answers.')
        details = []
        for stage in summary['stages']:
            for question in stage['question_readiness']:
                qid = question['question_id']
                row = live.get(qid, {})
                usage = row.get('audit', {}).get('usage', {})
                timed = [r['timings'][qid] for r in history['runs']
                         if r['manifest']['mode'] == 'live' and qid in r.get('timings', {})]
                details.append(question | {'stage': stage['name'],
                    'generation': row.get('status', 'NOT_RUN'),
                    'deterministic_validation': row.get('post_validation', {}).get('overall_status', 'NOT_RUN'),
                    'actual_input_tokens': usage.get('input_tokens'),
                    'actual_output_tokens': usage.get('output_tokens'),
                    'actual_usage_estimated_cost_usd': usage.get('total_estimated_cost_usd'),
                    'end_to_end_ms': timed[-1]['end_to_end_ms'] if timed else None,
                    'stage_timing': 'MEASURED' if timed else 'NOT_MEASURED',
                    'semantic_review': row.get('semantic_status', 'PENDING_REVIEW')})
        st.dataframe(details, hide_index=True)
        st.caption('Verified rollout manifest: ' + path)
        st.caption('Per-question actual tokens, costs, validation and measured latency remain in '
                   'the existing run-history selector below. Independent semantic review remains pending.')
    except (ArtifactError, ValueError, TypeError, KeyError, OSError):
        st.warning('BLOCKED — rollout or generation-history bindings require review.')
