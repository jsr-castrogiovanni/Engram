# ARCHITECTURE.md - Engram Module Map for Contributors

This document provides an overview of Engram's codebase structure, helping new contributors understand how the pieces fit together.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     MCP Client (Claude, Cursor, etc.)          │
└──────────────────────────────┬──────────────────────────────────┘
                               │ MCP Protocol
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     engram/server.py                           │
│                     (FastMCP server, 8 tools)                  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐
│   engine.py     │  │  dashboard.py   │  │     rest.py         │
│ (Core logic)   │  │  (HTML UI)      │  │  (HTTP API)         │
└────────┬────────┘  └────────┬────────┘  └──────────┬──────────┘
         │                    │                      │
         └────────────────────┼──────────────────────┘
                              ▼
         ┌───────────────────────────────────────────────┐
         │              storage.py / postgres_storage.py │
         │              (Data persistence layer)         │
         └───────────────────────────────────────────────┘
```

## Module Overview

### Core Modules

| Module | Location | Purpose |
|--------|----------|---------|
| **server.py** | `src/engram/server.py` | MCP server entry point. Defines 8 MCP tools using FastMCP. |
| **engine.py** | `src/engram/engine.py` | Core memory engine. Handles commit, query, conflict detection. |
| **storage.py** | `src/engram/storage.py` | SQLite storage backend. Implements `BaseStorage` interface. |
| **postgres_storage.py** | `src/engram/postgres_storage.py` | PostgreSQL storage backend for team mode. |

### Supporting Modules

| Module | Location | Purpose |
|--------|----------|---------|
| **workspace.py** | `src/engram/workspace.py` | Workspace config management (team ID, db_url, invite keys). |
| **cli.py** | `src/engram/cli.py` | CLI commands (serve, verify, install). |
| **schema.py** | `src/engram/schema.py` | Database schema definitions (SQLite + PostgreSQL). |
| **dashboard.py** | `src/engram/dashboard.py` | HTML dashboard with HTMX. Routes: `/dashboard/*`. |
| **rest.py** | `src/engram/rest.py` | REST API for non-MCP clients. Endpoints: `/api/commit`, `/api/query`. |
| **embeddings.py** | `src/engram/embeddings.py` | Embedding generation using sentence-transformers. |
| **suggester.py** | `src/engram/suggester.py` | LLM-powered conflict resolution suggestions. |
| **entities.py** | `src/engram/entities.py` | Entity extraction and classification. |
| **auth.py** | `src/engram/auth.py` | Authentication and rate limiting. |
| **federation.py** | `src/engram/federation.py` | Cross-team federation (Phase 6). |

## MCP Tools (in server.py)

The MCP server exposes 8 tools:

1. **engram_status** - Check setup state, guides agent through onboarding
2. **engram_init** - Create new workspace (team founder only)
3. **engram_join** - Join existing workspace via invite key
4. **engram_reset_invite_key** - Reset invite key after security breach
5. **engram_commit** - Write verified fact to shared memory
6. **engram_query** - Read what the team knows
7. **engram_conflicts** - See contradictions between facts
8. **engram_resolve** - Settle a disagreement
9. **engram_promote** - Graduate ephemeral fact to durable memory

## Database Schema

### PostgreSQL (Team Mode)

Tables in the `engram` schema:
- `workspaces` - Workspace configuration
- `facts` - Committed knowledge facts
- `facts_ephemeral` - Temporary facts (24h TTL)
- `conflicts` - Detected contradictions
- `claims` - Individual claims in conflicts
- `invite_keys` - Invite key management
- `query_log` - Query history for analytics

### SQLite (Local Mode)

Same schema but stored in `~/.engram/engram.db`.

## Key Design Patterns

### 1. Storage Abstraction

Both `storage.py` and `postgres_storage.py` implement the `BaseStorage` interface, allowing the engine to work with either backend seamlessly.

### 2. Conflict Detection Tiers

- **Tier 0**: Entity exact-match (e.g., "rate limit is 1000" vs "rate limit is 2000")
- **Tier 1**: NLI cross-encoder semantic similarity
- **Tier 2**: Numeric/temporal rules
- **Tier 3**: LLM escalation (rare, optional)

### 3. Invite Key Security

Invite keys are self-contained JWT-like tokens containing:
- Encrypted database URL
- Workspace ID
- Schema name
- Key generation counter

When a key is reset, the generation counter increments, invalidating all old keys.

### 4. Dashboard Routes

The dashboard uses HTMX for progressive enhancement. Routes include:
- `/dashboard` - Main knowledge base view
- `/dashboard/conflicts` - Conflict queue
- `/dashboard/activity` - Agent activity timeline

## Running the Project

```bash
# Development
cd /home/ismaeldev/Engram
source .venv/bin/activate
python -m engram.cli serve --http

# Run tests
pytest tests/ -x

# Dashboard at http://localhost:7474/dashboard
```

## Key Files for Contributors

| File | Why You Might Edit It |
|------|----------------------|
| `server.py` | Add new MCP tools, modify tool descriptions |
| `engine.py` | Change conflict detection logic, query ranking |
| `storage.py` | Add new queries, optimize existing ones |
| `dashboard.py` | Add new dashboard views, modify UI |
| `cli.py` | Add new CLI commands |
| `docs/IMPLEMENTATION.md` | Deep dive into architecture decisions |

## External Dependencies

- **FastMCP** - MCP server framework
- **asyncpg** - PostgreSQL async driver (team mode)
- **SQLAlchemy** - Database ORM
- **sentence-transformers** - Embedding models for semantic search
- **HTMX** - Dashboard UI (loaded from CDN)

## Version Info

- Schema version tracked in `src/engram/schema.py`
- Check `docs/MIGRATION_SCHEMA.md` when making DB changes