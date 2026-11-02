"""Read-only sealed run discovery; no runner, provider or request construction imports."""
from pathlib import Path

from tools.quality_dashboard.artifacts import ArtifactError, Store, digest

from .plan import BASE, VERSION
from .timing import validate_timing


def discover(root):
    runs, rejected = [], []
    for path in sorted((Path(root) / BASE).glob('*/MANIFEST.json')):
        try:
            store = Store(root)
            name = path.relative_to(root).as_posix()
            manifest = store.manifest(name, schema=VERSION)
            if (manifest['status'] != 'SEALED_PENDING_OWNER_REVIEW'
                    or manifest['mode'] not in {'dry-run', 'mock', 'live'}):
                raise ArtifactError('INVALID_RUN')
            base = name.rsplit('/', 1)[0]
            result, plan = store.json(base + '/RESULTS.json'), store.json(base + '/PLAN.json')
            if (plan['plan_sha256'] != digest({k: v for k, v in plan.items() if k != 'plan_sha256'})
                    or manifest['plan_sha256'] != plan['plan_sha256']
                    or [q['question_id'] for q in result['questions']] != manifest['question_ids']
                    or result['mode'] != manifest['mode']
                    or any(q['mode'] != manifest['mode'] for q in result['questions'])
                    or 'M9-Q05' in manifest['question_ids']):
                raise ArtifactError('RUN_IDENTITY_MISMATCH')
            for row in result['questions']:
                qid = row['question_id']
                if store.json(base + f'/questions/{qid}/RESULT.json') != row:
                    raise ArtifactError('QUESTION_RESULT_MISMATCH')
                if manifest['mode'] != 'live' and (row['provider_calls'] or row['generation_executed']):
                    raise ArtifactError('OFFLINE_RUN_CONTAINS_PROVIDER_CALLS')
            timings = {}
            for row in result['questions']:
                qid = row['question_id']
                expected = f'questions/{qid}/STAGE_TIMINGS.json'
                if 'stage_timings' not in row:
                    if expected in manifest['files']:
                        raise ArtifactError('UNREFERENCED_TIMING_RECEIPT')
                    continue  # Historical NOT_MEASURED, never inferred from another run.
                if row['stage_timings'] != expected or expected not in manifest['files']:
                    raise ArtifactError('UNSEALED_TIMING_RECEIPT')
                timing = validate_timing(store.json(base + '/' + expected), question_id=qid,
                    run_id=manifest['run_id'], mode=manifest['mode'], request_sha256=row['request_sha256'])
                if timing['M8_package_sha256'] != row['M8_package_sha256']:
                    raise ArtifactError('TIMING_PACKAGE_MISMATCH')
                seal_name = f'questions/{qid}/QUESTION_RESULT_MANIFEST.json'
                seal = store.json(base + '/' + seal_name)
                if (seal['question_id'] != qid or seal['run_id'] != manifest['run_id']
                        or seal['files'].get('RESULT.json') != manifest['files'][f'questions/{qid}/RESULT.json']):
                    raise ArtifactError('TIMING_RESULT_SEAL_MISMATCH')
                timings[qid] = timing
            # Preserve history even if a future implementation changes: never execute from this reader.
            runs.append({'manifest': manifest, 'results': result, 'plan': plan, 'manifest_path': name,
                         'timings': timings})
        except (ArtifactError, ValueError, TypeError, KeyError, OSError):
            rejected.append({'run_id': path.parent.name, 'status': 'UNAVAILABLE'})
    return {'runs': runs, 'rejected': rejected}


def render_latency(st, run, qid):
    """Only sealed source-free receipts. Exclusive totals, not overlapping wall spans."""
    st.subheader('Execution Latency Breakdown')
    timing = run.get('timings', {}).get(qid) if run else None
    if timing is None:
        st.info('NOT_MEASURED — this historical question result has no stage-timing receipt.')
        return
    st.caption(f"{timing['mode']} · {timing['generation_label']} · run {timing['run_id']}")
    st.metric('Question end-to-end elapsed', f"{timing['end_to_end_ms']:,.2f} ms")
    rows = [{'Stage': s['stage'], 'Status': s['status'], 'Exclusive ms': s['duration_ms'],
             'Calls': s['calls']} for s in timing['stages']]
    st.dataframe(rows, hide_index=True)
    measured = [s for s in timing['stages'] if s['duration_ms'] is not None]
    if measured and timing['end_to_end_ms'] > 0:
        slowest = max(measured, key=lambda s: s['duration_ms'])
        st.caption(f"Slowest measured stage: {slowest['stage']} — "
                   f"{100 * slowest['duration_ms'] / timing['end_to_end_ms']:.1f}% of elapsed time.")
    st.caption('Exclusive times avoid double-counting nested calls. M8 validation performs additional '
               'reconstruction, shown in the nested spans. Mock metadata/count replay historical '
               'observations; their durations measure local replay only. Provider-reported inference '
               'latency is unavailable; local adapter duration is recorded separately.')
    with st.expander('Technical Details — stage timing'):
        import json
        st.caption(timing['scope'])
        base = run['manifest_path'].rsplit('/', 1)[0]
        relative = f'questions/{qid}/STAGE_TIMINGS.json'
        st.text('Sealed receipt: ' + base + '/' + relative)
        st.text('Experiment manifest: ' + run['manifest_path'])
        st.text('Receipt SHA-256: ' + run['manifest']['files'][relative])
        st.download_button('Download source-free timing receipt',
            json.dumps(timing, sort_keys=True, indent=2), file_name=f'{qid}-STAGE_TIMINGS.json',
            mime='application/json', key='timing-' + timing['run_id'] + '-' + qid)
        st.json(timing)


def compact_latency(st, root, qid):
    """Question view: show latest runner observation, explicitly separate from real answers."""
    history = discover(root)
    matching = [run for run in history['runs'] if qid in run['manifest']['question_ids']]
    run = matching[-1] if matching else None
    st.caption('Latest runner execution observation; MOCK timing is separate from real generation telemetry.')
    render_latency(st, run, qid)
    available = sorted({question for item in history['runs'] for question in item.get('timings', {})})
    if available:
        st.caption('Measured stage timings available for: ' + ', '.join(available))
        if qid not in available:
            target = available[0]

            def select_measured_question():
                # Navigation only: callbacks run before the next widget construction.
                st.session_state.update(expanded_cohort='All Questions',
                    expanded_generation_filter='All', expanded_evaluation_filter='All',
                    expanded_answerability='All', expanded_question=target)

            st.button('Show measured stage timings: ' + target,
                      on_click=select_measured_question, key='show-measured-stage-timings')


def render(st, root, data):
    st.title('Grounded Generation Runner')
    st.warning('Generation execution is disabled in this dashboard. Human Review supports explicit local POC '
               'or advanced signed decisions; neither grants generation permission.')
    from tools.human_review.poc_ui import render as render_review
    with st.expander('Generation Runner → Human Review', expanded=True):
        render_review(st, root)
    telemetry = discover(root)
    st.session_state['generation_runner_telemetry'] = telemetry
    if not telemetry['runs']:
        st.info('NOT_RUN — no sealed runner records available.')
        return
    chosen = st.selectbox('Generation runner run', range(len(telemetry['runs'])),
                          index=len(telemetry['runs']) - 1,
                          format_func=lambda i: telemetry['runs'][i]['manifest']['run_id'])
    run = telemetry['runs'][chosen]
    st.caption('Mode: ' + run['manifest']['mode'] + ' — mock results never count as benchmark generation.')
    plan, results = run['plan'], run['results']
    st.subheader('Configuration and execution readiness')
    st.json({k: plan[k] for k in ['model', 'prompt_version', 'response_schema', 'pricing_version',
            'aggregate_cap_usd', 'aggregate_maximum_estimated_cost_usd', 'expected_future_calls']})
    st.caption('Saved qualification is a historical observation. Live runs reassemble M8, compare exact '
               'request hashes, refresh model access/token count/context/cost, and reserve cost before sending.')
    st.dataframe([{k: q.get(k) for k in ['question_id', 'cohort_id', 'input_tokens',
        'maximum_cost_usd', 'per_question_cap_usd', 'readiness', 'request_sha256']}
        for q in plan['questions']], hide_index=True)
    st.subheader('Mock tests / future run history')
    st.json({k: v for k, v in results.items() if k != 'questions'})
    ids = [q['question_id'] for q in results['questions']]
    if ids:
        qid = st.selectbox('Generation runner question', ids,
            index=ids.index(st.session_state.get('expanded_question'))
            if st.session_state.get('expanded_question') in ids else 0)
        st.session_state['expanded_question'] = qid
        st.caption(data['records'][qid]['reference']['cohort_label'])
        row = next(q for q in results['questions'] if q['question_id'] == qid)
        st.json({k: row.get(k) for k in ['status', 'fixture_only', 'provider_calls',
                 'generation_executed', 'source_integrity', 'included_parents', 'evidence_BGE_tokens',
                 'semantic_status', 'request_sha256']})
        if row.get('audit'):
            st.json({'usage': row['audit'].get('usage'), 'blocking_reasons': row['audit'].get('blocking_reasons')})
        if row.get('response'):
            from tools.answer_quality.abstention import render_response
            render_response(st, row['response'])
            st.json({k: row['response'][k] for k in ['status', 'missing_information', 'relevant_qualifications']})
        if row.get('post_validation'):
            post = row['post_validation']
            st.json({k: post.get(k) for k in ['overall_status', 'structural_validation',
                'qualification_status', 'semantic_status', 'fully_validated']})
        from tools.answer_quality.reporting import render as render_quality
        render_quality(st, root, row)
        render_latency(st, run, qid)
    st.caption('Verified manifest: ' + run['manifest_path'])
    st.code('PYTHONPATH=. tools/generation/.venv/bin/python -m tools.generation_runner dry-run --pending-generation')
    st.code('PYTHONPATH=. tools/generation/.venv/bin/python -m tools.generation_runner mock --question M9-Q01')
    if telemetry['rejected']:
        st.warning(f"{len(telemetry['rejected'])} malformed or unsealed runs excluded.")
