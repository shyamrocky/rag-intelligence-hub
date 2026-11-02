"""Durable admission, exclusive attempts and fail-closed offline adapters."""
import json
import os
from decimal import Decimal
from pathlib import Path

from tools.generation.openai_adapter import ProviderError
from tools.preflight_suite.artifacts import now, save
from tools.quality_dashboard.artifacts import digest


def durable(path, value):
    save(path, value)
    with Path(path).open('rb') as stream:
        os.fsync(stream.fileno())
    fd = os.open(Path(path).parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class Budget:
    """Serial, conservative reservations. Failures never release estimated spend."""
    def __init__(self, run, plan):
        self.run = Path(run)
        self.cap = Decimal(plan['aggregate_cap_usd'])
        self.rows = {r['question_id']: r for r in plan['questions']}
        self.reserved = Decimal(0)
        self.attempted = set()

    def admit(self, qid, cost, request_hash, *, mode):
        if mode not in {'live', 'mock'}:
            raise ValueError('ATTEMPT_MODE_INVALID')
        row = self.rows[qid]
        cost = Decimal(cost)
        if (not cost.is_finite() or cost <= 0
                or cost > Decimal(row['per_question_cap_usd'])
                or cost > Decimal(row['maximum_cost_usd'])
                or self.reserved + cost > self.cap):
            raise ProviderError('COST_CAP_EXCEEDED_NO_SEND')
        if qid in self.attempted or request_hash != row['request_sha256']:
            raise ProviderError('DUPLICATE_OR_CHANGED_REQUEST_NO_SEND')
        filename = 'LIVE_ATTEMPT.json' if mode == 'live' else 'MOCK_ATTEMPT.json'
        durable(self.run / 'questions' / qid / filename,
                {'question_id': qid, 'request_sha256': request_hash, 'reserved_usd': str(cost),
                 'aggregate_reserved_after_usd': str(self.reserved + cost), 'created_at': now(),
                 'mode': mode, 'no_retry_even_if_outcome_unknown': True})
        self.attempted.add(qid)
        self.reserved += cost


class OfflineAdapter:
    """No SDK/client/credential/socket path. Owned fixtures only, never provider calls."""
    def __init__(self, row, *, mode='dry-run', scenario='success', request=None,
                 settings=None, pricing=None, day=None, budget=None, answer=None, capture_sink=None):
        self.row, self.mode, self.scenario = row, mode, scenario
        self.request, self.settings, self.pricing, self.day = request, settings, pricing, day
        self.budget, self.answer = budget, answer
        self.calls = []
        self.capture_sink, self.last_capture = capture_sink, None

    def configuration_error(self):
        return None

    def _mock_only(self, operation):
        if self.mode != 'mock':
            raise ProviderError('ALL_PROVIDER_OPERATIONS_DENIED_IN_DRY_RUN')
        if operation in self.calls:
            raise ProviderError('NO_RETRY')
        self.calls.append(operation)

    def verify_model(self, model):
        self._mock_only('metadata')
        if model != self.settings.model:
            raise ProviderError('MOCK_MODEL_MISMATCH')
        return {'status': 'ACCOUNT_MODEL_ACCESS_VERIFIED', 'measurement': 'OWNED_MOCK'}

    def count(self, request):
        self._mock_only('count')
        if digest(request) != self.row['request_sha256']:
            raise ProviderError('MOCK_REQUEST_HASH_MISMATCH')
        return {'input_tokens': self.row['input_tokens'], 'request_sha256': digest(request),
                'method': 'SEALED_COUNT_REPLAY_NOT_NEW_MEASUREMENT'}

    def invoke(self, request):
        from tools.generation.telemetry import capture_usage, estimate_max_cost

        self._mock_only('generation')
        estimate = estimate_max_cost(self.settings.model, self.row['input_tokens'],
            self.settings.max_output_tokens, self.pricing, tier=self.settings.service_tier,
            region=self.settings.region, as_of=self.day)
        if estimate['status'] != 'ESTIMATED_MAX_API_COST':
            raise ProviderError('COST_UNAVAILABLE_NO_SEND')
        self.budget.admit(self.row['question_id'], estimate['estimated_max_cost_usd'],
                          digest(request), mode='mock')
        if self.scenario == 'api-failure':
            if self.capture_sink:
                self.last_capture = self.capture_sink.capture(None, unavailable_reason='OWNED_MOCK_NO_RESPONSE')
            raise ProviderError('OWNED_MOCK_PROVIDER_FAILURE_NO_RETRY', capture=self.last_capture)
        answer = self.answer or {'status': 'ABSTAINED', 'answer': '', 'claims': [],
            'missing_information': ['Owned mock control; no factual answer was generated.'],
            'relevant_qualifications': [], 'requirement_coverage': [], 'conflicts_detected': []}
        raw = {'id': 'owned_mock_' + self.row['question_id'], 'model': self.settings.model,
               'status': 'completed', 'service_tier': self.settings.service_tier,
               'output': [{'type': 'message', 'content': [{'type': 'output_text',
                    'text': '{}' if self.scenario == 'schema-error' else json.dumps(answer)}]}],
               'usage': {'input_tokens': self.row['input_tokens'], 'output_tokens': 10,
                        'total_tokens': self.row['input_tokens'] + 10,
                        'input_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0,
                            'cache_write_tokens_details': {'ttl_30m_tokens': 0, 'ttl_12h_tokens': 0}},
                        'output_tokens_details': {'reasoning_tokens': 0}}}
        if self.capture_sink:
            self.last_capture = self.capture_sink.capture(json.dumps(raw).encode(), http_status=200)
        usage = capture_usage(raw, self.settings.model, 0.0)
        if self.last_capture and self.last_capture['status'] == 'RAW_RESPONSE_CAPTURE_FAILED':
            raise ProviderError('RAW_RESPONSE_CAPTURE_FAILED', capture=self.last_capture, usage=usage)
        return raw, usage
