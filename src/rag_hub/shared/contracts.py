"""Minimal versioned admission; legacy records and validators remain unchanged."""

from typing import Literal

from pydantic import Field

from rag_hub.acquire import Registry as LegacyRegistry
from rag_hub.acquire import SourceSpec
from rag_hub.schemas import SourceManifest


class ExtendedSource(SourceManifest):
    schema_version: Literal["0.2"] = "0.2"
    source_format: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")


class ExtendedSpec(SourceSpec):
    source_format: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")


class ExtendedRegistry(LegacyRegistry):
    schema_version: Literal["0.2"] = "0.2"
    sources: tuple[ExtendedSpec, ...] = Field(min_length=1)


def read_source(value):
    version = value.get("schema_version", "0.1")
    if version == "0.1":
        return SourceManifest.model_validate(value)
    if version == "0.2":
        return ExtendedSource.model_validate(value)
    raise ValueError("unsupported_source_schema")


def read_registry(value):
    version = value.get("schema_version")
    if version == "0.1":
        return LegacyRegistry.model_validate(value)
    if version == "0.2":
        return ExtendedRegistry.model_validate(value)
    raise ValueError("unsupported_registry_schema")
