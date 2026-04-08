# MCP Tool Description Quality Audit

This document reviews all MCP tool descriptions in `src/engram/server.py` and provides quality ratings and improvement suggestions.

## Audit Summary

| Tool | Quality | Status |
|------|---------|--------|
| engram_status | ★★★★★ | Excellent |
| engram_init | ★★★★☆ | Good |
| engram_join | ★★★★★ | Excellent |
| engram_reset_invite_key | ★★★★☆ | Good |
| engram_commit | ★★★★★ | Excellent |
| engram_query | ★★★★★ | Excellent |
| engram_conflicts | ★★★★☆ | Good |
| engram_resolve | ★★★★☆ | Good |
| engram_promote | ★★★☆☆ | Needs Improvement |

---

## Detailed Review

### 1. engram_status

**Lines:** 98-125

**Description:**
```python
"""Check whether Engram is configured and get the next setup step.

Call this FIRST in every new session. If status is 'ready', proceed
to engram_query. If not, read 'next_prompt' and say it to the user.

Returns: {status, next_prompt?, engram_id?, mode?}
"""
```

**Strengths:**
- Clear instruction to call first in every session
- Explains how to use next_prompt field
- Return format clearly documented

**Rating:** ★★★★★ Excellent

---

### 2. engram_init

**Lines:** 160-186

**Description:**
```python
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
"""
```

**Strengths:**
- Clear about requirements (ENGRAM_DB_URL)
- Explains security model (encrypted DB URL in key)
- Good parameter descriptions

**Suggestions:**
- Could mention where to get a free PostgreSQL database
- Could clarify what happens if workspace already exists

**Rating:** ★★★★☆ Good

---

### 3. engram_join

**Lines:** 282-293

**Description:**
```python
"""Join an existing Engram workspace using only an Invite Key.

The invite key contains everything needed — the database URL and
workspace ID are encrypted inside it. No Team ID required.

Parameters:
- invite_key: The invite key shared by the workspace founder (e.g. ek_live_...).

Returns: {status, engram_id, schema, next_prompt}
"""
```

**Strengths:**
- Very clear that only the key is needed
- Good example format
- Return format documented

**Rating:** ★★★★★ Excellent

---

### 4. engram_reset_invite_key

**Lines:** 361-385

**Description:**
```python
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
```

**Strengths:**
- Clear security context
- Explains what happens to existing members
- Notes permission restriction

**Rating:** ★★★★☆ Good

---

### 5. engram_commit

**Lines:** 478-566

**Description:**
```python
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
...
```

**Strengths:**
- Excellent examples (BAD vs GOOD)
- Clear importance notes about secrets and rate limits
- Comprehensive parameter documentation
- All IMPORTANT guidelines are prominent

**Rating:** ★★★★★ Excellent

---

### 6. engram_query

**Lines:** 618-694

**Description:**
```python
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
...
```

**Strengths:**
- Clear "call before starting work" instruction
- Multiple IMPORTANT guidelines for safety
- Parameter descriptions with examples
- Return format documented

**Rating:** ★★★★★ Excellent

---

### 7. engram_conflicts

**Lines:** 700-726

**Description:**
```python
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
```

**Strengths:**
- Clear purpose
- Good context about what conflicts mean

**Suggestions:**
- Could add note about when to check conflicts (before major decisions)

**Rating:** ★★★★☆ Good

---

### 8. engram_resolve

**Lines:** 731-769

**Description:**
```python
"""Settle a disagreement between claims.

Three resolution types:
- "winner": One claim is correct. Pass winning_claim_id. The losing
  claim is marked superseded.
- "merge": Both claims are partially correct. Commit a new merged
  claim first, then resolve with this tool.
- "dismissed": The conflict is a false positive (claims don't actually
  contradict). This feedback improves future detection accuracy.
...
```

**Strengths:**
- Clear explanation of resolution types
- Good parameter documentation

**Suggestions:**
- Could add example workflow for each resolution type

**Rating:** ★★★★☆ Good

---

### 9. engram_promote

**Lines:** 775-799

**Description:**
```python
"""Promote an ephemeral fact to durable persistent memory.

Use this when an ephemeral observation has proven its value and should
become part of the team's persistent knowledge base. Promotion makes
the fact visible in default queries and enables conflict detection.

Ephemeral facts are also auto-promoted when they appear in query
results at least twice (the "proved useful more than once" heuristic),
so explicit promotion is only needed when you want to fast-track a
fact you know is valuable.

Parameters:
- fact_id: The ID of the ephemeral fact to promote.

Returns: {promoted: true, fact_id, durability: "durable"}
"""
```

**Strengths:**
- Explains when to use vs auto-promotion

**Suggestions:**
- Add IMPORTANT note that agent must be confident the fact is valuable
- Mention how to get fact_id (from query results)
- Add example of when to use this

**Rating:** ★★★☆☆ Needs Improvement

---

## Summary of Improvements Needed

### High Priority

1. **engram_promote** - Add more guidance about when to use, how to get fact_id, and add IMPORTANT note about only promoting valuable facts

### Medium Priority

2. **engram_init** - Add reference to getting free PostgreSQL database
3. **engram_conflicts** - Add guidance on when to check conflicts
4. **engram_resolve** - Add example workflows for each resolution type

### Low Priority

5. Consider adding "See also" references between related tools (e.g., engram_commit ↔ engram_query)

---

## General Patterns Observed

**Good:**
- IMPORTANT guidelines are prominent and clear
- Parameter descriptions are detailed with examples
- BAD vs GOOD examples are very effective
- Return formats are documented

**Could Improve:**
- Some tools could benefit from "See also" references
- Add more context about when to use each tool
- Some tools lack example values for parameters