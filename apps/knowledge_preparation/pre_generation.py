"""Read-only preparation journey over existing sealed preflight readers."""
from importlib import import_module
from pathlib import Path

import streamlit as st

from tools.preflight_suite.artifacts import CONFIG, read_run
from tools.preflight_suite.dashboard import discover
from tools.quality_dashboard.artifacts import ArtifactError, digest
from tools.quality_dashboard.completion_adapter import load_completed
from tools.quality_dashboard.preflight_history import historical_runs

ROOT = Path(__file__).resolve().parents[2]
UNAVAILABLE = "UNAVAILABLE"


def load():
    data = load_completed(ROOT)
    telemetry = discover(ROOT)
    observations = []
    for run in telemetry["runs"]:
        for row in run["results"]["questions"]:
            if row["question_id"] not in data["records"]:
                raise ArtifactError("UNKNOWN_QUESTION")
            observations.append({"row": row, "run": run["manifest"]["run_id"],
                                 "mode": run["manifest"]["mode"], "manifest": run["manifest_path"],
                                 "historical": False})
    for run in historical_runs(ROOT):
        for row in run["questions"]:
            if row["question_id"] in data["records"]:
                observations.append({"row": row, "run": run["run_id"], "mode": run["mode"],
                                     "manifest": run["manifest"], "historical": True})
    # The older funded answer has an independently recorded provider count receipt;
    # never substitute actual generation usage for a missing preflight count.
    for qid, record in data["records"].items():
        if any(item["row"]["question_id"] == qid for item in observations):
            continue
        for attempt in record.get("attempts", []):
            audit = attempt.get("audit", {})
            receipt = audit.get("token_count_receipt", {})
            prompt = local_prompt(record)
            if not (attempt.get("completed") and receipt.get("request_sha256") == audit.get("request_sha256")
                    and type(receipt.get("input_tokens")) is int
                    and audit.get("M8_package_sha256") == prompt.get("M8_package_sha256")):
                continue
            cost = audit.get("cost_estimate", {})
            observations.append({"row": {
                "question_id": qid, "status": "HISTORICAL_PROVIDER_QUALIFICATION",
                "included_parents": prompt.get("M8_counts", {}).get("selected_parents"),
                "omitted_parents": prompt.get("M8_counts", {}).get("omitted_parents"),
                "evidence_BGE_tokens": prompt.get("M8_BGE_budget", {}).get("exact_llm_evidence_tokens"),
                "prompt_version": audit.get("prompt_template"), "schema_version": audit.get("response_schema"),
                "model": audit.get("model"), "input_tokens": receipt["input_tokens"],
                "context_fit": audit.get("context_fit"), "maximum_cost_usd": cost.get("estimated_max_cost_usd"),
                "pricing_version": cost.get("pricing_version"), "request_sha256": audit.get("request_sha256"),
                "M8_package_sha256": audit.get("M8_package_sha256"),
            }, "run": "Historical funded request", "mode": "funded-request qualification",
                "manifest": data["frozen_data"]["store"].references[attempt["manifest_ref"]]["artifact"],
                "historical": True, "funded_history": True})
            break
    # Run identifiers order observations; no dates are displayed in the primary UI.
    observations.sort(key=lambda item: item["run"])
    return data, observations, telemetry["rejected"]


def latest(observations, qid):
    return next((item for item in reversed(observations) if item["row"]["question_id"] == qid), None)


def local_prompt(record):
    return (record.get("frozen") or {}).get("prompt") or {}


def value(item):
    return UNAVAILABLE if item is None else item


def evidence_summary(record, observation):
    if observation:
        row = observation["row"]
        return row.get("included_parents"), row.get("evidence_BGE_tokens"), row.get("prompt_version")
    prompt = local_prompt(record)
    return (prompt.get("M8_counts", {}).get("selected_parents"),
            prompt.get("M8_BGE_budget", {}).get("exact_llm_evidence_tokens"), prompt.get("template_version"))


def prompt_instructions(version, expected):
    modules = {"grounded-generation-prompt-v1": "prompt_v2",
               "grounded-generation-prompt-v2": "prompt_v3",
               "grounded-generation-prompt-v2.1": "prompt_v21",
               "grounded-generation-prompt-v2.2": "prompt_v22"}
    if version not in modules or not expected:
        return None
    system = import_module("tools.pre_generation_gate." + modules[version]).SYSTEM
    if digest(system) != expected:
        return None
    return system  # Generic instructions/synthetic example only; never publisher payload.



def saved_summary(row, has_prompt=False):
    status = row.get("status")
    if status in {"MODEL_QUALIFIED", "HISTORICAL_PROVIDER_QUALIFICATION"}:
        return "Saved preparation checks passed: model-token, context and cost qualification was recorded."
    if status == "LOCAL_VALIDATED":
        return "Local evidence and prompt checks passed. Model qualification was not established by this local check."
    if status and status.startswith("BLOCKED"):
        return "Saved preparation check blocked. Review the recorded reasons before further qualification."
    return "Historical prompt audit only; model qualification unavailable." if has_prompt else "No saved preparation check available."


def measurement_rows(row):
    fit = row.get("context_fit")
    fit = fit if isinstance(fit, dict) else {}
    input_tokens = row.get("input_tokens")
    reserved = fit.get("reserved_output_tokens", row.get("reserved_output_tokens"))
    safety = fit.get("safety_margin_tokens", row.get("safety_margin_tokens"))
    parts = (input_tokens, reserved, safety)
    total = sum(parts) if all(type(part) is int and part >= 0 for part in parts) else None

    def display(item):
        if item is None:
            return UNAVAILABLE
        if type(item) is bool:
            return "Yes" if item else "No"
        return f"{item:,}" if type(item) is int else str(item)

    rows = [
        ("Input tokens", "Size of the complete request sent to the model: instructions, question, evidence and schema.", input_tokens),
        ("Output reservation", "Maximum space allowed for the model’s response.", reserved),
        ("Safety margin", "Extra capacity kept unused as a buffer.", safety),
        ("Total context allocation", "Input tokens + output reservation + safety margin; calculated from the saved counts.", total),
        ("Model context limit", "Recorded maximum token capacity for the selected model.", fit.get("context_window")),
        ("Remaining headroom", "Recorded capacity left after input, output reservation and safety margin.", fit.get("remaining_context_margin")),
        ("Context fit", "Whether the request and reserved capacity fit the recorded model limits.", fit.get("fits")),
        ("Maximum estimated cost · USD", "Conservative projected request cost using counted input and the full output allowance—not actual spending.", row.get("maximum_cost_usd")),
    ]
    formula = " + ".join(f"{part:,}" for part in parts) + f" = {total:,} tokens" if total is not None else None
    return [{"Measurement": label, "Description": description,
             "Saved observation (tokens / result)": display(item)} for label, description, item in rows], formula

def render():
    from apps.knowledge_preparation.bot_records import source
    if source('Pre-Generation'):
        return
    st.title("Pre-Generation")
    st.write("From verified evidence to a complete, model-qualified request.")
    st.caption("Read-only saved observations · No assembly, provider calls or generation on refresh")
    st.info("Evidence prepared → Prompt assembled → Model capacity checked → Cost checked")
    try:
        data, observations, rejected = load()
    except (ArtifactError, ValueError, KeyError, TypeError, OSError):
        st.error("UNAVAILABLE — benchmark or preflight artifact bindings failed verification.")
        return
    records = data["records"]
    selected = {qid: latest(observations, qid) for qid in records}
    observed = sum(item is not None and not item.get("funded_history") for item in selected.values())
    counted = sum(item is not None and item["row"].get("input_tokens") is not None for item in selected.values())
    for col, label, count in zip(st.columns(3),
                                 ["Benchmark questions", "Questions with suite observations", "Questions with saved model-token counts"],
                                 [len(records), observed, counted], strict=True):
        with col.container(border=True):
            st.metric(label, count)
    st.caption("Counts reflect saved measurements, not current generation eligibility. Earlier and later prompt versions remain separate.")
    with st.expander("Benchmark preparation overview"):
        st.dataframe([{
            "Question": qid, "Cohort": record["reference"]["cohort_label"],
            "Included Evidence Units": value(evidence_summary(record, selected[qid])[0]),
            "Evidence size (BGE tokens)": value(evidence_summary(record, selected[qid])[1]),
            "Prompt version": value(evidence_summary(record, selected[qid])[2]),
            "Saved check summary": saved_summary(selected[qid]["row"] if selected[qid] else {}, bool(local_prompt(record))),
            "Generator input tokens": str(value(selected[qid]["row"].get("input_tokens"))) if selected[qid] else UNAVAILABLE,
        } for qid, record in records.items()], hide_index=True, width="stretch")
    ids = list(records)
    if st.session_state.get("pg_question") not in ids:
        st.session_state["pg_question"] = st.session_state.get("kr_question", ids[0])
    qid = st.selectbox("Question", ids, key="pg_question")
    record = records[qid]
    st.caption(record["reference"]["cohort_label"])
    st.markdown(record["question"])
    available = [o for o in observations if o["row"]["question_id"] == qid]
    observation = selected[qid]
    if available:
        with st.expander("History / Technical details", expanded=False):
            st.caption("Preparation checks are successive steps, not competing experiments. The latest saved check "
                       "is shown by default. Select an earlier check only to investigate its own request and prompt version.")
            index = st.selectbox("Saved preparation check", range(len(available)), index=len(available) - 1,
                                 format_func=lambda i: f"Check {i + 1} · "
                                 f"{'Local evidence and prompt check' if available[i]['mode'] == 'local-check' else 'Model token and cost preflight' if available[i]['mode'] == 'model-preflight' else 'Historical funded-request qualification'} · "
                                 f"{available[i]['row'].get('prompt_version', UNAVAILABLE)}",
                                 key="pg_observation_" + qid)
        observation = available[index]
        if index != len(available) - 1:
            st.info("Viewing an earlier saved preparation check. Its values and outcome below are not the latest check.")
    row = observation["row"] if observation else {}
    prompt = local_prompt(record)
    request = {}
    model_receipt = {}
    local = {}
    if observation and not observation["historical"]:
        try:
            _, _, store = read_run(ROOT, observation["manifest"])
            base = observation["manifest"].rsplit("/", 1)[0] + f"/questions/{qid}/"
            request = store.json(base + "REQUEST_PACKAGE.json")
            local = store.json(base + "LOCAL_VALIDATION.json")
            if observation["mode"] == "model-preflight":
                model_receipt = store.json(base + "MODEL_PREFLIGHT.json")
        except (ArtifactError, ValueError, KeyError, TypeError, OSError):
            st.error("UNAVAILABLE — selected observation failed verification.")
            return
    included, tokens, version = evidence_summary(record, observation)
    with st.container(border=True):
        st.subheader("1 · Evidence supplied to prompt assembly")
        for col, label, measurement in zip(st.columns(3), ["Complete Evidence Units", "Evidence size · BGE tokens", "Evidence budget · BGE tokens"],
                                            [included, tokens, CONFIG["M8_BGE_budget"]], strict=True):
            with col.container(border=True):
                st.metric(label, value(measurement))
        st.write("The evidence package contains complete parent Evidence Units with required context, citations and qualifications. Units are never truncated to fit.")
        omitted = row.get("omitted_parents", local.get("M8_counts", {}).get("omitted_parents", prompt.get("M8_counts", {}).get("omitted_parents")))
        st.caption("Excluded Evidence Units: " + str(value(omitted)))
        target = record.get("target")
        if target and record["group_ids"]:
            result = target["m8"]
            missing = result.get("missing_group_ids", [])
            st.write("Saved retrieval/context-assembly coverage: " + ("All human-approved evidence requirements delivered." if not missing else "Partial evidence; missing required groups: " + ", ".join(missing)))
            st.caption("This is the separately saved benchmark coverage observation, not a new semantic judgment or a rescore of this prompt package.")
        elif not record["group_ids"]:
            st.caption("Unsupported benchmark control: no positive evidence-group denominator. Retrieved material does not establish answerability.")
        st.page_link(st.session_state["kp_pages"]["Knowledge Retrieval"], label="Inspect retrieval selection and context exclusions →")
        st.page_link(st.session_state["kp_pages"]["Chunks & Lineage"], label="Inspect source chunks and Evidence Unit relationships →")
    with st.container(border=True):
        st.subheader("2 · Prompt assembly")
        schema = row.get("schema_version", prompt.get("response_schema_version"))
        st.write(f"Prompt: **{value(version)}** · Response schema: **{value(schema)}**")
        st.write("Instructions + original question + authorized evidence package + structured response requirements → complete generator request.")
        source_status = row.get("source_integrity", local.get("source_integrity", prompt.get("source_integrity")))
        source_label = "Verified during the recorded check" if source_status == "LIVE_M8_VALIDATED" else UNAVAILABLE
        st.dataframe([{"Saved assembly check": label, "Outcome": str(value(outcome))} for label, outcome in [
            ("Source and evidence bindings", source_label),
            ("Prompt structure complete", local.get("prompt_complete", prompt.get("prompt_complete")) if not observation or not observation.get("funded_history") else None),
            ("Response schema validated", local.get("response_schema_validated", prompt.get("response_schema_validated")) if not observation or not observation.get("funded_history") else None),
        ]], hide_index=True, width="stretch")
        st.caption("The question and evidence are data, not instructions. Benchmark gold labels and expected answers are not inserted into the model request.")
        with st.expander("Prompt instructions and request structure"):
            expected = request.get("template_sha256", prompt.get("template_sha256")) if version == prompt.get("template_version") or request else None
            instructions = prompt_instructions(version, expected)
            if instructions:
                st.caption(f"Verified generic instruction size: {len(instructions):,} characters. This is not a generator-token measurement.")
                st.code(instructions, language=None)
            else:
                st.info("UNAVAILABLE — exact recorded instructions cannot be verified for this observation.")
            st.caption("Generic prompt instructions only. Full source-bearing prompts and publisher payloads are not displayed.")
            st.write("Request components: system instructions; question; complete evidence with authorized references; output schema; generation settings.")
    with st.container(border=True):
        st.subheader("3 · Model tokens, context and estimated cost")
        st.write("Model: **" + str(value(row.get("model"))) + "**")
        measurements, formula = measurement_rows(row)
        st.table(measurements)
        if formula:
            st.markdown("**Total context allocation:** " + formula)
        else:
            st.caption("Total context allocation is unavailable until input, output reservation and safety margin are all recorded.")
        st.caption("Total context allocation includes reserved capacity; it is not actual token usage or a billable-token total.")
        st.caption("128K BGE tokens covers evidence only. Generator tokens measure the complete request using a different tokenizer; these counts must not be added or substituted. Component-level generator counts are unavailable unless independently recorded.")
        if model_receipt:
            st.write("Cost assumption: " + model_receipt.get("cost_estimate", {}).get("assumption", UNAVAILABLE))
        st.caption("Maximum projected cost is planning telemetry, not actual spending, an invoice or account balance.")
    with st.container(border=True):
        st.subheader("4 · Saved preparation summary")
        st.write(saved_summary(row, bool(prompt)))
        st.warning("Historical observation—not fresh execution approval. Before any separately authorized generation, revalidate source integrity, exact request hashes, model access, token count, context fit, pricing and spending permission.")
        if observation and observation["historical"] and not observation.get("funded_history"):
            st.info("Dependencies changed: this preserved observation is not currently qualified for reuse.")
        if observation and observation.get("funded_history"):
            st.caption("Historical funded-request qualification: token count comes from its recorded provider count receipt, not generation usage. Its earlier prompt audit has a different version; unverified instruction text is not substituted.")
        if row.get("blocking_reasons"):
            st.write("Recorded blocking reasons: " + ", ".join(row["blocking_reasons"]))
    with st.expander("Technical details — verified provenance and observation history"):
        st.dataframe([{"Observation": i + 1, "Run identity": o["run"], "Mode": o["mode"],
                       "Prompt": o["row"].get("prompt_version"), "Saved outcome": o["row"]["status"],
                       "Request SHA-256": o["row"].get("request_sha256"), "Manifest": o["manifest"]}
                      for i, o in enumerate(available)], hide_index=True, width="stretch")
        st.json({"pricing_policy_version": row.get("pricing_version"), "request_sha256": row.get("request_sha256", prompt.get("request_sha256")),
                 "evidence_package_sha256": row.get("M8_package_sha256", prompt.get("M8_package_sha256")),
                 "prompt_sha256": expected,
                 "response_schema_sha256": request.get("response_schema_sha256") if request else
                     prompt.get("response_schema_sha256") if version == prompt.get("template_version") else None})
        if not available:
            st.caption("No suite record for this question. Historical prompt audit is preserved separately; no other question’s token counts are reused.")
    if rejected:
        st.caption("Some publications failed current compatibility checks; only verified current-compatible or separately verified historical observations are shown.")
