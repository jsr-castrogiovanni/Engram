# CLAUDE.md - Engram Developer Guide

This file provides Claude Code with Engram-specific guidance for contributing to this codebase.

## Running Tests

```bash
cd /home/ismaeldev/Engram
pytest tests/ -x
```

## Module Map

| Module | Purpose |
|--------|---------|
| `server.py` | MCP server with 8 tools (engram_status, engram_init, engram_commit, etc.) |
| `engine.py` | Core memory engine with conflict detection |
| `storage.py` / `postgres_storage.py` | SQLite and PostgreSQL backends |
| `dashboard.py` | HTML dashboard with HTMX at `/dashboard` |
| `workspace.py` | Workspace configuration (team ID, db_url, schema) |
| `cli.py` | CLI commands (serve, verify, install) |
| `rest.py` | REST API for non-MCP clients (`/api/commit`, `/api/query`) |
| `embeddings.py` | Embedding generation for semantic search |
| `suggester.py` | LLM-powered conflict resolution suggestions |

## Schema Version Invariant

- Database schema version is tracked in `src/engram/schema.py`
- When adding new tables/columns, increment the version and document migration in `docs/MIGRATION_SCHEMA.md`

## Before Editing Engine Code

1. **Read `docs/IMPLEMENTATION.md`** - Contains detailed architecture decisions
2. **Run existing tests** - `pytest tests/ -x` to ensure nothing breaks
3. **Check `docs/MIGRATION_SCHEMA.md`** - If changes affect database, document the migration path

## MCP Tools Available

- `engram_status` - Check setup state, guides onboarding
- `engram_init` - Create new workspace (team founder)
- `engram_join` - Join existing workspace via invite key
- `engram_commit` - Write verified fact to shared memory
- `engram_query` - Read team knowledge
- `engram_conflicts` - See contradictions between facts
- `engram_resolve` - Settle a disagreement
- `engram_promote` - Graduate ephemeral fact to durable memory

## Key Files

- `HIRING.md` - Explains paid contract opportunities for contributors ($125-$185/hr)
- `CONTRIBUTING.md` - General contribution guidelines
- `README.md` - Project overview and quick start
- `docs/IMPLEMENTATION.md` - Detailed implementation documentation

## Server Running

Engram MCP server is running locally:
- HTTP: `http://localhost:7474`
- MCP: `localhost:11434`
- Dashboard: `http://localhost:7474/dashboard`