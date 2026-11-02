"""Read-only layout extension; preserve the hash-bound historical UI module.

Reuse its exact quality function and controls with an isolated rendering namespace.
Only the pipeline renderer is composed. No module globals are patched, no layout
is copied, and the historical entry points keep their original behavior.
"""
from types import FunctionType

from tools.generation_runner.dashboard import compact_latency

from . import coverage_ui


def quality(data, *, root):
    def pipeline_with_latency(data, row, attempt):
        compact_latency(coverage_ui.st, root, row['question_id'])
        coverage_ui.pipeline(data, row, attempt)

    original = coverage_ui.quality
    render = FunctionType(original.__code__,
        original.__globals__ | {'pipeline': pipeline_with_latency},
        name=original.__name__, argdefs=original.__defaults__, closure=original.__closure__)
    return render(data)
