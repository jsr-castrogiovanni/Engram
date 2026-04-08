"""Phase 6 — Cross-team federation.

Pull-based sync of the append-only facts journal. Remote facts arrive
with their original agent_id, committed_at, and valid_from. Local
conflict detection runs on ingested remote facts using the same pipeline.

Federation is eventually consistent: row-level immutability guarantees
convergence.
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from engram.engine import EngramEngine
from engram.storage import BaseStorage as Storage

logger = logging.getLogger("engram")


class FederationClient:
    """Pulls facts from a remote Engram instance and ingests them locally."""

    def __init__(
        self,
        engine: EngramEngine,
        storage: Storage,
        remote_url: str,
        auth_token: str | None = None,
    ) -> None:
        self.engine = engine
        self.storage = storage
        self.remote_url = remote_url.rstrip("/")
        self.auth_token = auth_token

    async def sync(
        self,
        after: str,
        scope_prefix: str | None = None,
        limit: int = 1000,
    ) -> dict[str, Any]:
        """Pull facts from remote since watermark and ingest locally.

        Returns: {fetched: int, ingested: int, duplicates: int, latest_timestamp: str|None}
        """
        url = f"{self.remote_url}/federation/facts"
        params: dict[str, str] = {"after": after, "limit": str(limit)}
        if scope_prefix:
            params["scope"] = scope_prefix

        headers: dict[str, str] = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        timeout = aiohttp.ClientTimeout(total=30, connect=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params, headers=headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Federation sync failed ({resp.status}): {text}")
                data = await resp.json()

        facts = data.get("facts", [])
        ingested = 0
        duplicates = 0
        latest_ts: str | None = None

        for fact in facts:
            inserted = await self.storage.ingest_remote_fact(fact)
            if inserted:
                ingested += 1
                # Queue for local conflict detection
                await self.engine._detection_queue.put(fact["id"])
            else:
                duplicates += 1
            latest_ts = fact.get("committed_at", latest_ts)

        logger.info(
            "Federation sync: fetched=%d ingested=%d duplicates=%d",
            len(facts), ingested, duplicates,
        )
        return {
            "fetched": len(facts),
            "ingested": ingested,
            "duplicates": duplicates,
            "latest_timestamp": latest_ts,
        }


def build_federation_routes(storage: Storage) -> Any:
    """Build the federation HTTP routes (served alongside the dashboard).

    GET /federation/facts?after=<iso>&scope=<prefix>&limit=<n>
    """
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def get_facts_since(request: Request) -> JSONResponse:
        after = request.query_params.get("after")
        if not after:
            return JSONResponse({"error": "Missing 'after' parameter"}, status_code=400)
        scope = request.query_params.get("scope")
        limit = int(request.query_params.get("limit", "1000"))
        limit = min(limit, 5000)

        facts = await storage.get_facts_since(after, scope_prefix=scope, limit=limit)
        # Strip binary embedding from response (too large for JSON)
        clean = []
        for f in facts:
            f_copy = dict(f)
            f_copy.pop("embedding", None)
            clean.append(f_copy)

        return JSONResponse({"facts": clean, "count": len(clean)})

    return [
        Route("/federation/facts", get_facts_since, methods=["GET"]),
    ]
