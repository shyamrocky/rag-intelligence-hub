"""Seven-case illustrative projections; no parser, admission or source repair.

Raw canonical Sections remain provenance, not the consumable text for these
restricted units. Every consumable character is source-bound or an explicit
warning/label. Unsupported metric assertions never enter the consumable text.
"""

import ast
import copy
import json
from collections import Counter
from pathlib import Path

from rag_hub.acquire import digest, local_path
from rag_hub.html_acquire import encode
from rag_hub.markdown_corpus import load_corpus

PREVIOUS = "data/validation/markdown/v2/final-remediation-v1/assessment.json"
PREVIOUS_SHA = "801ba0b1f3a2557a023b3fc98a21e61e483508bf124c0c69de0ab9691f0ca7be"
VERSION = "markdown-complete-units-1.2"
OUT = "data/validation/markdown/v2/illustrative-recovery-v1"
DEFECTS = {
    91: {
        "type": "invalid_python_import",
        "lines": [302],
        "description": "Publisher source line 302 uses invalid Python syntax: a hyphenated module name in the Voyage AI import.",
    },
    103: {
        "type": "missing_python_indentation",
        "lines": [351, 352],
        "description": "Publisher source line 352 lacks indentation under the if statement on line 351.",
    },
    119: {
        "type": "missing_source_imports",
        "lines": [407, 410, 412],
        "description": "Publisher source references boto3, AWS4Auth and OpenSearchVectorSearch without imports or definitions in the captured source.",
    },
}
SCORE = {181, 182, 183, 184}


def assess_illustrative(root):
    """Reuse 107 candidates / 55 units; source-reassess only seven held rows."""
    from rag_hub.markdown_qualification import python_names

    root = Path(root).resolve()
    previous_raw = local_path(root, PREVIOUS).read_bytes()
    if digest(previous_raw) != PREVIOUS_SHA:
        raise ValueError("changed_previous_illustrative_baseline")
    previous = json.loads(previous_raw)
    for name, expected in previous["bindings"].items():
        if digest(local_path(root, name).read_bytes()) != expected:
            raise ValueError("changed_illustrative_source_binding: " + name)
    corpus = load_corpus(root, admitted_only=False)
    result = copy.deepcopy(previous)
    checks = result["sections"]
    numbers = {int(c["block_id"].rsplit("b", 1)[1]): c for c in checks}
    held = {n for n, c in numbers.items() if c["assessment"] == "hold"}
    if held != set(DEFECTS) | SCORE:
        raise ValueError("unexpected_seven_case_cohort")
    records = {r["section"].section_id: r for r in corpus["records"]}
    blocks = {r["block"]["block_id"]: r["block"] for r in corpus["structure"]["records"]}
    raw = local_path(root, result["source"]["raw_path"]).read_bytes()
    text = raw.decode()
    lines = text.splitlines(keepends=True)
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))
    for n in held:
        c = numbers[n]
        record = records[c["section_id"]]
        a, b = c["source_span"]["lines_1based_inclusive"]
        if (
            digest("".join(lines[a - 1 : b]).encode()) != c["source_span"]["raw_fragment_sha256"]
            or record["source_span"] != c["source_span"]
            or record["section"].normalized_sha256 != c["normalized_sha256"]
            or list(record["section"].heading_path) != c["heading_path"]
            or record["section"].provider_tab != c["provider_tab"]
        ):
            raise ValueError("changed_seven_case_source_context")
        if n in (91, 103):
            try:
                ast.parse(blocks[c["block_id"]]["content"])
            except SyntaxError:
                pass
            else:
                raise ValueError("source_defect_disappeared")
        if n == 119:
            missing = python_names(blocks[c["block_id"]]["content"])[1]
            if not {"boto3", "AWS4Auth", "OpenSearchVectorSearch"} <= missing:
                raise ValueError("source_definition_defect_changed")

    def sid(n):
        return numbers[n]["section_id"]

    def segment(n, a, b, *, end_column=None, role="quoted_source"):
        c = numbers[n]
        lo = starts[a - 1]
        hi = starts[b] if end_column is None else starts[b - 1] + end_column
        span = c["source_span"]["chars_0based_end_exclusive"]
        if not span[0] <= lo < hi <= span[1]:
            raise ValueError("projection_outside_source_Section")
        original = text[lo:hi]
        return {
            "section_id": sid(n),
            "role": role,
            "text": original,
            "source_lines": [a, b],
            "chars_0based_end_exclusive": [lo, hi],
            "bytes_0based_end_exclusive": [len(text[:lo].encode()), len(text[:hi].encode())],
            "text_sha256": digest(original.encode()),
            "source_sha256": result["source"]["raw_sha256"],
        }

    def full(n, role="required_source_context"):
        a, b = numbers[n]["source_span"]["lines_1based_inclusive"]
        return segment(n, a, b, role=role)

    def make_unit(member_numbers, classification, warnings, segments, *, defect=None, omitted=None):
        members = [sid(n) for n in sorted(member_numbers)]
        heading_ids = [
            c["section_id"]
            for c in checks
            if c["block_type"] == "heading"
            and any(
                records[m]["section"].heading_path[: len(c["heading_path"])]
                == tuple(c["heading_path"])
                for m in members
            )
        ]
        context = {
            m: {
                k: next(c for c in checks if c["section_id"] == m).get(k)
                for k in (
                    "heading_path",
                    "provider_tab",
                    "code_label",
                    "containers",
                    "alternative_selection_context",
                )
            }
            for m in members
        }
        providers = {records[m]["section"].provider_tab for m in members} - {None}
        if len(providers) > 1:
            raise ValueError("mixed_illustrative_provider_alternatives")
        restriction = {
            "schema": "restricted-illustrative-projection-1.0",
            "classification": classification,
            "warnings": warnings,
            "segments": segments,
            "omitted_from_consumable_projection": omitted or [],
            "raw_canonical_Sections_are_provenance_only": True,
            "not_executable_guidance": True,
            "no_independent_measurement_or_metric_claim": True,
            "source_defect": defect,
            "source_sha256": result["source"]["raw_sha256"],
        }
        unit = {
            "kind": "restricted_illustrative_source_projection",
            "required_section_ids": members,
            "supporting_heading_ids": heading_ids,
            "provider_tab": next(iter(providers), None),
            "whole_unit_required": True,
            "context_only_section_ids": [sid(184)]
            if classification == "ILLUSTRATIVE_METRIC_UNVERIFIED"
            else [],
            "source_spans": {m: records[m]["source_span"] for m in members + heading_ids},
            "context": context,
            "documentation_scope": {
                "classification": classification,
                "quoted_documentation_only": True,
                "tested_or_executable_guidance": False,
                "provider_selection": None,
                "selected_embedding_provider": None,
                "selected_vector_store_provider": None,
                "required_external_bindings": ["vector_store"]
                if classification == "ILLUSTRATIVE_METRIC_UNVERIFIED"
                else [],
                "limitations": warnings,
                "output_roles": {sid(184): "attributed_example_output_only"}
                if classification == "ILLUSTRATIVE_METRIC_UNVERIFIED"
                else {},
            },
            "restricted_projection": restriction,
            "source_semantics": "illustrative source evidence only; raw Sections do not authorize executable or metric claims",
            "example_prerequisites": "Retain all warnings, exact source-bound projection and complete unit; no source repair or provider inference.",
        }
        unit["unit_id"] = "C04:unit:" + digest(encode(unit))[:20]
        return unit

    added = []
    for n, defect in DEFECTS.items():
        c = numbers[n]
        # Include the source's same-provider installation and actual choice context.
        a, b = c["source_span"]["lines_1based_inclusive"]
        install = next(
            k
            for k, row in reversed(list(numbers.items()))
            if k < n
            and row["block_type"] == "code"
            and row["provider_tab"] == c["provider_tab"]
            and row["heading_path"] == c["heading_path"]
            and blocks[row["block_id"]]["language"] in ("shell", "bash")
        )
        context_numbers = [110, 111] if n == 119 else [43]
        warnings = [
            "ILLUSTRATIVE_SOURCE_DEFECT: the acquired publisher code contains a confirmed source error.",
            defect["description"],
            "Exact original code is retained, not repaired. Do not present this example as a working implementation or verified executable guidance.",
            "Use only to illustrate the publisher's documented integration/configuration pattern; imports, configuration, credentials and API behavior are not validated.",
        ]
        segments = [full(k) for k in context_numbers + [install]]
        segments.append(segment(n, a + 1, b - 1, role="verbatim_defective_publisher_code"))
        added.append(
            make_unit(
                context_numbers + [install, n],
                "ILLUSTRATIVE_SOURCE_DEFECT",
                warnings,
                segments,
                defect=defect,
            )
        )

    # Keep the entire four-Section relationship; qualify exact smaller textual
    # spans, not the captured paragraph's unsupported final metric sentence.
    prefix, sep, unsupported = lines[691].partition(" In this case,")
    if not sep or not prefix.endswith("Score meaning varies by provider."):
        raise ValueError("unsupported_score_projection_boundary")
    score_segments = [
        segment(182, 692, 692, end_column=len(prefix), role="provider_neutral_API_explanation"),
        segment(183, 698, 701, role="publisher_score_retrieval_example"),
        segment(184, 705, 705, role="attributed_score_output_only"),
    ]
    omitted = [
        {
            "section_id": sid(182),
            "source_lines": [692, 692],
            "description": "Final provider-specific metric sentence omitted from consumable text; full original retained as provenance.",
            "original_text": sep + unsupported,
        },
        {
            "section_id": sid(183),
            "source_lines": [695, 696],
            "description": "Unverified metric comments omitted; original example remains unchanged in provenance.",
        },
        {
            "section_id": sid(184),
            "source_lines": [707, 716],
            "description": "Nike financial excerpt is not needed to illustrate score retrieval and is not qualified by this projection.",
        },
    ]
    added.append(
        make_unit(
            [182, 183, 184],
            "ILLUSTRATIVE_METRIC_UNVERIFIED",
            [
                "ILLUSTRATIVE_METRIC_UNVERIFIED: the captured source does not identify the selected vector-store provider or establish its score interpretation.",
                "Illustrates only the publisher API returning a document and score. Do not infer the metric, direction, scale or comparability of the score.",
                "The numeric score is attributed publisher output, not an independently verified measurement. The example was not executed and requires a configured vector_store.",
                "Use only the source-bound textual projection; raw paragraph, comments and financial output are provenance, not qualified factual passages.",
            ],
            score_segments,
            omitted=omitted,
        )
    )

    result["units"].extend(added)
    qualified = {m for u in added for m in u["required_section_ids"] + u["supporting_heading_ids"]}
    for n in held:
        c = numbers[n]
        if c["section_id"] not in qualified:
            raise ValueError("seven_case_not_bound_to_complete_unit")
        c.update(
            assessment="candidate",
            reasons=[],
            primary_exception=None,
            human_review_required=False,
            qualification_scope="ILLUSTRATIVE_SOURCE_DEFECT"
            if n in DEFECTS
            else "ILLUSTRATIVE_METRIC_UNVERIFIED",
            raw_Section_not_qualified_for_direct_retrieval=True,
        )
    for c in checks:
        c["qualified_unit_ids"].extend(
            u["unit_id"]
            for u in added
            if c["section_id"] in u["required_section_ids"] + u["supporting_heading_ids"]
        )
    if any(
        next(c for c in checks if c["section_id"] == m)["assessment"]
        not in ("historical", "candidate")
        for u in added
        for m in u["required_section_ids"] + u["supporting_heading_ids"]
    ):
        raise ValueError("unapproved_illustrative_context")
    result.update(
        policy=VERSION,
        previous_qualified_assessment={"path": PREVIOUS, "sha256": PREVIOUS_SHA},
        illustrative_sections_reassessed=7,
        counts=dict(Counter(c["assessment"] for c in checks)),
        counts_by_type={
            kind: dict(Counter(c["assessment"] for c in checks if c["block_type"] == kind))
            for kind in ("code", "prose", "heading")
        },
        previous_107_candidates_and_55_units_preserved=True,
        source_defects_retained=3,
    )
    result["bindings"][PREVIOUS] = PREVIOUS_SHA
    return result


def restricted_payload(unit):
    """Warning-bearing consumable text; callers must first verify the unit."""
    restriction = unit["restricted_projection"]
    warnings = restriction["warnings"]
    if not warnings or warnings != unit["documentation_scope"]["limitations"]:
        raise ValueError("missing_or_changed_illustrative_limitations")
    rendered = restriction["classification"] + "\n\n" + "\n".join(warnings) + "\n\n"
    for s in restriction["segments"]:
        if digest(s["text"].encode()) != s["text_sha256"]:
            raise ValueError("changed_illustrative_source_projection")
        rendered += f"Publisher source, lines {s['source_lines'][0]}–{s['source_lines'][1]} ({s['role']}):\n"
        rendered += "\n".join("> " + line for line in s["text"].splitlines()) + "\n\n"
    rendered += "Limitations remain mandatory: " + " ".join(warnings)
    return {
        "schema": restriction["schema"],
        "unit_id": unit["unit_id"],
        "classification": restriction["classification"],
        "warnings": warnings,
        "consumable_text": rendered,
        "not_executable_guidance": True,
        "raw_Sections_are_provenance_only": True,
        "source_sha256": restriction["source_sha256"],
        "projection_sha256": digest(encode(restriction)),
        "segments": restriction["segments"],
    }


def validate_restricted_payload(root, payload, *, expected_unit_id):
    """Read-only consumer guard; altered warnings/text/context fail closed."""
    unit = next(
        (u for u in assess_illustrative(root)["units"] if u["unit_id"] == expected_unit_id), None
    )
    if unit is None or "restricted_projection" not in unit or payload != restricted_payload(unit):
        raise ValueError("altered_or_incomplete_illustrative_payload")
    return payload


def validate_illustrative_handoff(root, view):
    """Validate restricted consumer semantics; never creates an admission."""
    unit = next(
        (u for u in assess_illustrative(root)["units"] if u["unit_id"] == view.get("unit_id")), None
    )
    if unit is None or "restricted_projection" not in unit:
        raise ValueError("unknown_restricted_illustrative_unit")

    def section_data(entry):
        section = entry.get("section", {})
        return section.model_dump(mode="json") if hasattr(section, "model_dump") else section

    if (
        view.get("consumption_contract") != "restricted-illustrative-projection-1.0"
        or view.get("restricted_projection") != restricted_payload(unit)
        or view.get("documentation_scope") != unit["documentation_scope"]
        or view.get("context") != unit["context"]
        or view.get("provider_tab") != unit["provider_tab"]
        or view.get("whole_unit_required") is not True
        or view.get("source_evidence_is_retrievable") is not False
        or view.get("required_section_ids") != unit["required_section_ids"]
        or view.get("supporting_heading_ids") != unit["supporting_heading_ids"]
        or [m.get("section_id") for m in view.get("members", [])] != unit["required_section_ids"]
        or any("section" in m for m in view.get("members", []))
        or [section_data(m).get("section_id") for m in view.get("heading_context", [])]
        != unit["supporting_heading_ids"]
        or [section_data(m).get("section_id") for m in view.get("source_evidence", [])]
        != unit["required_section_ids"]
    ):
        raise ValueError("missing_or_altered_illustrative_handoff_contract")
    corpus = load_corpus(root, admitted_only=False)
    records = {r["section"].section_id: r for r in corpus["records"]}
    source = corpus["manifest"]["source"]
    if view.get("source") != {
        k: source[k]
        for k in ("doc_id", "title", "canonical_url", "original_url", "raw_sha256", "snapshot_id")
    }:
        raise ValueError("altered_illustrative_source_identity")
    for m in view["source_evidence"] + view["heading_context"]:
        data = section_data(m)
        record = records[data["section_id"]]
        if (
            data != record["section"].model_dump(mode="json")
            or m.get("source_span") != record["source_span"]
        ):
            raise ValueError("altered_illustrative_source_provenance")
    for m in view["members"]:
        if m.get("projection_segments") != [
            s
            for s in unit["restricted_projection"]["segments"]
            if s["section_id"] == m["section_id"]
        ]:
            raise ValueError("changed_illustrative_handoff_segment")
        decision = m.get("decision", {})
        original = records[m["section_id"]]["historical_qa_decision"]
        if original["status"] == "approved_for_index":
            valid = decision == original
        else:
            matching = [
                u
                for u in decision.get("scope", {}).get("units", [])
                if u.get("unit_id") == unit["unit_id"]
            ]
            valid = (
                decision.get("status") == "approved_for_index"
                and decision.get("basis") == "markdown_verified_content_unit"
                and matching == [unit]
                and decision.get("scope", {}).get("whole_unit_required") is True
            )
        if not valid:
            raise ValueError("altered_illustrative_decision_scope")
    return view


def source_issue_register(root, assessment, *, authoritative_check):
    """Full Section dashboard projection; current QA and proposed scope separate.

    authoritative_check is captured by the build from the actual main loader and
    unchanged historical ledger. Staged candidates never set retrieval_eligible.
    """
    root = Path(root)
    corpus = load_corpus(root, admitted_only=False)
    records = {r["section"].section_id: r for r in corpus["records"]}
    raw = local_path(root, assessment["source"]["raw_path"]).read_text()
    lines = raw.splitlines(keepends=True)
    assessment_sha = digest(encode(assessment))
    ledger = "data/validation/bf9ec63f85912861a86677647d2056a6e23a7e0758315682cec29d78c0fe4580/decisions.jsonl"
    ledger_sha = digest(local_path(root, ledger).read_bytes())
    entries = []
    for c in assessment["sections"]:
        sid = c["section_id"]
        n = int(c["block_id"].rsplit("b", 1)[1])
        decision = records[sid]["historical_qa_decision"]
        current_eligible = decision["status"] == "approved_for_index"
        if current_eligible != (sid in authoritative_check["admitted_section_ids"]):
            raise ValueError("current_authoritative_Markdown_QA_disagreement")
        units = [u for u in assessment["units"] if u["unit_id"] in c["qualified_unit_ids"]]
        restricted = next((u for u in units if "restricted_projection" in u), None)
        # Unrestricted supporting context may also belong to restricted units;
        # it retains its prior usable scope and is never relabeled defective.
        own_restricted = restricted if n in set(DEFECTS) | SCORE else None
        illustrative = bool(own_restricted or any(u.get("documentation_scope") for u in units))
        classification = (
            own_restricted["restricted_projection"]["classification"]
            if own_restricted
            else "illustrative"
            if illustrative and c["assessment"] == "candidate"
            else "excluded"
            if c["assessment"] == "excluded"
            else "standard"
        )
        warnings = (
            own_restricted["restricted_projection"]["warnings"]
            if own_restricted
            else list(
                dict.fromkeys(
                    w
                    for u in units
                    for w in u.get("documentation_scope", {}).get("limitations", [])
                )
            )
        )
        a, b = c["source_span"]["lines_1based_inclusive"]
        original = "".join(lines[a - 1 : b])
        if n in DEFECTS:
            origin, issue_type = "source", DEFECTS[n]["type"]
            description = DEFECTS[n]["description"]
        elif n in SCORE:
            origin, issue_type = "source", "provider_metric_interpretation_unverified"
            description = "Selected provider/metric is absent; qualify only the warning-bearing provider-neutral projection. Raw metric assertions remain unqualified."
        elif c["assessment"] == "excluded":
            origin, issue_type, description = (
                "QA policy",
                "intentional_POC_exclusion",
                "Acquired discovery/navigation, separator or footer has no standalone technical POC value.",
            )
        elif "residual_source_evidence" in c:
            origin, issue_type, description = (
                "context",
                "illustrative_context_mitigated",
                "Previously residual content is bound to a complete attributed unit and explicit limitations.",
            )
        else:
            origin, issue_type, description = (
                None,
                None,
                "Preserved prior source-backed Section and QA disposition.",
            )
        entries.append(
            {
                "source_id": "C04",
                "section_id": sid,
                "source_title": assessment["source"]["title"],
                "source_line_start": a,
                "source_line_end": b,
                "original_source_text": original,
                "source_sha256": assessment["source"]["raw_sha256"],
                "source_fragment_sha256": digest(original.encode()),
                "source_snapshot_id": assessment["source"]["snapshot_id"],
                "issue_origin": origin,
                "issue_type": issue_type,
                "description": description,
                "confirmed_original_source_defect": n in DEFECTS,
                "defective_source_lines": DEFECTS[n]["lines"] if n in DEFECTS else [],
                "confirmed_parser_failure": False,
                "acquisition_status": "acquired_successfully",
                "parsing_status": "exact_source_correspondence_verified",
                "content_type": c["block_type"],
                "evidence_classification": classification,
                "required_warning_or_limitation": warnings,
                "resolution_status": "excluded"
                if c["assessment"] == "excluded"
                else "mitigated"
                if illustrative
                else "verified",
                "source_defect_resolution": "unresolved_original_source_error"
                if n in DEFECTS
                else None,
                "retrieval_eligible": current_eligible,
                "retrieval_exclusion_reason": None
                if current_eligible
                else "intentional_POC_exclusion"
                if c["assessment"] == "excluded"
                else "pending_authoritative_shared_QA_integration",
                "current_authoritative_QA": {
                    "decision": decision,
                    "decision_sha256": digest(encode(decision)),
                    "ledger_path": ledger,
                    "ledger_sha256": ledger_sha,
                },
                "proposed_eligibility_after_integration": c["assessment"]
                in ("historical", "candidate"),
                "proposed_use": "supporting_heading_only"
                if c["block_type"] == "heading"
                else classification,
                "raw_Section_proposed_for_retrieval": not bool(own_restricted)
                and c["assessment"] in ("historical", "candidate"),
                "qualified_unit_ids": c["qualified_unit_ids"],
                "required_unit_context": [
                    {
                        "unit_id": u["unit_id"],
                        "required_section_ids": u["required_section_ids"],
                        "supporting_heading_ids": u["supporting_heading_ids"],
                    }
                    for u in units
                ],
                "qa_evidence_path": OUT + "/assessment.json",
                "qa_evidence_sha256": assessment_sha,
                "qa_decision_reference": "current_authoritative_QA; proposed scope is not an admission",
                "recommended_action": "Main owner must verify and enable restricted projection with warnings; original source error remains visible."
                if own_restricted
                else "Preserve prior qualified context; main owner integrates candidates."
                if c["assessment"] == "candidate"
                else "Preserve authoritative historical decision."
                if current_eligible
                else "Keep excluded; no remediation needed.",
            }
        )
    return {
        "schema": "markdown-source-issues-2.0",
        "status": "DIAGNOSTIC_AND_STAGED_SCOPE_NOT_QA_AUTHORITY",
        "sections": entries,
        "issues": [c for c in entries if c["issue_origin"] is not None],
        "authoritative_check": authoritative_check,
        "current_admitted": sum(c["retrieval_eligible"] for c in entries),
        "proposed_after_integration": sum(
            c["proposed_eligibility_after_integration"] for c in entries
        ),
        "source_defects_retained": 3,
        "parser_defects": 0,
        "source_readiness": "not_executed",
    }
