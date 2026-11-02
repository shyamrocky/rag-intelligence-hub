"""Real offline pinned-model controls; no corpus approvals or retrieval evaluation."""

import json
from pathlib import Path

import numpy as np
import pytest

from rag_hub.local_embeddings import LocalBGE, validate_vectors

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def model():
    p = ROOT / "workspace/rag-implementation/v1/m4-embeddings-v1/MODEL_CONFIGURATION_BINDING.json"
    if not p.is_file():
        pytest.skip("Private M4 model snapshot/configuration absent")
    b = json.loads(p.read_bytes())
    return LocalBGE(ROOT, configuration=b["path"], expected_sha256=b["sha256"])


def test_actual_CLS_pooling_and_L2(model):
    texts = ["Preserve RAG-Sequence.", "all-MiniLM-L6-v2 is source text, not another loaded model."]
    result = model.verify_cls_normalization(texts, [384, 384])
    assert result["status"] == "PASS" and result["max_abs_difference"] < 2e-6


def test_pinned_runtime_token_ids_and_deterministic_batch(model):
    texts = ["Some source prose.", "Ω, F₁, semi-supervised and exact identifier."]
    ids = model.token_ids(texts, [384, 384])
    assert all(row[0] == 101 and row[-1] == 102 for row in ids)
    first = model.encode(texts, [384, 384])
    assert np.array_equal(first, model.encode(texts, [384, 384]))
    assert first.shape == (2, 384) and first.dtype == np.float32


@pytest.mark.parametrize("texts,limits", [([], []), ([""], [384]), (["x"], []),
    (["x"], [385]), (["word " * 600], [512]), (["word " * 400], [384])])
def test_empty_invalid_or_over_budget_fails_without_truncation(model, texts, limits):
    with pytest.raises(ValueError):
        model.encode(texts, limits)


@pytest.mark.parametrize("kind", ["nan", "inf", "zero", "dimension", "dtype", "unnormalized"])
def test_corrupt_vectors_rejected(kind):
    vectors = np.zeros((2, 384), dtype=np.float32)
    vectors[:, 0] = 1
    if kind == "nan":
        vectors[0, 0] = np.nan
    elif kind == "inf":
        vectors[0, 0] = np.inf
    elif kind == "zero":
        vectors[0] = 0
    elif kind == "dimension":
        vectors = vectors[:, :383]
    elif kind == "dtype":
        vectors = vectors.astype(np.float64)
    else:
        vectors[0, 0] = 2
    with pytest.raises(ValueError, match="invalid_embedding"):
        validate_vectors(vectors, 2, 384)


def test_model_config_hash_tampering_fails_before_loading(model, tmp_path):
    p = tmp_path / "spec.json"
    p.write_text('{"forged": true}')
    with pytest.raises(ValueError, match="unified_binding_changed"):
        LocalBGE(tmp_path, configuration="spec.json", expected_sha256=model.config_sha256)
