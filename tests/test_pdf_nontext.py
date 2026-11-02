"""Owned PDF fixtures distinguish non-text observations from missing source text."""

import base64
from dataclasses import replace
from pathlib import Path

import pymupdf
import pytest

from rag_hub.acquire import digest
from rag_hub.normalize import normalize_blocks
from rag_hub.parse_pdf import parse_pdf
from rag_hub.pdf_nontext import account_pdf_nontext, inspect_nontext
from rag_hub.schemas import SourceManifest
from rag_hub.shared.builtins import entries
from rag_hub.shared.pipeline import HOME, execute
from rag_hub.shared.registry import Registry
from rag_hub.shared.structure import assess

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="
)


def fixture(blank=False):
    with pymupdf.open() as pdf:
        p = pdf.new_page()
        if not blank:
            p.insert_text((72, 72), "Exact identifier all-MiniLM-L6-v2; value -17.25.")
            p.insert_image(pymupdf.Rect(100, 100, 150, 150), stream=PNG)
        data = pdf.tobytes()
    source = SourceManifest(
        doc_id="OWNED",
        snapshot_id="sha256-" + digest(data),
        canonical_url="https://example.invalid/owned",
        title="Owned PDF",
        publisher="Synthetic",
        source_format="pdf",
        raw_path=Path("data/raw/x.pdf"),
        raw_sha256=digest(data),
        rights_status="local_use_approved",
    )
    return data, source, parse_pdf(data, source)


def test_native_image_audit_sidecar_and_unchanged_source():
    data, source, blocks = fixture()
    original = [b.model_dump(mode="json") for b in blocks]
    sections, audit, sides, images = account_pdf_nontext(
        data, source, blocks, *normalize_blocks(blocks)
    )
    assert len(images) == len(audit) == 1
    assert audit[0]["before"] == "" and audit[0]["after"] is None
    assert images[0]["original_observation"] == original[1]
    assert images[0]["visual_content_status"] == "unprocessed_HOLD"
    assert sections[0].text == blocks[0].content
    assert len(sections) == 1 and sections[0].index_status == "hold"
    figure = next(s for s in sides if s.kind == "figure")
    assert figure.verification_status == "hold" and figure.source_locator == blocks[1].locator
    parents = entries()[0].parents(source, blocks, {})
    conformance = assess(parents, blocks, audit)
    assert conformance["audited_exclusions"] == [blocks[1].block_id]
    assert len(conformance["source_accounting"]) == 1
    assert [b.model_dump(mode="json") for b in blocks] == original


@pytest.mark.parametrize(
    "defect",
    [
        "blank_page",
        "empty_text",
        "forged_flag",
        "wrong_location",
        "foreign_snapshot",
        "wrong_sequence",
        "invented_image_text",
        "missing_observation",
        "bad_source_hash",
    ],
)
def test_unconfirmed_or_substantive_empty_content_fails(defect):
    data, source, blocks = fixture(blank=defect == "blank_page")
    if defect in ("empty_text", "forged_flag"):
        b = blocks[0]
        blocks[0] = b.model_copy(
            update={
                "content": "",
                "content_sha256": digest(b""),
                "block_type": "figure_caption" if defect == "forged_flag" else "prose",
                "issues": ("image_content_requires_visual_review",),
            }
        )
    if defect == "wrong_location":
        blocks[1] = blocks[1].model_copy(
            update={"locator": blocks[1].locator.model_copy(update={"bbox": (0.0, 0.0, 1.0, 1.0)})}
        )
    if defect == "foreign_snapshot":
        blocks[1] = blocks[1].model_copy(update={"snapshot_id": "foreign"})
    if defect == "wrong_sequence":
        blocks[1] = blocks[1].model_copy(update={"sequence": 999})
    if defect == "invented_image_text":
        blocks[1] = blocks[1].model_copy(
            update={"content": "invented", "content_sha256": digest(b"invented")}
        )
    if defect == "missing_observation":
        blocks.pop()
    if defect == "bad_source_hash":
        source = source.model_copy(update={"raw_sha256": "0" * 64})
    with pytest.raises(ValueError):
        inspect_nontext(data, source, blocks)


def test_removing_audit_proof_does_not_make_image_disappear():
    _data, source, blocks = fixture()
    parents = entries()[0].parents(source, blocks, {})
    with pytest.raises(ValueError, match="unreferenced_source_blocks"):
        assess(parents, blocks, [])


def test_invalid_zero_span_still_rejected():
    _data, source, blocks = fixture()
    from rag_hub.shared.structure import atomic_parents

    with pytest.raises(ValueError, match="invalid_parent_spans_or_completeness"):
        assess(atomic_parents(source, blocks, {}), blocks, [])


def test_shared_guards_policy_and_contracts_are_reused():
    root = Path(__file__).resolve().parents[1]
    for original, promoted in (
        ("workspace/pdf-remediation/guard.py", "src/rag_hub/shared/guard.py"),
        ("workspace/pdf-remediation/report_contract.py", "src/rag_hub/shared/stage_contract.py"),
        ("workspace/ext01/v1/foundation/rag_ext01/structure.py", "src/rag_hub/shared/structure.py"),
        ("workspace/ext01/v1/foundation/rag_ext01/contracts.py", "src/rag_hub/shared/contracts.py"),
        ("workspace/ext01/v1/foundation/rag_ext01/registry.py", "src/rag_hub/shared/registry.py"),
    ):
        if (root / original).exists():
            assert (root / original).read_bytes() == (root / promoted).read_bytes()

    # Preserve exact historical equality against matching archived implementation,
    # not newer current code. All manifest entries and its original receipt verify.
    from historical_replay import historical_foundation_files

    freeze, chosen = historical_foundation_files()
    for name in ("content_validation", "validation_models", "validation_reviews"):
        rel = f"src/rag_hub/{name}.py"
        assert digest(chosen[rel].read_bytes()) == freeze["files"][rel]


def test_current_shared_policy_contracts_and_behavior_are_compatible(tmp_path):
    from rag_hub.shared import pipeline
    from rag_hub.validation_models import ValidationPolicy

    policy_path = Path(__file__).resolve().parents[1] / "config/validation-policy.json"
    policy = ValidationPolicy.model_validate_json(policy_path.read_bytes())
    assert digest(policy_path.read_bytes()) == (
        "63e25ee13339cf069308233d7d0d007a58e59edca5d24cee77d092730cba4a71"
    )
    assert policy.expected_hold_count == 1665
    # The real shared path, unchanged contracts and sole QA owner execute on owned input.
    assert pipeline.verify_foundation()["version"] == "publication-reader-regression-only"


@pytest.mark.parametrize(
    "failure",
    ["empty_substantive", "missing_fidelity", "bad_span", "parser_failure", "duplicate_id"],
)
def test_maintained_shared_failures_publish_explicit_outcomes(failure):
    import tempfile

    root = Path(__file__).resolve().parents[1]
    if not (HOME / "foundation-freeze.json").exists():
        pytest.skip("private qualified successor release not supplied")
    data, source, _blocks = fixture()
    with tempfile.TemporaryDirectory(prefix=".owned-negative-", dir=HOME) as d:
        path = Path(d) / "source.pdf"
        path.write_bytes(data)
        source = source.model_copy(
            update={
                "raw_path": path.relative_to(root),
                "snapshot_path": path.relative_to(root),
                "byte_size": len(data),
            }
        )
        adapter = entries()[0]
        if failure in ("empty_substantive", "parser_failure", "duplicate_id"):

            class Parser:
                def parse(self, src):
                    if failure == "parser_failure":
                        raise ValueError("owned_parser_failure")
                    values = parse_pdf(data, src)
                    if failure == "empty_substantive":
                        values[0] = values[0].model_copy(
                            update={"content": "", "content_sha256": digest(b"")}
                        )
                    if failure == "duplicate_id":
                        values.append(values[0])
                    return values

            def factory(data, options):
                return Parser()

            adapter = replace(adapter, parser_factory=factory)
        if failure == "missing_fidelity":

            def fidelity(*args):
                return []

            adapter = replace(adapter, fidelity=fidelity)
        if failure == "bad_span":

            def parents(src, values, options):
                result = entries()[0].parents(src, values, options)
                result[0]["members"][0]["end"] += 1
                return result

            adapter = replace(adapter, parents=parents)
        record = execute(
            source.model_dump(mode="json"), Registry((adapter,)), output=Path(d) / "out"
        )
        assert record["program_status"] == "failed", record["diagnostics"]
        assert record["stages"][-1]["status"] == "not_executed"
        assert not (Path(d) / "out/LATEST.json").exists()
        assert len({(s["stage"], s["source_id"], s["attempt_id"]) for s in record["stages"]}) == 5


@pytest.mark.parametrize(
    "defect",
    [
        "wrong_hash",
        "missing_component",
        "missing_dependency",
        "bad_dependency_version",
        "rewritten_receipt",
    ],
)
def test_successor_fingerprint_failures_are_explicit(defect, record_property):
    import json
    import tempfile

    if not (HOME / "foundation-freeze.json").exists():
        pytest.skip("private qualified successor release not supplied")
    root = Path(__file__).resolve().parents[1]
    data, source, _blocks = fixture()
    with tempfile.TemporaryDirectory(prefix=".release-negative-", dir=HOME) as d:
        path = Path(d)
        pdf = path / "fixture.pdf"
        pdf.write_bytes(data)
        source = source.model_copy(
            update={
                "raw_path": pdf.relative_to(root),
                "snapshot_path": pdf.relative_to(root),
                "byte_size": len(data),
            }
        )
        from rag_hub.shared.pipeline import verify_foundation

        # This verifies every bound component before any mutation. A successful owned
        # execution proves subsequent failures are caused by the single injected defect.
        verify_foundation(HOME)
        baseline = execute(
            source.model_dump(mode="json"), Registry(entries()),
            output=path / "baseline", release=HOME,
        )
        assert baseline["program_status"] == "completed", baseline["diagnostics"]
        assert [row["status"] for row in baseline["stages"]] == [
            "success", "success", "success", "partial", "not_executed",
        ]
        assert not baseline["stages"][-1]["checks"]  # No readiness/admission execution.
        freeze = json.loads((HOME / "foundation-freeze.json").read_bytes())
        expected = {
            "wrong_hash": "ValueError: foundation_fingerprint_mismatch: src/rag_hub/pdf_nontext.py",
            "missing_component": "foundation_file_set_changed",
            "missing_dependency": "FileNotFoundError",
            "bad_dependency_version": "dependency_version_mismatch",
            "rewritten_receipt": "foundation_manifest_rewritten_after_freeze",
        }[defect]
        if defect == "wrong_hash":
            freeze["files"]["src/rag_hub/pdf_nontext.py"] = "0" * 64
        if defect == "missing_component":
            freeze["files"].pop("src/rag_hub/shared/guard.py")
        if defect == "missing_dependency":
            freeze["files"]["workspace/does-not-exist-protected.py"] = "0" * 64
        if defect == "bad_dependency_version":
            freeze["dependencies"]["pydantic"] = "0.0.0"
        if defect == "rewritten_receipt":
            (path / "foundation-freeze-receipt.json").write_text(
                json.dumps({"foundation_manifest_sha256": "0" * 64})
            )
        (path / "foundation-freeze.json").write_text(json.dumps(freeze))
        record = execute(
            source.model_dump(mode="json"), Registry(entries()), output=path / "out", release=path
        )
        assert record["program_status"] == "failed"
        error = record["diagnostics"]["error"]
        if defect == "missing_dependency":
            assert error.startswith("FileNotFoundError:")
            assert "workspace/does-not-exist-protected.py" in error
        elif defect == "wrong_hash":
            assert error == expected  # A different component cannot satisfy this test.
        else:
            assert error == "ValueError: " + expected
        record_property("baseline_program_status", baseline["program_status"])
        record_property("injected_defect", defect)
        record_property("actual_error", error)
        record_property("failure_stage", record["stages"][0]["stage"])
        assert record["stages"][0]["stage"] == "acquisition"
        assert record["stages"][0]["checks"][0]["outcome"] == "fail"
        assert [s["status"] for s in record["stages"]] == [
            "failure",
            "blocked",
            "blocked",
            "blocked",
            "not_executed",
        ]


@pytest.mark.parametrize("missing", ["prefix", "internal", "suffix"])
def test_source_character_omissions_still_fail(missing):
    from rag_hub.shared.structure import parent, span

    _data, source, blocks = fixture()
    b = blocks[0]
    members = {
        "prefix": [span(b, 1)],
        "internal": [span(b, 0, 5), span(b, 6)],
        "suffix": [span(b, 0, len(b.content) - 1)],
    }[missing]
    p = parent("owned", "paragraph", members, source, {b.block_id: b})
    with pytest.raises(ValueError, match="invalid_parent_spans_or_completeness"):
        assess([p], [b], [])
