"""Shared read-only question overview. Existing readers remain the authorities."""
from datetime import datetime
from decimal import Decimal
from math import isfinite

import streamlit as st

from tools.benchmark_tracker.adapter import returned_status, selected_attempt
from tools.bot_runtime.projection import discover as load_bots
from tools.bot_runtime.trace_read import discover as traces_for
from tools.quality_dashboard.artifacts import ArtifactError

PHASES = {
    'Context assembly': {'M8_EVIDENCE_ASSEMBLY', 'M8_SOURCE_VALIDATION'},
    'Pre-generation': {'SAVED_INPUT_VERIFICATION', 'PROMPT_ASSEMBLY', 'MODEL_PREFLIGHT',
                       'MODEL_METADATA', 'MODEL_TOKEN_COUNT', 'REQUEST_BINDING_AND_POLICY'},
    'Generation': {'LLM_GENERATION'},
}
MISSING = 'Not measured'
TABLE_HEIGHT = 390


def duration(ms):
    if ms is None:
        return MISSING
    if type(ms) not in {int, float} or not isfinite(ms) or ms < 0:
        raise ValueError('INVALID_SUMMARY_DURATION')
    seconds = ms / 1000
    return f'{seconds:.2f}s' if seconds < 60 else f'{int(seconds // 60)}m {seconds % 60:05.2f}s'


def phase_times(stages):
    """Only exclusive durations; never sum inclusive nested measurements."""
    output = {}
    for phase, names in PHASES.items():
        values = [s['duration_ms'] for s in stages if s['stage'] in names and s.get('duration_ms') is not None]
        output[phase] = sum(values) if values else None
    return output


def other_processing(phases, total):
    """Derived remainder in the same timing scope, not an observed stage."""
    if total is None or any(value is None for value in phases.values()):
        return None
    for value in [total, *phases.values()]:
        if type(value) not in {int, float} or not isfinite(value) or value < 0:
            raise ValueError('INVALID_SUMMARY_DURATION')
    remainder = total - sum(phases.values())
    if remainder < -1:  # Same millisecond accounting tolerance as request_timing.
        raise ValueError('SUMMARY_TIMING_EXCEEDS_REQUEST')
    return max(0.0, remainder)


def trace_stages(events):
    """Partition existing serial trace spans, preserving missing measurements."""
    stack, output = [], []
    for event in events:
        key = (event['stage'], event['operation'])
        if event['status'] == 'RUNNING':
            stack.append([key, 0.0])
        elif event.get('duration_ms') is not None:
            if not stack or stack[-1][0] != key:
                raise ValueError('UNVERIFIED_SUMMARY_TRACE_NESTING')
            _, children = stack.pop()
            inclusive = event['duration_ms']
            exclusive = inclusive - children
            if not isfinite(exclusive) or exclusive < 0:
                raise ValueError('INVALID_SUMMARY_TRACE_DURATION')
            output.append({'stage': event['stage'], 'duration_ms': exclusive})
            if stack:
                stack[-1][1] += inclusive
    if stack:
        raise ValueError('INCOMPLETE_SUMMARY_TRACE')
    return output


def recorded_timing(attempt):
    if attempt.get('native_attempt'):
        return attempt.get('timings')
    if attempt.get('run'):
        return attempt['run'].get('timings', {}).get(attempt['question_id'])
    return attempt.get('timings')


def request_timing(root, record, attempt):
    """Use full Bot dispatch only when it encloses this exact sealed execution.

    Historical benchmark totals retain their recorded runner-only scope. Previous
    local/preflight observations are not silently added to a later independent run.
    """
    timing = recorded_timing(attempt)
    phases = phase_times(timing['stages']) if timing else dict.fromkeys(PHASES)
    total = timing['end_to_end_ms'] if timing else None
    scope = 'runner' if attempt.get('run') or attempt.get('native_attempt') else 'local check'
    chat = record.get('chat_execution') or {}
    native = attempt.get('native_attempt')
    if (native and timing and chat.get('references', {}).get('generation') == attempt.get('manifest_path')):
        observed = traces_for(root, record['question_id'], progress=False)
        expected = {chat['references'][name].rsplit('/', 1)[0] + '/REQUEST_TRACE'
                    for name in ('local', 'qualification')}
        expected.add(native['source']['result_path'].rsplit('/', 1)[0] + '/REQUEST_TRACE')
        relevant = [t for t in observed['traces'] if t['folder'] in expected and t['execution_seal_verified']]
        if {t['folder'] for t in relevant} == expected:
            start = min(datetime.fromisoformat(t['events'][0]['timestamp']) for t in relevant)
            end = max(datetime.fromisoformat(t['events'][-1]['timestamp']) for t in relevant)
            drivers = [t for t in observed['traces'] if t['mode'] == 'chat'
                       and t['observation'] == 'SEALED_DIAGNOSTIC_ONLY'
                       and datetime.fromisoformat(t['events'][0]['timestamp']) <= start
                       and datetime.fromisoformat(t['events'][-1]['timestamp']) >= end]
            if len(drivers) == 1:
                spans = [e for e in drivers[0]['events'] if e['stage'] == 'BACKEND_DISPATCH'
                         and e['status'] == 'COMPLETED' and e.get('duration_ms') is not None]
                if len(spans) == 1:
                    stages = [s for t in relevant for s in trace_stages(t['events'])]
                    phases = phase_times(stages)
                    total, scope = spans[0]['duration_ms'], 'full request'
                    if sum(x for x in phases.values() if x is not None) > total + 1:
                        raise ValueError('SUMMARY_TIMING_EXCEEDS_REQUEST')
    if phases['Generation'] is None:
        usage = attempt.get('usage') or {}
        phases['Generation'] = usage.get('latency_ms')
    return phases, total, scope


def preview(response, rejected=False):
    if rejected:
        return 'Unaccepted response — inspect saved diagnostics'
    if not response:
        return 'No generated answer'
    text = response.get('answer') or ' '.join(response.get('missing_information', []))
    return ' '.join(text.split())[:180] or 'No answer text recorded'


def overview_row(root, qid, record, attempt, *, source, tracked=None):
    base = {'Question': qid + ' — ' + record['question'], 'Source': source,
            'Answer preview': 'No generated answer', 'Execution': 'NOT_RUN', 'Model status': 'NOT_RUN',
            'Technical validation': 'NOT_RUN', 'Human Review': 'NOT_RUN',
            **dict.fromkeys(PHASES, MISSING), 'Other processing': MISSING,
            'Total runtime': MISSING, 'Cost (USD)': None}
    if not attempt:
        return base
    tracked = tracked or {}
    native = attempt.get('native_attempt')
    normalized = native or attempt
    response = normalized.get('response')
    rejected = bool(not response and (normalized.get('row', {}).get('generation_attempted')
                                    or attempt.get('generation_attempted') or attempt.get('generation_executed')))
    status = normalized.get('status', attempt.get('execution_status', 'NOT_RUN'))
    usage = normalized.get('usage') or attempt.get('usage') or {}
    cost = usage.get('total_estimated_cost_usd', attempt.get('cost_usd'))
    model = tracked.get('Model status') or attempt.get('model_status')
    if not model and (native or normalized.get('run')):
        model = returned_status(root, normalized)[0]
    validation = tracked.get('Validation') or attempt.get('validation_status') or (
        normalized.get('validation') or {}).get('overall_status') or 'NOT_RUN'
    owner = tracked.get('Owner review') or attempt.get('owner_review_status') or 'PENDING_REVIEW'
    if not response and not rejected:
        owner = 'NOT_RUN — NO ANSWER'
    elif rejected and owner == 'PENDING_REVIEW':
        owner = 'PENDING_REVIEW — DIAGNOSTICS'
    if cost is not None and (not Decimal(cost).is_finite() or Decimal(cost) < 0):
        raise ValueError('INVALID_SUMMARY_COST')
    if attempt.get('mode') == 'mock':
        status, owner, cost = 'MOCK — ' + status, 'SIMULATION — NOT ELIGIBLE', None
    if record.get('disposition') == 'DISCARDED':
        status = 'DISCARDED — ' + status
    phases, total, scope = request_timing(root, record, attempt)
    base.update({'Answer preview': preview(response, rejected), 'Execution': status,
                 'Model status': model or (response or {}).get('status') or 'NOT_RUN',
                 'Technical validation': validation, 'Human Review': owner,
                 **{k: duration(v) for k,v in phases.items()},
                 'Other processing': duration(other_processing(phases, total)),
                 'Total runtime': duration(total) + (' · ' + scope if total is not None else ''),
                 'Cost (USD)': float(Decimal(cost)) if cost is not None else None})
    return base


def rows(root, data, tracker, bots):
    output, unavailable = [], 0
    tracked = {r['Question']: r for r in tracker['rows']}
    for source, records in [('Benchmark', data['records']), ('Bot', bots['records'])]:
        for qid, record in records.items():
            attempt = selected_attempt(record) if source == 'Benchmark' else next(
                reversed(record['attempts']), None)
            try:
                row = overview_row(root, qid, record, attempt, source=source, tracked=tracked.get(qid))
            except (ArtifactError, OSError, ValueError, TypeError, KeyError):
                # Keep the question visible. Unverified data never becomes a pass/zero.
                row = overview_row(root, qid, record, None, source=source)
                row.update(Execution='UNAVAILABLE — UNVERIFIED', **{'Technical validation': 'UNVERIFIED',
                            'Human Review': 'UNVERIFIED'})
                unavailable += 1
            output.append(row)
    return output, unavailable


def render(root, *, loader, key):
    """First, scrollable table on both pages; return existing data for detail views."""
    st.subheader('All questions — current outcomes and runtime')
    try:
        data, tracker = loader()
        bots = load_bots(root)
        values, unavailable = rows(root, data, tracker, bots)
        if bots['rejected'] or unavailable:
            st.warning('Some records or timing bindings could not be verified. No acceptance or zero cost is inferred.')
        with st.container(horizontal=True):
            source = st.selectbox('Summary source', ['All questions', 'Benchmark', 'Bot'], key=key+'-source')
            options = sorted({v['Execution'] for v in values})
            statuses = st.multiselect('Summary execution status', options, key=key+'-status')
        filtered = [{k:v for k,v in row.items() if k != 'Source'} for row in values
                    if (source == 'All questions' or row['Source'] == source)
                    and (not statuses or row['Execution'] in statuses)]
        st.dataframe(filtered, hide_index=True, width='stretch', height=TABLE_HEIGHT, row_height=35,
            column_config={
                'Question': st.column_config.TextColumn(width='large', pinned=True),
                'Answer preview': st.column_config.TextColumn(width='large'),
                'Model status': st.column_config.TextColumn(help='The model’s declaration, including unaccepted responses; not independent answer-quality acceptance.'),
                'Cost (USD)': st.column_config.NumberColumn(format='%.6f', help='Calculated from actual token usage and recorded pricing; may differ from final billing. Missing cost is unavailable, not zero.'),
                'Other processing': st.column_config.TextColumn(help='Derived: total runtime minus context assembly, pre-generation and generation, within the same timing scope. Includes omitted processing and unattributed time; not a separately measured stage. Unavailable when a required timing is missing.'),
                'Total runtime': st.column_config.TextColumn(help='Full Bot request when a matching sealed dispatch is available. Runner/local-check labels identify narrower historical measurements.'),
                **{name:st.column_config.TextColumn(help='Recorded exclusive work only; nested durations are not counted twice. Generation is local request elapsed time, not independently measured model inference.') for name in PHASES},
            }, key=key+'-table')
        st.caption(f'{len(filtered)} of {len(values)} questions · About 10 rows visible; scroll vertically for more and horizontally for additional columns. Use the existing question selector below for full details and attempt history.')
        st.caption('Other processing = total runtime minus the three displayed stages; it includes omitted processing and unattributed time, not an independently measured stage. Values are rounded. Historical runner/local-check totals have narrower scope; missing timings are not estimated. Cost is for the displayed attempt, not all historical retries.')
        return data, tracker, bots
    except (ArtifactError, OSError, ValueError, KeyError, TypeError):
        st.warning('Question summary unavailable: saved records failed verification. Existing detail views remain available.')
        return None
