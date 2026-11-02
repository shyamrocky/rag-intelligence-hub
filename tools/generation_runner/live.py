"""Future explicit-owner execution only. This module is never imported offline or by UI."""
import json
import logging
import os

import httpx

from tools.generation.openai_adapter import OpenAIAdapter, ProviderError
from tools.generation.response_capture import ResponseCapture
from tools.generation.telemetry import estimate_max_cost
from tools.preflight_suite.provider import load_key
from tools.quality_dashboard.artifacts import digest


class LimitedTransport(httpx.BaseTransport):
    """Exact model/count/generation endpoints, exact bodies, one attempt each."""
    def __init__(self, qdir, request, *, inner=None):
        self.qdir, self.request = qdir, request
        self.inner = inner or httpx.HTTPTransport(retries=0)
        self.calls = []

    def handle_request(self, request):
        route = (request.method, request.url.path)
        allowed = {('GET', '/v1/models/' + self.request['model']): 'METADATA',
                   ('POST', '/v1/responses/input_tokens'): 'COUNT',
                   ('POST', '/v1/responses'): 'GENERATION'}
        if (request.url.scheme != 'https' or request.url.host != 'api.openai.com'
                or request.url.port not in (None, 443) or request.url.query or route not in allowed):
            raise ProviderError('UNAUTHORIZED_PROVIDER_ENDPOINT')
        kind = allowed[route]
        if kind in self.calls:
            raise ProviderError('PROVIDER_REQUEST_ALREADY_ATTEMPTED_NO_RETRY')
        if kind != 'METADATA':
            expected = self.request if kind == 'GENERATION' else {
                k: self.request[k] for k in ('model', 'input', 'text', 'reasoning', 'truncation')}
            if digest(json.loads(request.content)) != digest(expected):
                raise ProviderError('OUTBOUND_REQUEST_CHANGED_NO_SEND')
        if kind == 'GENERATION' and not (self.qdir / 'LIVE_ATTEMPT.json').is_file():
            raise ProviderError('DURABLE_COST_RESERVATION_REQUIRED')
        # The adapter's fsynced LIVE_ATTEMPT precedes this generation transport marker.
        from .controls import durable
        durable(self.qdir / (kind + '_HTTP_ATTEMPT.json'), {'endpoint': route[1],
                'method': route[0], 'request_sha256': digest(self.request)})
        self.calls.append(kind)
        return self.inner.handle_request(request)

    def close(self):
        self.inner.close()


class LimitedAdapter(OpenAIAdapter):
    def __init__(self, *, row, budget, settings, pricing, day, trust_guard, **kwargs):
        super().__init__(**kwargs)
        self.row, self.budget, self.settings = row, budget, settings
        self.pricing, self.day = pricing, day
        self.latest_count = None
        self.trust_guard = trust_guard

    def count(self, request):
        receipt = super().count(request)
        if receipt['input_tokens'] != self.row['input_tokens']:
            raise ProviderError('INPUT_TOKEN_COUNT_CHANGED_NEW_OWNER_REVIEW_REQUIRED')
        self.latest_count = receipt
        return receipt

    def invoke(self, request):
        self.trust_guard()
        if not self.latest_count or self.latest_count['request_sha256'] != digest(request):
            raise ProviderError('FRESH_COUNT_REQUIRED')
        cost = estimate_max_cost(self.settings.model, self.latest_count['input_tokens'],
            self.settings.max_output_tokens, self.pricing, tier=self.settings.service_tier,
            region=self.settings.region, as_of=self.day)
        if cost['status'] != 'ESTIMATED_MAX_API_COST':
            raise ProviderError('CURRENT_COST_UNAVAILABLE')
        self.budget.admit(self.row['question_id'], cost['estimated_max_cost_usd'],
                          digest(request), mode='live')
        return super().invoke(request)


def create(root, qdir, request, row, budget, settings, pricing, day, *, trust_guard):
    from openai import OpenAI

    trust_guard()
    load_key(root)  # Only reached after explicit, verified, unused owner authorization.
    if reason := OpenAIAdapter().configuration_error():
        raise ProviderError(reason)
    for name in ('openai', 'httpx', 'httpcore'):
        logging.getLogger(name).setLevel(logging.WARNING)
    transport = LimitedTransport(qdir, request)
    capture = ResponseCapture(root, qdir, question_id=row['question_id'], run_id=qdir.parent.parent.name,
        request_sha256=digest(request), package_sha256=row['M8_package_sha256'], mode='LIVE')
    client = OpenAI(api_key=os.environ['OPENAI_API_KEY'], base_url='https://api.openai.com/v1',
                    max_retries=0, timeout=settings.timeout_seconds,
                    http_client=httpx.Client(transport=transport, timeout=settings.timeout_seconds,
                                             follow_redirects=False))
    return LimitedAdapter(client=client, capture_sink=capture, row=row, budget=budget, settings=settings,
                          pricing=pricing, day=day, trust_guard=trust_guard), client, transport
