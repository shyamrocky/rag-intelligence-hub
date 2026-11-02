"""Read-only, QA-aware Markdown content units; no chunking or new decisions."""

import inspect
import json
from pathlib import Path

from rag_hub.acquire import digest, local_path
from rag_hub.markdown_corpus import load_corpus
from rag_hub.markdown_qualification import evidence_proofs
from rag_hub.validation_models import ValidationPolicy, ValidationResult
from rag_hub.validation_reviews import make_decisions


def load_units(root, *, admission=None):
    """Default: exactly the historical forty approvals, never staged candidates.

    Future integration supplies a trusted descriptor with publication path/hash
    plus all six evidence_proofs arguments. Values come from owner-approved run
    configuration, not the source, publication or a caller's claimed Section status.
    Every new unit requires all body members AND supporting headings admitted.
    """
    root = Path(root).resolve()
    corpus = load_corpus(root, admitted_only=False)
    records = {r["section"].section_id: r for r in corpus["records"]}
    historical = {
        sid: r["historical_qa_decision"]
        for sid, r in records.items()
        if r["historical_qa_decision"]["status"] == "approved_for_index"
    }
    decisions, units = dict(historical), []
    if admission is not None:
        if "markdown_proofs" not in inspect.signature(make_decisions).parameters:
            raise ValueError("Markdown_policy_not_integrated_by_shared_QA_owner")
        args = {
            k: v
            for k, v in admission.items()
            if k not in ("publication_path", "publication_sha256")
        }
        raw = local_path(root, admission["publication_path"]).read_bytes()
        if digest(raw) != admission["publication_sha256"]:
            raise ValueError("Markdown_authoritative_publication_hash_mismatch")
        publication = json.loads(raw)
        if (
            publication.get("schema") != "markdown-unit-QA-publication-1.0"
            or publication.get("status") != "AUTHORITATIVE_SHARED_QA"
        ):
            raise ValueError("staged_or_unsupported_Markdown_publication")
        qa = publication["qa"]
        support = qa["markdown_support"]
        if support["arguments"] != args:
            raise ValueError("Markdown_publication_not_bound_to_trusted_selection")
        policy = ValidationPolicy.model_validate_json(support["policy_json"])
        results = [ValidationResult.model_validate_json(v) for v in support["validation_json"]]
        if (
            policy.model_dump(mode="json") != qa["policy"]
            or [r.model_dump(mode="json") for r in results] != qa["validation_results"]
        ):
            raise ValueError("Markdown_decision_fingerprint_input_mismatch")
        proofs = evidence_proofs(
            root,
            corpus["records"][0]["source"],
            [r["section"] for r in corpus["records"]],
            results,
            **args,
        )
        expected = make_decisions(results, policy, qa["cohort_gates"], {}, markdown_proofs=proofs)
        if [d.model_dump(mode="json") for d in expected] != qa["quality_decisions"]:
            raise ValueError("Markdown_publication_not_authoritative_engine_output")
        decisions = {
            d.section_id: d.model_dump(mode="json")
            for d in expected
            if d.status == "approved_for_index"
        }
        if any(decisions.get(sid) != d for sid, d in historical.items()):
            raise ValueError("historical_Markdown_approval_changed")
        evidence = json.loads(local_path(root, args["evidence_path"]).read_bytes())
        units = evidence["units"]
    result, included = [], set()

    def project(unit, historical_only=False):
        members = unit["required_section_ids"]
        headings = unit.get("supporting_heading_ids", [])
        if any(sid not in decisions for sid in members + headings):
            raise ValueError("partial_or_unapproved_Markdown_unit")
        providers = {records[sid]["section"].provider_tab for sid in members} - {None}
        if len(providers) > 1 or providers and unit.get("provider_tab") not in providers:
            raise ValueError("mixed_Markdown_provider_alternatives")
        if not any(records[sid]["section"].block_type != "heading" for sid in members):
            raise ValueError("isolated_heading_cannot_be_content")
        source = corpus["manifest"]["source"]
        view = {
            "unit_id": unit["unit_id"],
            "whole_unit_required": True,
            "required_section_ids": members,
            "supporting_heading_ids": headings,
            "provider_tab": unit.get("provider_tab"),
            "source": {
                k: source[k]
                for k in (
                    "doc_id",
                    "title",
                    "canonical_url",
                    "original_url",
                    "raw_sha256",
                    "snapshot_id",
                )
            },
            "members": [
                {
                    "section": records[sid]["section"],
                    "source_span": records[sid]["source_span"],
                    "decision": decisions[sid],
                }
                for sid in members
            ],
            "heading_context": [
                {"section": records[sid]["section"], "source_span": records[sid]["source_span"]}
                for sid in headings
            ],
            "context": unit.get("context", {}),
            "documentation_scope": unit.get("documentation_scope", {}),
            "context_only_section_ids": unit.get("context_only_section_ids", []),
            "source_semantics": unit.get("source_semantics"),
            "historical_approval_only": historical_only,
            "code_execution_verified": False,
        }

        if "restricted_projection" in unit:
            from rag_hub.markdown_illustrative import (
                restricted_payload,
                validate_illustrative_handoff,
            )

            view["consumption_contract"] = "restricted-illustrative-projection-1.0"
            view["restricted_projection"] = restricted_payload(unit)
            view["source_evidence"] = view["members"]
            view["source_evidence_is_retrievable"] = False
            # Fail closed for consumers expecting raw Section.text passages.
            # The exact canonical Section is available only as provenance.
            view["members"] = [
                {
                    "section_id": sid,
                    "source_span": records[sid]["source_span"],
                    "decision": decisions[sid],
                    "projection_segments": [
                        segment
                        for segment in unit["restricted_projection"]["segments"]
                        if segment["section_id"] == sid
                    ],
                }
                for sid in members
            ]
            validate_illustrative_handoff(root, view)
        return view

    for unit in units:
        result.append(project(unit))
        included.update(unit["required_section_ids"])
    for sid in historical:
        if sid in included:
            continue
        s = records[sid]["section"]
        parsed = corpus["structure"]
        a, b = records[sid]["source_span"]["lines_1based_inclusive"]
        containers = [
            c
            for c in parsed["mdx_containers"]
            if c["source_span"]["lines_1based_inclusive"][0]
            < a
            <= b
            < c["source_span"]["lines_1based_inclusive"][1]
        ]
        unit = {
            "unit_id": "historical:" + sid,
            "required_section_ids": [sid],
            "provider_tab": s.provider_tab,
            "context": {
                sid: {
                    "heading_path": list(s.heading_path),
                    "provider_tab": s.provider_tab,
                    "code_label": s.code_label,
                    "containers": containers,
                }
            },
        }
        result.append(project(unit, historical_only=True))
    return result
