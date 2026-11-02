"""Fast CLI policy checks; do not load private evidence or invoke providers."""

import json

import pytest

from tools.generation.cli import main


def test_unknown_model_is_explicit_without_retrieval_or_fallback(capsys):
    assert main(["--model", "not-qualified", "--dry-run"]) == 2
    value = json.loads(capsys.readouterr().out)
    assert value["blocking_reasons"] == ["UNSUPPORTED_MODEL_NO_FALLBACK"]
    assert value["generation_executed"] is False


def test_live_command_requires_explicit_opt_ins():
    with pytest.raises(SystemExit) as info:
        main(["--live"])
    assert info.value.code == 2
