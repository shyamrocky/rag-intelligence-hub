"""Explicit non-secret configuration; constructing it performs no I/O."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    vector_store: Literal["chroma"] = "chroma"
    index_dir: Path = Path("data/indexes")
    generation_model: str | None = None
    top_k: int = Field(default=5, gt=0)
    max_chars: int = Field(default=750, gt=0)
    overlap_chars: int = Field(default=120, ge=0)

    @model_validator(mode="after")
    def valid_overlap(self) -> "Settings":
        if self.overlap_chars >= self.max_chars:
            raise ValueError("overlap_chars must be smaller than max_chars")
        return self
