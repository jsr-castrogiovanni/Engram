# Engram Implementation Plan

This plan is grounded in the papers in [`./papers/`](./papers/) and three rounds of adversarial research in [`LITERATURE.md`](./LITERATURE.md).

- **Round 1** exposed failure modes in embedding retrieval, LLM-as-judge contradiction detection, and multi-agent memory scaling.
- **Round 2** discovered that NLI cross-encoders (`cross-encoder/nli-deberta-v3-base`, 92% accuracy, ~10ms/pair, local) replace the LLM judge for the majority of contradiction checks.
- **Round 3** found the fundamental flaw: the architecture itself was accumulating complexity to mitigate problems caused by its own design. The fix was not more mechanisms — it was fewer. The entire system collapses to a single abstraction: **an append-only event log with derived projections**.

Components removed in Round 3: graph database, BFT consensus, quorum-based commits, complex async pipeline, separate conflict resolution workflow. Components that survived: append-only log, NLI cross-encoder, hybrid retrieval, content-hash dedup, single-writer MCP server.

---

## The Unifying Abstraction

> A fact committed to shared memory is an event. The log of events is the system. Everything else is a projection.

```
┌──────────────────────────────────────────────┐
│              MCP Interface (I/O)             │
│   engram_commit / engram_query /             │
│   engram_conflicts / engram_resolve          │
├──────────────────────────────────────────────┤
│              Projections (Read Models)        │
│   ┌────────────┐ ┌──────────┐ ┌───────────┐ │
│   │ Retrieval  │ │ Conflict │ │ Analytics │ │
│   │ (emb+BM25) │ │ (NLI)    │ │ (stats)   │ │
│   └────────────┘ └──────────┘ └───────────┘ │
├──────────────────────────────────────────────┤
│              Event Log (Source of Truth)      │
│   append-only claims, immutable, content-    │
│   addressed, single-writer SQLite WAL        │
└──────────────────────────────────────────────┘
```

The MCP server is the single writer. All agent commits serialize through one process. SQLite's single-writer model is not a limitation — it is the correct design for a consistency layer [20]. Projections are derived views, rebuildable from the log.

---

## Phase 1 — The Event Log

**Goal:** Define the single source of truth. Everything else derives from this.

### Claim schema

The word "fact" implies truth. These are *claims* — assertions by agents that may or may not be correct.

```sql
CREATE TABLE claims (
    id                  TEXT PRIMARY KEY,
    content             TEXT NOT NULL,
    content_hash        TEXT NOT NULL,     -- SHA-256 of normalized content
    scope               TEXT NOT NULL,
    confidence          REAL NOT NULL,
    confidence_source   TEXT NOT NULL DEFAULT 'agent',
    agent_id            TEXT NOT NULL,
    engineer            TEXT,
    entities            TEXT,              -- JSON array of extracted entities
    embedding           BLOB,
    embedding_model     TEXT NOT NULL,
    embedding_model_ver TEXT NOT NULL,
    committed_at        TEXT NOT NULL,
    superseded_by       TEXT,
    source_claim_id     TEXT,
    utility_score       REAL DEFAULT 1.0
);

CREATE INDEX idx_claims_content_hash ON claims(content_hash);
CREATE INDEX idx_claims_scope ON claims(scope);
CREATE INDEX idx_claims_agent_id ON claims(agent_id);
CREATE INDEX idx_claims_committed_at ON claims(committed_at);
```

**Design decisions:**
- `content_hash` enables O(1) dedup [9]. Two agents committing the same knowledge produce the same hash.
- `entities` provides hash-based retrieval keys immune to the Orthogonality Constraint [7].
- `embedding_model` + `embedding_model_ver` prevent silent index corruption on model upgrade [21].
- `superseded_by` expresses versioning without mutation. The log is append-only.
- `source_claim_id` tracks derivation chains to detect the Mandela Effect [8].
- `utility_score` supports consolidation (Phase 4). Claims that are never queried decay toward archival.
- No `keywords`, `tags`, or `summary` columns. These were A-Mem-inspired enrichments that add LLM calls to the commit path without improving conflict detection. If needed later, they become a projection.

### Agent registry

```sql
CREATE TABLE agents (
    agent_id             TEXT PRIMARY KEY,
    engineer             TEXT NOT NULL,
    label                TEXT,
    registered_at        TEXT NOT NULL,
    last_seen            TEXT,
    total_commits        INTEGER DEFAULT 0,
    contradicted_commits INTEGER DEFAULT 0
);
```

`contradicted_commits / total_commits` provides agent reliability for query scoring [18].

### Events table

Conflicts, resolutions, and dismissals are events in the log — not a separate table.

```sql
CREATE TABLE events (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL,  -- 'conflict_detected' | 'conflict_resolved' | 'conflict_dismissed' | 'claim_superseded' | 'claim_archived'
    payload     TEXT NOT NULL,  -- JSON
    created_at  TEXT NOT NULL,
    created_by  TEXT            -- agent_id or 'system'
);

CREATE INDEX idx_events_type ON events(type);
```

A conflict is an event with `type = 'conflict_detected'` and payload:
```json
{
  "claim_a_id": "...",
  "claim_b_id": "...",
  "detection_method": "nli | numeric | temporal",
  "nli_score": 0.92,
  "severity": "high | medium | low",
  "explanation": "..."
}
```

A resolution is an event with `type = 'conflict_resolved'` and payload:
```json
{
  "conflict_event_id": "...",
  "resolution": "...",
  "winning_claim_id": "..."
}
```

This is simpler than a separate `conflicts` table with mutable `status` fields. The event log is append-only. The current state of any conflict is derived by replaying its events.

### SQLite configuration

```sql
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
```

All write transactions use `BEGIN IMMEDIATE`. All inference (embedding generation, NLI scoring) happens *outside* transactions. The transaction boundary is: validate → begin immediate → insert → commit. No LLM or model calls inside transactions.

---

## Phase 2 — MCP Server + Retrieval Projection

**Goal:** A working MCP server with commit, query, and conflict listing. Conflict detection comes in Phase 3.

### Stack

- Python 3.11+ with `fastmcp`
- `aiosqlite` (WAL mode)
- `sentence-transformers` for embeddings (`all-MiniLM-L6-v2`, ~80MB)
- `cross-encoder/nli-deberta-v3-base` for NLI (~400MB)
- `rank_bm25` for lexical retrieval
- `numpy` for cosine similarity

No graph database. No external LLM API dependency for core features.

### `engram_commit(content, scope, confidence, agent_id?, source_claim_id?)`

1. Validate inputs
2. Compute `content_hash` (SHA-256 of lowercased, whitespace-normalized content)
3. **Dedup check:** If `content_hash` matches a non-superseded claim in the same scope, return existing claim_id with `duplicate: true`
4. Generate embedding
5. Extract entities (service names, API endpoints, config keys, numeric values with units, version numbers) — use a lightweight local model or regex-based extraction, not an LLM call
6. **Outside any transaction:** run NLI conflict scan (Phase 3)
7. `BEGIN IMMEDIATE` → insert into `claims` → insert any conflict events → `COMMIT`
8. Update in-memory retrieval index
9. Return `{claim_id, committed_at, duplicate, conflicts_detected}`

### `engram_query(topic, scope?, limit?)`

1. Generate embedding for `topic`
2. **Hybrid retrieval** — three parallel paths:
   - *Path A:* Top-20 embedding-similar claims (relative ranking, no absolute threshold [14])
   - *Path B:* Top-10 BM25 lexical matches [6]
   - *Path C:* Entity overlap matches
3. Fuse via Reciprocal Rank Fusion (RRF)
4. Score with four signals:
   - `relevance` — RRF rank (weight: 0.5)
   - `recency` — `exp(-0.05 * days_since_commit)` (weight: 0.2)
   - `agent_reliability` — `1.0 - (contradicted / total)` for committing agent [18] (weight: 0.15)
   - `confidence` — agent-reported, downweighted if agent has low reliability (weight: 0.15)
5. Return top-`limit` (default 10), each with `agent_id`, `confidence`, `committed_at`, `source_claim_id`, `has_open_conflict`
6. Boost queried claims' `utility_score` by 0.1 (capped at 1.0)

### `engram_conflicts(scope?)`

Query the events table for `type = 'conflict_detected'` where neither claim has been superseded and no corresponding `conflict_resolved` or `conflict_dismissed` event exists. This is a derived view over the event log.

### `engram_resolve(conflict_event_id, resolution, winning_claim_id?)`

Append a `conflict_resolved` event. If `winning_claim_id` is provided, also append a `claim_superseded` event and update the losing claim's `superseded_by`.

### Server entrypoint

```
engram serve [--host HOST] [--port PORT] [--db PATH] [--embedding-model MODEL]
```

Default: `localhost:7474`, `~/.engram/knowledge.db`, MCP at `/mcp`, health at `/health`.

---

## Phase 3 — Conflict Detection (NLI Pipeline)

**Goal:** The core differentiator. No other system does this.

Triggered after every `engram_commit`, *before* the write transaction.

### Tier 0 — Deterministic pre-checks (< 1ms)

- **Content hash dedup:** Already handled in commit step 3.
- **Entity overlap:** If `entities` overlap with existing claims (same entity, different value), flag as candidate.

### Tier 1 — NLI Cross-Encoder (< 500ms total)

Retrieve candidates via three parallel paths (same as query: embedding top-20, BM25 top-10, entity overlap). Union, dedup, cap at 30.

For each pair `(new_claim, candidate)`:

```python
nli_model = CrossEncoder('cross-encoder/nli-deberta-v3-base')
scores = nli_model.predict([(new_claim.content, candidate.content)])
# scores = [contradiction_score, entailment_score, neutral_score]
```

- `contradiction_score > 0.85` → conflict (high confidence). Record as event.
- `contradiction_score` 0.5–0.85 → escalate to Tier 3 (LLM).
- `entailment_score > 0.85` from different agent → corroboration link.

At 30 candidates × ~10ms/pair = ~300ms. Conflict detection is effectively synchronous.

### Tier 2 — Numeric/Temporal (< 5ms, parallel with Tier 1)

- Extract numeric values with units from `entities`
- If same entity + attribute with different numeric values → conflict with `detection_method = "numeric"`
- Temporal references resolved against `committed_at`

### Tier 3 — LLM Escalation (only when needed)

Invoked only when NLI score is ambiguous (0.5–0.85) or explanation text is needed for the dashboard. Uses adversarial framing [12] and includes the NLI score to anchor judgment. Uses a fast, cheap model (e.g., `claude-haiku-4-5`).

### Severity

| Condition | Severity |
|---|---|
| Different engineers, both high-confidence, NLI > 0.9 | high |
| NLI > 0.85, same engineer | medium |
| NLI 0.5–0.85, confirmed by LLM | medium |
| Numeric/temporal contradiction | high |
| One or both low-confidence (< 0.5) | low |

### Performance

| Metric | Old (LLM-only) | Current (Tiered NLI) |
|---|---|---|
| Latency per commit | 60–150s async | ~500ms sync |
| Cost per commit | $0.01–0.05 | ~$0 + $0.01 for escalations |
| LLM dependency | Hard | Soft (10-20% of commits) |
| Determinism | No | Yes for Tiers 0-2 |

---

## Phase 4 — Consolidation

**Goal:** Prevent unbounded growth. Without this, the system degrades over weeks of team use [16].

### Utility decay

- Each query boosts a claim's `utility_score` by 0.1 (capped at 1.0)
- Daily background job: `utility_score *= 0.995`
- Claims with `utility_score < 0.1` and `committed_at` older than 90 days → archive

### Archival

Archived claims move to `claims_archive` (same schema). Excluded from query and conflict detection. Queryable via `engram_query_archive` for audit.

### Consolidation (opt-in per scope)

When a scope exceeds 100 active claims:
1. Cluster by entity overlap
2. For clusters with 5+ claims, generate a summary claim
3. Mark originals as superseded by the summary
4. Requires human approval via dashboard before executing

---

## Phase 5 — Auth + Access Control

### Agent registration

On first connection: `{agent_id, engineer, label}`. If omitted, server generates per-session ID.

### Scope permissions

```sql
CREATE TABLE scope_permissions (
    agent_id  TEXT NOT NULL,
    scope     TEXT NOT NULL,
    can_read  BOOLEAN NOT NULL DEFAULT TRUE,
    can_write BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (agent_id, scope)
);
```

Unauthenticated mode (default local): all agents read/write all scopes. Team mode: admins assign permissions. Schema supports extension with `valid_from`/`valid_until` for time-evolving policies [15].

### Token auth

Bearer token per engineer, stored hashed. HTTPS required for non-localhost. Token rotation supported.

```
engram serve --auth
engram token create --engineer [email]
```

---

## Phase 6 — Federation

**Goal:** Multiple Engram instances share claims without centralization.

### Model

Each instance is a node. The append-only claims table is a replicated journal [27]. Sync is pull-based:

```yaml
federation:
  peers:
    - url: https://engram.teamb.internal
      token: <bearer>
      scopes: ["shared/*"]
      sync_interval: 60
```

1. Node A fetches `/claims/since?timestamp=T&scope=shared/*` from Node B
2. Remote claims written locally with original `agent_id` and `committed_at`, plus `origin_node`
3. NLI conflict detection runs locally on each node — no cross-node LLM calls
4. Eventually consistent [26]. Future: model claims as a grow-only set CRDT.

---

## Phase 7 — Dashboard

**Goal:** Human-in-the-loop review. CLAIRE [25] shows this is essential — automated detection has a hard ceiling around 75% AUROC.

### Views

- **Knowledge base** — active claims, filterable by scope/agent/engineer/date
- **Conflict queue** — open conflicts by scope, sortable by severity, side-by-side comparison
- **Timeline** — commits over time, colored by agent/engineer
- **Agent activity** — per-engineer commits, conflict rate, reliability score

### Stack

FastAPI (same process), server-rendered HTML with HTMX or minimal SPA. Endpoint: `/dashboard`.

---

## Delivery Sequence

| Phase | Deliverable | Unlocks |
|---|---|---|
| 1 | Schema + migrations | All subsequent phases |
| 2 | MCP server: commit + query | Usable by agents today |
| 3 | Conflict detection (NLI pipeline) | Core differentiator |
| 4 | Consolidation | Long-term scalability |
| 5 | Auth + access control | Team deployment |
| 6 | Federation | Multi-team / org-wide |
| 7 | Dashboard | Human oversight |

Phases 1–3 are the minimum viable Engram. Ship before Letta adds conflict detection.

---

## What Was Removed (and Why)

### Graph database
The previous plan called for replacing SQLite with a graph database as "Key Design Constraint #1." This was wrong. Engram's data model is a flat claim store with entity links. The relationships between claims (contradicts, supersedes, corroborates) are simple typed edges that SQLite handles via foreign keys and the events table. A graph database would add operational complexity, deployment friction, and a dependency without improving conflict detection. [Source: GraphRAG Trap, Hamel/Bergum, Gading Nasution]

### BFT consensus
The previous plan included Byzantine Fault-Tolerant consensus for all writes. BFT requires 3f+1 replicas. For a team of 5-20 engineers, this is absurd overengineering. The threat model is sloppy LLM outputs, not Byzantine generals. Rate limiting + content-hash dedup + derivation tracking + human review are sufficient.

### Quorum-based commits
The previous plan required a quorum of independent agents to commit a claim before it was "trusted." This adds latency and complexity to every write for a marginal security benefit. Content-hash dedup, single-source flagging, and the dashboard provide equivalent protection without blocking the commit path.

### Separate conflicts table with mutable status
Replaced by the events table. Conflicts, resolutions, and dismissals are events in the log. The current state of any conflict is derived by replaying events. This is simpler, more auditable, and consistent with the append-only invariant.

### LLM-generated keywords, tags, summary on commit
These added an LLM call to every commit for metadata that doesn't improve conflict detection. Entity extraction (which can be regex-based for the common cases: service names, API endpoints, config keys, numbers) is the only enrichment that directly serves the detection pipeline. If semantic search metadata is needed later, it becomes a background projection.

### Complex async conflict pipeline
The NLI cross-encoder runs in ~300ms for 30 candidates. Conflict detection is synchronous. No job queue, no async workers, no race conditions between detection and commit.

---

## What Engram Is Not Building

- **Parametric memory** — does not alter LLM weights
- **Cache-level protocols** — does not share LLM internal caches
- **Episodic/procedural memory** — stores factual claims about codebases, not interaction history
- **RL-driven memory management** — out of scope for initial implementation
- **Multimodal memory** — text only
- **Agent orchestration** — Agent-MCP handles task management; Engram handles consistency
- **Full knowledge graph** — flat claim store with entity links, optimized for conflict detection

### Strategic positioning

Engram is a **consistency layer** that could sit on top of existing shared memory systems (Letta, Agent-MCP). Other systems handle storage and retrieval; Engram handles "are these claims consistent?" This makes Engram complementary rather than competitive.

---

## Architectural Invariants

These are the rules that cannot be violated. Every design decision must satisfy all of them.

1. **The log is the system.** Claims are events. Conflicts are events. Resolutions are events. The log is append-only and immutable.
2. **Single writer.** The MCP server process is the only writer. All agent commits serialize through one path. No concurrent write contention.
3. **No inference inside transactions.** Embedding generation, NLI scoring, and LLM calls happen before `BEGIN IMMEDIATE`. The transaction boundary is: validate → begin → insert → commit.
4. **Projections are disposable.** The retrieval index, conflict index, and analytics views can be rebuilt from the log at any time. They are caches, not sources of truth.
5. **Prefer deletion over addition.** Every new component must justify its existence against the alternative of not having it.
6. **Prefer invariants over mechanisms.** Content-hash dedup is an invariant (same content → same hash). BFT consensus is a mechanism. Invariants scale; mechanisms accumulate.
