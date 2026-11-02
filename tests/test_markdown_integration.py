"""Actual selected Markdown publication and cross-format compatibility controls."""

import copy
import json
from pathlib import Path

import pytest

from rag_hub.acquire import digest
from rag_hub.html_acquire import encode
from rag_hub.markdown_handoff import load_units
from rag_hub.markdown_illustrative import validate_illustrative_handoff
from rag_hub.markdown_qualification import verify_release

ROOT = Path(__file__).resolve().parents[1]
SELECTOR = ROOT / "config/markdown-admission-publication-v1-1.json"


@pytest.fixture(scope="module")
def published():
    if not SELECTOR.exists():
        pytest.skip("owner-selected Markdown publication not installed")
    selection = json.loads(SELECTOR.read_bytes())
    units = load_units(ROOT, **selection)
    admission = selection["admission"]
    publication = json.loads((ROOT / admission["publication_path"]).read_bytes())
    return selection, units, publication


def test_actual_publication_is_complete_and_preserves_legacy(published):
    selection, units, publication = published
    decisions = publication["qa"]["quality_decisions"]
    approved = {d["section_id"] for d in decisions if d["status"] == "approved_for_index"}
    assert len(decisions) == 158 and len(approved) == 154
    assert len(units) == 86
    assert sum(u["historical_approval_only"] for u in units) == 27
    assert sum(not u["historical_approval_only"] for u in units) == 59
    ids = {
        m.get("section_id") or m["section"].section_id for u in units for m in u["members"]
    } | {sid for u in units for sid in u["supporting_heading_ids"]}
    assert ids == approved
    historical = {
        m["section"].section_id: m["decision"]
        for u in load_units(ROOT)
        for m in u["members"]
    }
    assert len(historical) == 40
    assert all(next(d for d in decisions if d["section_id"] == sid) == d for sid, d in historical.items())
    a = selection["admission"]
    assert verify_release(ROOT, a["qa_release_path"], a["expected_qa_release_sha256"])[
        "version"
    ] == "combined-markdown-qa-1.1"


def test_published_restricted_units_have_no_raw_text_fallback(published):
    _, units, _ = published
    restricted = [u for u in units if u.get("restricted_projection")]
    assert len(restricted) == 4
    for unit in restricted:
        validate_illustrative_handoff(ROOT, unit)
        assert unit["source_evidence_is_retrievable"] is False
        assert all("section" not in m for m in unit["members"])
        payload = unit["restricted_projection"]
        assert payload["warnings"]
        assert all(w in payload["consumable_text"] for w in payload["warnings"])


@pytest.mark.parametrize("tamper", ["partial", "forged", "warnings", "wrong_hash"])
def test_actual_publication_tampering_fails_closed(published, tmp_path, monkeypatch, tamper):
    import rag_hub.markdown_handoff as handoff

    selection, _, publication = published
    altered = copy.deepcopy(publication)
    descriptor = dict(selection["admission"])
    if tamper == "partial":
        altered["qa"]["quality_decisions"].pop()
    elif tamper == "forged":
        next(d for d in altered["qa"]["quality_decisions"] if d["status"] == "hold")[
            "status"
        ] = "approved_for_index"
    elif tamper == "warnings":
        decision = next(
            d for d in altered["qa"]["quality_decisions"] if ":b00091:" in d["section_id"]
        )
        decision["scope"]["units"][0]["restricted_projection"]["warnings"] = []
    path = tmp_path / "corrupt-publication.json"
    path.write_bytes(encode(altered))
    original = handoff.local_path
    monkeypatch.setattr(
        handoff, "local_path", lambda root, name: path if name == "CONTROL.json" else original(root, name)
    )
    descriptor.update(publication_path="CONTROL.json", publication_sha256=digest(path.read_bytes()))
    if tamper == "wrong_hash":
        descriptor["publication_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="hash_mismatch|not_authoritative_engine_output"):
        load_units(ROOT, admission=descriptor)


@pytest.mark.parametrize(
    "name", ["html-auto-qa-successor", "html-context-qa-successor", "html-text-qa-successor"]
)
def test_actual_HTML_predecessor_verifies_under_integrated_identity(name):
    from rag_hub.html_qualification import verify_release as verify_html

    path = f"config/{name}.json"
    verify_html(ROOT, path, digest((ROOT / path).read_bytes()))


def test_unlisted_HTML_predecessor_cannot_claim_compatibility(tmp_path, monkeypatch):
    import rag_hub.html_qualification as html

    original = html.local_path
    raw = (ROOT / "config/html-text-qa-successor.json").read_bytes()
    path = tmp_path / "untrusted-parent.json"
    path.write_bytes(raw)
    monkeypatch.setattr(
        html, "local_path", lambda root, name: path if name == "UNLISTED.json" else original(root, name)
    )
    with pytest.raises(ValueError, match="unapproved_Markdown_compatibility"):
        html.verify_release(ROOT, "UNLISTED.json", digest(raw))


@pytest.mark.parametrize("tamper", ["validator_stamp", "cohort_stamp", "sample_membership"])
def test_HTML_compatibility_does_not_ignore_forged_sampling_metadata(tmp_path, monkeypatch, tamper):
    import rag_hub.html_handoff as handoff

    selection = json.loads((ROOT / "config/html-text-admission-publication.json").read_bytes())
    manifest = json.loads((ROOT / selection["manifest_path"]).read_bytes())
    entry = manifest["publications"][0]
    original_path = entry["path"]
    publication = json.loads((ROOT / original_path).read_bytes())
    qa = publication["qa"]
    if tamper == "validator_stamp":
        qa["sample"]["validator_sha256"] = "0" * 64
    elif tamper == "cohort_stamp":
        next(iter(qa["cohort_gates"].values()))["qualification_sha256"] = "0" * 64
    else:
        qa["sample"]["selected_ids"] = []
    fake = tmp_path / "html-publication.json"
    fake.write_bytes(encode(publication))
    entry["sha256"] = digest(fake.read_bytes())
    selected = tmp_path / "html-manifest.json"
    selected.write_bytes(encode(manifest))
    original = handoff.local_path
    replacements = {original_path: fake, selection["manifest_path"]: selected}
    monkeypatch.setattr(
        handoff, "local_path", lambda root, name: replacements.get(str(name)) or original(root, name)
    )
    with pytest.raises(ValueError, match="partial_forged_or_neighboring"):
        handoff.load_units(
            ROOT, **dict(selection, expected_manifest_sha256=digest(selected.read_bytes()))
        )
