"""Normalize sealed measurements. Hash checks do not authorize publisher evidence."""
import math
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .artifacts import ArtifactError, Store, digest, safe_path, sha

VERSION = "quality-telemetry-1.0"
FREEZE = "e287a5f5fe9156720ff76421ba2742952afedfa050c0b9fda99f8df57113afa6"
BASES = {
    "freeze": ("data/evals/ranking/dataset-v1/FREEZE_MANIFEST.json", FREEZE),
    "phase2": ("data/evals/ranking/phase2-v1/PHASE2_MANIFEST.json",
               "7bdc29b463f1c6909f4881d29359dd6cff6ab23856f9d69aebeb40b6d3b99a58"),
    "ranking": ("data/evals/ranking/phase3-experiment-v1/EXPERIMENT_MANIFEST.json",
                "d4147705c4c648e29ef8a806a5e77345925b0d2d4827d94edd79bdee5dc057d9"),
    "selection": ("data/evals/rrf-supplementation/experiment-v1/EXPERIMENT_MANIFEST.json",
                  "116092b32e8da279eaa0dc2abd1cd93ac622d879f170ef3247f7de649ef21e74"),
    "delivery": ("data/evals/m8-delivery/experiment-v1/EXPERIMENT_MANIFEST.json",
                 "f1c718a89bfe4830e3b9e840ccf8f02016120c30cd0e7d046ca4fc34ae465e42"),
    "prompt": ("data/evals/prompt-assembly/experiment-v1/EXPERIMENT_MANIFEST.json",
               "d3593231d6453f2251dfec14cf2ff84bba2bafa7a2c02d34e45985deb2483abe"),
    "candidates": ("data/evals/pre-generation-gate/experiment-v1/EXPERIMENT_MANIFEST.json",
                   "51689a136f965be4f5f73541c4d86b7146cd99529a1c6978b7127901796597f6"),
    "qualification": ("data/evals/qualification-disclosure/successor-v1/MANIFEST.json",
                      "d27bd86fe627629b35ee546680c4a92e99edf6dd8b3572f25f141ff0e578bb19"),
    "explorer": ("data/visualizations/retrieval-pipeline-explorer-v1/OUTPUT_MANIFEST.json",
                 "6350defbdeee60b151b467dcaa5002b0abf9b5f291e1a85556f1f7a35b172838"),
}
GENERATION_SCHEMAS = {"funded-one-question-generation-manifest-1.0",
                      "quality-generation-experiment-1.0", "one-live-generation-experiment-manifest-1.0"}
STATUSES = {"MEASURED", "REUSED_HISTORICAL", "NOT_RUN", "UNAVAILABLE", "PENDING_REVIEW",
            "FAILED", "INDETERMINATE"}


def metric(store, name, value, source, experiment, method, *, status="REUSED_HISTORICAL",
           numerator=None, denominator=None, unit=None, version=None):
    if status not in STATUSES:
        raise ArtifactError("INVALID_MEASUREMENT_STATUS")
    if denominator is not None and (type(denominator) is not int or denominator <= 0):
        raise ArtifactError("INVALID_DENOMINATOR")
    if numerator is not None and (type(numerator) is not int or numerator < 0
                                  or (denominator is not None and numerator > denominator)):
        raise ArtifactError("INVALID_NUMERATOR")
    return {"name": name, "value": value, "numerator": numerator, "denominator": denominator,
            "unit": unit, "status": status, "artifact_ref": store.reference(source),
            "experiment": experiment, "method": method, "version": version or experiment}


def normalize_attempt(store, manifest_name, manifest, questions, deliveries):
    """Read only known audit/answer fields, never the raw provider response or prompt."""
    if manifest.get("schema") not in GENERATION_SCHEMAS:
        raise ArtifactError("UNSUPPORTED_GENERATION_SCHEMA")
    if manifest.get("schema") == "quality-generation-experiment-1.0":
        if (manifest.get("status") != "COMPLETED_SEALED"
                or manifest.get("dataset_freeze_manifest_sha256") != FREEZE):
            raise ArtifactError("UNSEALED_OR_INCOMPATIBLE_GENERATION")
    elif not manifest.get("status", "").startswith(("TECHNICAL_", "SINGLE_", "EXPERIMENT_COMPLETED_")):
        raise ArtifactError("UNSEALED_GENERATION")
    qid = manifest.get("question_id")
    if qid not in questions:
        raise ArtifactError("UNKNOWN_GENERATION_QUESTION")
    parent = str(Path(manifest_name).parent)
    audit_name = parent + "/GENERATION_AUDIT.json"
    audit = store.json(audit_name)
    if audit.get("schema") != "generation-result-1.0" or not audit.get("generation_executed"):
        raise ArtifactError("NOT_A_GENERATION_ATTEMPT")
    case = deliveries[(qid, "B", 128000)]
    if audit.get("M8_package_sha256") != case["M8_package_sha256"]:
        raise ArtifactError("GENERATION_PACKAGE_CONFIGURATION_MISMATCH")
    if audit.get("source_integrity") != "LIVE_M8_VALIDATED":
        raise ArtifactError("GENERATION_SOURCE_BINDING_UNVERIFIED")
    review_name = parent + "/POSTSEALED_VALIDATION_AND_REVIEW.json"
    review = store.json(review_name) if review_name in store.verified else None
    response_name = parent + "/GENERATED_RESPONSE.json"
    complete = (audit.get("response_status") == "completed"
                and audit.get("status", "").startswith("GENERATED_")
                and response_name in store.verified)
    response = store.json(response_name) if complete else None
    if response:
        from tools.pre_generation_gate.response_v2 import validate_response_shape

        response = validate_response_shape(response, authorized_unit_ids=set(
            case["actual_M8_included_parent_ids"])).model_dump()
        if audit.get("response_schema") != "grounded-response-2.0":
            raise ArtifactError("UNSUPPORTED_GENERATION_RESPONSE_SCHEMA")
    for field in ("model", "prompt_template", "response_schema", "request_sha256"):
        if not isinstance(audit.get(field), str) or not audit[field]:
            raise ArtifactError("MISSING_GENERATION_CONFIGURATION")
    if (audit["prompt_template"] not in {"grounded-generation-prompt-v2", "grounded-generation-prompt-v2.1"}
            or audit["response_schema"] != "grounded-response-2.0"):
        raise ArtifactError("UNQUALIFIED_PROMPT_SCHEMA_PAIR")
    usage = audit.get("usage", {})
    validate_usage_fields(usage)
    if usage.get("usage_status") == "MEASURED_API_USAGE":
        counts = [usage.get(k) for k in ("input_tokens", "output_tokens", "total_tokens")]
        if (any(type(x) is not int or x < 0 for x in counts)
                or counts[0] + counts[1] != counts[2]):
            raise ArtifactError("GENERATION_TOKEN_RECONCILIATION_FAILED")
    evidence_ids = sorted({u for c in response["claims"] for u in c["evidence_unit_ids"]}) \
        if response else []
    return {"experiment": parent, "manifest_ref": store.reference(manifest_name),
            "audit_ref": store.reference(audit_name), "question_id": qid,
            "status": "REUSED_HISTORICAL" if complete else "FAILED", "completed": complete,
            "response": response, "response_ref": store.reference(response_name) if response else None,
            "response_file_sha256": store.verified.get(response_name),
            "audit": audit, "usage": usage, "cited_parent_ids": evidence_ids,
            "engineering_review": review,
            "engineering_review_ref": store.reference(review_name) if review else None,
            "supplied_parents": len(case["actual_M8_included_parent_ids"]),
            "timestamp_or_version": manifest.get("date", parent),
            "question_sha256": digest(questions[qid]["question"]), "validation": None}


def load_dashboard(root):
    """All refreshes are artifact reads only; no inference, retrieval or live M8 work."""
    store = Store(root)
    manifests = {key: store.manifest(path, expected=expected)
                 for key, (path, expected) in BASES.items()}
    source = store.json("data/evals/ranking/phase2-v1/SOURCE_INTEGRITY_RECEIPT.json")
    for name, fingerprint in (source["accepted_M7_files"]
                              | source["live_M8_M4_M3_Unified_binding_files"]).items():
        store.bind(name, fingerprint)
    dataset = store.json("data/evals/ranking/dataset-v1/FROZEN_DATASET.json")
    questions = {q["question_id"]: q for q in dataset["questions"]}
    groups = {label["question_id"]: [g["group_id"] for g in label["required_evidence_groups"]]
              for label in dataset["labels"]}
    if (len(questions) != dataset["question_count"] or set(groups) != set(questions)
            or any(dataset["effective_owner_status_by_question"][q] != "OWNER_APPROVED"
                   for q in questions)):
        raise ArtifactError("FROZEN_DATASET_ACCOUNTING_FAILED")
    selection_path = "data/evals/rrf-supplementation/experiment-v1/RESULTS.json"
    selection = store.json(selection_path)
    measured_path = "data/evals/m8-delivery/experiment-v1/RESULTS.json"
    delivery = store.json(measured_path)
    deliveries = {}
    delivery_metrics = {}
    for row in delivery["metrics"]:
        qid, arm, budget = row["question_id"], row["arm"], row["budget"]
        key = (qid, arm, budget)
        if key in delivery_metrics or qid not in questions:
            raise ArtifactError("DUPLICATE_OR_UNKNOWN_DELIVERY")
        case_path = f"data/evals/m8-delivery/experiment-v1/cases/{qid}-{arm}-{budget}.json"
        case = store.json(case_path)
        if (case["question_id"] != qid or case["counts"]["selected_parents"] != row["included_parents"]
                or case["budget_accounting"]["exact_llm_evidence_tokens"] != row["exact_tokens"]
                or {g["group_id"] for g in row["group_outcomes"]} != set(groups[qid])
                or sum(g["included"] for g in row["group_outcomes"]) != row["delivered_groups"]):
            raise ArtifactError("DELIVERY_METRIC_RECONCILIATION_FAILED")
        deliveries[key], delivery_metrics[key] = case, row
    ranking = store.json("data/evals/ranking/phase3-experiment-v1/PER_QUESTION_RESULTS.json")
    ranking = {row["question_id"]: row for row in ranking}
    records = {}
    for qid, question in questions.items():
        selected = selection["questions"][qid]
        if selected["question"] != question["question"]:
            raise ArtifactError("QUESTION_BINDING_MISMATCH")
        native = selected["strategies"]["rrf_top30"]
        m8 = delivery_metrics[(qid, "B", 128000)]
        case = deliveries[(qid, "B", 128000)]
        if native["selected_chunk_ids"] != case["considered_chunk_ids"]:
            raise ArtifactError("RRF_DELIVERY_INPUT_MISMATCH")
        if {g["group_id"] for g in native["groups"]} != set(groups[qid]):
            raise ArtifactError("EVIDENCE_GROUP_BINDING_MISMATCH")
        prompt_path = f"data/evals/prompt-assembly/experiment-v1/audits/{qid}.json"
        prompt = store.json(prompt_path)
        if (prompt["M8_package_sha256"] != case["M8_package_sha256"]
                or prompt["M7_result_sha256"] != case["candidate_envelope_sha256"]):
            raise ArtifactError("PROMPT_PACKAGE_BINDING_MISMATCH")
        result_name = f"data/evals/pre-generation-gate/experiment-v1/candidates/{qid}.json"
        actual_result = store.json(result_name)
        if digest(actual_result) != case["candidate_envelope_sha256"]:
            raise ArtifactError("M7_CANDIDATE_RESULT_CHANGED")
        metrics = [metric(store, "M7 direct-witness groups", native["complete_groups"],
                          selection_path, "rrf_top30", "Approved OR / joint-AND direct witnesses",
                          numerator=native["complete_groups"], denominator=len(groups[qid])),
                   metric(store, "M7 parent-located groups", native["parent_located_groups"],
                          selection_path, "rrf_top30", "Approved supporting parent located",
                          numerator=native["parent_located_groups"], denominator=len(groups[qid])),
                   metric(store, "M8 delivered groups", m8["delivered_groups"], measured_path,
                          "RRF-30 / M8-128000", "Complete approved parent included",
                          numerator=m8["delivered_groups"], denominator=len(groups[qid])),
                   metric(store, "M8 evidence tokens", m8["exact_tokens"],
                          f"data/evals/m8-delivery/experiment-v1/cases/{qid}-B-128000.json",
                          "RRF-30 / M8-128000", "m8-atomic-bge-json-1.0", unit="BGE tokens")]
        records[qid] = {"question_id": qid, "question": question["question"],
                        "category": question.get("category", "NATURAL_LANGUAGE"), "group_ids": groups[qid],
                        "retrieval": native, "m8": m8, "m8_case": case,
                        "prompt": prompt, "prompt_ref": store.reference(prompt_path),
                        "ranking_metrics": ranking[qid], "metrics": metrics,
                        "retrieval_parameters": actual_result["parameters"],
                        "attempts": [], "latest": None, "diagnoses": []}
        for group in m8["group_outcomes"]:
            if not group["included"]:
                category = "EVIDENCE_ASSEMBLY_LOSS" if group["parent_located"] else "RETRIEVAL_GAP"
                records[qid]["diagnoses"].append({"category": category, "group_id": group["group_id"],
                                                "basis": group["delivery_attribution"],
                                                "artifact_ref": metrics[2]["artifact_ref"]})
    rejected, attempts, seen = [], [], set()
    root = store.root
    known_generation = {
        "data/evals/generation/live-q05-funded-v1/MANIFEST.json":
            "3077d9d502dfdab16791ce85f2b1ab432ef8c0e8f39e2f5874dce36c279297f8",
        "data/evals/generation/live-q05-v1/MANIFEST.json":
            "7a94516c8b72bb21fba805231cbfa0ddeeb3b7e8304deab3c1aac0b96d3b3ac5",
    }
    for path in sorted((root / "data/evals/generation").glob("*/MANIFEST.json")):
        name = path.relative_to(root).as_posix()
        # Candidate unrecognized manifests remain unavailable, never parsed as measurements.
        try:
            header = store.manifest(name, expected=known_generation.get(name))
            if header.get("schema") not in GENERATION_SCHEMAS:
                continue
            attempt = normalize_attempt(store, name, header, questions, deliveries)
            identity = attempt["audit"].get("response_id") or store.verified[name]
            if identity in seen:
                continue
            seen.add(identity)
            attempts.append(attempt)
            records[attempt["question_id"]]["attempts"].append(attempt)
        except (ArtifactError, KeyError, TypeError, ValueError):
            rejected.append({"artifact_id": store.ref_id(name), "status": "UNAVAILABLE",
                             "reason": "UNSEALED_MALFORMED_OR_INCOMPATIBLE_GENERATION"})
    for row in records.values():
        complete = [a for a in row["attempts"] if a["completed"]]
        if complete:
            row["latest"] = max(complete, key=lambda a: (a["timestamp_or_version"],
                                                        a["experiment"]))
    qualification_path = "data/evals/qualification-disclosure/successor-v1/M9-Q05_ASSESSMENT.json"
    qualification = store.json(qualification_path)
    for row in records.values():
        for attempt in row["attempts"]:
            if (attempt["completed"] and
                    qualification["M8_package_sha256"] == attempt["audit"]["M8_package_sha256"] and
                    qualification["response_sha256"] == digest(attempt["response"])):
                attempt["qualification_review"] = qualification
                attempt["qualification_ref"] = store.reference(qualification_path)
    validations = discover_validations(store, records, rejected)
    successful = [row["latest"] for row in records.values() if row["latest"]]
    post = [a for a in successful if a["validation"]]
    measured = [a for a in successful if a["usage"].get("usage_status") == "MEASURED_API_USAGE"]
    costed = [a for a in measured if a["usage"].get("cost_status") == "ESTIMATED_API_COST"]
    summary = {"questions": len(questions), "groups": sum(map(len, groups.values())),
               "m7_direct_groups": sum(r["retrieval"]["complete_groups"] for r in records.values()),
               "m7_parent_groups": sum(r["retrieval"]["parent_located_groups"] for r in records.values()),
               "m8_groups": sum(r["m8"]["delivered_groups"] for r in records.values()),
               "m8_complete_questions": sum(r["m8"]["complete_question"] for r in records.values()),
               "generated_questions": len(successful), "validated_questions": len(post),
               "fully_validated_answers": sum(a["validation"].get("fully_validated") is True for a in post),
               "answer_statuses": dict(Counter(a["response"]["status"] for a in successful)),
               "input_tokens": sum(a["usage"]["input_tokens"] for a in measured),
               "output_tokens": sum(a["usage"]["output_tokens"] for a in measured),
               "measured_usage_questions": len(measured),
               "known_estimated_api_cost_usd": str(sum((Decimal(a["usage"]["total_estimated_cost_usd"])
                                                       for a in costed), Decimal(0))),
               "cost_measured_questions": len(costed),
               "average_generation_latency_ms": (sum(a["usage"]["latency_ms"] for a in measured)
                                                  / len(measured)) if measured else None,
               "failed_attempts": sum(not a["completed"] for a in attempts),
               "retrieval_evaluations": len(selection["aggregate"]),
               "delivery_evaluations": len(delivery["aggregate"])}
    enrich_metrics(store, records)
    summary_metrics = summarize_provenance(store, summary, records, selection_path, measured_path)
    original_m9 = load_original_m9(store)
    return {"schema": VERSION, "records": records, "summary": summary, "summary_metrics": summary_metrics, "original_m9": original_m9,
            "selection_comparison": selection["aggregate"], "budget_comparison": delivery["aggregate"],
            "references": store.references, "store": store, "rejected": rejected,
            "validation_experiments": validations,
            "current_prompt": manifests["qualification"]["current_prompt"],
            "current_response_schema": manifests["qualification"]["response_schema"],
            "precision": "UNAVAILABLE — INSUFFICIENT RELEVANCE LABELS",
            "ndcg": "UNAVAILABLE — NOT_MEASURED",
            "semantic_review": "PENDING_REVIEW", "refresh_executes_generation": False,
            "current_prompt_dry_run": store.json(
                "data/evals/qualification-disclosure/successor-v1/CURRENT_LOCAL_DRY_RUN.json")}


def discover_validations(store, records, rejected):
    found = []
    base = store.root / "data/evals/post-generation"
    if not base.exists():
        return found
    paths = list(base.glob("*/MANIFEST.json"))
    # Directory names are not chronology (v10 must not lose to v2).
    def chronology(path):
        from .artifacts import read_json

        try:
            return str(read_json(path).get("date", "")), path.name
        except ArtifactError:
            return "", path.name

    for path in sorted(paths, key=chronology):
        name = path.relative_to(store.root).as_posix()
        try:
            manifest = store.manifest(name, schema="post-generation-validation-manifest-1.0")
            if (manifest.get("status") != "COMPLETED_SEALED"
                    or manifest.get("dataset_freeze_manifest_sha256") != FREEZE):
                raise ArtifactError("INCOMPATIBLE_VALIDATION")
            for source, fingerprint in manifest["input_bindings"].items():
                store.bind(source, fingerprint)
            result_name = str(path.parent.relative_to(store.root) / "VALIDATION.json")
            value = store.json(result_name)
            if not valid_validation_shape(value):
                raise ArtifactError("INVALID_VALIDATION_SCHEMA")
            qid = value["question_id"]
            matched = [a for a in records[qid]["attempts"] if a["completed"] and
                       a["response_file_sha256"] == value["response_file_sha256"] and
                       a["audit"]["M8_package_sha256"] == value["M8_package_sha256"]]
            if not matched:
                raise ArtifactError("VALIDATION_RESPONSE_BINDING_MISMATCH")
            if value.get("semantic_status") not in {"PENDING_REVIEW", "UNAVAILABLE"}:
                # A new qualified semantic review needs its own reviewed adapter, not an invented score.
                raise ArtifactError("UNQUALIFIED_SEMANTIC_RECEIPT")
            if value.get("fully_validated") is not False:
                raise ArtifactError("UNSUPPORTED_FULL_VALIDATION_CLAIM")
            for attempt in matched:
                attempt["validation"] = value | {"artifact_ref": store.reference(result_name)}
            found.append(name)
        except (ArtifactError, KeyError, TypeError, ValueError):
            rejected.append({"artifact_id": store.ref_id(name), "status": "UNAVAILABLE",
                             "reason": "UNSEALED_MALFORMED_OR_INCOMPATIBLE_VALIDATION"})
    return found


def explorer_html(store):
    name = "data/visualizations/retrieval-pipeline-explorer-v1/RAG_Retrieval_Pipeline_Explorer.html"
    path = safe_path(store.root, name)
    if sha(path) != store.verified[name]:
        raise ArtifactError("EXPLORER_CHANGED")
    return path.read_text()


def load_original_m9(store):
    """Reuse the existing M9 verified-results reader, with its 29-question scope intact."""
    from tools.evaluation.results import load_results

    selector = "config/retrieval-evaluation-results-m9-v1.json"
    fingerprint = "f3420b4645ac8b37819a37750d1d9a33e74b7d1e828f7711eef14e573d868ece"
    store.bind(selector, fingerprint)
    value = load_results(store.root, expected_sha=fingerprint)
    selected = store.json(selector)
    store.bind(selected["manifest_path"], selected["manifest_sha256"])
    manifest = value["manifest"]
    for prefix in ("results", "analysis", "verification", "oversized", "configuration"):
        store.bind(manifest[prefix + "_path"], manifest[prefix + "_sha256"])
    return {"scope": {"questions": manifest["questions"], "answerable": manifest["answerable"],
                      "unsupported": manifest["unsupported"]},
            "summary": value["results"]["summary"],
            "per_question": [{"question_id": c["question_id"], "mode": c["mode"],
                              "retrieval": c["retrieval"]} for c in value["results"]["cases"]],
            "artifact_ref": store.reference(manifest["results_path"])}


def enrich_metrics(store, records):
    """Every displayed measurement retains its source, configuration and accounting method."""
    for qid, row in records.items():
        case = f"data/evals/m8-delivery/experiment-v1/cases/{qid}-B-128000.json"
        for field in ("candidate_count", "included_parents", "omitted_parents", "complete_question",
                      "individually_oversized_parents", "displaced_parents", "utilization"):
            row["metrics"].append(metric(store, "M8 " + field, row["m8"][field], case,
                                         "RRF-30 / M8-128000", "Copied sealed actual M8 measurement"))
        prompt = f"data/evals/prompt-assembly/experiment-v1/audits/{qid}.json"
        for field in ("template_version", "response_schema_version", "source_integrity", "status"):
            row["metrics"].append(metric(store, "Historical prompt " + field, row["prompt"][field],
                                         prompt, "prompt-assembly/experiment-v1", "Exact sealed audit field"))
        for attempt in row["attempts"]:
            audit = attempt["experiment"] + "/GENERATION_AUDIT.json"
            for field, value in attempt["usage"].items():
                row["metrics"].append(metric(store, "Generation " + field, value, audit,
                                             attempt["experiment"], "Sealed application-owned API telemetry",
                                             status="REUSED_HISTORICAL" if value is not None else "UNAVAILABLE"))
            if attempt["completed"]:
                source = attempt["experiment"] + "/GENERATED_RESPONSE.json"
                row["metrics"].append(metric(store, "Model-reported claim count", len(attempt["response"]["claims"]),
                                             source, attempt["experiment"], "Count response claims, no entailment claim"))
                row["metrics"].append(metric(store, "Cited-Parent Utilization", len(attempt["cited_parent_ids"])
                                             / attempt["supplied_parents"], source, attempt["experiment"],
                                             "Distinct cited included parents / supplied complete parents",
                                             numerator=len(attempt["cited_parent_ids"]),
                                             denominator=attempt["supplied_parents"]))


def valid_validation_shape(value):
    """Recognize measurement receipts, never accept an unsupported semantic certificate."""
    if not isinstance(value, dict) or value.get("schema") != "post-generation-validation-1.0":
        return False
    if value.get("qualification_status") not in {
            "QUALIFICATIONS_VALID", "QUALIFICATIONS_MISSING", "QUALIFICATION_APPLICABILITY_UNDETERMINED"}:
        return False
    checks = value.get("checks")
    if (not isinstance(checks, list) or not checks or
            value.get("overall_status") not in {"MEASURED", "FAILED", "INDETERMINATE"}):
        return False
    for row in checks:
        if (not isinstance(row, dict) or not isinstance(row.get("check"), str)
                or row.get("status") not in STATUSES or not isinstance(row.get("outcome"), str)):
            return False
        if "denominator" in row and (type(row["denominator"]) is not int or row["denominator"] < 0):
            return False
        if "numerator" in row and (type(row["numerator"]) is not int or row["numerator"] < 0
                                   or row["numerator"] > row.get("denominator", row["numerator"])):
            return False
    return True


def summarize_provenance(store, summary, records, selection, delivery):
    dataset = "data/evals/ranking/dataset-v1/FROZEN_DATASET.json"
    sources = {"questions": dataset, "groups": dataset,
               "m7_direct_groups": selection, "m7_parent_groups": selection,
               "m8_groups": delivery, "m8_complete_questions": delivery,
               "retrieval_evaluations": selection, "delivery_evaluations": delivery}
    audit_sources = [a["experiment"] + "/GENERATION_AUDIT.json" for r in records.values()
                     for a in r["attempts"]]
    rows = []
    for key, value in summary.items():
        source = sources.get(key, audit_sources[0] if audit_sources else dataset)
        row = metric(store, key, value, source, "frozen-15 / RRF-30 / M8-128000",
                     "Manifest-verified record count or sum over latest completed question results; "
                     "failed attempts kept separately; see linked per-question provenance")
        row["source_artifact_refs"] = [store.reference(p) for p in audit_sources] if key not in sources else [row["artifact_ref"]]
        rows.append(row)
    return rows


def validate_usage_fields(usage):
    """Stable safe telemetry schema; unknown billable categories fail closed."""
    counts = {"input_tokens", "output_tokens", "total_tokens", "reasoning_tokens", "cached_input_tokens",
              "cache_write_tokens", "cache_write_30m_tokens", "cache_write_12h_tokens"}
    costs = {"input_cost_usd", "output_cost_usd", "cached_input_cost_usd", "cache_write_cost_usd",
             "total_estimated_cost_usd"}
    labels = {"model", "selected_model", "service_tier", "response_status", "pricing_version",
              "usage_status", "cost_status", "pricing_effective_from", "pricing_effective_through"}
    if not isinstance(usage, dict) or set(usage) - counts - costs - labels - {"latency_ms", "cost_reasons", "usage_errors"}:
        raise ArtifactError("UNRECOGNIZED_USAGE_CATEGORY")
    for field in counts:
        value = usage.get(field)
        if value is not None and (type(value) is not int or value < 0):
            raise ArtifactError("INVALID_USAGE_COUNT")
    for field in costs:
        value = usage.get(field)
        if value is not None:
            try:
                number = Decimal(value)
            except (InvalidOperation, TypeError, ValueError):
                raise ArtifactError("INVALID_COST_VALUE") from None
            if not number.is_finite() or number < 0:
                raise ArtifactError("INVALID_COST_VALUE")
    latency = usage.get("latency_ms")
    if latency is not None and (type(latency) not in {int, float} or not math.isfinite(latency) or latency < 0):
        raise ArtifactError("INVALID_LATENCY")
    import re

    for field in labels:
        value = usage.get(field)
        if value is not None and (not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_./:-]{1,160}", value)):
            raise ArtifactError("INVALID_TELEMETRY_LABEL")
    for field in ("cost_reasons", "usage_errors"):
        for value in usage.get(field, []):
            if not isinstance(value, str) or not re.fullmatch(r"[A-Z0-9_:.-]{1,200}", value):
                raise ArtifactError("INVALID_TELEMETRY_DIAGNOSTIC")
