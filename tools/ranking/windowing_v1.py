"""Pinned experimental scoring windows. No model execution or evidence authorization.

Callers must reopen authorized source inputs and validate frozen bindings first.
Outputs remain private search representations requiring complete verified parents.
This module neither loads models nor changes accepted M7/M8 behavior.
"""

import hashlib
import json
import math

POLICY = "ce-fullcoverage-two-window-1.0"
SCHEMA = "ce-window-plan-1.0"
LIMIT = 512
CLS, SEP = 101, 102
CHUNK_A = "rc:retrieval-chunk-1.0:2e020020eccd4dace0859786ab39087ea3de913649299341331e682583a97c4c"
CHUNK_B = "rc:retrieval-chunk-1.0:9a448b2a9de1d3c8b516bd68a1d92e1a7058c3b637e08dbf3b5979ba1cf10a4a"
APPROVED = {
    ("M9-Q05", CHUNK_A): (21, 505, ((0, 488), (17, 505))),
    ("M9-Q25", CHUNK_B): (27, 483, ((0, 482), (1, 483))),
    ("R02", CHUNK_A): (15, 505, ((0, 494), (11, 505))),
}


def encode(value):
    """Same canonical token-list encoding used by the sealed full-pair preflight."""
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode()


def digest(value):
    return hashlib.sha256(encode(value)).hexdigest()


def text_digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def _require(condition, error):
    if not condition:
        raise ValueError(error)


def _tokens(ids):
    _require(isinstance(ids, list) and ids and all(
        type(v) is int and 0 <= v < 30522 for v in ids), "invalid_token_ids")


def offset_ledger(text, offsets):
    """Bind tokenizer offsets and losslessly account for untokenized display gaps.

    Offsets are Python character offsets into the exact authorized input, including
    its approved headings. They are NOT new raw HTML/PDF citation coordinates.
    Gap hashes preserve original whitespace/normalizer-ignored text without claiming
    the model observes it. No text is decoded, re-encoded, repaired or exported.
    """
    _require(isinstance(text, str) and text and offsets, "empty_display_or_offsets")
    gaps, cursor = [], 0
    for offset in offsets:
        _require(isinstance(offset, (list, tuple)) and len(offset) == 2
                 and all(type(v) is int for v in offset), "invalid_offset_type")
        start, end = offset
        _require(cursor <= start < end <= len(text), "invalid_offset_order_or_range")
        if start > cursor:
            fragment = text[cursor:start]
            gaps.append({"range": [cursor, start], "sha256": text_digest(fragment),
                         "kind": "WHITESPACE" if fragment.isspace() else
                         "TOKENIZER_UNMAPPED_ORIGINAL_DISPLAY"})
        cursor = end
    if cursor < len(text):
        fragment = text[cursor:]
        gaps.append({"range": [cursor, len(text)], "sha256": text_digest(fragment),
                     "kind": "WHITESPACE" if fragment.isspace() else
                     "TOKENIZER_UNMAPPED_ORIGINAL_DISPLAY"})
    return {"precision": "AUTHORIZED_INPUT_DISPLAY_CHARACTERS_NOT_RAW_SOURCE",
            "text_sha256": text_digest(text), "character_count": len(text),
            "offsets": [list(v) for v in offsets], "gaps": gaps,
            "token_mapped_characters": sum(e - s for s, e in offsets),
            "gap_characters": sum(g["range"][1] - g["range"][0] for g in gaps)}


def intervals(question_id, chunk_id, question_length, passage_length):
    _require(type(question_length) is int and type(passage_length) is int
             and 0 < question_length < LIMIT - 3 and passage_length > 0,
             "invalid_question_or_passage_budget")
    key = (question_id, chunk_id)
    budget = LIMIT - question_length - 3
    if key in APPROVED:
        q, p, windows = APPROVED[key]
        _require((q, p) == (question_length, passage_length), "approved_pair_lengths_changed")
    else:
        _require(passage_length <= budget, "unexpected_overflow_stop_for_owner_review")
        windows = ((0, passage_length),)
    _require(windows[0][0] == 0 and windows[-1][1] == passage_length,
             "incomplete_passage_coverage")
    last_end = 0
    for start, end in windows:
        _require(0 <= start <= last_end < end <= passage_length and end - start <= budget,
                 "invalid_or_uncovered_window_interval")
        last_end = end
    return [list(v) for v in windows]


def pair_ids(question_ids, passage_ids):
    return [CLS] + question_ids + [SEP] + passage_ids + [SEP]


def _source_reference(binding):
    _require(binding.get("complete_parent_rehydration_required") is True
             and binding.get("mandatory_evidence_refs", {}).get("scope") ==
             "complete_verified_unit_only", "missing_complete_parent_obligation")
    for field in ("chunk_id", "unit_id", "input_text_sha256", "qualification_sha256",
                  "publication_identity", "parent_binding", "lineage",
                  "reference_classification"):
        _require(bool(binding.get(field)), "missing_source_binding:" + field)
    return {"binding_sha256": digest(binding), "unit_id": binding["unit_id"],
            "classification": binding["reference_classification"],
            "qualification_sha256": binding["qualification_sha256"],
            "publication_sha256": digest(binding["publication_identity"]),
            "lineage_sha256": digest(binding["lineage"]),
            "complete_parent_rehydration_required": True,
            "authority": "INTERNAL_SCORING_INPUT_NOT_INDEPENDENT_EVIDENCE"}


def build_pair(question_id, chunk_id, question, passage, tokenizer, binding, baseline):
    """Construct an approved scoring plan; baseline must come from the verified seal."""
    _require(binding.get("chunk_id") == chunk_id and baseline.get("chunk_id") == chunk_id
             and baseline.get("question_id") == question_id
             and baseline.get("unit_id") == binding.get("unit_id"), "pair_identity_mismatch")
    _require(text_digest(question) == baseline["question_sha256"]
             and text_digest(passage) == baseline["passage_sha256"] ==
             binding["input_text_sha256"], "original_input_changed")
    _require(tokenizer.is_fast and tokenizer.cls_token_id == CLS
             and tokenizer.sep_token_id == SEP and tokenizer.model_max_length == LIMIT
             and tokenizer.num_special_tokens_to_add(pair=True) == 3,
             "incompatible_pinned_tokenizer")
    reference = _source_reference(binding)
    q = tokenizer(question, add_special_tokens=False, truncation=False,
                  return_offsets_mapping=True)
    p = tokenizer(passage, add_special_tokens=False, truncation=False,
                  return_offsets_mapping=True)
    full = tokenizer(question, passage, add_special_tokens=True, truncation=False,
                     padding=False, return_offsets_mapping=True)
    qi, pi = list(q["input_ids"]), list(p["input_ids"])
    _tokens(qi)
    _tokens(pi)
    expected = pair_ids(qi, pi)
    expected_offsets = [(0, 0)] + list(q["offset_mapping"]) + [(0, 0)] + list(
        p["offset_mapping"]) + [(0, 0)]
    _require(full["input_ids"] == expected
             and list(full["offset_mapping"]) == expected_offsets
             and full.sequence_ids() == [None] + [0] * len(qi) + [None] +
             [1] * len(pi) + [None]
             and full["token_type_ids"] == [0] * (len(qi) + 2) + [1] * (len(pi) + 1)
             and full["attention_mask"] == [1] * len(expected), "full_pair_composition_mismatch")
    _require((len(qi), len(pi), len(expected), digest(expected)) == (
        baseline["question_tokens"], baseline["passage_tokens"],
        baseline["complete_pair_tokens"], baseline["pair_token_ids_sha256"]),
        "sealed_original_tokens_changed")
    _require(len(q["offset_mapping"]) == len(qi) and len(p["offset_mapping"]) == len(pi),
             "token_offset_count_mismatch")
    qledger, pledger = offset_ledger(question, q["offset_mapping"]), offset_ledger(
        passage, p["offset_mapping"])
    record = {"schema": SCHEMA, "policy": POLICY, "question_id": question_id,
              "chunk_id": chunk_id, "source_reference": reference,
              "question_sha256": text_digest(question), "passage_sha256": text_digest(passage),
              "original_pair_token_ids_sha256": digest(expected),
              "question_token_ids": qi, "passage_token_ids": pi,
              "question_display": qledger, "passage_display": pledger, "windows": []}
    for start, end in intervals(question_id, chunk_id, len(qi), len(pi)):
        ids = pair_ids(qi, pi[start:end])
        window = {"passage_token_range": [start, end],
                  "passage_display_range": [pledger["offsets"][start][0],
                                            pledger["offsets"][end - 1][1]],
                  "input_ids": ids, "input_ids_sha256": digest(ids),
                  "token_type_ids": [0] * (len(qi) + 2) + [1] * (end - start + 1),
                  "attention_mask": [1] * len(ids)}
        window["scoring_input_id"] = _window_id(record, window)
        record["windows"].append(window)
    record["record_sha256"] = digest(record)
    validate_pair(record)
    return record


def _window_id(record, window):
    return "scoring-input:" + POLICY + ":" + digest({
        "policy": POLICY, "question_id": record["question_id"], "chunk_id": record["chunk_id"],
        "question_sha256": record["question_sha256"], "passage_sha256": record["passage_sha256"],
        "source_reference": record["source_reference"],
        "range": window["passage_token_range"], "input_ids_sha256": window["input_ids_sha256"]})


def _validate_ledger(ledger, token_count, text_hash):
    _require(ledger["precision"] == "AUTHORIZED_INPUT_DISPLAY_CHARACTERS_NOT_RAW_SOURCE"
             and ledger["text_sha256"] == text_hash, "display_binding_mismatch")
    offsets, gaps, length = ledger["offsets"], ledger["gaps"], ledger["character_count"]
    _require(type(length) is int and length > 0 and len(offsets) == token_count,
             "display_mapping_count_mismatch")
    cursor, expected_gaps = 0, []
    for start, end in offsets:
        _require(type(start) is int and type(end) is int and cursor <= start < end <= length,
                 "invalid_display_offsets")
        if start > cursor:
            expected_gaps.append([cursor, start])
        cursor = end
    if cursor < length:
        expected_gaps.append([cursor, length])
    _require([g["range"] for g in gaps] == expected_gaps
             and all(g["kind"] in {"WHITESPACE", "TOKENIZER_UNMAPPED_ORIGINAL_DISPLAY"}
                     and isinstance(g["sha256"], str) and len(g["sha256"]) == 64 for g in gaps),
             "display_gap_accounting_mismatch")
    _require(ledger["token_mapped_characters"] == sum(e - s for s, e in offsets)
             and ledger["gap_characters"] == sum(e - s for s, e in expected_gaps)
             and ledger["token_mapped_characters"] + ledger["gap_characters"] == length,
             "display_character_coverage_mismatch")


def validate_pair(record):
    """Structural integrity only, never an admission check or detached permission."""
    _require(record["schema"] == SCHEMA and record["policy"] == POLICY, "wrong_plan_policy")
    unsigned = {k: v for k, v in record.items() if k != "record_sha256"}
    _require(record["record_sha256"] == digest(unsigned), "plan_record_changed")
    ref = record["source_reference"]
    _require(ref["authority"] == "INTERNAL_SCORING_INPUT_NOT_INDEPENDENT_EVIDENCE"
             and ref["complete_parent_rehydration_required"] is True
             and all(ref.get(k) for k in ("binding_sha256", "unit_id", "classification",
                                         "qualification_sha256", "publication_sha256",
                                         "lineage_sha256")), "source_obligation_changed")
    qi, pi = record["question_token_ids"], record["passage_token_ids"]
    _tokens(qi)
    _tokens(pi)
    _require(digest(pair_ids(qi, pi)) == record["original_pair_token_ids_sha256"],
             "original_pair_token_binding_changed")
    _validate_ledger(record["question_display"], len(qi), record["question_sha256"])
    _validate_ledger(record["passage_display"], len(pi), record["passage_sha256"])
    ranges = intervals(record["question_id"], record["chunk_id"], len(qi), len(pi))
    _require([w["passage_token_range"] for w in record["windows"]] == ranges,
             "window_membership_or_coverage_changed")
    offsets = record["passage_display"]["offsets"]
    for window, (start, end) in zip(record["windows"], ranges, strict=True):
        ids = pair_ids(qi, pi[start:end])
        _require(len(ids) <= LIMIT and window["input_ids"] == ids
                 and window["input_ids_sha256"] == digest(ids)
                 and window["scoring_input_id"] == _window_id(record, window)
                 and window["passage_display_range"] == [offsets[start][0], offsets[end - 1][1]]
                 and window["token_type_ids"] == [0] * (len(qi) + 2) + [1] * (end - start + 1)
                 and window["attention_mask"] == [1] * len(ids), "invalid_scoring_window")


def validate_plan(records, *, expected_memberships, expected_plan_sha256):
    """Expected hashes/identities must come from the verified experiment manifest."""
    _require(digest(records) == expected_plan_sha256, "untrusted_or_changed_plan")
    actual = [(r["question_id"], r["chunk_id"]) for r in records]
    _require(isinstance(expected_memberships, (list, tuple)) and all(
        isinstance(p, (list, tuple)) and len(p) == 2
        and all(isinstance(v, str) and v for v in p) for p in expected_memberships),
        "malformed_expected_membership")
    expected = [tuple(p) for p in expected_memberships]
    _require(actual == expected and len(set(actual)) == len(actual),
             "wrong_duplicate_or_missing_original_membership")
    handles = []
    for record in records:
        validate_pair(record)
        handles.extend(w["scoring_input_id"] for w in record["windows"])
    _require(len(handles) == len(set(handles)), "duplicate_scoring_input_mapping")
    return handles


def aggregate_window_scores(records, scores, *, expected_memberships, expected_plan_sha256):
    """Pure deterministic aggregation; preflight callers may use synthetic values ONLY.

    A real score must come from separately authorized inference. This function does
    not perform inference, RRF, retrieval, qualification or evidence consumption.
    """
    handles = validate_plan(records, expected_memberships=expected_memberships,
                            expected_plan_sha256=expected_plan_sha256)
    _require(isinstance(scores, list), "scores_must_be_explicit_records")
    supplied = [s["scoring_input_id"] for s in scores]
    _require(len(supplied) == len(set(supplied)) and set(supplied) == set(handles),
             "missing_duplicate_or_unknown_window_score")
    values = {}
    for score in scores:
        value = score["score"]
        _require(type(value) in (int, float) and math.isfinite(value), "nonfinite_or_invalid_score")
        values[score["scoring_input_id"]] = value
    by_question = {}
    for record in records:
        diagnostics = [{"scoring_input_id": w["scoring_input_id"],
                        "passage_token_range": w["passage_token_range"],
                        "score": values[w["scoring_input_id"]]} for w in record["windows"]]
        result = {"question_id": record["question_id"], "chunk_id": record["chunk_id"],
                  "score": max(d["score"] for d in diagnostics),
                  "aggregation": "MAX_FINITE_RAW_WINDOW_SCORE", "window_scores": diagnostics,
                  "source_reference": record["source_reference"],
                  "complete_parent_rehydration_required": True}
        by_question.setdefault(record["question_id"], []).append(result)
    for candidates in by_question.values():
        candidates.sort(key=lambda r: (-r["score"], r["chunk_id"]))
        for rank, result in enumerate(candidates, 1):
            result["rank"] = rank
    return by_question
