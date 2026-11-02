"""Independent small fixtures for experimental metrics and original-rank fusion."""

import pytest

from tools.ranking.comparison_v1 import evaluate, subset_rrf, summarize, timing_summary
from tools.retrieval.contract import fuse


def label(alternatives):
    return {"question_id": "synthetic", "required_evidence_groups": [
        {"group_id": "g1", "alternatives": alternatives}]}


def test_joint_is_and_alternatives_or_and_mrr_completes_at_last_joint_member():
    q = label([{"unit_id": "u", "proposed_positive_chunk_ids": [],
                "proposed_joint_positive_chunk_ids": ["a", "b"]},
               {"unit_id": "v", "proposed_positive_chunk_ids": ["d"]}])
    ids = ["a", "x", "b", "d"]
    row = evaluate(q, ids, {c: c for c in ids}, ids)
    assert row["first_witness_completion_rank"] == 3
    assert row["MRR_at_10"] == 1 / 3
    assert row["discovery_ceiling"]["groups_complete"] == 1


def test_contextual_cannot_satisfy_group_and_parent_location_is_not_witness():
    q = label([{"unit_id": "u", "proposed_positive_chunk_ids": ["a"]},
               {"unit_id": "v", "proposed_positive_chunk_ids": ["b"],
                "eligible_as_group_alternative": False}])
    row = evaluate(q, ["b", "x"], {"b": "v", "x": "u"}, ["b", "x"])
    assert row["MRR_at_10"] == 0
    assert row["at_k"]["5"]["Recall"] == 0
    assert row["at_k"]["5"]["parent_location_coverage"] == 1


def test_mrr_at_10_is_bounded_and_group_denominators_independent_of_equivalents():
    q = label([{"unit_id": "u", "expected_relevant_chunk_ids": ["a", "b", "c"]}])
    q["required_evidence_groups"].append({"group_id": "g2", "alternatives": [
        {"unit_id": "v", "expected_relevant_chunk_ids": ["z"]}]})
    ids = [f"x{i}" for i in range(10)] + ["a", "z"]
    row = evaluate(q, ids, {c: c for c in ids}, ids)
    assert row["MRR_at_10"] == 0
    assert row["required_group_count"] == 2
    assert row["at_k"]["10"]["Recall"] == 0
    assert row["at_k"]["20"]["Recall"] == 1
    assert summarize([row])["at_k"]["20"]["groups_complete"] == 2


@pytest.mark.parametrize("ids,expected", [(["a", "a"], ["a"]), (["b"], ["a"])])
def test_wrong_scope_fails(ids, expected):
    with pytest.raises(ValueError):
        evaluate(label([{"unit_id": "u", "expected_relevant_chunk_ids": ["a"]}]),
                 ids, {"a": "u"}, expected)


def test_rrf_restriction_is_exact_accepted_formula_and_not_rank_renumbering():
    meta = {"document_id": "S", "format": "html", "reference_classification": "STANDARD"}
    inventory = {cid: meta for cid in ["a", "b", "c"]}
    lists = {"bm25": [{"chunk_id": c, "rank": i, "score": float(4-i), **meta}
                       for i, c in enumerate(["a", "b", "c"], 1)],
             "vector": [{"chunk_id": c, "rank": i, "distance": float(i), **meta}
                        for i, c in enumerate(["c", "b", "a"], 1)]}
    full = fuse(lists, mode="hybrid", top_k=3, rrf_k=60, inventory=inventory, filters={})
    subset = [{"chunk_id": c, "discovered_by": {n: {"rank": next(
        h["rank"] for h in hits if h["chunk_id"] == c)} for n, hits in lists.items()}}
              for c in ["b", "c"]]
    rows = subset_rrf(subset)
    assert [(r["chunk_id"], r["rrf_score"]) for r in rows] == [
        (r["chunk_id"], r["rrf_score"]) for r in full if r["chunk_id"] in {"b", "c"}]


@pytest.mark.parametrize("rank", [0, -1, 51, True, 1.0])
def test_invalid_original_rank_rejected(rank):
    with pytest.raises(ValueError):
        subset_rrf([{"chunk_id": "a", "discovered_by": {"bm25": {"rank": rank}}}])


def test_nearest_rank_timing_and_denominators():
    rows = [{"wall_seconds": i, "cpu_seconds": i / 2, "candidate_count": 10,
             "scoring_items": 11, "peak_RSS_bytes": 100} for i in [1, 2, 3, 4, 5]]
    summary = timing_summary(rows)
    assert summary["p50_seconds"] == 3 and summary["p95_seconds"] == 5
    assert summary["process_CPU_percent_of_one_core"] == 50
    assert summary["original_candidates_per_second"] == 50 / 15
    assert summary["scoring_items_per_second"] == 55 / 15
