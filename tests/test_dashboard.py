"""Tests for dashboard rendering."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest

from engram.dashboard import _esc, _render_index
from engram.storage import Storage


def test_html_escape():
    assert _esc("<script>") == "&lt;script&gt;"
    assert _esc(None) == ""
    assert _esc('a"b') == "a&quot;b"


def test_render_index():
    html = _render_index(
        facts_count=42,
        total_facts=100,
        open_conflicts=3,
        resolved_conflicts=7,
        agents=[],
        expiring_count=2,
    )
    assert "42" in html
    assert "Engram Dashboard" in html
    assert "Open Conflicts" in html


@pytest.mark.asyncio
async def test_dashboard_counts(storage: Storage):
    """Storage count helpers work correctly."""
    assert await storage.count_facts() == 0
    assert await storage.count_conflicts() == 0

    now = datetime.now(timezone.utc).isoformat()
    await storage.insert_fact({
        "id": uuid.uuid4().hex,
        "lineage_id": uuid.uuid4().hex,
        "content": "test",
        "content_hash": "h1",
        "scope": "test",
        "confidence": 0.9,
        "fact_type": "observation",
        "agent_id": "a1",
        "engineer": None,
        "provenance": None,
        "keywords": "[]",
        "entities": "[]",
        "artifact_hash": None,
        "embedding": None,
        "embedding_model": "test",
        "embedding_ver": "1.0",
        "committed_at": now,
        "valid_from": now,
        "valid_until": None,
        "ttl_days": None,
    })
    assert await storage.count_facts() == 1
