"""Source-free, serial, nested monotonic spans; observers never repeat an operation."""
from contextlib import contextmanager
from datetime import UTC, datetime
from functools import wraps
from math import isclose, isfinite
from time import perf_counter_ns

VERSION = 'grounded-generation-stage-timings-1.0'
STAGES = (
    'SAVED_INPUT_VERIFICATION', 'M8_EVIDENCE_ASSEMBLY', 'M8_SOURCE_VALIDATION',
    'PROMPT_ASSEMBLY', 'MODEL_PREFLIGHT', 'MODEL_METADATA', 'MODEL_TOKEN_COUNT',
    'LLM_GENERATION', 'POST_GENERATION_VALIDATION', 'ARTIFACT_PERSISTENCE',
    'REQUEST_BINDING_AND_POLICY', 'GENERATION_SERVICE_OVERHEAD', 'FINAL_SOURCE_CHECK',
)
SCOPE = ('Question entry through RESULT/local-audit writes and QUESTION_RESULT_MANIFEST sealing. '
         'Excludes shared run setup/planning, timing-receipt publication and shared final run sealing.')


class StageTimer:
    def __init__(self, question_id, run_id, mode, *, clock=perf_counter_ns):
        self.question_id, self.run_id, self.mode = question_id, run_id, mode.upper()
        self.clock, self.start = clock, clock()
        self.started_at = datetime.now(UTC).isoformat()
        self.events, self.stack = [], []
        self.error_stage = None

    @contextmanager
    def span(self, stage):
        if stage not in STAGES:
            raise ValueError('UNKNOWN_TIMING_STAGE')
        event = {'stage': stage, 'parent': self.stack[-1] if self.stack else None,
                 'start_ns': self.clock() - self.start, 'status': 'MEASURED', 'children_ns': 0}
        index = len(self.events)
        self.events.append(event)
        self.stack.append(index)
        try:
            yield
        except BaseException:  # Preserve partial timings, never exception text/arguments.
            event['status'] = 'FAILED'
            if self.error_stage is None:
                self.error_stage = stage
            raise
        finally:
            event['end_ns'] = self.clock() - self.start
            elapsed = event['end_ns'] - event['start_ns']
            event['duration_ms'] = elapsed / 1_000_000
            event['exclusive_ms'] = (elapsed - event.pop('children_ns')) / 1_000_000
            self.stack.pop()
            if self.stack:
                self.events[self.stack[-1]]['children_ns'] += elapsed

    @contextmanager
    def observe(self, owner, method, stage):
        """Temporarily observe an existing bound method; same arguments/result/exceptions.

        Instance-local except the already serial preparation helper's imported
        validate_candidates function. Always restore the original attribute.
        """
        original = getattr(owner, method)
        own = method in vars(owner)
        previous = vars(owner).get(method)

        @wraps(original)
        def measured(*args, **kwargs):
            with self.span(stage):
                return original(*args, **kwargs)

        setattr(owner, method, measured)
        try:
            yield
        finally:
            if own:
                setattr(owner, method, previous)
            else:
                delattr(owner, method)

    def finish(self, *, request_sha256, package_sha256, usage=None):
        if self.stack:
            raise ValueError('OPEN_TIMING_SPAN')
        end = self.clock()
        total = (end - self.start) / 1_000_000
        stages = []
        for name in STAGES:
            events = [e for e in self.events if e['stage'] == name]
            stages.append({'stage': name,
                'status': 'FAILED' if any(e['status'] == 'FAILED' for e in events)
                          else 'MEASURED' if events else 'SKIPPED',
                'calls': len(events),
                'duration_ms': sum(e['exclusive_ms'] for e in events) if events else None,
                'inclusive_ms': sum(e['duration_ms'] for e in events) if events else None})
        accounted = sum(s['duration_ms'] or 0 for s in stages)
        value = {'schema': VERSION, 'question_id': self.question_id, 'run_id': self.run_id,
            'mode': self.mode, 'clock': 'time.perf_counter_ns', 'unit': 'milliseconds',
            'started_at': self.started_at, 'ended_at': datetime.now(UTC).isoformat(),
            'scope': SCOPE, 'end_to_end_ms': total, 'stages': stages, 'spans': self.events,
            'unattributed_overhead_ms': total - accounted, 'error_stage': self.error_stage,
            'request_sha256': request_sha256, 'M8_package_sha256': package_sha256,
            'generation_label': 'MOCK_ADAPTER_DURATION' if self.mode == 'MOCK'
                                else 'LOCAL_PROVIDER_REQUEST_DURATION',
            'preflight_observation': 'REUSED_HISTORICAL' if self.mode == 'MOCK' else 'MEASURED',
            'provider_reported_latency_ms': None,
            'provider_reported_latency_status': 'UNAVAILABLE',
            'existing_usage_latency_ms': (usage or {}).get('latency_ms'),
            'existing_usage_latency_kind': 'MOCK_SYNTHETIC' if self.mode == 'MOCK'
                                            else 'ADAPTER_LOCAL_HTTP_DURATION',
            'measurement_semantics': 'Exclusive stage totals partition elapsed time. Inclusive spans '
                'overlap and MUST NOT be summed. M8 validation reassemblies remain visible as nested spans.'}
        validate_timing(value)
        return value


def validate_timing(value, *, question_id=None, run_id=None, mode=None, request_sha256=None):
    """Reject malformed/tampered accounting before showing a sealed sidecar."""
    fields = {'schema', 'question_id', 'run_id', 'mode', 'clock', 'unit', 'started_at', 'ended_at',
        'scope', 'end_to_end_ms', 'stages', 'spans', 'unattributed_overhead_ms', 'error_stage',
        'request_sha256', 'M8_package_sha256', 'generation_label', 'preflight_observation',
        'provider_reported_latency_ms', 'provider_reported_latency_status',
        'existing_usage_latency_ms', 'existing_usage_latency_kind', 'measurement_semantics'}
    if (set(value) != fields or value['schema'] != VERSION
            or value['mode'] not in {'MOCK', 'LIVE', 'DRY-RUN'}
            or value['clock'] != 'time.perf_counter_ns' or value['unit'] != 'milliseconds'
            or value['scope'] != SCOPE or value['error_stage'] not in (*STAGES, None)
            or (question_id is not None and value['question_id'] != question_id)
            or (run_id is not None and value['run_id'] != run_id)
            or (mode is not None and value['mode'] != mode.upper())
            or (request_sha256 is not None and value['request_sha256'] != request_sha256)
            or [s['stage'] for s in value['stages']] != list(STAGES)):
        raise ValueError('INVALID_TIMING_IDENTITY')
    expected_label = 'MOCK_ADAPTER_DURATION' if value['mode'] == 'MOCK' else 'LOCAL_PROVIDER_REQUEST_DURATION'
    if value['generation_label'] != expected_label:
        raise ValueError('INVALID_TIMING_SEMANTICS')
    def number(n):
        return type(n) in {int, float} and isfinite(n) and n >= 0
    total, overhead = value['end_to_end_ms'], value['unattributed_overhead_ms']
    if not number(total) or not number(overhead):
        raise ValueError('INVALID_TIMING_DURATION')
    spans = value['spans']
    for i, event in enumerate(spans):
        if (set(event) != {'stage', 'parent', 'start_ns', 'end_ns', 'status', 'duration_ms', 'exclusive_ms'}
                or event['stage'] not in STAGES or event['status'] not in {'MEASURED', 'FAILED'}
                or not all(type(event[k]) is int for k in ('start_ns', 'end_ns'))
                or not 0 <= event['start_ns'] <= event['end_ns'] <= total * 1_000_000 + 1
                or not number(event['duration_ms']) or not number(event['exclusive_ms'])):
            raise ValueError('INVALID_TIMING_SPAN')
        parent = event['parent']
        if parent is not None and (type(parent) is not int or not 0 <= parent < i
                or not spans[parent]['start_ns'] <= event['start_ns'] <= event['end_ns'] <= spans[parent]['end_ns']):
            raise ValueError('INVALID_TIMING_PARENT')
        siblings = [e for e in spans[:i] if e['parent'] == parent]
        if siblings and siblings[-1]['end_ns'] > event['start_ns']:
            raise ValueError('OVERLAPPING_TIMING_SIBLINGS')
        children = sum(e['end_ns'] - e['start_ns'] for e in spans if e['parent'] == i)
        if (not isclose(event['duration_ms'], (event['end_ns'] - event['start_ns']) / 1e6, abs_tol=1e-6)
                or not isclose(event['exclusive_ms'], event['duration_ms'] - children / 1e6, abs_tol=1e-6)):
            raise ValueError('INVALID_TIMING_EXCLUSIVE_ACCOUNTING')
    for stage in value['stages']:
        if set(stage) != {'stage', 'status', 'calls', 'duration_ms', 'inclusive_ms'}:
            raise ValueError('INVALID_TIMING_STAGE_FIELDS')
        events = [e for e in spans if e['stage'] == stage['stage']]
        expected = 'FAILED' if any(e['status'] == 'FAILED' for e in events) else 'MEASURED' if events else 'SKIPPED'
        if stage['status'] != expected or stage['calls'] != len(events):
            raise ValueError('INVALID_TIMING_STAGE_STATUS')
        for field, span_field in [('duration_ms', 'exclusive_ms'), ('inclusive_ms', 'duration_ms')]:
            actual = stage[field]
            if ((not events and actual is not None) or (events and (not number(actual)
                    or not isclose(actual, sum(e[span_field] for e in events), abs_tol=1e-6)))):
                raise ValueError('INVALID_TIMING_STAGE_TOTAL')
    if not isclose(sum(s['duration_ms'] or 0 for s in value['stages']) + overhead, total, abs_tol=1e-6):
        raise ValueError('INVALID_TIMING_TOTAL')
    return value
