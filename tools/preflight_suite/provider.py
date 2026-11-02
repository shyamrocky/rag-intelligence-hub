"""Provider preflight only. Transport rejects every generation and alternate endpoint."""
import json
import os
import re
import shlex
import time

import httpx

from tools.generation.openai_adapter import OpenAIAdapter, ProviderError
from tools.pre_generation_gate.contract import digest

from .artifacts import now, save


def load_key(root):
    """Opt-in credential read, confined to provider mode; no shell sourcing or logging."""
    if os.environ.get('OPENAI_API_KEY'):
        return
    values = []
    for line in (root / '.env').read_text().splitlines():
        match = re.match(r'^\s*(?:export\s+)?OPENAI_API_KEY\s*=\s*(.*)$', line)
        if match:
            parts = shlex.split(match.group(1), comments=True)
            if len(parts) == 1 and parts[0] and not parts[0].startswith('${'):
                values.append(parts[0])
    if len(values) != 1:
        raise ProviderError('KEY_CONFIGURATION_INVALID')
    os.environ['OPENAI_API_KEY'] = values[0]


class CountOnlyTransport(httpx.BaseTransport):
    """Two attempts per question maximum; durable markers precede any network send."""

    def __init__(self, question_dir, model, count_payload_sha256, *, inner=None):
        self.question_dir, self.model = question_dir, model
        self.expected = count_payload_sha256
        self.inner = inner or httpx.HTTPTransport(retries=0)
        self.receipts = []

    def handle_request(self, request):
        route = (request.method, request.url.path)
        allowed = {('GET', '/v1/models/' + self.model), ('POST', '/v1/responses/input_tokens')}
        if (request.url.scheme != 'https' or request.url.host != 'api.openai.com'
                or request.url.port not in (None, 443) or request.url.query
                or route not in allowed):
            raise ProviderError('GENERATION_AND_NON_PREFLIGHT_ENDPOINTS_FORBIDDEN')
        if route in [(r['method'], r['endpoint']) for r in self.receipts]:
            raise ProviderError('PER_QUESTION_REQUEST_LIMIT_EXCEEDED_NO_RETRY')
        if request.method == 'POST' and digest(json.loads(request.content)) != self.expected:
            raise ProviderError('OUTBOUND_REQUEST_HASH_MISMATCH')
        row = {'method': route[0], 'endpoint': route[1], 'started_at': now(),
               'full_authorized_evidence_transfer': request.method == 'POST'}
        save(self.question_dir / ('METADATA_ATTEMPT.json' if request.method == 'GET'
                                 else 'TOKEN_COUNT_ATTEMPT.json'), row)
        self.receipts.append(row)
        start = time.perf_counter()
        try:
            response = self.inner.handle_request(request)
            row['http_status'] = response.status_code
            return response
        except Exception:
            row['status'] = 'TRANSPORT_FAILED_NO_RETRY'
            raise
        finally:
            row['latency_ms'] = (time.perf_counter() - start) * 1000

    def close(self):
        self.inner.close()


class CountOnlyAdapter(OpenAIAdapter):
    def invoke(self, request):
        raise ProviderError('ANSWER_GENERATION_FORBIDDEN_IN_PREFLIGHT_SUITE')


def adapter(root, question_dir, request, timeout):
    from openai import OpenAI

    load_key(root)
    probe = OpenAIAdapter()
    if reason := probe.configuration_error():
        raise ProviderError(reason)
    args = {k: request[k] for k in ('model', 'input', 'text', 'reasoning', 'truncation')}
    transport = CountOnlyTransport(question_dir, request['model'], digest(args))
    client = OpenAI(api_key=os.environ['OPENAI_API_KEY'], base_url='https://api.openai.com/v1',
                    max_retries=0, timeout=timeout,
                    http_client=httpx.Client(transport=transport, timeout=timeout, follow_redirects=False))
    return CountOnlyAdapter(client=client, timeout_seconds=timeout), client, transport
