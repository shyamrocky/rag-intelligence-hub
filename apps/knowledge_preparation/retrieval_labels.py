"""Display projections of saved evidence accounting and approved labels. No scoring."""
from tools.quality_dashboard.artifacts import ArtifactError

UNAVAILABLE = "UNAVAILABLE — not recorded in saved receipt"
REASONS = {
    "BUDGET_EXHAUSTED": "Cannot fit within the remaining evidence budget",
    "PARENT_EXCEEDS_TOTAL_BUDGET": "Evidence Unit exceeds the total evidence budget",
    "INDIVIDUALLY_OVERSIZED": "Evidence Unit exceeds the total evidence budget",
}


def unit_rows(case):
    obligations = {o["unit_id"]: o for o in case.get("obligations", [])}
    omitted = {o["unit_id"]: o for o in case["omitted"]}
    included = set(case["actual_M8_included_parent_ids"])
    rows = []
    for uid in case["considered_parent_ids"]:
        observation = obligations.get(uid, {}) if uid in included else omitted.get(uid, {})
        code = observation.get("reason")
        rows.append({"Evidence Unit ID": uid, "Outcome": "Included" if uid in included else "Excluded",
                     "BGE tokens": str(observation.get("token_count", UNAVAILABLE)),
                     "Remaining BGE budget at exclusion": str(observation.get("remaining_tokens", "Not applicable" if uid in included else UNAVAILABLE)),
                     "Reason": "Included whole within the recorded evidence budget" if uid in included else REASONS.get(code, code or UNAVAILABLE)})
    return rows


def group_rows(data, record, case):
    expected = set(record["group_ids"])
    if not expected:
        return []
    store = data["store"]
    frozen = store.json("data/evals/ranking/dataset-v1/FROZEN_DATASET.json")
    label = next((r for r in frozen["labels"] if r["question_id"] == record["question_id"]), None)
    if label is None:
        labels = store.json("data/evals/m9/benchmark-v1/PROPOSED_EVIDENCE_LABELS.json")
        label = next(r for r in labels["labels"] if r["question_id"] == record["question_id"])
    groups = {g["group_id"]: g for g in label["required_evidence_groups"]}
    observations = (record.get("completion") or {}).get("group_outcomes")
    if set(groups) != expected or observations is None or {g["group_id"] for g in observations} != expected:
        raise ArtifactError("GROUP_DISPLAY_IDENTITY_MISMATCH")
    included = set(case["actual_M8_included_parent_ids"])
    rows = []
    for obs in observations:
        group = groups[obs["group_id"]]
        provided = [a["unit_id"] for a in obs["alternatives"] if a["complete_parent_included"]]
        if any(uid not in included for uid in provided) or bool(provided) != obs["included"]:
            raise ArtifactError("GROUP_DISPLAY_DELIVERY_MISMATCH")
        # Only use a description already recorded in the approved label, never infer a new requirement.
        description = group.get("requirement") or group.get("description") or "Description not recorded in approved label; see source references"
        refs = []
        for alt in group["alternatives"]:
            pages = sorted({loc["page"] for loc in alt.get("citation_locators", []) if loc.get("page") is not None})
            loc = " · pp. " + ", ".join(map(str, pages)) if pages else ""
            refs.append(alt.get("document_id", "Source reference") + loc)
        rows.append({"Human-approved evidence group": obs["group_id"], "Coverage": "Covered" if obs["included"] else "Not covered",
                     "Recorded requirement": description,
                     "Approved source references": "; ".join(dict.fromkeys(refs)),
                     "Supporting included Evidence Unit(s)": "\n".join(provided) if provided else "None delivered for this required group"})
    return rows
