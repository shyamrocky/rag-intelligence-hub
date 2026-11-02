"""Read-only scope-bound HTML handoff. Revalidates evidence, never mints admission."""

import json

from rag_hub.acquire import digest, local_path
from rag_hub.html_acquire import encode
from rag_hub.html_admission_models import ScopedHtmlDecision
from rag_hub.html_qa_execution import assess_document
from rag_hub.html_qualification import MARKDOWN_COMPATIBILITY_RELEASE, verify_release
from rag_hub.html_validation import load_documents


def load_units(
    root,
    *,
    manifest_path,
    expected_manifest_sha256,
    release_path,
    expected_release_sha256,
    authorization_sha256,
    filters=None,
):
    verify_release(root, release_path, expected_release_sha256)
    raw = local_path(root, manifest_path).read_bytes()
    if digest(raw) != expected_manifest_sha256:
        raise ValueError("stale_HTML_publication_manifest")
    manifest = json.loads(raw)
    if manifest.get("schema") == "html-scoped-publication-manifest-1.1":
        selection = {
            "manifest_path": str(manifest_path),
            "expected_manifest_sha256": expected_manifest_sha256,
            "release_path": str(release_path),
            "expected_release_sha256": expected_release_sha256,
            "authorization_sha256": authorization_sha256,
        }
        return load_successor(root, manifest, selection, filters or {})
    if filters:
        raise ValueError("consumption_filters_require_versioned_contract")
    if (
        manifest.get("schema") != "html-scoped-publication-manifest-1.0"
        or manifest["release_path"] != str(release_path)
        or manifest["expected_release_sha256"] != expected_release_sha256
        or manifest["authorization"]["sha256"] != authorization_sha256
    ):
        raise ValueError("unselected_HTML_publication")
    docs = load_documents(root)
    units, seen = [], set()
    for descriptor in manifest["publications"]:
        raw = local_path(root, descriptor["path"]).read_bytes()
        if digest(raw) != descriptor["sha256"]:
            raise ValueError("tampered_HTML_QA_publication")
        value = json.loads(raw)
        doc = value["doc_id"]
        if doc in seen or doc not in docs:
            raise ValueError("duplicate_or_foreign_HTML_publication")
        seen.add(doc)
        admission = value["admission"]
        if (
            value.get("schema") != "html-scoped-QA-publication-1.0"
            or value["corpus_manifest_sha256"] != manifest["corpus_manifest_sha256"]
            or docs[doc]["manifest_sha256"] != manifest["corpus_manifest_sha256"]
            or admission
            != {
                "release_path": str(release_path),
                "expected_release_sha256": expected_release_sha256,
                "authorization_path": manifest["authorization"]["path"],
                "authorization_sha256": authorization_sha256,
            }
        ):
            raise ValueError("HTML_scope_or_authorization_binding_mismatch")
        # Shared QA replays deterministic evidence and sole decision function. No writes.
        expected = assess_document(root, docs[doc], admission)
        if encode(expected) != encode(value["qa"]):
            expected = compatible_replay_metadata(root, expected, release_path)
            if encode(expected) != encode(value["qa"]):
                raise ValueError("partial_forged_or_neighboring_HTML_admission")
        accepted = {
            r["section_id"]: ScopedHtmlDecision.model_validate(r)
            for r in value["qa"]["quality_decisions"]
            if r["status"] == "approved_for_index"
        }
        for unit in expected["scoped_html_support"]["units"]:
            if not set(unit["required_section_ids"]) <= accepted.keys():
                raise ValueError("partial_HTML_unit")
            units.append(
                {
                    **unit,
                    "authoritative_publication": descriptor,
                    "qa_release_sha256": expected_release_sha256,
                    "qualification_policy_sha256": next(iter(accepted.values())).scope[
                        "qualification_policy_sha256"
                    ],
                    "authorization_sha256": authorization_sha256,
                    "whole_source_ready": False,
                }
            )
    if seen != set(docs):
        raise ValueError("incomplete_HTML_corpus_publication")
    verify_release(root, release_path, expected_release_sha256)
    return units


def compatible_replay_metadata(root, expected, release_path):
    """Rebind only a known predecessor's non-admission sampling fingerprints.

    The successor pins exact old component bytes. Sample membership, validations,
    decisions, scopes, evidence and all other fields still compare byte-for-byte.
    No old validator or decision engine is executed or substituted.
    """
    import copy

    from rag_hub.markdown_qualification import verify_release as verify_successor
    from rag_hub.validation_models import SamplePlan
    from rag_hub.validation_sampling import fingerprint

    path = local_path(root, MARKDOWN_COMPATIBILITY_RELEASE)
    if not path.exists():
        return expected
    successor = verify_successor(root, MARKDOWN_COMPATIBILITY_RELEASE, digest(path.read_bytes()))
    predecessor = json.loads(local_path(root, release_path).read_bytes())
    if successor.get("compatible_html_releases", {}).get(str(release_path)) != digest(
        local_path(root, release_path).read_bytes()
    ):
        raise ValueError("unbound_HTML_sampling_compatibility")
    observation = successor["predecessor_validator_observation"]
    parts = []
    for name in observation["modules"]:
        source = "src/rag_hub/" + name + ".py"
        archived = observation["overrides"].get(source, source)
        raw = local_path(root, archived).read_bytes()
        if digest(raw) != predecessor["files"][source]:
            raise ValueError("changed_HTML_predecessor_validator_observation")
        parts.append(raw)
    if digest(b"".join(parts)) != observation["validator_sha256"]:
        raise ValueError("invalid_HTML_predecessor_validator_fingerprint")
    view = copy.deepcopy(expected)
    plan = SamplePlan.model_validate(view["sample"]).model_copy(
        update={"validator_sha256": observation["validator_sha256"]}
    )
    view["sample"] = plan.model_dump(mode="json")
    # HTML qualification uses no manual review receipts in these frozen runs.
    qualification = digest(fingerprint(plan).encode())
    for gate in view["cohort_gates"].values():
        gate["qualification_sha256"] = qualification
    return view


def load_successor(root, manifest, selection, filters):
    """Inherit exact old approvals, append one authoritative C10 scope, project once."""
    from rag_hub.consumption import SCHEMA, excluded_view, html_view, select
    from rag_hub.html_c10 import SECTION, validate_relationships

    release = verify_release(root, selection["release_path"], selection["expected_release_sha256"])
    policy = json.loads(local_path(root, release["qualification_policy_path"]).read_bytes())
    prior_path = policy["predecessor_selector_path"]
    prior = json.loads(local_path(root, prior_path).read_bytes())
    if (
        manifest["predecessor"] != prior
        or manifest["consumption_schema"] != SCHEMA
        or manifest["release_path"] != selection["release_path"]
        or manifest["expected_release_sha256"] != selection["expected_release_sha256"]
        or manifest["authorization"]["sha256"] != selection["authorization_sha256"]
    ):
        raise ValueError("C10_unbound_successor_manifest")
    units = load_units(root, **prior)
    descriptor = manifest["delta_publication"]
    raw = local_path(root, descriptor["path"]).read_bytes()
    if digest(raw) != descriptor["sha256"]:
        raise ValueError("C10_tampered_delta_publication")
    publication = json.loads(raw)
    expected_arguments = {
        "release_path": selection["release_path"],
        "expected_release_sha256": selection["expected_release_sha256"],
        "authorization_path": manifest["authorization"]["path"],
        "authorization_sha256": selection["authorization_sha256"],
    }
    if (
        publication.get("schema") != "html-scoped-QA-publication-1.0"
        or publication.get("doc_id") != "C10"
        or publication.get("admission") != expected_arguments
    ):
        raise ValueError("C10_unbound_delta_scope")
    document = load_documents(root)["C10"]
    if publication["corpus_manifest_sha256"] != document["manifest_sha256"]:
        raise ValueError("C10_changed_corpus_identity")
    expected = assess_document(root, document, expected_arguments)
    # A pinned PDF-only successor changes the validator byte fingerprint, not
    # this historical C10 sample, gates, decisions, scopes or source evidence.
    pdf_successor_path = "config/pdf-residual-qa-successor-v1.json"
    if not local_path(root, pdf_successor_path).exists():
        pdf_successor_path = "config/pdf-text-qa-successor.json"
    pdf_successor = local_path(root, pdf_successor_path)
    if pdf_successor.exists():
        from rag_hub.pdf_text_recovery import verify_release as verify_pdf_text
        from rag_hub.validation_models import SamplePlan
        from rag_hub.validation_sampling import fingerprint

        successor = verify_pdf_text(root, pdf_successor_path, digest(pdf_successor.read_bytes()))
        observation = successor["predecessor_validator_observation_c10"]
        parts = []
        for name in observation["modules"]:
            source = "src/rag_hub/" + name + ".py"
            archived = observation["overrides"].get(source, source)
            old = local_path(root, archived).read_bytes()
            if digest(old) != release["files"][source]:
                raise ValueError("changed_C10_predecessor_validator_evidence")
            parts.append(old)
        if digest(b"".join(parts)) != observation["validator_sha256"]:
            raise ValueError("unbound_C10_predecessor_validator_evidence")
        plan = SamplePlan.model_validate(expected["sample"]).model_copy(
            update={"validator_sha256": observation["validator_sha256"]}
        )
        expected["sample"] = plan.model_dump(mode="json")
        for gate in expected["cohort_gates"].values():
            gate["qualification_sha256"] = digest(fingerprint(plan).encode())
    if encode(expected) != encode(publication["qa"]):
        raise ValueError("C10_forged_QA_delta")
    added = [
        u for u in expected["scoped_html_support"]["units"] if u["content_section_ids"] == [SECTION]
    ]
    if len(added) != 1 or added[0]["id"] != manifest["delta_unit_id"]:
        raise ValueError("C10_partial_or_unapproved_unit")
    unit = added[0]
    approved = {
        d["section_id"]
        for d in expected["quality_decisions"]
        if d["status"] == "approved_for_index"
    }
    if not set(unit["required_section_ids"]) <= approved:
        raise ValueError("C10_incomplete_approved_scope")
    unit = dict(
        unit,
        authoritative_publication=descriptor,
        qa_release_sha256=selection["expected_release_sha256"],
        authorization_sha256=selection["authorization_sha256"],
        qualification_policy_sha256=release["files"][release["qualification_policy_path"]],
        whole_source_ready=False,
    )
    units.append(unit)
    validate_relationships(units)
    identity = {**selection, "schema": manifest["schema"], "predecessor": prior}
    lookup = {u["id"]: u for u in units}
    # Both dashboard and consumers use this same publication-bound exclusion view.
    ref = manifest["exclusions"]
    raw = local_path(root, ref["path"]).read_bytes()
    if digest(raw) != ref["sha256"]:
        raise ValueError("C10_stale_exclusion_register")
    exclusions = json.loads(raw)
    if SECTION in exclusions or len(exclusions) != 30:
        raise ValueError("C10_exclusion_scope_changed")
    views = [excluded_view(e, identity) for e in exclusions.values()]
    issue_ref = manifest["issue_register"]
    if digest(local_path(root, issue_ref["path"]).read_bytes()) != issue_ref["sha256"]:
        raise ValueError("C10_stale_issue_register")
    register = json.loads(local_path(root, issue_ref["path"]).read_bytes())
    if register["publication_binding"] != {
        "predecessor_manifest_sha256": prior["expected_manifest_sha256"],
        "delta_publication_sha256": descriptor["sha256"],
        "qa_release_sha256": selection["expected_release_sha256"],
    }:
        raise ValueError("C10_issue_register_publication_disagreement")
    current_issues = {i["issue_id"]: i for i in register["issues"]}
    views = [html_view(u, lookup, identity, current_issues=current_issues) for u in units] + views
    return select(views, **filters)


def validate_consumption_unit(root, view, *, selection):
    """Re-read pinned authority and source evidence, then compare the entire view."""
    candidates = load_units(root, **selection, filters={"admission_status": "ALL"})
    expected = next((u for u in candidates if u["unit_id"] == view.get("unit_id")), None)
    if expected is None or encode(expected) != encode(view):
        raise ValueError("altered_or_incomplete_consumption_contract")
    return view


def serialize_consumption_unit(root, view, *, selection):
    return encode(validate_consumption_unit(root, view, selection=selection))
