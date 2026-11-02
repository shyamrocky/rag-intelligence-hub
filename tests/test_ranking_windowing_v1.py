"""Synthetic tests only: no model loading, inference, RRF or private source data."""

import copy
import json

import pytest

from tools.ranking.windowing_v1 import (
    APPROVED,
    CHUNK_A,
    CHUNK_B,
    aggregate_window_scores,
    build_pair,
    digest,
    intervals,
    offset_ledger,
    pair_ids,
    text_digest,
    validate_pair,
    validate_plan,
)


class Batch(dict):
    def sequence_ids(self):
        return self.sequences


class SyntheticTokenizer:
    """Character fixtures exercise contracts; never claim real tokenizer behavior."""

    is_fast = True
    cls_token_id = 101
    sep_token_id = 102
    model_max_length = 512

    def num_special_tokens_to_add(self, pair):
        assert pair is True
        return 3

    def __call__(self, text, other=None, **kwargs):
        assert kwargs["truncation"] is False
        offsets = [(i, i + 1) for i, c in enumerate(text) if not c.isspace()]
        ids = [ord(text[s]) for s, _ in offsets]
        if other is None:
            return Batch(input_ids=ids, offset_mapping=offsets)
        second = self(other, truncation=False)
        batch = Batch(input_ids=pair_ids(ids, second["input_ids"]),
                      offset_mapping=[(0, 0)] + offsets + [(0, 0)] +
                      second["offset_mapping"] + [(0, 0)],
                      token_type_ids=[0] * (len(ids) + 2) +
                      [1] * (len(second["input_ids"]) + 1),
                      attention_mask=[1] * (len(ids) + len(second["input_ids"]) + 3))
        batch.sequences = [None] + [0] * len(ids) + [None] + [1] * len(
            second["input_ids"]) + [None]
        return batch


def fixture(qid="synthetic-Q", cid="synthetic-chunk", qlen=5, plen=9):
    tokenizer = SyntheticTokenizer()
    q, p = "q" * qlen, "p" * plen
    binding = {"chunk_id": cid, "unit_id": "synthetic-unit",
               "input_text_sha256": text_digest(p), "qualification_sha256": "a" * 64,
               "publication_identity": {"synthetic": True}, "parent_binding": {"synthetic": True},
               "lineage": {"section_ids": ["synthetic-section"]},
               "reference_classification": "ILLUSTRATIVE_REFERENCE",
               "complete_parent_rehydration_required": True,
               "mandatory_evidence_refs": {"scope": "complete_verified_unit_only"}}
    baseline = {"question_id": qid, "chunk_id": cid, "unit_id": "synthetic-unit",
                "question_sha256": text_digest(q), "passage_sha256": text_digest(p),
                "question_tokens": qlen, "passage_tokens": plen,
                "complete_pair_tokens": qlen + plen + 3,
                "pair_token_ids_sha256": digest(pair_ids([ord("q")] * qlen, [ord("p")] * plen))}
    return qid, cid, q, p, tokenizer, binding, baseline


def resign(record):
    record["record_sha256"] = digest({k: v for k, v in record.items() if k != "record_sha256"})


def plan_arguments(records):
    return {"expected_memberships": [(r["question_id"], r["chunk_id"]) for r in records],
            "expected_plan_sha256": digest(records)}


@pytest.mark.parametrize("qid,cid,qlen,plen,expected", [
    ("M9-Q05", CHUNK_A, 21, 505, [[0, 488], [17, 505]]),
    ("M9-Q25", CHUNK_B, 27, 483, [[0, 482], [1, 483]]),
    ("R02", CHUNK_A, 15, 505, [[0, 494], [11, 505]]),
])
def test_exact_approved_windows_full_question_and_coverage(qid, cid, qlen, plen, expected):
    record = build_pair(*fixture(qid, cid, qlen, plen))
    assert [w["passage_token_range"] for w in record["windows"]] == expected
    covered = set()
    for w in record["windows"]:
        start, end = w["passage_token_range"]
        covered.update(range(start, end))
        assert w["input_ids"][1:qlen + 1] == record["question_token_ids"]
        assert w["input_ids"][qlen + 2:-1] == record["passage_token_ids"][start:end]
        assert len(w["input_ids"]) == 512
    assert covered == set(range(plen))
    assert record["source_reference"]["complete_parent_rehydration_required"] is True


def test_fitting_512_preserves_original_full_sequence():
    record = build_pair(*fixture(qlen=1, plen=508))
    assert len(record["windows"]) == 1
    assert record["windows"][0]["input_ids_sha256"] == record["original_pair_token_ids_sha256"]
    assert build_pair(*fixture(qlen=1, plen=508)) == record


@pytest.mark.parametrize("qlen,plen", [(1, 509), (30, 500), (511, 5), (0, 5), (5, 0)])
def test_unexpected_overflow_or_invalid_budget_fails(qlen, plen):
    with pytest.raises(ValueError):
        intervals("synthetic", "unknown", qlen, plen)


@pytest.mark.parametrize("key", list(APPROVED))
def test_declared_pair_length_change_rejected(key):
    q, p, _ = APPROVED[key]
    with pytest.raises(ValueError, match="approved_pair_lengths_changed"):
        intervals(*key, q, p - 1)


@pytest.mark.parametrize("field,value", [
    ("input_text_sha256", "wrong"), ("chunk_id", "wrong"), ("unit_id", "wrong"),
    ("complete_parent_rehydration_required", False), ("qualification_sha256", ""),
    ("mandatory_evidence_refs", {}), ("publication_identity", {}), ("lineage", {}),
])
def test_source_and_qualification_mismatch_rejected(field, value):
    args = list(fixture())
    args[5][field] = value
    with pytest.raises(ValueError):
        build_pair(*args)


@pytest.mark.parametrize("field,value", [
    ("question_sha256", "wrong"), ("passage_sha256", "wrong"),
    ("pair_token_ids_sha256", "wrong"), ("question_tokens", 6),
    ("chunk_id", "wrong"), ("unit_id", "wrong"),
])
def test_sealed_baseline_changes_rejected(field, value):
    args = list(fixture())
    args[6][field] = value
    with pytest.raises(ValueError):
        build_pair(*args)


@pytest.mark.parametrize("attribute,value", [
    ("is_fast", False), ("model_max_length", 513), ("cls_token_id", 100), ("sep_token_id", 100),
])
def test_wrong_tokenizer_rejected(attribute, value):
    args = list(fixture())
    setattr(args[4], attribute, value)
    with pytest.raises(ValueError, match="incompatible_pinned_tokenizer"):
        build_pair(*args)


def test_display_gaps_honest_precision_and_hashes():
    ledger = offset_ledger(" \ta\nb  ", [(2, 3), (4, 5)])
    assert ledger["token_mapped_characters"] + ledger["gap_characters"] == 7
    assert [g["range"] for g in ledger["gaps"]] == [[0, 2], [3, 4], [5, 7]]
    assert all(g["kind"] == "WHITESPACE" for g in ledger["gaps"])
    ignored = offset_ledger("a\x00b", [(0, 1), (2, 3)])
    assert ignored["gaps"][0]["kind"] == "TOKENIZER_UNMAPPED_ORIGINAL_DISPLAY"
    assert "NOT_RAW_SOURCE" in ignored["precision"]


@pytest.mark.parametrize("offsets", [
    [(-1, 1)], [(0, 0)], [(0, 4)], [(0, 2), (1, 3)], [(2, 3), (0, 1)],
    [(False, 1)], [(0, "1")], [(0,)], [],
])
def test_invalid_display_offsets_rejected(offsets):
    with pytest.raises(ValueError):
        offset_ledger("abc", offsets)


@pytest.mark.parametrize("mutation", [
    "missing_window", "range_gap", "wrong_token", "reordered_tokens", "missing_question",
    "wrong_offset", "wrong_type_ids", "wrong_attention", "wrong_handle", "stripped_parent",
    "false_precision", "gap_accounting", "removed_token",
])
def test_forged_scoring_plan_rejected_even_with_record_checksum(mutation):
    record = build_pair(*fixture("M9-Q05", CHUNK_A, 21, 505))
    if mutation == "missing_window":
        record["windows"].pop()
    elif mutation == "range_gap":
        record["windows"][1]["passage_token_range"][0] = 489
    elif mutation == "wrong_token":
        record["windows"][0]["input_ids"][30] += 1
    elif mutation == "reordered_tokens":
        record["windows"][0]["input_ids"] = list(reversed(record["windows"][0]["input_ids"]))
    elif mutation == "missing_question":
        del record["windows"][0]["input_ids"][1]
    elif mutation == "wrong_offset":
        record["windows"][0]["passage_display_range"][0] += 1
    elif mutation == "wrong_type_ids":
        record["windows"][0]["token_type_ids"][0] = 1
    elif mutation == "wrong_attention":
        record["windows"][0]["attention_mask"][0] = 0
    elif mutation == "wrong_handle":
        record["windows"][0]["scoring_input_id"] = "forged"
    elif mutation == "stripped_parent":
        record["source_reference"]["complete_parent_rehydration_required"] = False
    elif mutation == "false_precision":
        record["passage_display"]["precision"] = "EXACT_RAW_SOURCE"
    elif mutation == "gap_accounting":
        record["passage_display"]["gap_characters"] = 2
    elif mutation == "removed_token":
        record["passage_token_ids"].pop()
    resign(record)
    with pytest.raises(ValueError):
        validate_pair(record)


def test_plan_manifest_and_membership_fail_closed():
    records = [build_pair(*fixture())]
    args = plan_arguments(records)
    handles = validate_plan(records, **args)
    assert len(handles) == 1
    wrong = copy.deepcopy(records)
    wrong[0]["source_reference"]["qualification_sha256"] = "changed"
    resign(wrong[0])
    with pytest.raises(ValueError, match="untrusted_or_changed_plan"):
        validate_plan(wrong, **args)
    with pytest.raises(ValueError, match="membership"):
        validate_plan(records, expected_memberships=[], expected_plan_sha256=digest(records))
    with pytest.raises(ValueError, match="membership"):
        validate_plan(records * 2, expected_memberships=args["expected_memberships"] * 2,
                      expected_plan_sha256=digest(records * 2))


def test_saved_json_plan_reopens_with_exact_original_memberships():
    records, scores = synthetic_aggregation()
    arguments = plan_arguments(records)
    saved = json.loads(json.dumps({"records": records, "arguments": arguments}))
    reopened = saved["records"]
    assert digest(reopened) == arguments["expected_plan_sha256"]
    assert validate_plan(reopened, **saved["arguments"]) == validate_plan(records, **arguments)
    assert aggregate_window_scores(reopened, scores, **saved["arguments"]) == (
        aggregate_window_scores(records, scores, **arguments))


def test_malformed_saved_expected_membership_fails_closed():
    records = [build_pair(*fixture())]
    with pytest.raises(ValueError, match="malformed_expected_membership"):
        validate_plan(records, expected_memberships=["synthetic-Q"],
                      expected_plan_sha256=digest(records))


def synthetic_aggregation():
    records = [build_pair(*fixture("M9-Q05", CHUNK_A, 21, 505)),
               build_pair(*fixture("M9-Q05", "synthetic-z", 21, 9)),
               build_pair(*fixture("other-Q", "synthetic-z", 5, 9))]
    values = [-3.0, 2.0, 2.0, -1.0]
    handles = [w["scoring_input_id"] for r in records for w in r["windows"]]
    scores = [{"scoring_input_id": h, "score": s} for h, s in zip(handles, values, strict=True)]
    return records, scores


def test_synthetic_max_ties_one_candidate_per_chunk_question_and_no_mutation():
    records, scores = synthetic_aggregation()
    before = copy.deepcopy((records, scores))
    result = aggregate_window_scores(records, scores, **plan_arguments(records))
    assert len(result["M9-Q05"]) == 2 and len(result["other-Q"]) == 1
    assert result["M9-Q05"][0]["chunk_id"] == CHUNK_A
    assert result["M9-Q05"][0]["score"] == 2.0
    assert [d["score"] for d in result["M9-Q05"][0]["window_scores"]] == [-3.0, 2.0]
    assert [c["rank"] for c in result["M9-Q05"]] == [1, 2]
    assert aggregate_window_scores(records, list(reversed(scores)), **plan_arguments(records)) == result
    assert (records, scores) == before


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), True, "1", None])
def test_nonfinite_or_non_numeric_scores_rejected(value):
    records, scores = synthetic_aggregation()
    scores[0]["score"] = value
    with pytest.raises(ValueError, match="nonfinite_or_invalid_score"):
        aggregate_window_scores(records, scores, **plan_arguments(records))


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "unknown"])
def test_window_score_mapping_rejected(mutation):
    records, scores = synthetic_aggregation()
    if mutation == "missing":
        scores.pop()
    elif mutation == "duplicate":
        scores.append(scores[0])
    else:
        scores[0]["scoring_input_id"] = "forged"
    with pytest.raises(ValueError, match="window_score"):
        aggregate_window_scores(records, scores, **plan_arguments(records))
