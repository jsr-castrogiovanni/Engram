"""Tests for federation storage helpers and route validation."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, timedelta

import pytest

from unittest.mock import MagicMock

from starlette.applications import Starlette
from starlette.testclient import TestClient

from engram.engine import EngramEngine
from engram.federation import build_federation_routes
from engram.storage import Storage


@pytest.mark.asyncio
async def test_get_facts_since(storage: Storage):
    """Pull-based sync returns facts after watermark."""
    now = datetime.now(timezone.utc)
    old = (now - timedelta(hours=2)).isoformat()
    recent = (now - timedelta(minutes=5)).isoformat()

    for i, ts in enumerate([old, recent]):
        await storage.insert_fact({
            "id": uuid.uuid4().hex,
            "lineage_id": uuid.uuid4().hex,
            "content": f"fact {i}",
            "content_hash": f"hash_{i}",
            "scope": "shared/test",
            "confidence": 0.9,
            "fact_type": "observation",
            "agent_id": "agent-1",
            "engineer": None,
            "provenance": None,
            "keywords": "[]",
            "entities": "[]",
            "artifact_hash": None,
            "embedding": None,
            "embedding_model": "test",
            "embedding_ver": "1.0",
            "committed_at": ts,
            "valid_from": ts,
            "valid_until": None,
            "ttl_days": None,
        })

    # Watermark 1 hour ago should return only the recent fact
    watermark = (now - timedelta(hours=1)).isoformat()
    facts = await storage.get_facts_since(watermark, scope_prefix="shared")
    assert len(facts) == 1
    assert facts[0]["content"] == "fact 1"


@pytest.mark.asyncio
async def test_ingest_remote_fact_dedup(storage: Storage):
    """Ingesting the same fact twice is idempotent."""
    fact_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    fact = {
        "id": fact_id,
        "lineage_id": uuid.uuid4().hex,
        "content": "remote fact",
        "content_hash": "remote_hash",
        "scope": "shared",
        "confidence": 0.8,
        "fact_type": "observation",
        "agent_id": "remote-agent",
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
    }
    assert await storage.ingest_remote_fact(fact) is True
    assert await storage.ingest_remote_fact(fact) is False  # duplicate


@pytest.mark.asyncio
async def test_detection_re_embeds_federated_fact(engine: EngramEngine, storage: Storage):
    """Facts ingested via federation (embedding=None) are re-embedded by the detection worker."""
    fact_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    fact = {
        "id": fact_id,
        "lineage_id": uuid.uuid4().hex,
        "content": "The payments service uses PostgreSQL for persistent storage",
        "content_hash": "federated_hash_123",
        "scope": "payments",
        "confidence": 0.9,
        "fact_type": "observation",
        "agent_id": "remote-agent-1",
        "engineer": None,
        "provenance": None,
        "keywords": json.dumps(["payments", "postgresql", "storage"]),
        "entities": "[]",
        "artifact_hash": None,
        "embedding": None,  # Federated facts arrive without embeddings
        "embedding_model": "all-MiniLM-L6-v2",
        "embedding_ver": "3.0.0",
        "committed_at": now,
        "valid_from": now,
        "valid_until": None,
        "ttl_days": None,
    }
    await storage.ingest_remote_fact(fact)

    # Queue the federated fact for detection (this is what FederationClient.sync() does)
    await engine._detection_queue.put(fact_id)

    # Wait for the detection worker to process it
    await engine._detection_queue.join()

    # The detection worker should have re-generated the embedding
    stored = await storage.get_fact_by_id(fact_id)
    assert stored is not None
    assert stored["embedding"] is not None, (
        "Detection worker should re-generate embeddings for federated facts"
    )


# ── /federation/facts route validation ───────────────────────────────


def _build_federation_client(storage=None):
    """Build a Starlette test client backed by a mock storage."""
    from unittest.mock import AsyncMock
    if storage is None:
        storage = MagicMock()
        storage.get_facts_since = AsyncMock(return_value=[])
    routes = build_federation_routes(storage)
    app = Starlette(routes=routes)
    return TestClient(app, raise_server_exceptions=False)


def test_federation_missing_after_param():
    """GET /federation/facts without 'after' must return 400."""
    client = _build_federation_client()
    resp = client.get("/federation/facts")
    assert resp.status_code == 400
    assert "after" in resp.json()["error"].lower()


def test_federation_invalid_limit_string():
    """Non-numeric limit must not crash (500) — must fall back to default 1000."""
    from unittest.mock import AsyncMock
    storage = MagicMock()
    storage.get_facts_since = AsyncMock(return_value=[])
    routes = build_federation_routes(storage)
    app = Starlette(routes=routes)
    client = TestClient(app, raise_server_exceptions=False)

    resp = client.get("/federation/facts?after=2024-01-01T00:00:00Z&limit=bad")
    # Must not crash with 500 — should succeed with fallback limit
    assert resp.status_code == 200


def test_federation_limit_capped_at_5000():
    """limit parameter must be capped at 5000."""
    from unittest.mock import AsyncMock
    storage = MagicMock()
    storage.get_facts_since = AsyncMock(return_value=[])
    routes = build_federation_routes(storage)
    app = Starlette(routes=routes)
    client = TestClient(app, raise_server_exceptions=False)

    client.get("/federation/facts?after=2024-01-01T00:00:00Z&limit=99999")
    # Verify the storage was called with limit <= 5000
    call_kwargs = storage.get_facts_since.call_args
    called_limit = call_kwargs[1].get("limit") or call_kwargs[0][2]
    assert called_limit <= 5000, f"Limit should be capped at 5000, got {called_limit}"


def test_federation_limit_minimum_one():
    """limit=0 or negative must be treated as limit=1."""
    from unittest.mock import AsyncMock
    storage = MagicMock()
    storage.get_facts_since = AsyncMock(return_value=[])
    routes = build_federation_routes(storage)
    app = Starlette(routes=routes)
    client = TestClient(app, raise_server_exceptions=False)

    client.get("/federation/facts?after=2024-01-01T00:00:00Z&limit=0")
    call_kwargs = storage.get_facts_since.call_args
    called_limit = call_kwargs[1].get("limit") or call_kwargs[0][2]
    assert called_limit >= 1, f"Limit should be at least 1, got {called_limit}"
