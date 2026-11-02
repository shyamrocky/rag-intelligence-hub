"""Source-bound residual MDX assessment; contributes evidence, never admission.

The initial 158-Section audit is reused unchanged. Only its 42 exceptions are
reassessed. Fixed source identities deliberately bound this documentation policy.
No example, shell command, MDX component or provider library is executed.
"""

import ast
import copy
import json
import shlex
from collections import Counter
from pathlib import Path

from rag_hub.acquire import digest, local_path
from rag_hub.html_acquire import encode
from rag_hub.markdown_corpus import load_corpus

BASE = "data/validation/markdown/v2/assessment.json"
BASE_SHA = "bf792c41bf22e2bf4ee6c31d294f6e9c395e04a2533e9dd317e6f90acaa3bc9d"
VERSION = "markdown-complete-units-1.1"
OUT = "data/validation/markdown/v2/final-remediation-v1"

# Reviewed original-source relationships, not substitutions for source text.
# Every entry is checked against frozen source extents and static syntax below.
EXAMPLES = {
    30: {"intro": 29, "kind": "credential_configuration", "inputs": []},
    106: {"kind": "embedding_usage", "inputs": ["documents", "embeddings"]},
    115: {"kind": "provider_template", "inputs": ["embeddings"]},
    123: {
        "kind": "provider_template",
        "inputs": [
            "ASTRA_DB_API_ENDPOINT",
            "ASTRA_DB_APPLICATION_TOKEN",
            "ASTRA_DB_NAMESPACE",
            "embeddings",
        ],
    },
    127: {"kind": "provider_template", "inputs": ["embeddings"]},
    131: {"kind": "provider_template", "inputs": ["embeddings"]},
    135: {
        "kind": "provider_template",
        "inputs": ["ATLAS_VECTOR_SEARCH_INDEX_NAME", "MONGODB_COLLECTION", "embeddings"],
    },
    139: {"kind": "provider_template", "inputs": ["embeddings"]},
    143: {"kind": "provider_template", "inputs": ["embeddings"]},
    147: {"kind": "provider_template", "inputs": ["embeddings", "index_name"]},
    151: {"kind": "provider_template", "inputs": ["embeddings"]},
    165: {"intro": 164, "kind": "index_usage", "inputs": ["all_splits", "vector_store"]},
    176: {"intro": 175, "kind": "query_usage", "inputs": ["vector_store"]},
    179: {"intro": 178, "kind": "async_query_usage", "inputs": ["vector_store"]},
    187: {"intro": 186, "kind": "vector_query_usage", "inputs": ["embeddings", "vector_store"]},
    196: {"intro": 195, "kind": "retriever_usage", "inputs": ["vector_store"]},
    199: {"intro": 198, "kind": "retriever_usage", "inputs": ["vector_store"]},
}
OUTPUTS = {107: 106, 177: 176, 180: 179, 188: 187, 197: 196, 200: 199}
BOILERPLATE = {1, 212, 213, 214}
DEFECTS = {
    91: (
        "invalid_python_import",
        "The original line 302 uses a hyphenated Python module name: from langchain-voyageai import VoyageAIEmbeddings.",
    ),
    103: (
        "missing_python_indentation",
        "Original line 352 is not indented under the if statement on line 351.",
    ),
    119: (
        "missing_source_imports",
        "boto3, AWS4Auth and OpenSearchVectorSearch are referenced without imports or definitions anywhere in the captured source. Placeholders alone are not the blocker.",
    ),
}
SCORE = {181, 182, 183, 184}


def assess_residual(root):
    """Reuse pinned audit evidence; validate source and reassess 42 rows only."""
    from rag_hub.markdown_qualification import python_names

    root = Path(root).resolve()
    base_raw = local_path(root, BASE).read_bytes()
    if digest(base_raw) != BASE_SHA:
        raise ValueError("changed_initial_Markdown_evidence")
    initial = json.loads(base_raw)
    for path, expected in initial["bindings"].items():
        if digest(local_path(root, path).read_bytes()) != expected:
            raise ValueError("changed_Markdown_source_binding: " + path)
    corpus = load_corpus(root, admitted_only=False)
    result = copy.deepcopy(initial)
    checks = result["sections"]
    by_number = {int(c["block_id"].rsplit("b", 1)[1]): c for c in checks}
    original = {c["section_id"]: c for c in initial["sections"]}
    records = {r["section"].section_id: r for r in corpus["records"]}
    blocks = {r["block"]["block_id"]: r["block"] for r in corpus["structure"]["records"]}
    source = result["source"]
    raw = local_path(root, source["raw_path"]).read_bytes()
    lines = raw.decode().splitlines(keepends=True)
    residual = [c for c in checks if c["assessment"] in ("hold", "excluded")]
    expected_numbers = (
        set(EXAMPLES)
        | set(OUTPUTS)
        | BOILERPLATE
        | set(DEFECTS)
        | SCORE
        | {29, 164, 174, 175, 178, 186, 195, 198}
    )
    if (
        len(residual) != 42
        or {int(c["block_id"].rsplit("b", 1)[1]) for c in residual} != expected_numbers
    ):
        raise ValueError("unexpected_residual_cohort")
    for c in residual:
        sid = c["section_id"]
        record = records[sid]
        a, b = c["source_span"]["lines_1based_inclusive"]
        fragment = "".join(lines[a - 1 : b])
        if (
            digest(fragment.encode()) != c["source_span"]["raw_fragment_sha256"]
            or record["source_span"] != c["source_span"]
            or record["section"].normalized_sha256 != c["normalized_sha256"]
            or list(record["section"].heading_path) != c["heading_path"]
            or record["section"].provider_tab != c["provider_tab"]
        ):
            raise ValueError("changed_residual_source_context")
        c["residual_source_evidence"] = {
            "raw_source_text": fragment,
            "source_lines": [a, b],
            "source_sha256": source["raw_sha256"],
            "raw_fragment_sha256": digest(fragment.encode()),
            "acquired_successfully": True,
            "source_verified": True,
            "prior_disposition": original[sid]["assessment"],
        }

    def sid(n):
        return by_number[n]["section_id"]

    def headings(members):
        paths = [records[m]["section"].heading_path for m in members]
        return [
            c["section_id"]
            for c in checks
            if c["block_type"] == "heading"
            and any(list(p[: len(c["heading_path"])]) == c["heading_path"] for p in paths)
        ]

    def prior_complete(n):
        identifier = sid(n)
        units = [u for u in initial["units"] if identifier in u["required_section_ids"]]
        if not units:
            raise ValueError("missing_prior_complete_dependency")
        return set(min(units, key=lambda u: len(u["required_section_ids"]))["required_section_ids"])

    new_units = []
    for n, spec in EXAMPLES.items():
        c = by_number[n]
        body = blocks[c["block_id"]]["content"]
        if n == 30:
            commands = [shlex.split(line) for line in body.splitlines() if line.strip()]
            if commands != [
                ["export", "LANGSMITH_TRACING=true"],
                ["export", "LANGSMITH_API_KEY=..."],
            ]:
                raise ValueError("unsupported_credential_template")
        else:
            _, missing, _ = python_names(body)
            if sorted(missing) != spec["inputs"]:
                raise ValueError("unreviewed_external_code_binding")
            # Top-level await is a notebook/async-context example, not a module
            # syntax error. AST only; never execute or import publisher code.
            ast.parse(body)
        members = {sid(n)}
        if "intro" in spec:
            members.add(sid(spec["intro"]))
        if spec["kind"] == "provider_template":
            # Retain the exact same-tab installation and source's choice lead-in.
            for previous in checks:
                if previous is c:
                    break
                if (
                    previous["block_type"] == "code"
                    and previous["provider_tab"] == c["provider_tab"]
                    and previous["heading_path"] == c["heading_path"]
                    and blocks[previous["block_id"]]["language"] in ("shell", "bash")
                ):
                    members.add(previous["section_id"])
            members.update({sid(110), sid(111)})
        if "documents" in spec["inputs"]:
            doc_example = next(
                row for row in checks if row["source_span"]["lines_1based_inclusive"] == [87, 100]
            )
            members.add(doc_example["section_id"])
        if n >= 165:
            members |= prior_complete(161)
        if n == 199:
            members |= {sid(195), sid(196)}  # explicit "example above" reference
        output = next((k for k, v in OUTPUTS.items() if v == n), None)
        if output:
            members.add(sid(output))
        ordered = sorted(members, key=lambda m: records[m]["source_span"]["lines_1based_inclusive"])
        provider = c["provider_tab"]
        scope = {
            "classification": "B_illustrative_documentation_example",
            "quoted_documentation_only": True,
            "tested_or_executable_guidance": False,
            "provider_selection": None,
            "required_external_bindings": spec["inputs"],
            "credential_or_configuration_placeholders_preserved": True,
            "limitations": [
                "Publisher documentation example; not executed, API-certified or complete runtime setup.",
                "Select/configure compatible providers and supply named inputs before execution; no provider choice is inferred.",
                "Quoted output illustrates source presentation, not a verified result, metric or fact about Nike.",
            ],
            "output_roles": {sid(output): "attributed_example_output_only"} if output else {},
            "external_bindings_are_requirements_not_supplied_values": True,
            "selected_embedding_provider": None,
            "selected_vector_store_provider": None,
        }
        if n == 30:
            scope["limitations"].append(
                "The literal ... API key is a credential placeholder, never a valid secret."
            )
        if n == 179:
            scope["limitations"].append("Top-level await requires an async/notebook context.")
        if n == 106:
            scope["limitations"].append(
                "The output's length 1536 is a captured illustration; the source does not identify its selected embedding model."
            )
        if n == 187:
            scope["limitations"].append(
                "The quoted output ends 'This was partially offset by:'; it is a partial Document excerpt, not a complete financial statement."
            )
        context = {
            m: {
                k: next(row for row in checks if row["section_id"] == m).get(k)
                for k in (
                    "heading_path",
                    "provider_tab",
                    "code_label",
                    "containers",
                    "alternative_selection_context",
                )
            }
            for m in ordered
        }
        for m in ordered:
            context[m]["consumption_role"] = (
                "attributed_example_output_only"
                if output and m == sid(output)
                else "documentation_example_or_required_context"
            )
            context[m]["limitations"] = scope["limitations"]
        unit = {
            "kind": "quoted_documentation_example",
            "required_section_ids": ordered,
            "supporting_heading_ids": headings(members),
            "provider_tab": provider,
            "whole_unit_required": True,
            "source_spans": {m: records[m]["source_span"] for m in ordered + headings(members)},
            "context": context,
            "documentation_scope": scope,
            "context_only_section_ids": [sid(output)] if output else [],
            "source_semantics": "attributed documentation template and output; not executed or independently factual",
            "example_prerequisites": "Explicit named inputs/configuration and compatible provider choice remain required.",
        }
        unit["unit_id"] = "C04:unit:" + digest(encode(unit))[:20]
        new_units.append(unit)

    qualified = {
        m for u in new_units for m in u["required_section_ids"] + u["supporting_heading_ids"]
    }
    for c in residual:
        n = int(c["block_id"].rsplit("b", 1)[1])
        if c["section_id"] in qualified:
            c.update(
                assessment="candidate",
                reasons=[],
                primary_exception=None,
                human_review_required=False,
            )
            c["qualification_scope"] = (
                "supporting_heading_only"
                if c["block_type"] == "heading"
                else "quoted_documentation_unit_only"
            )
        elif n in DEFECTS:
            c.update(
                assessment="hold",
                reasons=[DEFECTS[n][0]],
                primary_exception="original_source_defect",
                human_review_required=False,
            )
        elif n in SCORE:
            c.update(
                assessment="hold",
                reasons=["source_score_metric_provider_unspecified"],
                primary_exception="source_context_ambiguity",
                human_review_required=True,
            )
        elif n in BOILERPLATE:
            c.update(
                assessment="excluded",
                reasons=["publisher_navigation_footer_or_separator"],
                primary_exception="POC_scope_exclusion",
                human_review_required=False,
            )
        else:
            raise ValueError("unaccounted_residual_section")
    for u in new_units:
        providers = {records[m]["section"].provider_tab for m in u["required_section_ids"]} - {None}
        if len(providers) > 1 or providers and u["provider_tab"] not in providers:
            raise ValueError("mixed_provider_unit")
        if any(
            next(c for c in checks if c["section_id"] == m)["assessment"]
            not in ("candidate", "historical")
            for m in u["required_section_ids"] + u["supporting_heading_ids"]
        ):
            raise ValueError("unqualified_complete_unit_dependency")
    result["units"].extend(new_units)
    for c in checks:
        c["qualified_unit_ids"].extend(
            u["unit_id"]
            for u in new_units
            if c["section_id"] in u["required_section_ids"] + u["supporting_heading_ids"]
        )
    result.update(
        policy=VERSION,
        initial_assessment={"path": BASE, "sha256": BASE_SHA, "source_checks_reused": 158},
        residual_sections_reassessed=42,
        confirmed_original_source_defects=len(DEFECTS),
        counts=dict(Counter(c["assessment"] for c in checks)),
        counts_by_type={
            kind: dict(Counter(c["assessment"] for c in checks if c["block_type"] == kind))
            for kind in ("code", "prose", "heading")
        },
        independently_human_accepted=0,
        no_source_examples_executed=True,
    )
    result["bindings"][BASE] = BASE_SHA
    return result


def source_issues(assessment):
    """Dashboard observations, not QA decisions: eligibility comes from sole QA."""
    issues = []
    assessment_sha256 = digest(encode(assessment))
    for c in assessment["sections"]:
        if "residual_source_evidence" not in c:
            continue
        n = int(c["block_id"].rsplit("b", 1)[1])
        if n in DEFECTS:
            origin, kind, description = "source", *DEFECTS[n]
            action = "Retain HOLD. Publisher correction or separately reviewed erratum required; never rewrite the captured source."
        elif n in SCORE:
            origin, kind = "source", "ambiguous_provider_metric_context"
            description = "The captured source provides no selected store establishing the inverse-distance interpretation. Keep the complete score group HOLD; do not invent metric semantics."
            action = "Establish publisher-backed store/metric context before reconsidering these four Sections."
        elif n in BOILERPLATE:
            origin, kind = "QA policy", "intentional_POC_exclusion"
            description = "Successfully acquired publisher discovery/navigation, structural separator or footer MDX; outside the POC knowledge scope."
            action = "Retain source evidence; exclude from retrieval. No parser repair needed."
        else:
            origin, kind = "context", "illustrative_unit_context_mitigated"
            description = "Source-faithful example, introduction, heading or printed output is staged only with its complete attributed unit, named prerequisites and explicit limitations. No execution or standalone output claim."
            action = "Main owner must integrate and enable the exact bounded policy before admission. Preserve scope in every consumer."
        status = (
            "mitigated"
            if c["assessment"] == "candidate"
            else "excluded"
            if c["assessment"] == "excluded"
            else "unresolved"
        )
        a, b = c["source_span"]["lines_1based_inclusive"]
        issues.append(
            {
                "issue_id": f"C04:residual:{n:05d}",
                "source_id": "C04",
                "section_id": c["section_id"],
                "source_title": assessment["source"]["title"],
                "source_line_start": a,
                "source_line_end": b,
                "issue_origin": origin,
                "issue_type": kind,
                "description": description,
                "evidence": c["residual_source_evidence"],
                "resolution_status": status,
                "acquisition_status": "source_acquired_and_verified",
                "confirmed_parser_failure": False,
                "confirmed_original_source_defect": n in DEFECTS,
                "retrieval_eligible": False,
                "retrieval_exclusion_reason": "staged_pending_authoritative_main_QA_enablement"
                if c["assessment"] == "candidate"
                else c["reasons"][0],
                "recommended_action": action,
                "qa_disposition": c["assessment"],
                "qa_decision_reference": {
                    "assessment_path": OUT + "/assessment.json",
                    "assessment_sha256": assessment_sha256,
                    "section_id": c["section_id"],
                    "authority": "diagnostic_and_staged_only; not an admission decision",
                    "historical_decision_unchanged": True,
                },
                "qualified_unit_ids": c["qualified_unit_ids"],
                "required_context": [
                    {
                        "unit_id": u["unit_id"],
                        "required_section_ids": u["required_section_ids"],
                        "supporting_heading_ids": u["supporting_heading_ids"],
                        "documentation_scope": u.get("documentation_scope", {}),
                        "context_only_section_ids": u.get("context_only_section_ids", []),
                    }
                    for u in assessment["units"]
                    if u["unit_id"] in c["qualified_unit_ids"]
                ],
            }
        )
    return {
        "schema": "markdown-source-issues-1.0",
        "status": "DIAGNOSTIC_NOT_QA_AUTHORITY",
        "issues": issues,
        "source_readiness": "not_executed",
    }
