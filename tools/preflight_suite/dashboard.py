"""Source-free, read-only discovery. This module never imports the suite runner."""
from pathlib import Path

from tools.pre_generation_gate.current import DEFAULT_TEMPLATE_VERSION
from tools.quality_dashboard.artifacts import ArtifactError, sha

from .artifacts import BASE, read_run


def discover(root):
    runs, rejected = [], []
    for path in sorted((Path(root) / BASE).glob('*/MANIFEST.json')):
        name = path.relative_to(root).as_posix()
        try:
            manifest, results, _ = read_run(root, name)
            runs.append({'manifest': manifest, 'results': results, 'manifest_sha256': sha(path),
                         'manifest_path': name})
        except (ArtifactError, ValueError, TypeError, KeyError, OSError):
            rejected.append({'run_id': path.parent.name, 'status': 'UNAVAILABLE',
                             'reason': 'UNSEALED_OR_INCOMPATIBLE_RUN'})
    return {'runs': runs, 'rejected': rejected}


def compact(st, telemetry, qid):
    st.subheader('Pre-Generation Readiness — RAG Preflight Suite')
    records = [(run['manifest']['run_id'], run['manifest']['mode'], row)
               for run in telemetry['runs'] for row in run['results']['questions']
               if row['question_id'] == qid]
    if not records:
        st.info('NOT_RUN — no sealed preflight run for this question.')
        return
    st.dataframe([{'Run': name, 'Mode': mode, 'Status': r['status'],
                   'Prompt': r['prompt_version'], 'Request hash': r['request_sha256'],
                   'Exact input tokens': r['input_tokens'],
                   'Maximum estimated USD': r['maximum_cost_usd']}
                  for name, mode, r in records], hide_index=True)
    st.caption('Local assembly is not model qualification; qualification never authorizes generation.')
    st.caption('Current experimental prompt: ' + DEFAULT_TEMPLATE_VERSION +
               '. Historical request qualifications do not qualify a changed prompt.')


def suite(st, root, data, telemetry):
    st.title('RAG Preflight Suite')
    st.caption('Local Evidence & Prompt Check · Model Token & Cost Preflight · read-only run history')
    runs = telemetry['runs']
    st.write(f"Available benchmark questions: {len(data['records'])}")
    if not runs:
        st.info('NOT_RUN — no completed sealed preflight executions available.')
        return
    chosen = st.selectbox('Preflight run', list(range(len(runs))), index=len(runs) - 1,
                          format_func=lambda i: runs[i]['manifest']['run_id'])
    run = runs[chosen]
    manifest, result = run['manifest'], run['results']
    st.caption('Latest sealed run: ' + runs[-1]['manifest']['run_id'])
    st.json(result['summary'])
    st.dataframe([{'Cohort': c, **s} for c, s in result['cohorts'].items()], hide_index=True)
    with st.expander('Test configuration and provenance', expanded=False):
        st.json(manifest['configuration'])
        versions = sorted({r['prompt_version'] for r in result['questions']})
        st.text('Recorded prompt: ' + ', '.join(versions) + ' / response grounded-response-2.0')
        st.text('OpenAI / gpt-6-luna · output reservation 4096 · safety margin 1024')
        st.text('Benchmark manifest SHA-256: ' + manifest['expanded_benchmark_manifest_sha256'])
        st.text('Run manifest: ' + run['manifest_path'])
        st.text('Run manifest SHA-256: ' + run['manifest_sha256'])
    st.subheader('Execution transparency')
    st.write('M7 input verification → M8 live assembly/validation → Versioned prompt assembly → Model token/context/cost qualification')
    st.text('Entry point: python -m tools.preflight_suite')
    st.text('Existing public modules: EvidenceService.assemble / validate; PromptAssemblyGate.prepare; GenerationService.dry_run')
    if manifest['mode'] == 'local-check':
        st.info('Provider stages SKIPPED. No external evidence transfer; no model qualification.')
    else:
        st.info('Provider metadata and input-token counts only. Generation endpoints denied; no retries.')
    keys = ['question_id', 'cohort_id', 'status', 'included_parents', 'omitted_parents',
            'evidence_BGE_tokens', 'input_tokens', 'maximum_cost_usd', 'provider_calls']
    st.dataframe([{k: r.get(k) for k in keys} for r in result['questions']], hide_index=True)
    ids = [r['question_id'] for r in result['questions']]
    qid = st.selectbox('Preflight question', ids,
                        index=ids.index(st.session_state.get('expanded_question'))
                        if st.session_state.get('expanded_question') in ids else 0)
    st.session_state['expanded_question'] = qid
    row = next(r for r in result['questions'] if r['question_id'] == qid)
    st.caption(data['records'][qid]['reference']['cohort_label'])
    st.text(data['records'][qid]['question'])
    st.json({k: row.get(k) for k in ['status', 'M7_result_sha256', 'M8_package_sha256',
             'request_sha256', 'prompt_version', 'schema_version', 'model', 'pricing_version',
             'included_parents', 'omitted_parents', 'evidence_BGE_tokens', 'input_tokens',
             'context_fit', 'reserved_output_tokens', 'safety_margin_tokens', 'maximum_cost_usd',
             'blocking_reasons', 'provider_calls']})
    compact(st, telemetry, qid)
    st.subheader('Documented CLI — execution requires separate explicit authorization')
    st.code('PYTHONPATH=. tools/generation/.venv/bin/python -m tools.preflight_suite local-check --question ' + qid)
    st.code('PYTHONPATH=. tools/generation/.venv/bin/python -m tools.preflight_suite model-preflight --question '
            + qid + ' --local-manifest <sealed-local-run>/MANIFEST.json --authorize-transfer <owner-authorization-reference>')
    st.warning('No execution controls are active. Refresh, navigation and selection never run the suite. '
               'Exact token counts are provider observations; projected cost is not an invoice or balance. '
               'A qualified package must be freshly revalidated before any separately authorized generation.')
    if telemetry['rejected']:
        st.warning(f"{len(telemetry['rejected'])} incompatible preflight publications excluded")
