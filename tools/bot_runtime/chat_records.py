"""Source-free chat stop findings; pure readback, never runner execution."""
from pathlib import Path

from tools.quality_dashboard.artifacts import ArtifactError, sha

from .store import load, read, reference

BASE = 'data/runtime-chat/v1'


def record(root, qid):
    folder = Path(root) / BASE / 'runs' / qid
    if not folder.exists():
        blocks = sorted((Path(root) / BASE / 'blocks' / qid).glob('*'))
        if not blocks:
            return None
        folder = blocks[-1]
        load(folder, 'bot-chat-admission-block-1.0')
        value = read(folder / 'RESULT.json')
        if value.get('question_id') != qid or value.get('question_reference') != reference(root, qid):
            raise ArtifactError('CHAT_BLOCK_QUESTION_CHANGED')
        return value
    start = read(folder / 'START.json')
    expected = reference(root, qid)
    if start.get('question_id') != qid or start.get('question_reference') != expected:
        raise ArtifactError('CHAT_EXECUTION_QUESTION_CHANGED')
    submission = Path(root) / BASE / 'submissions' / qid
    load(submission, 'bot-chat-submission-1.0')
    if start['send'] != {'path': (submission / 'MANIFEST.json').relative_to(root).as_posix(),
                         'sha256': sha(submission / 'MANIFEST.json')}:
        raise ArtifactError('CHAT_EXECUTION_SEND_CHANGED')
    if not (folder / 'MANIFEST.json').exists():
        return {'question_id': qid, 'status': 'INCOMPLETE', 'finding': {
            'code': 'EXECUTION_INCOMPLETE', 'message': 'This request has no completed execution receipt. Its outcome or cost may be unknown; no automatic retry.',
            'stage': 'UNAVAILABLE', 'generation_attempted': None, 'cost_status': 'UNKNOWN'}}
    load(folder, 'bot-chat-execution-1.0')
    result = read(folder / 'RESULT.json')
    if result.get('question_id') != qid or result.get('question_reference') != expected:
        raise ArtifactError('CHAT_RESULT_QUESTION_CHANGED')
    return result | {'manifest_path': (folder / 'MANIFEST.json').relative_to(root).as_posix()}
