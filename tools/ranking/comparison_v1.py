"""Isolated ranking comparison metrics and original-rank subset kernel.

No admission, production defaults, source text, model loading or M8 assembly.
"""

import math
from statistics import mean

CUTOFFS = (5, 10, 20)


def subset_rrf(candidates, k=60):
    """Timing-only restriction of accepted RRF; never renumber native ranks."""
    if type(k) is not int or k != 60:
        raise ValueError("experiment_requires_rrf60")
    seen, rows = set(), []
    for candidate in candidates:
        cid = candidate["chunk_id"]
        contributions = candidate["discovered_by"]
        if cid in seen or not contributions or set(contributions) - {"bm25", "vector"}:
            raise ValueError("invalid_duplicate_or_unknown_candidate_contribution")
        seen.add(cid)
        ranks = [contributions[name]["rank"] for name in sorted(contributions)]
        if any(type(rank) is not int or not 1 <= rank <= 50 for rank in ranks):
            raise ValueError("invalid_original_native_rank")
        rows.append({"chunk_id": cid, "rrf_score": sum(1.0 / (k + rank) for rank in ranks)})
    rows.sort(key=lambda row: (-row["rrf_score"], row["chunk_id"]))
    return [row | {"rank": i} for i, row in enumerate(rows, 1)]


def witness_groups(label):
    """Preserve direct OR alternatives, joint AND witnesses and contextual exclusions."""
    groups = []
    for group in label["required_evidence_groups"]:
        alternatives = []
        for alternative in group["alternatives"]:
            if alternative.get("eligible_as_group_alternative", True) is False:
                continue
            direct = alternative.get("expected_relevant_chunk_ids",
                                     alternative.get("proposed_positive_chunk_ids", []))
            joint = alternative.get("proposed_joint_positive_chunk_ids", [])
            if not direct and not joint:
                raise ValueError("eligible_alternative_missing_frozen_witness")
            alternatives.append({"unit_id": alternative["unit_id"],
                                 "direct_OR": list(direct), "joint_AND": list(joint)})
        if not alternatives:
            raise ValueError("required_group_without_eligible_support")
        groups.append({"group_id": group["group_id"], "alternatives": alternatives})
    if not groups:
        raise ValueError("this_experiment_requires_supported_questions")
    return groups


def evaluate(label, ranked_ids, chunk_to_parent, expected_pool_ids):
    if (len(ranked_ids) != len(set(ranked_ids)) or set(ranked_ids) != set(expected_pool_ids)
            or any(cid not in chunk_to_parent for cid in ranked_ids)):
        raise ValueError("wrong_duplicate_or_unknown_ranking_scope")
    groups = witness_groups(label)
    ranks = {cid: i for i, cid in enumerate(ranked_ids, 1)}
    group_rows = []
    direct_positive_ids = set()
    for group in groups:
        alternatives = []
        for alternative in group["alternatives"]:
            direct = alternative["direct_OR"]
            joint = alternative["joint_AND"]
            direct_positive_ids.update(direct)
            direct_ranks = [ranks[c] for c in direct if c in ranks]
            joint_rank = max(ranks[c] for c in joint) if joint and set(joint) <= ranks.keys() else None
            completions = direct_ranks + ([joint_rank] if joint_rank is not None else [])
            alternatives.append(alternative | {
                "witness_completion_rank": min(completions, default=None),
                "direct_ranks": {c: ranks.get(c) for c in direct},
                "joint_ranks": {c: ranks.get(c) for c in joint},
                "missing_direct_alternatives": sorted(set(direct) - ranks.keys()),
                "missing_joint_members": sorted(set(joint) - ranks.keys())})
        group_rows.append({"group_id": group["group_id"], "alternatives": alternatives,
            "completion_rank": min((a["witness_completion_rank"] for a in alternatives
                                    if a["witness_completion_rank"] is not None), default=None)})
    completion = min((g["completion_rank"] for g in group_rows
                      if g["completion_rank"] is not None), default=None)
    out = {"question_id": label["question_id"], "required_group_count": len(groups),
           "pool_candidates": len(ranked_ids), "groups": group_rows,
           "first_witness_completion_rank": completion,
           "MRR_at_10": 1.0 / completion if completion is not None and completion <= 10 else 0.0,
           "first_single_direct_positive_rank": min(
               (ranks[c] for c in direct_positive_ids if c in ranks), default=None), "at_k": {}}
    for k in (*CUTOFFS, len(ranked_ids)):
        parents = {chunk_to_parent[c] for c in ranked_ids[:k]}
        direct_flags = [g["completion_rank"] is not None and g["completion_rank"] <= k
                        for g in group_rows]
        parent_flags = [any(a["unit_id"] in parents for a in g["alternatives"]) for g in groups]
        out["at_k"][str(k)] = {"groups_complete": sum(direct_flags),
            "group_flags": direct_flags, "Recall": sum(direct_flags) / len(groups),
            "all_required_groups_complete": all(direct_flags),
            "parent_location_groups": sum(parent_flags),
            "parent_location_coverage": sum(parent_flags) / len(groups),
            "all_required_parent_groups_located": all(parent_flags)}
    out["discovery_ceiling"] = out["at_k"][str(len(ranked_ids))]
    return out


def summarize(rows):
    if not rows:
        raise ValueError("no_evaluation_rows")
    denominator = sum(r["required_group_count"] for r in rows)
    return {"question_denominator": len(rows), "required_group_denominator": denominator,
        "MRR_at_10": mean(r["MRR_at_10"] for r in rows),
        "at_k": {str(k): {
            "Recall_macro": mean(r["at_k"][str(k)]["Recall"] for r in rows),
            "group_coverage_micro": sum(r["at_k"][str(k)]["groups_complete"] for r in rows)
                                    / denominator,
            "groups_complete": sum(r["at_k"][str(k)]["groups_complete"] for r in rows),
            "complete_questions": sum(r["at_k"][str(k)]["all_required_groups_complete"]
                                      for r in rows),
            "parent_location_coverage_macro": mean(r["at_k"][str(k)]["parent_location_coverage"]
                                                   for r in rows)} for k in CUTOFFS}}


def timing_summary(rows):
    if not rows or any(not math.isfinite(r["wall_seconds"]) or r["wall_seconds"] <= 0 for r in rows):
        raise ValueError("invalid_timing_samples")
    ordered = sorted(r["wall_seconds"] for r in rows)
    total_wall, total_cpu = sum(ordered), sum(r["cpu_seconds"] for r in rows)
    return {"samples": len(rows), "p50_seconds": ordered[math.ceil(.50 * len(rows)) - 1],
        "p95_seconds": ordered[math.ceil(.95 * len(rows)) - 1],
        "percentile_method": "nearest_rank ceil(p*n)",
        "total_wall_seconds": total_wall, "total_cpu_seconds": total_cpu,
        "process_CPU_percent_of_one_core": 100 * total_cpu / total_wall,
        "original_candidates_per_second": sum(r["candidate_count"] for r in rows) / total_wall,
        "scoring_items_per_second": sum(r["scoring_items"] for r in rows) / total_wall,
        "peak_process_RSS_bytes": max(r["peak_RSS_bytes"] for r in rows)}
