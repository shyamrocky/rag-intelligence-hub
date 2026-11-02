"""Runtime timing successor; reuse legacy nested monotonic accounting unchanged."""
from contextlib import contextmanager

from .timing import StageTimer, validate_timing

VERSION = 'runtime-generation-stage-timings-2.0'


class BotTimer:
    def __init__(self, qid, run_id, mode):
        self.timer = StageTimer(qid, run_id, 'mock' if mode == 'mock' else 'dry-run')
        self.mode = mode

    @contextmanager
    def span(self, stage):
        # Reuse the existing serial accounting engine. Remap only in the successor
        # receipt; never publish the internal placeholder as saved verification.
        internal = 'SAVED_INPUT_VERIFICATION' if stage == 'LIVE_RETRIEVAL' else stage
        with self.timer.span(internal):
            yield

    def observe(self, *args):
        return self.timer.observe(*args)

    def finish(self, request, package):
        value = self.timer.finish(request_sha256=request, package_sha256=package)
        value['schema'] = VERSION
        value['runtime_mode'] = self.mode
        value['preflight_observation'] = 'SYNTHETIC_NOT_PROVIDER_COUNTED' if self.mode == 'mock' else 'NOT_RUN'
        for entry in value['stages'] + value['spans']:
            if entry['stage'] == 'SAVED_INPUT_VERIFICATION':
                entry['stage'] = 'LIVE_RETRIEVAL'
        if value['error_stage'] == 'SAVED_INPUT_VERIFICATION':
            value['error_stage'] = 'LIVE_RETRIEVAL'
        value['retrieval_semantics'] = 'SYNTHETIC_SERVICE_BOUNDARY' if self.mode == 'mock' else 'PUBLIC_RETRIEVAL_SERVICE_SEARCH'
        return value


def validate(value):
    import copy
    if (value.get('schema') != VERSION or value.get('runtime_mode') not in {'mock', 'local-check'}
            or value.get('retrieval_semantics') != ('SYNTHETIC_SERVICE_BOUNDARY'
                if value['runtime_mode'] == 'mock' else 'PUBLIC_RETRIEVAL_SERVICE_SEARCH')):
        raise ValueError('INVALID_RUNTIME_TIMING')
    old = copy.deepcopy(value)
    old['schema'] = 'grounded-generation-stage-timings-1.0'
    mode = old.pop('runtime_mode')
    old.pop('retrieval_semantics')
    expected = 'SYNTHETIC_NOT_PROVIDER_COUNTED' if mode == 'mock' else 'NOT_RUN'
    if old['preflight_observation'] != expected:
        raise ValueError('INVALID_RUNTIME_COUNT_SEMANTICS')
    for entry in old['stages'] + old['spans']:
        if entry['stage'] == 'LIVE_RETRIEVAL':
            entry['stage'] = 'SAVED_INPUT_VERIFICATION'
    if old['error_stage'] == 'LIVE_RETRIEVAL':
        old['error_stage'] = 'SAVED_INPUT_VERIFICATION'
    validate_timing(old)
    return value
