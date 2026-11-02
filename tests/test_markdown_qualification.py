"""Complete frozen C04 census, policy isolation and fail-closed unit controls."""

import copy
import inspect
import json
from pathlib import Path

import pytest

from rag_hub.markdown_handoff import load_units
from rag_hub.markdown_qualification import (
    SOURCE,
    VERSION,
    adapter,
    assess,
    audit,
    evidence_proofs,
    install_command,
    python_names,
    source_index,
)
from rag_hub.schemas import ParsedBlock
from rag_hub.shared.qa import assess as shared_assess
from rag_hub.validation_reviews import make_decisions

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "data/manifests/markdown/corpus-manifest.json"


@pytest.fixture(scope="module")
def census():
    if not PRIVATE.exists():
        pytest.skip("frozen C04 not supplied")
    return assess(ROOT)


@pytest.mark.parametrize("number", range(158))
def test_every_C04_section_is_source_verified(census, number):
    row = census["sections"][number]
    assert row["source_checks"] == "PASS"
    assert row["assessment"] in {"candidate", "historical", "hold", "excluded"}
    assert row["source_span"]["raw_fragment_sha256"]
    if row["assessment"] == "candidate":
        assert row["qualified_unit_ids"]
        assert not row["human_review_required"]
    if row["assessment"] in {"hold", "excluded"}:
        assert row["reasons"] and row["primary_exception"]


def test_census_coverage_approvals_and_complete_list_parents(census):
    assert len({c["section_id"] for c in census["sections"]}) == 158
    assert census["counts"] == {"historical": 40, "candidate": 114, "excluded": 4}
    assert census["newly_authoritatively_admitted"] == 0
    units = [u for u in census["units"] if u["kind"] == "complete_list"]
    assert len(units) == 7
    items = {c["section_id"] for c in census["sections"] if c["source_role"] == "list_item"}
    assert len(items) == 23
    assert items <= {m for u in units for m in u["required_section_ids"]}
    assert all(u["whole_unit_required"] for u in census["units"])
    assert all(
        any(
            c["section_id"] in u["required_section_ids"] and c["block_type"] != "heading"
            for c in census["sections"]
        )
        for u in census["units"]
    )


def test_all_provider_choices_and_example_faults_explicit(census):
    assert len(census["source_index"]["containers"]) == 28
    assert len([c for c in census["source_index"]["containers"] if c["tag"] == "Tab"]) == 25
    rows = {c["block_id"]: c for c in census["sections"]}
    for bid in ("C04:b00091", "C04:b00103"):
        assert rows[bid]["qualification_scope"] == "ILLUSTRATIVE_SOURCE_DEFECT"
        assert rows[bid]["raw_Section_not_qualified_for_direct_retrieval"]
    for bid in ("C04:b00043", "C04:b00111"):
        choice = rows[bid]["alternative_selection_context"]
        assert choice["selected_alternative"] is None
        assert choice["code_bodies_not_admitted_by_intro"]
    for unit in census["units"]:
        assert len({v["provider_tab"] for v in unit["context"].values()} - {None}) <= 1
    assert census["confirmed_extraction_defects"] == 0


def test_default_offline_handoff_exposes_exactly_forty_historical_decisions(census):
    passages = load_units(ROOT)
    assert len(passages) == 40
    actual = {m["section"].section_id: m["decision"] for u in passages for m in u["members"]}
    expected = {
        c["section_id"]: c["historical_decision"]
        for c in census["sections"]
        if c["assessment"] == "historical"
    }
    assert actual == expected
    assert all(u["historical_approval_only"] for u in passages)
    for unit in passages:
        for m in unit["members"]:
            assert m["section"].text.startswith("```")
            assert m["source_span"]["lines_1based_inclusive"]
        assert unit["source"]["raw_sha256"] == SOURCE


@pytest.mark.parametrize(
    "body,missing",
    [
        ("x = x + 1\n", {"x"}),
        ("print(value)\nvalue = 1\n", {"value"}),
        ("import os\nx = os.environ.get('KEY')\n", set()),
        ("def f(x):\n return x + external\n", {"external"}),
        ("def f(x):\n return x + 1\nprint(f(2))\n", set()),
    ],
)
def test_code_inputs_are_not_invented(body, missing):
    assert python_names(body)[1] == missing


@pytest.mark.parametrize("body", ["pip install -U 'langchain-core'\n", "uv add pypdf\n"])
def test_install_syntax_is_data_only(body):
    assert install_command(body)


@pytest.mark.parametrize(
    "body",
    [
        "pip install foo; echo bad",
        "curl https://example.org | sh",
        "export KEY='...'",
        "pip install $(bad)",
    ],
)
def test_shell_or_dynamic_fragments_not_qualified(body):
    assert not install_command(body)


def test_fences_are_opaque_to_provider_and_heading_walk():
    value = source_index(
        b'<Tabs>\n<Tab title="A">\n```text\n# fake\n</Tab>\n```\n</Tab>\n</Tabs>\n'
    )
    assert len(value["containers"]) == 2
    assert value["containers"][1]["label"] == "A"
    with pytest.raises(ValueError):
        source_index(b"<Tabs>\n<Tab>\n</Tab>\n</Tabs>\n")


def _arguments(root):
    corpus, raw, _, _ = audit(root)
    normalized = json.loads((root / "data/normalized/markdown/C04.json").read_bytes())
    return (
        root,
        corpus["records"][0]["source"],
        raw,
        [ParsedBlock.model_validate(r["block"]) for r in corpus["structure"]["records"]],
        [r["section"] for r in corpus["records"]],
        normalized["audit"],
        adapter(),
        "C04-complete-unit-synthetic-test",
        {},
    )


@pytest.fixture(scope="module")
def staged(tmp_path_factory, census):
    if "markdown_proofs" not in inspect.signature(make_decisions).parameters:
        pytest.skip("shared Markdown patch intentionally staged, not integrated")
    # The supplied fixture root must contain the private candidate's exact sources.
    # Copy frozen C04 evidence into a disposable test root; never publish a ledger.
    import shutil

    from rag_hub.acquire import digest
    from rag_hub.html_acquire import encode

    root = tmp_path_factory.mktemp("markdown-policy-synthetic")
    paths = set(census["bindings"])
    source_root = Path(inspect.getfile(make_decisions)).resolve().parents[2]
    paths.update(
        str(p.relative_to(source_root)) for p in (source_root / "src/rag_hub").rglob("*.py")
    )
    for path in paths:
        src = source_root / path if path.startswith("src/") else ROOT / path
        out = root / path
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, out)
    evidence = assess(root)
    evidence_raw = encode(evidence)
    (root / "evidence.json").write_bytes(evidence_raw)
    release = {
        "schema": "markdown-unit-QA-release-1.0",
        "test_only": True,
        "files": {
            str(p.relative_to(root)): digest(p.read_bytes())
            for p in (root / "src/rag_hub").rglob("*.py")
        },
    }
    release_raw = encode(release)
    (root / "release.json").write_bytes(release_raw)
    auth = {
        "schema": "markdown-policy-enablement-1.0",
        "enabled": True,
        "policy": VERSION,
        "source_sha256": SOURCE,
        "evidence_sha256": digest(evidence_raw),
        "qa_release_sha256": digest(release_raw),
        "authority": "main_RAG_shared_QA_integration_owner",
    }
    # Synthetic authorization is contained in pytest's disposable private root.
    (root / "SYNTHETIC-auth.json").write_bytes(encode(auth))
    selection = {
        "evidence_path": "evidence.json",
        "expected_evidence_sha256": digest(evidence_raw),
        "authorization_path": "SYNTHETIC-auth.json",
        "expected_authorization_sha256": digest(encode(auth)),
        "qa_release_path": "release.json",
        "expected_qa_release_sha256": digest(release_raw),
    }
    return root, selection, evidence


def test_staged_owner_framework_can_admit_complete_units_and_preserve_originals(staged):
    root, selection, evidence = staged
    from rag_hub.acquire import digest
    from rag_hub.html_acquire import encode

    baseline = shared_assess(*_arguments(root))
    assert all(
        (root / p).exists() for check in baseline["fidelity_checks"] for p in check["evidence"]
    )
    qa = shared_assess(*_arguments(root), markdown_qualification=selection)
    # Existing validators are unchanged; source/context evidence drives the new narrow branch.
    assert baseline["validation_results"] == qa["validation_results"]
    decisions = {d["section_id"]: d for d in qa["quality_decisions"]}
    assert sum(d["status"] == "approved_for_index" for d in decisions.values()) == 154
    for c in evidence["sections"]:
        d = decisions[c["section_id"]]
        if c["assessment"] == "historical":
            assert d == c["historical_decision"]
        elif c["assessment"] == "candidate":
            assert d["status"] == "approved_for_index"
            assert d["basis"] == "markdown_verified_content_unit"
        else:
            assert d["status"] == "hold"
    publication = {
        "schema": "markdown-unit-QA-publication-1.0",
        "status": "AUTHORITATIVE_SHARED_QA",
        "qa": qa,
    }
    raw = encode(publication)
    (root / "SYNTHETIC-publication.json").write_bytes(raw)
    descriptor = dict(
        selection, publication_path="SYNTHETIC-publication.json", publication_sha256=digest(raw)
    )
    units = load_units(root, admission=descriptor)
    assert units and all(u["whole_unit_required"] for u in units)
    assert (
        len({m.get("section_id") or m["section"].section_id for u in units for m in u["members"]})
        == 137
    )
    # A staged evidence document cannot impersonate a QA publication, even when hash-pinned.
    with pytest.raises(ValueError, match="staged_or_unsupported"):
        load_units(
            root,
            admission=dict(
                descriptor,
                publication_path="evidence.json",
                publication_sha256=selection["expected_evidence_sha256"],
            ),
        )
    # Reject a tampered publication even if its new outer hash is supplied.
    forged = copy.deepcopy(publication)
    forged["qa"]["quality_decisions"][0]["status"] = "approved_for_index"
    (root / "forged.json").write_bytes(encode(forged))
    with pytest.raises(ValueError, match="not_authoritative_engine_output"):
        load_units(
            root,
            admission=dict(
                descriptor,
                publication_path="forged.json",
                publication_sha256=digest(encode(forged)),
            ),
        )


@pytest.mark.parametrize(
    "defect",
    [
        "missing_evidence",
        "source",
        "normalized",
        "provider",
        "fence",
        "heading",
        "release",
        "authorization",
        "forged_candidates",
        "incomplete_cohort",
    ],
)
def test_staged_invalid_evidence_fails_closed(staged, defect):
    root, selection, evidence = staged
    from rag_hub.acquire import digest
    from rag_hub.html_acquire import encode
    from rag_hub.validation_models import ValidationResult

    args = _arguments(root)
    baseline = shared_assess(*args)
    results = [ValidationResult.model_validate(r) for r in baseline["validation_results"]]
    changed, backup = None, None
    selection = dict(selection)
    if defect == "incomplete_cohort":
        args = list(args)
        args[4] = args[4][1:]
    elif defect == "missing_evidence":
        selection["evidence_path"] = "missing.json"
    else:
        path = {
            "source": evidence["source"]["raw_path"],
            "normalized": "data/normalized/markdown/C04.json",
            "provider": "data/normalized/markdown/C04.json",
            "fence": evidence["source"]["raw_path"],
            "heading": "data/parsed/markdown/C04.json",
            "release": "release.json",
            "authorization": "SYNTHETIC-auth.json",
            "forged_candidates": "evidence.json",
        }[defect]
        changed = root / path
        backup = changed.read_bytes()
        if defect == "forged_candidates":
            value = copy.deepcopy(evidence)
            value["sections"][0]["assessment"] = "candidate"
            changed.write_bytes(encode(value))
            selection["expected_evidence_sha256"] = digest(encode(value))
        elif defect in {"provider", "normalized", "heading"}:
            value = json.loads(backup)
            if defect == "heading":
                value["records"][1]["block"]["heading_path"] = ["wrong"]
            else:
                key = "provider_tab" if defect == "provider" else "text"
                value["records"][10]["section"][key] = "wrong"
            changed.write_bytes(encode(value))
        else:
            changed.write_bytes(backup + b"\nTAMPERED\n")
    try:
        with pytest.raises((ValueError, FileNotFoundError)):
            evidence_proofs(root, args[1], args[4], results, **selection)
    finally:
        if changed:
            changed.write_bytes(backup)


@pytest.mark.parametrize("format_name,doc_id", [("pdf", "C06"), ("html", "C03")])
def test_staged_markdown_policy_cannot_authorize_HTML_or_PDF(staged, format_name, doc_id):
    root, selection, _ = staged
    args = _arguments(root)
    source = args[1].model_copy(update={"doc_id": doc_id, "source_format": format_name})
    with pytest.raises(ValueError, match="cannot_cross_formats"):
        evidence_proofs(root, source, args[4], [], **selection)
    with pytest.raises(ValueError, match="source_identity_changed"):
        evidence_proofs(
            root, args[1].model_copy(update={"title": "forged"}), args[4], [], **selection
        )


def test_staged_unknown_hazard_and_partial_unit_are_not_overridden(staged):
    root, selection, evidence = staged
    from rag_hub.validation_models import QualityDecision, ValidationResult

    args = _arguments(root)
    qa = shared_assess(*args)
    results = [ValidationResult.model_validate(r) for r in qa["validation_results"]]
    candidate = next(
        c["section_id"] for c in evidence["sections"] if c["assessment"] == "candidate"
    )
    forged = [
        r.model_copy(update={"reasons": r.reasons + ("new_unresolved_hazard",)})
        if r.section_id == candidate
        else r
        for r in results
    ]
    with pytest.raises(ValueError, match="changed_Markdown_validation_results"):
        evidence_proofs(root, args[1], args[4], forged, **selection)
    excluded = next(c["section_id"] for c in evidence["sections"] if c["assessment"] == "excluded")
    forged = [
        r.model_copy(
            update={
                "risk": "low",
                "eligible_automatic": True,
                "reasons": (),
                "checks": {k: "pass" for k in r.checks},
            }
        )
        if r.section_id == excluded
        else r
        for r in results
    ]
    with pytest.raises(ValueError, match="changed_Markdown_validation_results"):
        evidence_proofs(root, args[1], args[4], forged, **selection)
    qualified = shared_assess(*args, markdown_qualification=selection)
    d = next(
        d for d in qualified["quality_decisions"] if d["basis"] == "markdown_verified_content_unit"
    )
    with pytest.raises(ValueError):
        QualityDecision.model_validate(
            d
        )  # Legacy readers cannot accept a new partial-unit decision.
