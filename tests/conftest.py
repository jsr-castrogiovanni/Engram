"""Shared fixtures for Engram tests."""

from __future__ import annotations

from pathlib import Path

import pytest_asyncio

from engram.engine import EngramEngine
from engram.storage import Storage


@pytest_asyncio.fixture
async def storage(tmp_path: Path):
    """Provide a fresh in-memory-like storage for each test."""
    db_path = tmp_path / "test.db"
    s = Storage(db_path=db_path)
    await s.connect()
    yield s
    await s.close()


@pytest_asyncio.fixture
async def engine(storage: Storage):
    """Provide an engine with detection worker running."""
    e = EngramEngine(storage)
    await e.start()
    yield e
    await e.stop()
