"""Actual shared candidate execution path; sole publisher per stage/source/attempt."""

import copy
import importlib.metadata
import io
import json
import resource
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import rag_hub
from rag_hub.acquire import digest, local_path
from rag_hub.normalize import normalize_blocks
from rag_hub.pdf_classification import classify_pdf, load_evidence, route_parents
from rag_hub.pdf_nontext import account_pdf_nontext
from rag_hub.schemas import ParsedBlock

from . import VERSION
from .contracts import read_source
from .evidence import ROOT, STAGES, Check, Execution, Issue, StageResult
from .qa import assess as assess_qa
from .structure import assess as assess_parents

HOME = ROOT / "workspace/pdf-remediation/phase3/level1-remediation-v1/release-v2"


def encoded(value):
    # Identical canonical bytes without retaining a full Unicode string and the
    # encoder's complete chunk list alongside the source/evidence graph.
    stream = io.BytesIO()
    encoder = json.JSONEncoder(sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False)
    for chunk in encoder.iterencode(value):
        stream.write(chunk.encode())
    stream.write(b"\n")
    return stream.getvalue()


def verify_foundation(home=None):
    home = Path(home or HOME).resolve()
    freeze = json.loads((home / "foundation-freeze.json").read_text())
    if Path(rag_hub.__file__).resolve() != ROOT / "src/rag_hub/__init__.py":
        raise ValueError("unexpected_legacy_import_origin")
    for name, expected in freeze["files"].items():
        if digest(local_path(ROOT, name).read_bytes()) != expected:
            raise ValueError("foundation_fingerprint_mismatch: " + name)
    actual_files = {
        str(p.relative_to(ROOT))
        for p in (ROOT / "src/rag_hub/shared").rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }
    expected_files = {p for p in freeze["files"] if p.startswith("src/rag_hub/shared" + "/")}
    if actual_files != expected_files:
        raise ValueError("foundation_file_set_changed")
    receipt_path = home / "foundation-freeze-receipt.json"
    if (
        receipt_path.exists()
        and digest((home / "foundation-freeze.json").read_bytes())
        != json.loads(receipt_path.read_text())["foundation_manifest_sha256"]
    ):
        raise ValueError("foundation_manifest_rewritten_after_freeze")
    actual = {p: importlib.metadata.version(p) for p in freeze["dependencies"]}
    if actual != freeze["dependencies"]:
        raise ValueError("dependency_version_mismatch")
    return freeze


def immutable(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError("immutable_artifact_mismatch")
    else:
        with path.open("xb") as stream:
            stream.write(data)


def execute(manifest, registry, *, output=None, release=None):
    home = Path(release or HOME).resolve()
    started = datetime.now(UTC)
    tick = time.perf_counter()
    attempt = started.strftime("%Y%m%dT%H%M%S.%fZ-") + uuid4().hex[:8]
    output = Path(output or home).resolve()
    if not output.is_relative_to(home.resolve()):
        raise ValueError("candidate_output_must_stay_in_private_workstream")
    source_id = str(manifest.get("doc_id", "unresolved-source"))
    source, run_id, error, active = None, None, None, "acquisition"
    stage_values, payloads, artifacts, fingerprints = {}, {}, {}, {}
    verified_artifacts = {}
    fingerprint_manifest = None
    try:
        freeze = verify_foundation(home)
        fingerprints = freeze["files"]
        fingerprint_manifest = digest(encoded(freeze))
        source = read_source(manifest)
        source_id = source.doc_id
        if source.rights_status not in ("local_use_approved", "redistribution_approved"):
            raise ValueError("local_use_not_authorized")
        if source.snapshot_path is None:
            raise ValueError("missing_existing_snapshot_reference")
        data = local_path(ROOT, source.snapshot_path).read_bytes()
        raw = local_path(ROOT, source.raw_path).read_bytes()
        if raw != data or digest(data) != source.raw_sha256 or len(data) != source.byte_size:
            raise ValueError("local_fixture_source_integrity_mismatch")
        verified_artifacts = {str(source.raw_path): source.raw_sha256}
        payloads["source.json"] = source.model_dump(mode="json")
        stage_values[active] = (
            "success",
            started,
            datetime.now(UTC),
            [
                Check(
                    name="existing_local_bytes_verified",
                    dimension="source_fidelity",
                    outcome="pass",
                    evidence=("source.json",),
                )
            ],
            [],
        )
        active, stage_start = "parsing", datetime.now(UTC)
        adapter = registry.resolve(source.source_format)
        component = adapter.identity()
        parser = adapter.parser_factory(data, copy.deepcopy(component["options"]))
        values = list(parser.parse(source))
        blocks = [
            ParsedBlock.model_validate(b.model_dump(mode="json") if hasattr(b, "model_dump") else b)
            for b in values
        ]
        if not blocks or len({b.block_id for b in blocks}) != len(blocks):
            raise ValueError("missing_or_duplicate_block_ids")
        if [b.sequence for b in blocks] != list(range(len(blocks))):
            raise ValueError("invalid_block_sequence")
        if any(
            (b.doc_id, b.raw_sha256, b.snapshot_id)
            != (source.doc_id, source.raw_sha256, source.snapshot_id)
            for b in blocks
        ):
            raise ValueError("foreign_block_provenance")
        if any(str(b.locator.url) != str(source.canonical_url) for b in blocks):
            raise ValueError("foreign_block_source_locator")
        payloads["source.json"] = source.model_dump(mode="json")
        payloads["blocks.json"] = [b.model_dump(mode="json") for b in blocks]
        payloads["component.json"] = component
        classifications = None
        if source.source_format == "pdf":
            type_descriptor = component["options"].get("classification_evidence")
            type_evidence = None
            if type_descriptor:
                type_evidence, _type_assets = load_evidence(ROOT, type_descriptor["bundle_path"])
                if type_evidence["bundle_sha256"] != type_descriptor["bundle_sha256"]:
                    raise ValueError("classification_bundle_changed_during_attempt")
            classifications = classify_pdf(
                data,
                source,
                blocks,
                type_evidence,
                component["options"].get("reviewed_split"),
            )
            payloads["pdf-classification.json"] = classifications
            del type_evidence  # Keep the audited classification, not duplicated raw proposals.
        stage_values[active] = (
            "success",
            stage_start,
            datetime.now(UTC),
            [
                Check(
                    name="registered_parser_blocks",
                    dimension="execution",
                    outcome="pass",
                    evidence=("blocks.json", "component.json"),
                )
            ],
            [],
        )
        if classifications is not None:
            stage_values[active][3].append(
                Check(
                    name="pdf_classification_provenance_and_accounting",
                    dimension="source_accounting",
                    outcome="pass",
                    evidence=("pdf-classification.json",),
                )
            )
        active, stage_start = "normalization", datetime.now(UTC)
        sections, audit, sidecars = normalize_blocks(blocks)
        nontext = []
        if source.source_format == "pdf":
            sections, audit, sidecars, nontext = account_pdf_nontext(
                data, source, blocks, sections, audit, sidecars
            )
        parents = adapter.parents(source, blocks, copy.deepcopy(component["options"]))
        structure = assess_parents(parents, blocks, audit)
        if classifications is not None:
            parents, routing = route_parents(classifications, parents, blocks)
            from rag_hub.pdf_structure import reconstruct_pdf

            parents, reconstruction = reconstruct_pdf(classifications, parents, blocks, source)
            payloads["reconstruction-routing.json"] = routing
            payloads["pdf-structural-evidence.json"] = reconstruction
            structure = assess_parents(parents, blocks, audit)
        reviewed = component["options"].get("reviewed_split")
        if reviewed and all(
            getattr(source, k) == reviewed["owner_case"]["source"][k]
            for k in ("doc_id", "raw_sha256", "snapshot_id")
        ):
            spec = reviewed["constraint"]
            payloads["review-facets.json"] = {
                "owner_case": reviewed["owner_case"],
                "mathematical_completeness": "FAIL/HOLD",
                "relationships": [
                    {
                        "from": "bpr01:" + spec["case_id"] + ":0",
                        "to_block": spec[key],
                        "type": kind,
                        "status": "unresolved_HOLD",
                        "source_sha256": source.raw_sha256,
                        "snapshot_id": source.snapshot_id,
                    }
                    for key, kind in (
                        ("unresolved_symbol", "unresolved_inline_symbol_dependency"),
                        ("separate_equation", "related_equation"),
                    )
                ],
                "eligibility": "HOLD",
            }
        payloads.update(
            {
                "sections.json": [s.model_dump(mode="json") for s in sections],
                "audit.json": audit,
                "sidecars.json": [s.model_dump(mode="json") for s in sidecars],
                "parents.json": parents,
                "structure.json": structure,
                "nontext.json": nontext,
            }
        )
        stage_values[active] = (
            "success",
            stage_start,
            datetime.now(UTC),
            [
                Check(
                    name="source_parent_conformance",
                    dimension="source_accounting",
                    outcome="pass",
                    evidence=("parents.json", "structure.json"),
                )
            ],
            [],
        )
        active, stage_start = "quality_assurance", datetime.now(UTC)
        # Actual deterministic input bundle, distinct from final validation output.
        input_artifacts = {
            "manifest.json": [source.model_dump(mode="json")],
            "blocks.jsonl": payloads["blocks.json"],
            "sections.jsonl": payloads["sections.json"],
            "holds.jsonl": payloads["sections.json"],
            "audit.jsonl": audit,
            "sidecars.jsonl": payloads["sidecars.json"],
            "reviews.json": [],
            "report.json": {
                "component": component,
                "foundation": fingerprint_manifest,
                "source": source.raw_sha256,
                "original_approvals": 0,
                "sections": len(sections),
            },
        }
        if classifications is not None:
            input_artifacts["report.json"]["pdf_classification"] = classifications
        input_hashes = {name: digest(encoded(value)) for name, value in input_artifacts.items()}
        input_id = digest(encoded(input_hashes))
        qa = assess_qa(
            ROOT,
            source,
            data,
            blocks,
            sections,
            audit,
            adapter,
            input_id,
            input_hashes,
            classifications=classifications,
        )
        if adapter.identity() != component:
            raise ValueError("adapter_configuration_or_code_changed_during_attempt")
        verify_foundation(home)
        payloads["qa.json"] = qa
        payloads["input-bundle.json"] = {
            "input_id": input_id,
            "hashes": input_hashes,
            "artifacts": input_artifacts,
            "encoding": "canonical JSON values keyed by legacy artifact role; not legacy on-disk JSONL",
        }
        payloads["source-witness.json"] = {
            "source_sha256": source.raw_sha256,
            "decoded_codepoints": len(data.decode("utf-8"))
            if source.source_format != "pdf"
            else None,
            "blocks": len(blocks),
            "parent_relations": len(structure["relationships"]),
            "fidelity_component": component["callables"],
        }
        qa_checks = [Check.model_validate(c) for c in qa["fidelity_checks"]]
        qa_checks.append(
            Check(
                name="source_structure",
                dimension="structure",
                outcome="pass",
                evidence=("structure.json",),
            )
        )
        qa_checks.append(
            Check(
                name="content_qualification",
                dimension="structure",
                outcome="pending",
                evidence=("qa.json",),
            )
        )
        if classifications is not None:
            qa_checks.append(
                Check(
                    name="pdf_semantic_classification_qualification",
                    dimension="structure",
                    outcome="pending",
                    evidence=("pdf-classification.json", "qa.json"),
                )
            )
        issues = [
            Issue(
                issue_id=source_id + ":qualification",
                code="registration_is_not_qualification",
                severity="warning",
                dimension="structure",
                detail="Existing quality authority retains HOLD; no readiness gate executed.",
                evidence={"source_id": source_id},
                artifact_refs=("qa.json",),
            )
        ]
        qa_status = "failure" if qa["source_fidelity"] == "fail" else "partial"
        if qa_status == "failure":
            issues.append(
                Issue(
                    issue_id=source_id + ":fidelity",
                    code="source_fidelity_failed",
                    severity="error",
                    dimension="source_fidelity",
                    detail="Registered independent source checker detected mismatch.",
                    evidence={"source_id": source_id},
                    artifact_refs=("qa.json",),
                )
            )
        stage_values[active] = (qa_status, stage_start, datetime.now(UTC), qa_checks, issues)
        payloads["identity.json"] = {
            "foundation_sha256": fingerprint_manifest,
            "component": component,
            "source": source.model_dump(mode="json"),
            "lock_sha256": freeze["files"]["uv.lock"],
        }
        run_id = digest(encoded({name: digest(encoded(value)) for name, value in payloads.items()}))
        for name, value in payloads.items():
            path = output / "runs" / run_id / name
            serialized = encoded(value)
            immutable(path, serialized)
            artifacts[str(path.relative_to(ROOT))] = digest(serialized)
            del serialized
    except Exception as exc:  # noqa: BLE001 -- publish every in-path failure through same owner
        error = type(exc).__name__ + ": " + str(exc)
        failure_evidence = getattr(exc, "evidence", {})
        issue = Issue(
            issue_id=source_id + ":" + active + ":failure",
            code="stage_execution_failed",
            severity="error",
            dimension="execution",
            detail=error,
            evidence={"active_stage": active},
            artifact_refs=("attempt_record",),
        )
        stage_values[active] = (
            "failure",
            locals().get("stage_start", started),
            datetime.now(UTC),
            [
                Check(
                    name="stage_execution",
                    dimension="execution",
                    outcome="fail",
                    evidence=("attempt_record",),
                )
            ],
            [issue],
        )
    if error:
        payloads["failure.json"] = {
            "stage": active,
            "error": error,
            "source_id": source_id,
            "evidence": locals().get("failure_evidence", {}),
        }
        run_id = digest(encoded({name: digest(encoded(value)) for name, value in payloads.items()}))
        for name, value in payloads.items():
            path = output / "runs" / run_id / name
            immutable(path, encoded(value))
            artifacts[str(path.relative_to(ROOT))] = digest(encoded(value))
    # Preflight failures may precede source loading/artifacts. Identity and failures
    # remain visible; other stages never receive fabricated successful outcomes.
    rows = []
    failed_upstream = False
    for stage in STAGES:
        if stage in stage_values:
            status, begin, end, checks, issues = stage_values[stage]
            failed_upstream = failed_upstream or status == "failure"
        elif stage != "ingestion_readiness_gate" and failed_upstream:
            status, begin, end = "blocked", datetime.now(UTC), datetime.now(UTC)
            checks = [
                Check(
                    name="upstream_evidence",
                    dimension="execution",
                    outcome="fail",
                    evidence=("attempt_record",),
                )
            ]
            issues = [
                Issue(
                    issue_id=source_id + ":" + stage + ":blocked",
                    code="upstream_stage_failed",
                    severity="error",
                    dimension="execution",
                    detail="Required upstream evidence failed; stage not processed.",
                    evidence={"failed_stage": active},
                    artifact_refs=("attempt_record",),
                )
            ]
        else:
            status, begin, end, checks, issues = "not_executed", None, None, [], []
        # A failure after a source has loaded still needs an artifact evidence map;
        # otherwise success rows are unsafe. Reference the immutable local fixture.
        row_artifacts = artifacts or verified_artifacts
        contributors = {
            "acquisition": (
                "rag_hub.acquire.local_path",
                "rag_hub.acquire.digest",
                "verified-existing-local-bytes",
            ),
            "parsing": tuple(component["callables"][:1])
            if "component" in locals()
            else ("trusted-registry-validation",),
            "normalization": (
                "rag_hub.normalize.normalize_blocks",
                "original-span-guard",
                "declared-parent-conformance",
            ),
            "quality_assurance": (
                "rag_hub.content_validation.validate_section",
                "registered-fidelity-checker",
                "rag_hub.validation_reviews.make_decisions",
            ),
        }
        rows.append(
            StageResult(
                source_id=source_id,
                stage=stage,
                attempt_id=attempt,
                publisher="ext01-" + stage + "-owner"
                if status != "not_executed"
                else "not_invoked",
                publisher_version=VERSION,
                status=status,
                source=source,
                components=contributors.get(stage, ()) if status != "not_executed" else (),
                artifacts=row_artifacts if status != "not_executed" else {},
                checks=tuple(checks),
                issues=tuple(issues),
                provenance=tuple(fingerprints),
                started_at=begin,
                ended_at=end,
                note="Local owned-input conformance only; no new corpus acquisition, eligibility or readiness permission.",
            )
        )
    execution = Execution(
        attempt_id=attempt,
        started_at=started,
        ended_at=datetime.now(UTC),
        run_id=run_id,
        program_status="failed" if error else "completed",
        fingerprints=fingerprints,
        stages=tuple(rows),
        diagnostics={
            "error": error,
            "wall_seconds": time.perf_counter() - tick,
            "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            * (1 if sys.platform == "darwin" else 1024),
        },
    )
    record = execution.model_dump(mode="json")
    immutable(output / "attempts" / (attempt + ".json"), encoded(record))
    # Content/QA failures do not publish a successful pointer either.
    if not error and all(r.status not in ("failure", "blocked") for r in rows):
        (output / "LATEST.json").write_bytes(
            encoded(
                {
                    "run_id": run_id,
                    "attempt_id": attempt,
                    "qualification": "not granted; all content HOLD",
                }
            )
        )
    return record
