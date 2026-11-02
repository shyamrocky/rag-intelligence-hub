"""Stable initial clock for two frozen regression modules' expiry-crossing fixtures.

This changes no assertion, source file, publication or production clock. New M2
acceptance runs without this plugin and verifies the real current expiration state.
"""

from datetime import datetime
from pathlib import Path

import pytest


@pytest.fixture(scope="module", autouse=True)
def historical_crossing_fixture_clock(request):
    if Path(request.module.__file__).name not in {
        "test_unified_consumption.py", "test_chunk_preparation.py",
    }:
        yield
        return
    import rag_hub.pdf_publication as publication

    original = publication.utc_now
    publication.utc_now = lambda: datetime.fromisoformat("2026-10-23T06:12:22+00:00")
    try:
        yield
    finally:
        publication.utc_now = original
