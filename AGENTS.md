# AGENTS.md - Universal Agent Guidelines

This file provides universal guidance for any AI assistant working on the Engram codebase.

## Quick Start

```bash
cd /home/ismaeldev/Engram
source .venv/bin/activate
pytest tests/ -x
```

## Project Context

**Engram** is a multi-agent memory consistency platform. It provides:
- Shared persistent memory for AI agent teams
- Conflict detection when agents contradict each other
- MCP (Model Context Protocol) server integration

**Goal:** Become a top contributor to potentially get hired ($35-65/hour contract)

## Important Notes

1. **Always run tests before submitting PRs** - `pytest tests/ -x`
2. **Database changes require schema migration documentation** - Check `docs/MIGRATION_SCHEMA.md`
3. **Read IMPLEMENTATION.md before touching core engine code**
4. **Keep PRs focused** - One change per PR, explain the why in the description

## Key Documentation

- `README.md` - Project overview
- `CONTRIBUTING.md` - Contribution workflow
- `HIRING.md` - Paid contract opportunities
- `docs/IMPLEMENTATION.md` - Detailed architecture
- `docs/MIGRATION_SCHEMA.md` - Database migration guide

## Running the Server

```bash
cd /home/ismaeldev/Engram
python -m engram.cli serve --http
# Dashboard at http://localhost:7474/dashboard
```

## Current Issues to Work On

1. #107 - Add CLAUDE.md to repo root (in progress)
2. #114 - Document all next_prompt strings as contributor guide
3. #112 - docs/ARCHITECTURE.md: module map for new contributors
4. #109 - MCP tool description quality audit
5. #111 - Per-IDE quickstart guides in docs/quickstart/