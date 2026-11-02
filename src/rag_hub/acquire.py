"""Local-only, fail-closed acquisition; registry contains metadata, never corpus text."""

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from rag_hub.schemas import SourceManifest


class SourceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    doc_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    file: str
    byte_size: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    title: str
    publisher: str
    canonical_url: HttpUrl
    original_url: HttpUrl
    source_version: str | None
    source_format: Literal["pdf", "markdown_mdx"]
    expected_pages: int | None = Field(default=None, gt=0)
    language: str

    @model_validator(mode="after")
    def safe_filename(self):
        if Path(self.file).name != self.file or self.file in (".", ".."):
            raise ValueError("source file must be a basename")
        return self


class Registry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["0.1"]
    sources: tuple[SourceSpec, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_sources(self):
        for field in ("doc_id", "file"):
            values = [getattr(s, field) for s in self.sources]
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {field}")
        return self


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def local_path(root: Path, relative: str | Path) -> Path:
    """Reject traversal/symlinks, including symlinked intermediate directories."""
    root = root.resolve()
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("path must be relative to project root")
    p = root
    for part in rel.parts:
        p = p / part
        if p.is_symlink():
            raise ValueError("symlinks are not permitted for corpus inputs/outputs")
    if not p.resolve().is_relative_to(root):
        raise ValueError("path escaped project root")
    return p


def load_registry(root: Path, path: str = "config/sources.json") -> Registry:
    return Registry.model_validate_json(local_path(root, path).read_text())


def verify_source(root: Path, spec: SourceSpec) -> bytes:
    data = local_path(root, Path("data/raw") / spec.file).read_bytes()
    if len(data) != spec.byte_size or digest(data) != spec.sha256:
        raise ValueError(f"{spec.doc_id}: source integrity mismatch")
    return data


def acquire_sources(root: Path, registry: Registry, use_basis: str) -> list[SourceManifest]:
    if not use_basis.strip():
        raise ValueError("explicit local-use basis is required; redistribution is separate")
    # Verify the entire input set before creating any snapshots.
    verified = [(spec, verify_source(root, spec)) for spec in registry.sources]
    snapshot = "sha256-" + digest(
        json.dumps(
            sorted((s.doc_id, s.sha256) for s in registry.sources), separators=(",", ":")
        ).encode()
    )
    manifests = []
    for spec, data in verified:
        relative = Path("data/snapshots") / spec.sha256 / spec.file
        destination = local_path(root, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if destination.read_bytes() != data:
                raise ValueError("immutable snapshot was modified")
        else:
            with destination.open("xb") as stream:
                stream.write(data)
        manifests.append(
            SourceManifest(
                doc_id=spec.doc_id,
                snapshot_id=snapshot,
                canonical_url=spec.canonical_url,
                original_url=spec.original_url,
                publisher=spec.publisher,
                title=spec.title,
                source_format=spec.source_format,
                source_version=spec.source_version,
                captured_at=None,
                raw_path=Path("data/raw") / spec.file,
                snapshot_path=relative,
                raw_sha256=spec.sha256,
                byte_size=spec.byte_size,
                language=spec.language,
                acquisition_basis=use_basis,
                rights_status="local_use_approved",
            )
        )
    return manifests
