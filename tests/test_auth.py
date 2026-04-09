"""Tests for auth, rate limiting, and scope permissions."""

from __future__ import annotations


import pytest

from engram.auth import (
    RateLimiter,
    check_scope_permission,
    create_token,
    verify_token,
)
from engram.storage import Storage


def test_create_and_verify_token():
    token = create_token(engineer="alice@example.com")
    payload = verify_token(token)
    assert payload is not None
    assert payload["sub"] == "alice@example.com"
    assert payload["aud"] == "engram-mcp"


def test_expired_token():
    token = create_token(engineer="bob@example.com", expires_hours=0)
    # Token with 0 hours expires immediately
    payload = verify_token(token)
    assert payload is None


def test_invalid_token():
    assert verify_token("not.a.token") is None
    assert verify_token("") is None
    assert verify_token("a.b") is None


def test_tampered_token():
    token = create_token(engineer="alice@example.com")
    # Tamper with the payload
    parts = token.split(".")
    parts[1] = parts[1] + "x"
    tampered = ".".join(parts)
    assert verify_token(tampered) is None


def test_rate_limiter_allows():
    rl = RateLimiter(max_per_hour=5)
    for _ in range(5):
        assert rl.check("agent-1") is True
        rl.record("agent-1")
    # 6th should be denied
    assert rl.check("agent-1") is False


def test_rate_limiter_different_agents():
    rl = RateLimiter(max_per_hour=2)
    rl.record("agent-1")
    rl.record("agent-1")
    assert rl.check("agent-1") is False
    assert rl.check("agent-2") is True


@pytest.mark.asyncio
async def test_scope_permission_default(storage: Storage):
    """Default (no row): full access."""
    allowed = await check_scope_permission(storage, "agent-1", "auth", "write")
    assert allowed is True


@pytest.mark.asyncio
async def test_scope_permission_denied(storage: Storage):
    await storage.set_scope_permission("agent-1", "payments", can_read=True, can_write=False)
    allowed = await check_scope_permission(storage, "agent-1", "payments", "write")
    assert allowed is False
    allowed = await check_scope_permission(storage, "agent-1", "payments", "read")
    assert allowed is True


@pytest.mark.asyncio
async def test_scope_permission_hierarchical(storage: Storage):
    """payments/webhooks inherits from payments."""
    await storage.set_scope_permission("agent-1", "payments", can_read=True, can_write=False)
    allowed = await check_scope_permission(storage, "agent-1", "payments/webhooks", "write")
    assert allowed is False
