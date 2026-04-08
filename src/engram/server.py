"""Engram MCP Server.

Eight tools total:
  engram_status           — check setup state; guides agent through onboarding
  engram_init             — founder creates a new workspace (requires ENGRAM_DB_URL)
  engram_join             — teammate joins an existing workspace via Invite Key
  engram_reset_invite_key — creator resets the invite key after a security breach
  engram_commit           — write a verified fact to shared memory
  engram_query            — read what the team's agents collectively know
  engram_conflicts        — surface contradictions between facts
  engram_resolve          — settle a disagreement

Tool descriptions embed behavioral guidance for the LLM.
The 'next_prompt' field in onboarding responses tells the agent exactly what to say.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP

from engram.engine import EngramEngine
from engram.storage import BaseStorage

logger = logging.getLogger("engram")

mcp = FastMCP(
    "Engram",
    instructions=(
        "Engram is a shared team memory layer with conflict detection. "
        "IMPORTANT: On your very first tool call in a new session, call engram_status() "
        "to check if the workspace is configured. "
        "Read the 'next_prompt' field in every response from engram_status, engram_init, "
        "and engram_join — say that text to the user verbatim. Follow each prompt in sequence. "
        "Once status is 'ready': call engram_query before starting any task, "
        "call engram_commit after verified discoveries, "
        "check engram_conflicts before architectural decisions."
    ),
)

# Engine and storage are initialized at startup via cli.py
_engine: EngramEngine | None = None
_storage: BaseStorage | None = None
_auth_enabled: bool = False
_rate_limiter: Any = None


def get_engine() -> EngramEngine:
    if _engine is None:
        raise RuntimeError("Engram engine not initialized.")
    return _engine


def set_auth_enabled(enabled: bool) -> None:
    global _auth_enabled
    _auth_enabled = enabled


def set_rate_limiter(limiter: Any) -> None:
    global _rate_limiter
    _rate_limiter = limiter


_DISCONNECTED_NEXT_PROMPT = (
    "Your Engram client has been temporarily disconnected due to a security key reset.\n\n"
    "The workspace creator has issued a new invite key. To reconnect:\n\n"
    "1. Obtain the new invite key from your workspace creator.\n"
    "2. Call engram_join with the new invite key.\n"
    "3. Restart your MCP client (Claude Code / Claude Desktop / IDE extension).\n\n"
    "Until you reconnect, Engram operations are suspended for your agent."
)


async def _check_key_generation(ws: Any) -> dict[str, Any] | None:
    """Return a disconnected response if the local key_generation is behind the DB.

    Returns None if the generation is current or the check cannot be performed.
    """
    if _storage is None or not ws or not ws.db_url:
        return None
    db_gen = await _storage.get_key_generation(ws.engram_id)
    if db_gen > ws.key_generation:
        return {
            "status": "disconnected",
            "next_prompt": _DISCONNECTED_NEXT_PROMPT,
        }
    return None


# ── engram_status ─────────────────────────────────────────────────────


@mcp.tool(annotations={"readOnlyHint": True})
async def engram_status() -> dict[str, Any]:
    """Check whether Engram is configured and get the next setup step.

    Call this FIRST in every new session. If status is 'ready', proceed
    to engram_query. If not, read 'next_prompt' and say it to the user.

    Returns: {status, next_prompt?, engram_id?, mode?}
    """
    from engram.workspace import is_configured, is_team_mode, read_workspace, WORKSPACE_PATH

    ws = read_workspace()

    if ws and ws.db_url:
        disconnected = await _check_key_generation(ws)
        if disconnected:
            return disconnected
        return {
            "status": "ready",
            "mode": "team",
            "engram_id": ws.engram_id,
            "schema": ws.schema,
            "anonymous_mode": ws.anonymous_mode,
        }

    if ws and not ws.db_url and WORKSPACE_PATH.exists():
        return {
            "status": "ready",
            "mode": "local",
            "engram_id": "local",
        }

    db_url = os.environ.get("ENGRAM_DB_URL", "")
    if db_url:
        return {
            "status": "db_url_detected",
            "next_prompt": (
                "I detected a database connection string in your environment.\n\n"
                "Do you have an Invite Key to join an existing workspace, "
                "or are you setting up a new one?\n\n"
                "Note: Engram will create its tables in a separate 'engram' schema "
                "in your database, so it won't interfere with your application tables."
            ),
        }

    return {
        "status": "unconfigured",
        "next_prompt": (
            "Welcome to Engram — shared memory for your team's agents.\n\n"
            "Do you have an Invite Key to join an existing workspace, "
            "or are you setting up a new one?\n\n"
            "If setting up a new workspace, you'll need a PostgreSQL database. "
            "You can either:\n"
            "  • Use your existing app database (Engram creates a separate 'engram' schema)\n"
            "  • Get a free dedicated database at neon.tech, supabase.com, or railway.app"
        ),
    }


# ── engram_init ───────────────────────────────────────────────────────


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False})
async def engram_init(
    anonymous_mode: bool = False,
    anon_agents: bool = False,
    invite_expires_days: int = 90,
    invite_uses: int = 10,
    schema: str = "engram",
) -> dict[str, Any]:
    """Set up a new Engram workspace (team founder only).

    Requires ENGRAM_DB_URL to be set in the environment. Runs schema
    setup, generates a Team ID and invite key, and writes workspace.json.

    The invite key contains the database URL encrypted inside it —
    teammates only need the Team ID and Invite Key (not the db URL).

    Parameters:
    - anonymous_mode: If true, engineer names are stripped from all commits.
      Ask the user: "Should commits show who made them, or stay anonymous?"
    - anon_agents: If true, agent IDs are randomized each session.
    - invite_expires_days: How long the invite key is valid (default 90 days).
    - invite_uses: How many times the invite key can be used (default 10).
    - schema: PostgreSQL schema name for Engram tables (default "engram").
      Engram creates all tables in this schema to avoid conflicts with
      your application tables.

    Returns: {status, engram_id, invite_key, next_prompt}
    """
    db_url = os.environ.get("ENGRAM_DB_URL", "")
    if not db_url:
        # Check if .env file exists in current directory
        env_file = Path.cwd() / ".env"
        env_exists = env_file.exists()

        return {
            "status": "awaiting_db",
            "next_prompt": (
                "To set up Engram, add your database connection string to your environment.\n\n"
                + (
                    f"I see you have a .env file at {env_file}. Add this line:\n\n"
                    "  ENGRAM_DB_URL='postgres://user:password@host:port/database'\n\n"
                    if env_exists
                    else "Create a .env file in your project root with:\n\n"
                    "  ENGRAM_DB_URL='postgres://user:password@host:port/database'\n\n"
                    "Or set it in your shell config (.bashrc, .zshrc, etc.):\n\n"
                    "  export ENGRAM_DB_URL='postgres://user:password@host:port/database'\n\n"
                )
                + "IMPORTANT: Don't paste your database URL in this chat for security reasons.\n\n"
                "You can:\n"
                "  • Use your existing app database (Engram creates a separate 'engram' schema)\n"
                "  • Get a free dedicated database at neon.tech, supabase.com, or railway.app\n\n"
                "Once set, restart this chat and I'll detect it automatically."
            ),
        }

    from engram.workspace import (
        WorkspaceConfig,
        generate_invite_key,
        generate_team_id,
        write_workspace,
    )

    engram_id = generate_team_id()
    invite_key, key_hash = generate_invite_key(
        db_url=db_url,
        engram_id=engram_id,
        expires_days=invite_expires_days,
        uses_remaining=invite_uses,
    )

    # Set up schema and workspace row in the database
    if _storage is not None:
        from datetime import timezone
        import time

        expires_ts = datetime.fromtimestamp(
            time.time() + invite_expires_days * 86400, tz=timezone.utc
        ).isoformat()

        await _storage.ensure_workspace(engram_id, anonymous_mode, anon_agents)
        await _storage.insert_invite_key(
            key_hash=key_hash,
            engram_id=engram_id,
            expires_at=expires_ts,
            uses_remaining=invite_uses,
        )

    # Write workspace.json
    config = WorkspaceConfig(
        engram_id=engram_id,
        db_url=db_url,
        schema=schema,
        anonymous_mode=anonymous_mode,
        anon_agents=anon_agents,
        key_generation=0,
        is_creator=True,
    )
    write_workspace(config)
    logger.info(
        "Workspace initialized: %s (schema: %s, anonymous=%s)", engram_id, schema, anonymous_mode
    )

    return {
        "status": "initialized",
        "engram_id": engram_id,
        "schema": schema,
        "invite_key": invite_key,
        "next_prompt": (
            f"Your team workspace is ready.\n\n"
            f"Engram tables are in the '{schema}' schema in your database — "
            f"completely isolated from your application tables.\n\n"
            f"Share this with teammates via iMessage, WhatsApp, Slack, or any channel:\n\n"
            f"  Invite Key: {invite_key}\n\n"
            f"That's all they need. They install Engram, start a chat, paste the key, "
            f"and their agent handles the rest.\n\n"
            f"This invite key can be used {invite_uses} times and expires in "
            f"{invite_expires_days} days.\n\n"
            f"Your workspace ID (for your own reference): {engram_id}"
        ),
    }


# ── engram_join ───────────────────────────────────────────────────────


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False})
async def engram_join(invite_key: str) -> dict[str, Any]:
    """Join an existing Engram workspace using only an Invite Key.

    The invite key contains everything needed — the database URL and
    workspace ID are encrypted inside it. No Team ID required.

    Parameters:
    - invite_key: The invite key shared by the workspace founder (e.g. ek_live_...).

    Returns: {status, engram_id, schema, next_prompt}
    """
    from engram.workspace import (
        WorkspaceConfig,
        decode_invite_key,
        invite_key_hash,
        write_workspace,
    )

    # Decode the invite key — self-contained, no other input needed
    try:
        payload = decode_invite_key(invite_key)
    except ValueError as e:
        return {
            "status": "error",
            "next_prompt": (
                f"That invite key isn't valid: {e}\n\n"
                "Please double-check it with the person who set up the workspace."
            ),
        }

    db_url = payload["db_url"]
    engram_id = payload["engram_id"]
    schema = payload.get("schema", "engram")  # backward compatibility
    key_generation = payload.get("key_generation", 0)

    # Server-side validation: check uses_remaining and expiry in the database
    key_hash = invite_key_hash(invite_key)
    if _storage is not None:
        key_row = await _storage.validate_invite_key(key_hash)
        if key_row is None:
            return {
                "status": "error",
                "next_prompt": (
                    "This invite key has been revoked or used up. "
                    "Ask the workspace creator to generate a new one with engram_reset_invite_key."
                ),
            }
        await _storage.consume_invite_key(key_hash)

    # Write workspace.json — db_url extracted silently, never shown to user
    config = WorkspaceConfig(
        engram_id=engram_id,
        db_url=db_url,
        schema=schema,
        anonymous_mode=False,
        anon_agents=False,
        key_generation=key_generation,
        is_creator=False,
    )
    write_workspace(config)
    logger.info(
        "Joined workspace: %s (schema: %s, generation: %d)", engram_id, schema, key_generation
    )

    return {
        "status": "joined",
        "engram_id": engram_id,
        "schema": schema,
        "next_prompt": (
            "You're in. Your agent is now connected to the team's shared memory.\n\n"
            f"Engram tables are in the '{schema}' schema — isolated from your app.\n\n"
            "I'll query team knowledge before starting any task and commit "
            "discoveries after. You don't need to think about Engram — it's just there."
        ),
    }


# ── engram_reset_invite_key ──────────────────────────────────────────


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True})
async def engram_reset_invite_key(
    invite_expires_days: int = 90,
    invite_uses: int = 10,
) -> dict[str, Any]:
    """Reset the workspace invite key (workspace creator only).

    Use this when you suspect a security breach or the current invite key
    has been compromised. This will:
      1. Revoke all existing invite keys for your workspace.
      2. Increment the workspace key generation counter.
      3. Generate a new invite key.

    All existing members will be temporarily disconnected. They will see a
    message telling them to obtain the new invite key and call engram_join.

    This tool is only available to the workspace creator (the agent that
    originally called engram_init). Other agents will receive an error.

    Parameters:
    - invite_expires_days: Validity period for the new key (default 90 days).
    - invite_uses: Max number of times the new key can be used (default 10).

    Returns: {status, invite_key, key_generation, next_prompt}
    """
    from engram.workspace import (
        WorkspaceConfig,
        generate_invite_key,
        read_workspace,
        write_workspace,
    )

    ws = read_workspace()
    if ws is None or not ws.db_url:
        return {
            "status": "error",
            "next_prompt": "No team workspace is configured. Only usable in team mode.",
        }

    if not ws.is_creator:
        return {
            "status": "error",
            "next_prompt": (
                "Only the workspace creator can reset the invite key. "
                "If you set up this workspace, check that your workspace.json has is_creator=true."
            ),
        }

    if _storage is None:
        return {
            "status": "error",
            "next_prompt": "Storage not initialized. Restart the Engram server and try again.",
        }

    import time
    from datetime import timezone

    # Revoke all existing invite keys and bump the generation counter
    await _storage.revoke_all_invite_keys(ws.engram_id)
    new_gen = await _storage.bump_key_generation(ws.engram_id)

    # Generate new invite key embedding the new generation
    invite_key, key_hash = generate_invite_key(
        db_url=ws.db_url,
        engram_id=ws.engram_id,
        expires_days=invite_expires_days,
        uses_remaining=invite_uses,
        schema=ws.schema,
        key_generation=new_gen,
    )

    expires_ts = datetime.fromtimestamp(
        time.time() + invite_expires_days * 86400, tz=timezone.utc
    ).isoformat()
    await _storage.insert_invite_key(
        key_hash=key_hash,
        engram_id=ws.engram_id,
        expires_at=expires_ts,
        uses_remaining=invite_uses,
    )

    # Update creator's local workspace.json with new generation
    updated_config = WorkspaceConfig(
        engram_id=ws.engram_id,
        db_url=ws.db_url,
        schema=ws.schema,
        anonymous_mode=ws.anonymous_mode,
        anon_agents=ws.anon_agents,
        key_generation=new_gen,
        is_creator=True,
    )
    write_workspace(updated_config)
    logger.warning(
        "Invite key reset by creator: workspace=%s, new_generation=%d", ws.engram_id, new_gen
    )

    return {
        "status": "reset",
        "invite_key": invite_key,
        "key_generation": new_gen,
        "next_prompt": (
            f"Security reset complete. All existing invite keys have been revoked.\n\n"
            f"Key generation is now {new_gen}. All members have been temporarily "
            f"disconnected — they will see a message asking them to reconnect.\n\n"
            f"Share this new invite key with your team via a secure channel "
            f"(iMessage, WhatsApp, Slack DM, etc.):\n\n"
            f"  Invite Key: {invite_key}\n\n"
            f"Members rejoin by calling engram_join with this key, then restarting "
            f"their MCP client. This key can be used {invite_uses} times and expires "
            f"in {invite_expires_days} days."
        ),
    }


# ── engram_commit ────────────────────────────────────────────────────


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    }
)
async def engram_commit(
    content: str,
    scope: str,
    confidence: float,
    agent_id: str | None = None,
    engineer: str | None = None,
    corrects_lineage: str | None = None,
    provenance: str | None = None,
    fact_type: str = "observation",
    ttl_days: int | None = None,
    operation: str = "add",
    durability: str = "durable",
) -> dict[str, Any]:
    """Commit a claim about the codebase to shared team memory.

    Use this when your agent discovers something worth preserving:
    a hidden side effect, a failed approach, an undocumented constraint,
    an architectural decision, or a configuration detail.

    IMPORTANT: Do not commit speculative or uncertain claims. Only commit
    facts your agent has verified through code reading, testing, or
    direct observation. Set confidence below 0.5 for uncertain claims.

    IMPORTANT: Do not include secrets, API keys, passwords, or credentials
    in the content field. The server will reject commits containing
    detected secrets.

    IMPORTANT: Do not call this tool more than 5 times per task. Batch
    related discoveries into a single, well-structured claim.

    Parameters:
    - content: The claim in plain English. Be specific. Include service
      names, version numbers, config keys, and numeric values where
      relevant. BAD: "auth is broken". GOOD: "The auth service
      rate-limits to 1000 req/s per IP using a sliding window in Redis,
      configured via AUTH_RATE_LIMIT in .env".
    - scope: Hierarchical topic path. Examples: "auth", "payments/webhooks",
      "infra/docker". Use consistent scopes across your team.
    - confidence: 0.0-1.0. How certain is this claim? 1.0 = verified in
      code. 0.7 = observed behavior. 0.3 = inferred from context.
    - agent_id: Your agent identifier. Use your agent name for attribution
      (e.g. the name field from your AgentConfig when using open-multi-agent).
      Auto-generated if omitted.
    - engineer: Optional human identifier (email or username) of the engineer
      whose agent is making this commit. Used for team attribution and trust
      scoring. Example: "alice@example.com" or your GitHub username.
    - corrects_lineage: If this claim corrects a previous one, pass the
      lineage_id of the claim being corrected. The old claim will be
      marked as superseded.
    - provenance: Optional evidence trail. File path, line number, test
      output, or tool call ID that generated this evidence. Facts with
      provenance are marked as verified in query results.
    - fact_type: "observation" (directly observed in code/tests/logs),
      "inference" (concluded from observations), or "decision"
      (architectural decision by humans or agents). Default: observation.
    - ttl_days: Optional time-to-live in days. When set, the fact
      automatically expires after this period. Useful for facts about
      external dependencies, API contracts, or infrastructure that
      change frequently. Default: null (no expiry).
    - operation: Memory CRUD intent. One of:
        "add"    (default) — new independent fact.
        "update" — supersede an outdated fact. If corrects_lineage is
                   omitted, the engine automatically finds the most
                   semantically similar active fact in scope and supersedes
                   it (no lineage tracking required from the caller).
        "delete" — retire an existing fact without replacement; requires
                   corrects_lineage (the lineage_id to close).
        "none"   — no-op; signals the agent has nothing new to add.
    - durability: Memory tier. One of:
        "durable"   (default) — persistent fact. Included in queries by
                     default. Triggers conflict detection. Use for verified
                     discoveries that the team should know about.
        "ephemeral" — scratchpad memory. Excluded from queries unless
                     include_ephemeral=true is passed. Skips conflict
                     detection. Auto-expires after ttl_days (default 1 day).
                     Automatically promoted to durable when queried at least
                     twice. Use for in-progress observations, hypotheses,
                     or context that hasn't proven its value yet.

    Returns: {fact_id, committed_at, duplicate, conflicts_detected,
              memory_op, supersedes_fact_id, durability}
    """
    engine = get_engine()

    # Key generation check — block disconnected agents
    from engram.workspace import read_workspace as _rw

    _ws = _rw()
    _disc = await _check_key_generation(_ws)
    if _disc:
        return _disc

    # Rate limiting (Phase 5)
    effective_agent = agent_id or "anonymous"
    if _rate_limiter is not None:
        if not _rate_limiter.check(effective_agent):
            raise ValueError(
                f"Rate limit exceeded for agent '{effective_agent}'. "
                f"Max {_rate_limiter.max_per_hour} commits per hour."
            )

    # Scope permission check (Phase 5)
    if _storage is not None and agent_id:
        from engram.auth import check_scope_permission

        allowed = await check_scope_permission(_storage, agent_id, scope, "write")
        if not allowed:
            raise ValueError(
                f"Agent '{agent_id}' does not have write permission for scope '{scope}'."
            )

    result = await engine.commit(
        content=content,
        scope=scope,
        confidence=confidence,
        agent_id=agent_id,
        engineer=engineer,
        corrects_lineage=corrects_lineage,
        provenance=provenance,
        fact_type=fact_type,
        ttl_days=ttl_days,
        operation=operation,
        durability=durability,
    )

    # Record rate limit usage after successful commit
    if _rate_limiter is not None:
        _rate_limiter.record(effective_agent)

    return result


# ── engram_query ─────────────────────────────────────────────────────


@mcp.tool(
    annotations={"readOnlyHint": True},
)
async def engram_query(
    topic: str,
    scope: str | None = None,
    limit: int = 10,
    as_of: str | None = None,
    fact_type: str | None = None,
    agent_id: str | None = None,
    include_ephemeral: bool = False,
) -> list[dict[str, Any]]:
    """Query what your team's agents collectively know about a topic.

    Call this BEFORE starting work on any area of the codebase. It returns
    claims from all agents across all engineers, ordered by relevance.

    IMPORTANT: Claims marked with has_open_conflict=true are disputed.
    Do not treat them as settled facts. Check the conflict details before
    relying on them.

    IMPORTANT: Claims marked with verified=false lack provenance. Treat
    them with appropriate skepticism.

    IMPORTANT: Do not call this tool more than 3 times per task. Refine
    your query to be specific rather than making multiple broad queries.

    Parameters:
    - topic: What you want to know about. Be specific. BAD: "auth".
      GOOD: "How does the auth service handle JWT token refresh?"
    - scope: Optional filter. "auth" returns claims in "auth" and all
      sub-scopes like "auth/jwt", "auth/oauth".
    - limit: Max results (default 10, max 50).
    - as_of: ISO 8601 timestamp for historical queries. Returns what
      the system knew at that point in time.
    - fact_type: Optional filter. "observation", "inference", or
      "decision". Omit to return all types.
    - agent_id: Your agent identifier. Used for read permission checks
      when the server runs in auth mode (--auth flag). Match the same
      agent_id you use when calling engram_commit.
    - include_ephemeral: When true, includes ephemeral (scratchpad) facts
      alongside durable facts. Ephemeral facts are short-lived observations
      that haven't proven their value yet. They rank lower than durable
      facts. Ephemeral facts that appear in query results are tracked;
      once queried twice they are automatically promoted to durable.
      Default: false.

    Returns: List of claims with content, scope, confidence, agent_id,
    committed_at, has_open_conflict, verified, fact_type, durability,
    and provenance metadata.
    """
    engine = get_engine()

    # Key generation check — block disconnected agents
    from engram.workspace import read_workspace as _rw

    _ws = _rw()
    _disc = await _check_key_generation(_ws)
    if _disc:
        return _disc

    # Scope read permission check when auth is enabled and scope is specified
    if _auth_enabled and _storage is not None and agent_id and scope:
        from engram.auth import check_scope_permission

        allowed = await check_scope_permission(_storage, agent_id, scope, "read")
        if not allowed:
            raise ValueError(
                f"Agent '{agent_id}' does not have read permission for scope '{scope}'."
            )

    return await engine.query(
        topic=topic,
        scope=scope,
        limit=limit,
        as_of=as_of,
        fact_type=fact_type,
        include_ephemeral=include_ephemeral,
    )


# ── engram_conflicts ─────────────────────────────────────────────────


@mcp.tool(
    annotations={"readOnlyHint": True},
)
async def engram_conflicts(
    scope: str | None = None,
    status: str = "open",
) -> list[dict[str, Any]]:
    """See where agents disagree about the codebase.

    Returns pairs of claims that contradict each other. Each conflict
    includes both claims, the detection method, severity, and an
    explanation (when available).

    Review these before making architectural decisions. A conflict means
    two agents (possibly from different engineers) believe incompatible
    things about the same system.

    Parameters:
    - scope: Optional filter by scope prefix.
    - status: "open" (default), "resolved", "dismissed", or "all".

    Returns: List of conflicts with claim pairs, severity, detection
    method, and resolution status.
    """
    engine = get_engine()
    return await engine.get_conflicts(scope=scope, status=status)


# ── engram_resolve ───────────────────────────────────────────────────


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def engram_resolve(
    conflict_id: str,
    resolution_type: str,
    resolution: str,
    winning_claim_id: str | None = None,
) -> dict[str, Any]:
    """Settle a disagreement between claims.

    Three resolution types:
    - "winner": One claim is correct. Pass winning_claim_id. The losing
      claim is marked superseded.
    - "merge": Both claims are partially correct. Commit a new merged
      claim first, then resolve with this tool.
    - "dismissed": The conflict is a false positive (claims don't actually
      contradict). This feedback improves future detection accuracy.

    Parameters:
    - conflict_id: The conflict to resolve.
    - resolution_type: "winner", "merge", or "dismissed".
    - resolution: Human-readable explanation of why this resolution
      is correct.
    - winning_claim_id: Required when resolution_type is "winner".

    Returns: {resolved: true, conflict_id, resolution_type}
    """
    engine = get_engine()
    return await engine.resolve(
        conflict_id=conflict_id,
        resolution_type=resolution_type,
        resolution=resolution,
        winning_claim_id=winning_claim_id,
    )


# ── engram_promote ───────────────────────────────────────────────────


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def engram_promote(fact_id: str) -> dict[str, Any]:
    """Promote an ephemeral fact to durable persistent memory.

    Use this when an ephemeral observation has proven its value and should
    become part of the team's persistent knowledge base. Promotion makes
    the fact visible in default queries and enables conflict detection.

    IMPORTANT: Only promote facts you're confident are valuable. Promotion
    signals to the team that this knowledge is trustworthy and worth
    remembering permanently.

    IMPORTANT: To get fact_id, query with include_ephemeral=true. Ephemeral
    facts in query results include their fact_id field. You can then pass
    that ID here to promote it.

    Ephemeral facts are also auto-promoted when they appear in query
    results at least twice (the "proved useful more than once" heuristic),
    so explicit promotion is only needed when you want to fast-track a
    fact you know is valuable immediately.

    Example workflow:
    1. Query with include_ephemeral=true to find relevant ephemeral facts
    2. Review the facts and determine which are valuable enough to promote
    3. Call engram_promote with the fact_id of each valuable fact

    Parameters:
    - fact_id: The ID of the ephemeral fact to promote. Get this from
      query results (include_ephemeral=true returns fact_id for each fact).

    Returns: {promoted: true, fact_id, durability: "durable"}
    """
    engine = get_engine()
    return await engine.promote(fact_id=fact_id)
