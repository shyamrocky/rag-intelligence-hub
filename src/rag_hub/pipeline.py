"""Offline G0–G2 orchestration; no chunking, inference, indexing or retrieval."""

import importlib.metadata
import json
import tempfile
from collections import Counter
from pathlib import Path

from rag_hub.acquire import acquire_sources, digest, load_registry, local_path, verify_source
from rag_hub.normalize import normalize_blocks
from rag_hub.parse_markdown import parse_markdown
from rag_hub.parse_pdf import parse_pdf
from rag_hub.pdf_classification import classify_pdf, load_evidence
from rag_hub.quality import apply_reviews
from rag_hub.schemas import ReviewReceipt

IMPLEMENTATION_MODULES = (
    "acquire",
    "schemas",
    "parse_markdown",
    "parse_pdf",
    "normalize",
    "quality",
    "pipeline",
    "pdf_classification",
    "pdf_nontext",
    "shared/guard",
    "shared/structure",
)


def encode(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def jsonl(records) -> str:
    return "".join(
        json.dumps(
            r.model_dump(mode="json") if hasattr(r, "model_dump") else r,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n"
        for r in records
    )


def verify_inputs(root: Path, registry_path: str = "config/sources.json"):
    registry = load_registry(root, registry_path)
    results = []
    for spec in registry.sources:
        data = verify_source(root, spec)
        results.append(
            {
                "doc_id": spec.doc_id,
                "byte_size": len(data),
                "sha256": digest(data),
                "historical_manifest_match": True,
            }
        )
    return results


def ingest(
    root: Path,
    *,
    registry_path="config/sources.json",
    use_basis: str,
    reviews_path: str | None = None,
    source_manifest: str | None = None,
    release: str | None = None,
    pdf_constraints: str | None = None,
    pdf_classification_evidence: str | None = None,
    output: str | None = None,
) -> dict:
    root = root.resolve()
    if source_manifest is not None:
        if reviews_path or not use_basis.strip():
            raise ValueError(
                "maintained shared ingestion requires local-use basis and no legacy receipts"
            )
        from dataclasses import replace

        from rag_hub.shared.builtins import entries
        from rag_hub.shared.evidence import ROOT
        from rag_hub.shared.pipeline import execute
        from rag_hub.shared.registry import Registry

        if root != ROOT or release is None or output is None:
            raise ValueError(
                "shared ingestion requires project root, pinned release and private output"
            )

        def private(path):
            value = local_path(root, path)
            if not any(value.is_relative_to(root / d) for d in ("workspace", "data")):
                raise ValueError("shared inputs and outputs must remain private")
            return value

        adapters = list(entries())
        if pdf_constraints:
            bundle = json.loads(private(pdf_constraints).read_bytes())
            if bundle.get("schema") != "reviewed-pdf-split-1.0":
                raise ValueError("unsupported_constraint_bundle")
            adapters[0] = replace(
                adapters[0], options={"reviewed_split": bundle}, assets=(private(pdf_constraints),)
            )
        if pdf_classification_evidence:
            evidence, assets = load_evidence(root, pdf_classification_evidence)
            adapters[0] = replace(
                adapters[0],
                options={
                    **adapters[0].options,
                    "classification_evidence": {
                        "bundle_path": str(private(pdf_classification_evidence).relative_to(root)),
                        "bundle_sha256": evidence["bundle_sha256"],
                    },
                },
                assets=(*adapters[0].assets, *assets),
            )
        if pdf_classification_evidence:
            del evidence  # Referenced artifacts are loaded inside the Parsing boundary.
        return execute(
            json.loads(private(source_manifest).read_bytes()),
            Registry(adapters),
            release=private(release),
            output=private(output),
        )
    if any(v is not None for v in (release, pdf_constraints, output)):
        raise ValueError("shared options require source_manifest")
    registry = load_registry(root, registry_path)
    manifests = acquire_sources(root, registry, use_basis)
    blocks = []
    classifications = {}
    evidence = (
        load_evidence(root, pdf_classification_evidence)[0] if pdf_classification_evidence else None
    )
    for source, spec in zip(manifests, registry.sources, strict=True):
        data = local_path(root, source.snapshot_path).read_bytes()
        if digest(data) != source.raw_sha256:
            raise ValueError("snapshot integrity mismatch")
        if source.source_format == "pdf":
            extracted = parse_pdf(data, source, spec.expected_pages)
            classifications[source.doc_id] = classify_pdf(data, source, extracted, evidence)
            blocks.extend(extracted)
        else:
            blocks.extend(parse_markdown(data, source))
    sections, audit, sidecars = normalize_blocks(blocks)
    receipts = []
    if reviews_path:
        path = local_path(root, reviews_path)
        if not path.is_relative_to(root / "workspace") and not path.is_relative_to(root / "data"):
            raise ValueError("review receipts must be stored privately under workspace/ or data/")
        receipts = [ReviewReceipt.model_validate(r) for r in json.loads(path.read_text())]
        sections = apply_reviews(sections, receipts)
    approved = {s.section_id for s in sections if s.index_status == "approved_for_index"}
    sidecars = [s for s in sidecars if not (s.kind == "mixed_pdf" and s.section_id in approved)]
    versions = {
        package: importlib.metadata.version(package)
        for package in ("pymupdf", "markdown-it-py", "pydantic")
    }
    code_hash = digest(
        b"".join((Path(__file__).parent / (m + ".py")).read_bytes() for m in IMPLEMENTATION_MODULES)
    )
    identity = {
        "registry": registry.model_dump(mode="json"),
        "versions": versions,
        "implementation_sha256": code_hash,
        "use_basis": use_basis,
        "receipts": [r.model_dump(mode="json") for r in receipts],
        "pdf_classification_sha256": digest(encode(classifications).encode()),
    }
    run_id = digest(encode(identity).encode())
    directory = local_path(root, Path("data/ingestion") / run_id)
    report = {
        "schema_version": "0.1",
        "run_id": run_id,
        "snapshot_id": manifests[0].snapshot_id,
        "versions": versions,
        "implementation_sha256": code_hash,
        "sources": [s.model_dump(mode="json") for s in manifests],
        "blocks": len(blocks),
        "sections": len(sections),
        "sidecars": len(sidecars),
        "approved_sections": len(approved),
        "held_sections": len(sections) - len(approved),
        "by_document": {
            s.doc_id: {
                "blocks": sum(b.doc_id == s.doc_id for b in blocks),
                "sections": sum(t.doc_id == s.doc_id for t in sections),
                "approved": sum(
                    t.doc_id == s.doc_id and t.section_id in approved for t in sections
                ),
            }
            for s in manifests
        },
        "block_types": dict(Counter(b.block_type for b in blocks)),
        "pdf_classification": classifications,
        "limits": [
            "PDF native reading order/heading heuristics need visual review",
            "No OCR or mathematical/table reconstruction",
            "Unreviewed and unsafe evidence remains HOLD",
            "One atomic block per section; no chunking implemented",
            "Original capture dates unknown; no fabricated timestamps",
            "Local-use authorization is not redistribution clearance",
        ],
    }
    artifacts = {
        "manifest.json": encode([s.model_dump(mode="json") for s in manifests]),
        "blocks.jsonl": jsonl(blocks),
        "sections.jsonl": jsonl(sections),
        "audit.jsonl": jsonl(audit),
        "sidecars.jsonl": jsonl(sidecars),
        "holds.jsonl": jsonl([s for s in sections if s.section_id not in approved]),
        "reviews.json": encode([r.model_dump(mode="json") for r in receipts]),
        "report.json": encode(report),
    }
    directory.parent.mkdir(parents=True, exist_ok=True)
    if directory.exists():
        for name, content in artifacts.items():
            p = local_path(root, directory.relative_to(root) / name)
            if not p.exists() or p.read_text() != content:
                raise ValueError("immutable run artifacts differ; refusing overwrite")
    else:
        with tempfile.TemporaryDirectory(dir=directory.parent) as temp:
            staging = Path(temp) / "run"
            staging.mkdir()
            for name, content in artifacts.items():
                (staging / name).write_text(content)
            staging.rename(directory)
    return {
        "run_id": run_id,
        "output": str(directory.relative_to(root)),
        "sources": len(manifests),
        "blocks": len(blocks),
        "sections": len(sections),
        "approved_sections": len(approved),
        "held_sections": len(sections) - len(approved),
    }
