"""Read-only discovery of sealed RRF30/M8-128K completion measurements.

No retrieval, assembly, prompt preparation, provider calls or offline scoring runs here.
"""

from .artifacts import ArtifactError, digest
from .expanded_adapter import MANIFEST_SHA, TARGET, load_expanded

CONFIGURATION = TARGET | {"M8_BGE_budget": 128000}


def validate_measurement(question, measurement, result, case):
    """Cross-check transport and accounting; receipts never replace live M8 authorization."""
    if (
        measurement.get("question_id") != question["question_id"]
        or measurement.get("question_sha256") != question["question_text_sha256"]
        or result.get("query_sha256") != question["question_text_sha256"]
        or result.get("retrieval_mode") != "hybrid"
        or result.get("parameters") != {k: v for k, v in TARGET.items() if k != "mode"}
        or case.get("candidate_envelope_sha256") != digest(result)
        or measurement.get("M7_result_sha256") != digest(result)
        or case.get("M8_package_sha256") != measurement.get("m8", {}).get("M8_package_sha256")
        or case.get("budget_accounting", {}).get("limit") != 128000
        or case["budget_accounting"].get("truncation") is not False
        or len(result.get("candidates", [])) != 30
        or case.get("considered_chunk_ids") != [h["chunk_id"] for h in result["candidates"]]
    ):
        raise ArtifactError("COMPLETION_QUERY_CONFIGURATION_OR_PACKAGE_MISMATCH")
    included = case["actual_M8_included_parent_ids"]
    omitted = [o["unit_id"] for o in case["omitted"]]
    from tools.evidence.contract import POLICY

    budget, counts, m = case["budget_accounting"], case["counts"], measurement["m8"]
    if (
        budget.get("policy") != POLICY
        or len(set(included + omitted)) != len(included) + len(omitted)
        or counts["candidates"] != 30
        or counts["selected_parents"] != len(included)
        or counts["omitted_parents"] != len(omitted)
        or counts["distinct_parents"] != len(included) + len(omitted)
        or m["included_parents"] != len(included)
        or m["omitted_parents"] != len(omitted)
        or type(budget["exact_llm_evidence_tokens"]) is not int
        or not 0 <= budget["exact_llm_evidence_tokens"] <= budget["reserved_block_tokens"] <= 128000
        or m["exact_tokens"] != budget["exact_llm_evidence_tokens"]
        or any(o["partial_parent_returned"] is not False for o in case["omitted"])
    ):
        raise ArtifactError("COMPLETION_ATOMIC_ACCOUNTING_MISMATCH")
    groups = measurement["group_outcomes"]
    if {g["group_id"] for g in groups} != set(
        question["mandatory_evidence_group_ids"]
    ) or measurement["required_groups"] != len(groups):
        raise ArtifactError("COMPLETION_LABEL_DENOMINATOR_MISMATCH")
    unsupported = question["answerability"] == "UNSUPPORTED"
    if unsupported:
        if (
            groups
            or m["delivered_groups"] is not None
            or m["complete_question"] is not None
            or measurement["retrieval"]["complete_groups"] is not None
        ):
            raise ArtifactError("UNSUPPORTED_FALSE_POSITIVE_DENOMINATOR")
    elif (
        m["delivered_groups"] != sum(g["included"] for g in groups)
        or m["complete_question"] != all(g["included"] for g in groups)
        or measurement["retrieval"]["parent_located_groups"]
        != sum(g["parent_located"] for g in groups)
        or measurement["retrieval"]["complete_groups"]
        != sum(g["direct_witness_discovered"] for g in groups)
    ):
        raise ArtifactError("COMPLETION_GROUP_ACCOUNTING_MISMATCH")


def load_completed(root):
    data = load_expanded(root)
    store = data["store"]
    for row in data["records"].values():
        row["target"] = row["frozen"]
        row["completion"] = None
    observed = []
    for path in sorted((store.root / "data/evals/benchmark-completion").glob("*/MANIFEST.json")):
        name = path.relative_to(store.root).as_posix()
        try:
            manifest = store.manifest(name, schema="benchmark-completion-manifest-1.0")
            if (
                manifest.get("status") != "COMPLETED_SEALED_PENDING_OWNER_REVIEW"
                or manifest.get("expanded_benchmark_manifest_sha256") != MANIFEST_SHA
                or manifest.get("configuration") != CONFIGURATION
            ):
                raise ArtifactError("INCOMPATIBLE_COMPLETION_MANIFEST")
            for n, h in manifest["input_bindings"].items():
                store.bind(n, h)
            base = path.parent.relative_to(store.root).as_posix()
            review_ref = report_ref = None
            review_path = path.parent / "REVIEW_MANIFEST.json"
            if review_path.exists():
                review_name = base + "/REVIEW_MANIFEST.json"
                review = store.manifest(review_name, schema="benchmark-completion-review-manifest-1.0")
                if (review.get("status") != "TECHNICALLY_VERIFIED_PENDING_OWNER_REVIEW"
                        or review.get("measurement_manifest_sha256") != store.verified[name]):
                    raise ArtifactError("COMPLETION_REVIEW_BINDING_MISMATCH")
                review_ref = store.reference(review_name)
                report_ref = store.reference(base + "/REPORT.md")
            results = store.json(base + "/RESULTS.json")
            if results.get("schema") != "benchmark-completion-results-1.0":
                raise ArtifactError("WRONG_COMPLETION_RESULTS")
            ids = [r["question_id"] for r in results["questions"]]
            if len(ids) != len(set(ids)) or set(ids) != set(data["records"]):
                raise ArtifactError("INCOMPLETE_COMPLETION_INVENTORY")
            # Existing accepted contract only: no workers, queries or source reconstruction on refresh.
            from tools.evidence.contract import M7_SELECTOR, M7_SHA, validate_candidates
            from tools.retrieval.contract import load_release

            release, _, inventory = load_release(store.root, M7_SELECTOR, M7_SHA)
            pending = []
            for measurement in results["questions"]:
                qid = measurement["question_id"]
                row = data["records"][qid]
                if measurement["status"] == "BLOCKED":
                    pending.append((row, measurement, None))
                    continue
                result = store.json(base + f"/m7/{qid}.json")
                case = store.json(base + f"/m8/{qid}.json")
                validate_candidates(result, release, inventory)
                validate_measurement(row["reference"], measurement, result, case)
                pending.append((row, measurement, case))
            # Atomic discovery: one invalid record rejects this publication, never half-mixes it.
            for row, measurement, case in pending:
                qid = row["question_id"]
                row["completion"] = measurement
                row["completion_report_ref"] = report_ref
                if case is None:
                    continue
                row["target"] = {
                    "retrieval": measurement["retrieval"],
                    "m8": measurement["m8"],
                    "prompt": row["frozen"]["prompt"] if row["frozen"] else None,
                    "prompt_ref": row["frozen"]["prompt_ref"] if row["frozen"] else None,
                }
                for family, values, budget, target_key, child in (
                    (
                        "BENCHMARK_COMPLETION",
                        measurement["retrieval"],
                        None,
                        "retrieval_measurements",
                        "m7",
                    ),
                    ("BENCHMARK_COMPLETION", measurement["m8"], 128000, "m8_measurements", "m8"),
                ):
                    row[target_key].append(
                        {
                            "question_id": qid,
                            "family": family,
                            "mode": "rrf_top30",
                            "top_k": 30,
                            "budget": budget,
                            "status": measurement["m8"]["measurement"],
                            "artifact_ref": store.reference(base + f"/{child}/{qid}.json"),
                            "experiment": base,
                            "method": measurement["scoring_method"]
                            + "; complete-parent delivery; no source authorization on refresh",
                            "version": "benchmark-completion-1.0",
                            "values": values,
                        }
                    )
            observed.append(
                {
                    "manifest_ref": store.reference(name),
                    "results_ref": store.reference(base + "/RESULTS.json"),
                    "report_ref": report_ref,
                    "review_ref": review_ref,
                    "summary": results["summary"],
                    "cohorts": results["cohorts"],
                }
            )
        except (ArtifactError, ValueError, TypeError, KeyError, OSError):
            data["rejected"].append(
                {
                    "artifact_id": store.ref_id(name),
                    "status": "UNAVAILABLE",
                    "reason": "UNSEALED_OR_INCOMPATIBLE_COMPLETION",
                }
            )
    # Keep the sealed historical plan unchanged; expose only a current read-only overlay.
    import copy

    data["historical_run_plan"] = data["run_plan"]
    data["run_plan"] = copy.deepcopy(data["run_plan"])
    for plan in data["run_plan"]["questions"]:
        row = data["records"][plan["question_id"]]
        if row["completion"] and row["completion"]["status"] == "COMPLETE":
            plan["candidate_inputs"] = "VERIFIED_RRF30_RESULT_AVAILABLE_IN_COMPLETION_PUBLICATION"
            plan["historical_evidence_state"] = "ACTUAL_RRF30_128K_MEASUREMENT_AVAILABLE; FRESH_M8_REVALIDATION_REQUIRED_BEFORE_GENERATION"
            plan["blockers"] = [b for b in plan["blockers"] if b not in {
                "RRF30_128K_M8_MEASUREMENT_AND_PACKAGE_NOT_AVAILABLE",
                "REQUIRED_NATIVE_TOP50_RRF30_INPUTS_NOT_AVAILABLE"}]
            plan["eligible_for_execution_now"] = False
    data["completion_publications"] = observed
    data["summary"]["M8_target_evaluated_questions"] = sum(
        r["target"] is not None for r in data["records"].values()
    )
    for cohort in data["cohorts"]:
        count = sum(
            r["target"] is not None
            for r in data["records"].values()
            if r["reference"]["cohort_id"] == cohort["cohort_id"]
        )
        cohort["M8 target config"] = str(count) if count else "UNAVAILABLE"
    return data


def filter_completed(data, **filters):
    # Reuse the existing filter contract, presenting the target projection only to that function.
    from .expanded_adapter import filter_questions

    view = dict(data)
    view["records"] = {q: r | {"frozen": r["target"]} for q, r in data["records"].items()}
    return filter_questions(view, **filters)
