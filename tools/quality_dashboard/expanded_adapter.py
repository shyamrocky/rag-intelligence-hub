"""Expanded reference-layer dashboard. Reads records; never executes a RAG stage."""
import hashlib
from collections import Counter

from .adapter import (
    FREEZE,
    normalize_attempt,
)
from .adapter import (
    load_dashboard as load_frozen,
)
from .artifacts import ArtifactError, digest

MANIFEST = "data/evals/expanded-benchmark/v1/MANIFEST.json"
MANIFEST_SHA = "dfddd4e1079c1de3d3dd637db1386f4b5638f594fd0d7cca590f974ef97119fe"
BENCHMARK = "data/evals/expanded-benchmark/v1/EXPANDED_BENCHMARK.json"
HOLDOUT = "data/evals/intersection-selection/holdout-v1"
COHORT_FILTERS = {"All Questions": None, "Original Difficult": "A", "NLP": "B",
                  "Original Remaining": "C", "Abstention": "D"}
TARGET = {"mode": "hybrid", "top_k": 30, "candidate_depth": 50, "rrf_k": 60, "filters": {}}
NOT_MEASURED = "NOT_MEASURED — M8 EXPERIMENT NOT AVAILABLE"


def validate_reference(value):
    if (value.get("schema") != "expanded-benchmark-reference-1.0"
            or value.get("dataset_id") != "expanded-benchmark-v1"):
        raise ArtifactError("WRONG_EXPANDED_BENCHMARK")
    rows = value.get("questions", [])
    ids = [r["question_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ArtifactError("DUPLICATE_QUESTION_ID")
    expected = value["summary"]
    if dict(Counter(r["cohort_id"] for r in rows)) != expected["cohorts"]:
        raise ArtifactError("COHORT_ACCOUNTING_MISMATCH")
    for row in rows:
        if (row["reconciliation_status"] != "RECONCILED_EXACT_ID_AND_BYTES"
                or hashlib.sha256(row["question_text"].encode()).hexdigest() != row["question_text_sha256"]):
            raise ArtifactError("QUESTION_RECONCILIATION_REQUIRED")
        unsupported = row["answerability"] == "UNSUPPORTED"
        if unsupported != (row["cohort_id"] == "D") or unsupported == bool(row["mandatory_evidence_group_ids"]):
            raise ArtifactError("ANSWERABILITY_LABEL_MISMATCH")
    return {r["question_id"]: r for r in rows}


def _measurement(store, qid, family, mode, top_k, budget, source, values, method):
    return {"question_id": qid, "family": family, "mode": mode, "top_k": top_k,
            "budget": budget, "unit": "BGE evidence tokens" if budget else "retrieval candidates",
            "status": "REUSED_HISTORICAL", "artifact_ref": store.reference(source),
            "experiment": source.rsplit("/", 1)[0], "method": method,
            "version": family, "values": values}


def load_expanded(root):
    frozen = load_frozen(root)
    store = frozen["store"]
    store.manifest(MANIFEST, expected=MANIFEST_SHA, schema="expanded-benchmark-manifest-1.0")
    reference = store.json(BENCHMARK)
    for name, fingerprint in reference["input_bindings"].items():
        store.bind(name, fingerprint)
    questions = validate_reference(reference)
    records = {qid: {"question_id": qid, "question": q["question_text"], "reference": q,
                     "group_ids": q["mandatory_evidence_group_ids"], "retrieval_measurements": [],
                     "m8_measurements": [], "frozen": frozen["records"].get(qid),
                     "attempts": [], "latest": None, "diagnoses": []}
               for qid, q in questions.items()}
    original_path = "data/evals/m9/runs/m9-v3/RESULTS.json"
    original = store.json(original_path)
    for case in original["cases"]:
        qid = case["question_id"]
        row = records[qid]
        metrics = case["retrieval"]
        if metrics["required_group_denominator"] != len(row["group_ids"]):
            raise ArtifactError("ORIGINAL_GROUP_DENOMINATOR_MISMATCH")
        row["retrieval_measurements"].append(_measurement(store, qid, "M9_ORIGINAL_29",
            case["mode"], original["settings"]["top_k"], None, original_path, metrics,
            "Saved M9 metrics: direct-positive-group hits use historical overlap semantics; "
            "not a new strict joint-witness score. Parent OR alternatives preserved."))
        for budget, measurement in case["budgets"].items():
            if measurement.get("live_native_parent_binding_validation") is not True:
                raise ArtifactError("UNVERIFIED_M8_HISTORICAL_RECEIPT")
            row["m8_measurements"].append(_measurement(store, qid, "M9_ORIGINAL_29",
                case["mode"], original["settings"]["top_k"], int(budget), original_path,
                measurement, "Actual accepted M8 assembly/replay; historical configuration only"))
    selection_path = "data/evals/rrf-supplementation/experiment-v1/RESULTS.json"
    selection = store.json(selection_path)
    for qid, q in selection["questions"].items():
        for strategy, values in q["strategies"].items():
            records[qid]["retrieval_measurements"].append(_measurement(store, qid,
                "FROZEN_15_STRICT_WITNESSES", strategy, values["candidate_count"], None,
                selection_path, values, "Saved approved OR / joint-AND direct-witness and parent-location outcomes"))
    delivered_path = "data/evals/m8-delivery/experiment-v1/RESULTS.json"
    delivered = store.json(delivered_path)
    for values in delivered["metrics"]:
        qid, arm, budget = values["question_id"], values["arm"], values["budget"]
        case_path = f"data/evals/m8-delivery/experiment-v1/cases/{qid}-{arm}-{budget}.json"
        case = store.json(case_path)
        records[qid]["m8_measurements"].append(_measurement(store, qid, "FROZEN_15_M8",
            {"A": "rrf_top10", "B": "rrf_top30", "C": "supplementation_stage1"}[arm],
            values["candidate_count"], budget, case_path,
            values | {"M8_package_sha256": case["M8_package_sha256"]},
            "Saved complete-parent delivery; C uses private processing-order adapter, not production-equivalent M8"))
    holdout_path = HOLDOUT + "/RESULTS.json"
    holdout = store.json(holdout_path)
    for qid, result in holdout.items():
        if result["question"] != questions[qid]["question_text"]:
            raise ArtifactError("HOLDOUT_QUESTION_MISMATCH")
        for strategy, values in result["strategies"].items():
            records[qid]["retrieval_measurements"].append(_measurement(store, qid,
                "TWO_QUESTION_HOLDOUT", strategy, values["candidates"], None, holdout_path,
                values, "Saved strict direct-witness / parent-location holdout; no new scoring"))
    # Existing Q05 history and qualification receipts remain exact objects/measurements.
    for qid, old in frozen["records"].items():
        records[qid]["attempts"] = list(old["attempts"])
        records[qid]["latest"] = old["latest"]
        records[qid]["diagnoses"] = old["diagnoses"]
    rejected = []
    discover_expanded_generation(store, records, questions, rejected)
    discover_expanded_validations(store, records, rejected)
    from .attempts import merge_native, totals
    merge_native(root, records, store, rejected)
    completed = [r["latest"] for r in records.values() if r["latest"]]
    summary = {"questions": len(records),
        "answerable": sum(r["reference"]["answerability"] != "UNSUPPORTED" for r in records.values()),
        "unsupported": sum(r["reference"]["answerability"] == "UNSUPPORTED" for r in records.values()),
        "mandatory_groups": sum(len(r["group_ids"]) for r in records.values()),
        "M7_evaluated_questions": sum(bool(r["retrieval_measurements"]) for r in records.values()),
        "M8_evaluated_questions_any_configuration": sum(bool(r["m8_measurements"]) for r in records.values()),
        "M8_target_evaluated_questions": sum(r["frozen"] is not None for r in records.values()),
        "generation_completed": len(completed), "pending_generation": len(records) - len(completed),
        "post_checked": sum(a["validation"] is not None for a in completed),
        "semantic_review_status": "PENDING_REVIEW", "independently_validated_answers": 0,
        **totals(records)}
    cohorts = []
    for cohort in sorted({q["cohort_id"] for q in questions.values()}):
        selected = [r for r in records.values() if r["reference"]["cohort_id"] == cohort]
        cohorts.append({"cohort_id": cohort, "cohort_label": selected[0]["reference"]["cohort_label"],
            "Questions": len(selected), "M7 evaluated": sum(bool(r["retrieval_measurements"]) for r in selected),
            "M8 evaluated (any historical config)": sum(bool(r["m8_measurements"]) for r in selected),
            "M8 target config": str(sum(r["frozen"] is not None for r in selected)) if any(r["frozen"] for r in selected) else "UNAVAILABLE",
            "Generated": sum(r["latest"] is not None for r in selected),
            "Post-validated (deterministic checks)": sum(bool(r["latest"] and r["latest"]["validation"]) for r in selected)})
    return {"schema": "expanded-quality-telemetry-1.0", "records": records, "summary": summary,
            "cohorts": cohorts, "references": store.references, "store": store, "rejected": rejected,
            "frozen_data": frozen, "reference": reference,
            "run_plan": store.json("data/evals/expanded-benchmark/v1/GENERATION_RUN_PLAN.json"),
            "reference_ref": store.reference(BENCHMARK),
            "remaining_report": store.json("data/evals/expanded-benchmark/v1/ORIGINAL_REMAINING_RRF10.json"),
            "precision": frozen["precision"], "refresh_executes_pipeline": False}


def filter_questions(data, *, cohort="All Questions", generation="All", evaluation="All", answerability="All"):
    if cohort not in COHORT_FILTERS or generation not in {"All", "COMPLETED", "NOT_RUN", "FAILED_ONLY"}:
        raise ArtifactError("INVALID_DASHBOARD_FILTER")
    if evaluation not in {"All", "M7 available", "M8 available", "Target M8 available", "Target M8 not measured"}:
        raise ArtifactError("INVALID_EVALUATION_FILTER")
    if answerability not in {"All", "Answerable", "Unsupported"}:
        raise ArtifactError("INVALID_ANSWERABILITY_FILTER")
    selected = []
    for qid, row in data["records"].items():
        ref = row["reference"]
        if COHORT_FILTERS[cohort] and ref["cohort_id"] != COHORT_FILTERS[cohort]:
            continue
        if generation == "COMPLETED" and not row["latest"]:
            continue
        if generation == "NOT_RUN" and row["attempts"]:
            continue
        if generation == "FAILED_ONLY" and (not row["attempts"] or row["latest"]):
            continue
        if answerability == "Answerable" and ref["answerability"] == "UNSUPPORTED":
            continue
        if answerability == "Unsupported" and ref["answerability"] != "UNSUPPORTED":
            continue
        if evaluation == "M7 available" and not row["retrieval_measurements"]:
            continue
        if evaluation == "M8 available" and not row["m8_measurements"]:
            continue
        if evaluation == "Target M8 available" and not row["frozen"]:
            continue
        if evaluation == "Target M8 not measured" and row["frozen"]:
            continue
        selected.append(qid)
    return selected


def discover_expanded_generation(store, records, questions, rejected):
    """Reuse the existing generation normalizer after binding new source-free preparation audits."""
    seen = {a["audit"].get("response_id") or a["experiment"] for r in records.values() for a in r["attempts"]}
    known = {a["experiment"] for r in records.values() for a in r["attempts"]}
    for path in sorted((store.root / "data/evals/generation").glob("*/MANIFEST.json")):
        parent = path.parent.relative_to(store.root).as_posix()
        if parent in known:
            continue
        name = path.relative_to(store.root).as_posix()
        try:
            manifest = store.manifest(name)
            if manifest.get("schema") != "quality-generation-experiment-1.0":
                continue
            if manifest.get("expanded_benchmark_manifest_sha256") != MANIFEST_SHA:
                raise ArtifactError("EXPANDED_QUESTION_BINDING_REQUIRED")
            qid = manifest["question_id"]
            if qid not in records:
                raise ArtifactError("UNKNOWN_EXPANDED_QUESTION")
            for input_name, fingerprint in manifest.get("input_bindings", {}).items():
                store.bind(input_name, fingerprint)
            prep = store.json(parent + "/PREPARATION_AUDIT.json")
            m7 = store.json(parent + "/M7_RESULT.json")
            audit = store.json(parent + "/GENERATION_AUDIT.json")
            validate_future_binding(store, questions[qid], prep, m7, audit)
            case = {"M8_package_sha256": prep["M8_package_sha256"],
                    "actual_M8_included_parent_ids": prep["included_parent_ids"]}
            question_view = {q: {"question": r["question_text"]} for q, r in questions.items()}
            attempt = normalize_attempt(store, name, manifest, question_view, {(qid, "B", 128000): case})
            identity = attempt["audit"].get("response_id") or name
            if identity in seen:
                continue
            seen.add(identity)
            attempt["preparation_audit"] = prep
            attempt["configuration_id"] = digest({"retrieval": m7["parameters"], "model": audit["model"],
                "prompt": audit["prompt_template"], "M8_package": prep["M8_package_sha256"]})
            records[qid]["attempts"].append(attempt)
        except (ArtifactError, KeyError, ValueError, TypeError, OSError):
            rejected.append({"artifact_id": store.ref_id(name), "status": "UNAVAILABLE",
                             "reason": "UNSEALED_OR_INCOMPATIBLE_EXPANDED_GENERATION"})
    for row in records.values():
        completed = [a for a in row["attempts"] if a["completed"]]
        if completed:
            row["latest"] = max(completed, key=lambda a: (a["timestamp_or_version"], a["experiment"]))


def validate_future_binding(store, question, prep, m7, audit):
    from tools.evidence.contract import M7_SELECTOR, M7_SHA, validate_candidates
    from tools.retrieval.contract import load_release

    if not hasattr(store, "_expanded_m7_contract"):
        release, _, inventory = load_release(store.root, M7_SELECTOR, M7_SHA)
        store._expanded_m7_contract = (release, inventory)
    release, inventory = store._expanded_m7_contract
    validate_candidates(m7, release, inventory)
    if (prep.get("schema") not in {"prompt-quality-gate-3.0", "prompt-quality-gate-3.1"}
            or prep.get("source_integrity") != "LIVE_M8_VALIDATED"
            or prep.get("question_sha256") != question["question_text_sha256"]
            or prep.get("M8_package_sha256") != audit.get("M8_package_sha256")
            or prep.get("request_sha256") != audit.get("neutral_request_sha256")
            or prep.get("M7_result_sha256") != digest(m7)
            or m7.get("query_sha256") != hashlib.sha256(question["question_text"].strip().encode()).hexdigest()
            or m7.get("parameters") != {k: v for k, v in TARGET.items() if k != "mode"}
            or m7.get("retrieval_mode") != TARGET["mode"]
            or prep.get("M8_BGE_budget", {}).get("limit") != 128000
            or prep.get("M8_BGE_budget", {}).get("truncation") is not False):
        raise ArtifactError("FUTURE_QUESTION_CONFIGURATION_PACKAGE_MISMATCH")
    ids = prep.get("included_parent_ids")
    if (not isinstance(ids, list) or len(ids) != len(set(ids)) or not ids
            or len(ids) != prep.get("M8_counts", {}).get("selected_parents")):
        raise ArtifactError("INVALID_PREPARATION_PARENT_SCOPE")
    # Compare the source-free receipt to the accepted explicit chain, never trust an ID alone.
    baseline = store.json("data/evals/prompt-assembly/experiment-v1/audits/M9-Q05.json")
    if (prep.get("source_selections") != baseline["source_selections"]
            or prep.get("M7_release") != baseline["M7_release"]
            or prep.get("M8_release") != baseline["M8_release"]
            or prep.get("template_version") != audit.get("prompt_template")
            or prep.get("response_schema_version") != audit.get("response_schema")
            or audit.get("context_fit", {}).get("fits") is not True
            or audit.get("token_count_receipt", {}).get("request_sha256") != audit.get("request_sha256")
            or audit.get("settings", {}).get("model") != audit.get("model")
            or type(audit.get("generator_input_tokens")) is not int
            or audit.get("generator_input_tokens", -1) <= 0
            or audit.get("token_count_receipt", {}).get("input_tokens") != audit.get("generator_input_tokens")
            or audit.get("token_count_receipt", {}).get("method") != "OPENAI_RESPONSES_INPUT_TOKENS"
            or audit.get("context_fit", {}).get("input_tokens") != audit.get("generator_input_tokens")):
        raise ArtifactError("FUTURE_RELEASE_OR_REQUEST_QUALIFICATION_MISMATCH")


def discover_expanded_validations(store, records, rejected):
    """Same existing deterministic receipt schema; expanded identity is an extra binding."""
    from .adapter import valid_validation_shape

    # Reuse accepted original-15 receipts directly, then inspect new expanded receipts.
    for path in sorted((store.root / "data/evals/post-generation").glob("*/MANIFEST.json")):
        name = path.relative_to(store.root).as_posix()
        try:
            manifest = store.manifest(name)
            if manifest.get("expanded_benchmark_manifest_sha256") != MANIFEST_SHA:
                continue
            if (manifest.get("schema") != "post-generation-validation-manifest-1.0"
                    or manifest.get("status") != "COMPLETED_SEALED"
                    or manifest.get("dataset_freeze_manifest_sha256") != FREEZE):
                raise ArtifactError("INVALID_EXPANDED_VALIDATION")
            for input_name, fingerprint in manifest["input_bindings"].items():
                store.bind(input_name, fingerprint)
            result_name = str(path.parent.relative_to(store.root) / "VALIDATION.json")
            result = store.json(result_name)
            if (not valid_validation_shape(result) or result.get("fully_validated") is not False
                    or result.get("semantic_status") not in {"PENDING_REVIEW", "UNAVAILABLE"}):
                raise ArtifactError("UNQUALIFIED_EXPANDED_VALIDATION")
            matches = [a for a in records[result["question_id"]]["attempts"] if a["completed"]
                       and a["response_file_sha256"] == result["response_file_sha256"]
                       and a["audit"]["M8_package_sha256"] == result["M8_package_sha256"]]
            if not matches:
                raise ArtifactError("UNBOUND_VALIDATION_RESPONSE")
            for attempt in matches:
                attempt["validation"] = result | {"artifact_ref": store.reference(result_name)}
        except (ArtifactError, KeyError, ValueError, TypeError, OSError):
            rejected.append({"artifact_id": store.ref_id(name), "status": "UNAVAILABLE",
                             "reason": "UNSEALED_OR_INCOMPATIBLE_EXPANDED_VALIDATION"})
