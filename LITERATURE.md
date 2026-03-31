# Literature

PDFs are in [`./papers/`](./papers/).

---

## [1] Multi-Agent Memory from a Computer Architecture Perspective: Visions and Challenges Ahead

**Authors:** Zhongming Yu, Naicheng Yu, Hejia Zhang, Wentao Ni, Mingrui Yin, Jiaying Yang, Yujie Zhao, Jishen Zhao
**Affiliations:** UC San Diego, Georgia Tech
**Venue:** Architecture 2.0 Workshop, March 23, 2026, Pittsburgh, PA
**ArXiv:** [2603.10062](https://arxiv.org/abs/2603.10062)
**File:** [`papers/2603.10062v1.pdf`](papers/2603.10062v1.pdf)

### Summary

This position paper — the direct intellectual foundation for Engram — frames multi-agent memory as a **computer architecture problem**. The central observation is that LLM agent systems are hitting a wall that looks exactly like the memory bottleneck in classical hardware: performance limited not by compute but by bandwidth, hierarchy, and consistency.

**Three-layer memory hierarchy:**
- *I/O layer* — interfaces ingesting audio, text, images, network calls (e.g., MCP)
- *Cache layer* — fast, limited-capacity short-term storage: compressed context, recent tool calls, KV caches, embeddings
- *Memory layer* — large-capacity long-term storage: full dialogue history, vector DBs, graph DBs

**Two missing protocols:**
1. *Agent cache sharing* — no principled protocol exists for one agent's cached artifacts to be transformed and reused by another (analogous to cache transfers in multiprocessors)
2. *Agent memory access control* — permissions, scope, and granularity for reading/writing another agent's memory remain under-specified

**Central claim:** The most pressing open challenge is **multi-agent memory consistency**. In single-agent settings, consistency means temporal coherence — new facts must not contradict established ones. In multi-agent settings, the problem compounds: multiple agents read from and write to shared memory concurrently, raising classical challenges of *visibility*, *ordering*, and *conflict resolution*. The difficulty is harder than hardware because memory artifacts are semantic and heterogeneous (evidence, tool traces, plans), and conflicts are often semantic and coupled to environment state.

**Relevance to Engram:** Engram directly implements the consistency layer this paper identifies as the field's most urgent gap. `engram_commit` is the shared write; `engram_query` is the read; `engram_conflicts` is the conflict detection mechanism. The paper's vocabulary — shared vs. distributed memory, hierarchy layers, consistency models — is the conceptual language of this project.

---

## [2] A-Mem: Agentic Memory for LLM Agents

**Authors:** Wujiang Xu, Zujie Liang, Kai Mei, Hang Gao, Juntao Tan, Yongfeng Zhang
**Affiliations:** Rutgers University, Independent Researcher, AIOS Foundation
**ArXiv:** [2502.12110](https://arxiv.org/abs/2502.12110) (v11, Oct 2025)
**File:** [`papers/2502.12110v11.pdf`](papers/2502.12110v11.pdf)

### Summary

A-Mem proposes a **Zettelkasten-inspired agentic memory system** that dynamically organizes memories without predefined schemas or fixed workflows. Each memory is stored as a structured note with content, timestamp, keywords, tags, contextual description, embedding, and links. Three-phase operation: note construction, link generation, memory evolution. Outperforms MemGPT, MemoryBank, and ReadAgent on LoCoMo benchmark.

**Relevance to Engram:** A-Mem solves *single-agent* memory organization. It has no notion of shared state or cross-agent consistency. Its note structure is instructive for how Engram enriches committed facts with semantic metadata.

---

## [3] MIRIX: Multi-Agent Memory System for LLM-Based Agents

**Authors:** Yu Wang, Xi Chen
**Affiliation:** MIRIX AI (Yu Wang: UCSD, Xi Chen: NYU Stern)
**ArXiv:** [2507.07957](https://arxiv.org/abs/2507.07957) (v1, Jul 2025)
**File:** [`papers/2507.07957v1.pdf`](papers/2507.07957v1.pdf)

### Summary

MIRIX proposes a modular, multi-agent memory system organized around six specialized memory types with a Meta Memory Manager handling routing. SOTA 85.4% on LOCOMO. Its multi-agent architecture is internal (multiple agents managing one user's memory), not cross-team.

**Relevance to Engram:** MIRIX is the state-of-the-art in comprehensive single-user memory architecture. Engram addresses what MIRIX does not: what happens when two engineers' agents independently commit contradictory facts about the same codebase.

---

## [4] Memory in the Age of AI Agents: A Survey

**Authors:** Yuyang Hu, Shichun Liu, Yanwei Yue, Guibin Zhang, et al.
**Affiliations:** NUS, Renmin University, Fudan, Peking, NTU, Tongji, UCSD, HKUST(GZ), Griffith, Georgia Tech, OPPO, Oxford
**ArXiv:** [2512.13564](https://arxiv.org/abs/2512.13564) (v2, Jan 2026)
**File:** [`papers/2512.13564v2.pdf`](papers/2512.13564v2.pdf)

### Summary

The most comprehensive survey of agent memory as of early 2026. Confirms that shared memory for multi-agent systems is an open frontier (Section 7.5) and that conflict detection and resolution are unsolved. The survey's taxonomy gives Engram a precise vocabulary: Engram stores *factual memory* in a *flat token-level* form with *append-only formation* and *explicit conflict evolution*.

---

## Landscape at a Glance

| Paper | Scope | Consistency | Conflict Detection | Year |
|---|---|---|---|---|
| Yu et al. [1] | Architecture framing | Named as #1 open problem | Not implemented | 2026 |
| Xu et al. [2] (A-Mem) | Single-agent memory organization | Temporal coherence only | No | 2025 |
| Wang & Chen [3] (MIRIX) | Single-user multi-component memory | Within one user's store | No | 2025 |
| Hu et al. [4] (Survey) | Full landscape | Flagged as unsolved frontier | No | 2026 |
| **Engram** | **Multi-agent shared memory** | **Cross-agent fact consistency** | **Yes (`engram_conflicts`)** | **2026** |



---

# Adversarial Literature: Three Rounds of Falsification

## Round 1 — Failure Modes in the Original Design

### [5] Foundations of Global Consistency Checking with Noisy LLM Oracles

**Authors:** Paul He et al.
**ArXiv:** [2601.13600](https://arxiv.org/abs/2601.13600) (Jan 2026)

Proves that pairwise LLM contradiction checks are insufficient for global consistency — three facts may each be pairwise consistent while being jointly inconsistent. Engram's detection is inherently pairwise. This is a known ceiling, not a solvable bug.

### [6] Negation is Not Semantic (Bharti et al.)

**ArXiv:** [2603.17580](https://arxiv.org/abs/2603.17580) (Mar 2026)

Embedding-based retrieval fails on negation. "Uses JWT" and "does not use JWT" produce nearly identical embeddings. BM25 lexical retrieval catches what embeddings miss. Engram uses hybrid retrieval (embedding + BM25) to address this.

### [7] The Orthogonality Constraint (Chana et al.)

**ArXiv:** [2601.15313](https://arxiv.org/abs/2601.15313) (Jan 2026)

Embedding retrieval degrades at high semantic density (ρ > 0.6, collapse at N=5 facts). Hash-based retrieval via structured entities maintains 100% accuracy. Engram uses entity extraction as a third retrieval path alongside embeddings and BM25.

### [8] Mandela Effect in Multi-Agent Systems (Xu et al.)

**ArXiv:** [2602.00428](https://arxiv.org/abs/2602.00428) (Jan 2026)

Agents reinforce each other's incorrect beliefs through shared memory. Conflict detection catches contradictions but not corroborating errors. Engram tracks derivation chains via `source_claim_id` and flags single-source clusters.

### [9] Why Do Multi-Agent LLM Systems Fail? (Cemri et al.)

**ArXiv:** [2503.13657](https://arxiv.org/abs/2503.13657) (Mar 2025)

Inter-agent misalignment accounts for 36.9% of MAS failures, including duplication. Engram uses content-hash deduplication to catch semantically identical commits.

### [10] Knowledge Conflicts for LLMs (Xu et al.)

**ArXiv:** [2403.08319](https://arxiv.org/abs/2403.08319) (Mar 2024)

LLMs exhibit unpredictable behavior when retrieved context conflicts with parametric knowledge. Engram cannot control what agents do with retrieved facts, but surfaces provenance and conflict flags to help agents decide.

### [11] Narrative Focus Bias (Purkayastha et al.)

**ArXiv:** [2603.09434](https://arxiv.org/abs/2603.09434) (Mar 2026)

LLMs detect contradictions about secondary entities more readily than primary subjects. Engram's NLI-based detection is not subject to this bias (NLI models don't have narrative focus).

### [12] Agreeableness Bias in LLM Judges (Ahmed et al.)

**ArXiv:** [2510.11822](https://arxiv.org/abs/2510.11822) (Oct 2025)

LLM judges have True Negative Rate < 25% — they miss 75%+ of contradictions. This was the critical finding that drove the shift from LLM-as-judge to NLI cross-encoders as the primary detection mechanism.

### [13] The Messy Reality of Contradiction Detection

**Source:** httphangar.com (2025)

Numeric contradictions (port numbers, rate limits, version numbers) are systematically missed by both embeddings and LLMs. Engram adds deterministic numeric/temporal extraction as a pre-check.

### [14] Cosine Similarity Limitations (You et al.)

**ArXiv:** [2504.16318](https://arxiv.org/abs/2504.16318) (Apr 2025)

Anisotropy in embedding spaces makes absolute cosine thresholds meaningless. Engram uses relative ranking (top-k) rather than fixed thresholds.

### [15] Collaborative Memory (Zhao et al.)

**ArXiv:** [2505.18279](https://arxiv.org/abs/2505.18279) (May 2025)

Real team deployments require time-evolving, asymmetric access policies. Engram's scope permissions are the MVP; the schema supports extension.

### [16] SEDM: Scalable Self-Evolving Distributed Memory (Xu et al.)

**ArXiv:** [2509.09498](https://arxiv.org/abs/2509.09498) (Sep 2025)

Append-only without consolidation leads to noise accumulation. Engram adds utility-based decay and periodic consolidation.

### [17] Learning to Share (Fioresi et al.)

**ArXiv:** [2602.05965](https://arxiv.org/abs/2602.05965) (Feb 2026)

Learned admission control dramatically improves shared memory efficiency. Engram uses novelty-based heuristic admission (content-hash dedup + entity overlap check) as a lightweight alternative.

### [18] MMA: Multimodal Memory Agent (Zhang et al.)

**ArXiv:** [2602.16493](https://arxiv.org/abs/2602.16493) (Feb 2026)

Agent reliability scoring (source credibility + temporal decay + conflict-aware consensus) improves retrieval quality. Engram incorporates agent reliability into query scoring.

---

## Round 2 — The NLI Simplification

### [23] NLI Cross-Encoders Replace LLM-as-Judge

**Model:** `cross-encoder/nli-deberta-v3-base` (92% accuracy, ~10ms/pair, runs locally)

The single most important finding. Replaces the slow, expensive, non-deterministic, agreeableness-biased LLM judge with a fast, free, deterministic NLI model for the majority of contradiction checks. LLM escalation only for ambiguous cases.

### [24] SummaC: Sentence-Level NLI Aggregation (Laban et al.)

**ArXiv:** [2111.09525](https://arxiv.org/abs/2111.09525)

Validates the pairwise NLI scoring + aggregation pattern for consistency checking.

### [25] CLAIRE: Corpus-Level Inconsistency Detection (Semnani et al.)

**ArXiv:** [2509.23233](https://arxiv.org/abs/2509.23233)

Best fully automated detection reaches 75.1% AUROC. Human-in-the-loop review is essential. The dashboard is not optional.

### [26] CodeCRDT (Pugachev et al.)

**ArXiv:** [2510.18893](https://arxiv.org/abs/2510.18893)

CRDTs achieve 100% convergence for multi-agent LLM systems. Validates eventual consistency for federation. 5-10% semantic conflict rate observed.

### [27] Semantic Conflict Model (Semenov et al.)

**ArXiv:** [2602.19231](https://arxiv.org/abs/2602.19231)

Replicated journal with semantic dependency tracking. Engram's append-only log is already a replicated journal — this formalizes the replication semantics for federation.

### [28] Letta (formerly MemGPT)

**Source:** [docs.letta.com](https://docs.letta.com), [GitHub](https://github.com/letta-ai/letta)

Shared memory blocks for multi-agent systems. No conflict detection. Closest competitor. Engram's moat is the consistency layer.

### [29] Agent-MCP

**Source:** [GitHub](https://github.com/rinadelph/Agent-MCP)

Shared knowledge graph MCP server. No conflict detection. Broader feature set (task management, visualization) but no consistency model.

### [30] MAGIC: Multi-Hop Contradictions (EMNLP 2025)

**ArXiv:** [2507.21544](https://arxiv.org/abs/2507.21544)

Confirms that multi-hop contradictions are practically hard for current models. Entity-based retrieval partially mitigates by ensuring facts about the same entities are compared.

### [31] Debate Collapse (Tang et al.)

**ArXiv:** [2602.07186](https://arxiv.org/abs/2602.07186)

Multi-agent feedback loops create cascading false beliefs. Engram tracks derivation chains and flags single-source clusters.

### [32] SCALE: NLI Over Long Documents (EMNLP 2023)

**ArXiv:** [2310.13189](https://arxiv.org/abs/2310.13189)

NLI should operate on full fact content rather than decomposing into sentences.

---

## Round 2 — Security and Infrastructure

### [19] MINJA: Memory Injection Attack

**ArXiv:** [2503.03704](https://arxiv.org/abs/2503.03704) (Mar 2025)

Shared memory is a target for poisoning attacks. Engram mitigates via rate limiting, derivation tracking, and single-source flagging. No quorum or BFT needed — those are overengineered for the threat model.

### [20] SQLite WAL Concurrency

**Source:** SQLite documentation, berthub.eu, tenthousandmeters.com (2024–2025)

SQLite serializes all writes. Under concurrent agent commits, this is a bottleneck. Mitigated by WAL mode, busy timeout, and performing all inference outside transactions. The single-writer principle (see Round 3) eliminates this entirely.

### [21] Silent Embedding Model Drift

**Sources:** Production RAG reports (Weaviate, 2024–2025)

Upgrading embedding models silently corrupts retrieval. Engram stores `embedding_model` and `embedding_model_ver` with every claim and provides `engram reindex`.

### [22] LLM Confidence Calibration Failure

**Sources:** NeurIPS 2024 calibration papers

Agent-reported confidence is systematically inflated. Engram treats it as a noisy signal, normalizes via historical calibration, and uses structural signals (same/different engineer, scope overlap) for severity classification.

---

## Round 3 — The Architectural Collapse

This round asked a different question: not "what failure modes exist?" but "is the architecture itself the problem?"

### The GraphRAG Trap

**Sources:** [Hamel Husain / Jo Kristian Bergum](https://hamel.dev/notes/llm/rag/p7-graph-db.html) (Jul 2025), [Gading Nasution](https://gading.dev/blog/the-graphrag-trap) (Jun 2026), [Substack: When to Use a Knowledge Graph](https://todatabeyond.substack.com/p/when-to-use-a-knowledge-graph-and) (Jun 2026)

Graph databases are unnecessary complexity for 90% of knowledge base use cases. Key arguments from production practitioners:

- A knowledge graph can live in a CSV, a JSON object, or a standard relational database. The hard part is entity disambiguation and maintenance, not storage.
- Graph databases add operational overhead (schema management, entity disambiguation, compute overhead of traversals) without proportional benefit for flat fact stores.
- Early Facebook ran its social graph on MySQL. You can get surprisingly far with general-purpose tools.
- For personal/small-team use, "RAG + structured memory" outperforms GraphRAG in speed, cost, and predictability.

**Impact on Engram:** The previous implementation plan called for replacing SQLite with a graph database (Key Design Constraint #1). This was wrong. Engram's data model is a flat fact store with entity links — not a graph. The relationships between facts (contradicts, supersedes, corroborates) are simple typed edges that SQLite handles natively via foreign keys. Adding a graph database would increase operational complexity, deployment friction, and the dependency surface without improving conflict detection accuracy.

### The Single-Writer Principle

**Source:** [Tacnode: 8 Coordination Patterns That Actually Work](https://tacnode.io/post/ai-agent-coordination) (Jan 2026)

Production multi-agent systems use "shared context, not shared state" — agents read from a single authoritative layer rather than syncing state. The single-writer principle assigns write authority for critical entities to exactly one process, eliminating race conditions by design.

**Impact on Engram:** Engram's SQLite write contention problem [20] is not a SQLite problem — it's an architecture problem. The MCP server process should be the single writer. All agent commits go through one serialized write path. This is not a limitation; it's the correct design for a consistency layer. SQLite's single-writer model becomes an advantage, not a bottleneck.

### Event Sourcing as the Unifying Abstraction

**Sources:** [Event Sourcing with SQLite](https://www.sqliteforum.com/p/event-sourcing-with-sqlite) (Dec 2025), [Reactive Principles: Communicate Facts](https://www.reactiveprinciples.org/patterns/communicate-facts.html), [Pat Helland / Jay Kreps / Martin Kleppmann](https://www.tigrisdata.com/blog/append-only-storage) (Feb 2026)

Engram's facts table is already an event log. Every commit is an immutable event. The current state is derived by replaying events (filtering by non-superseded, non-archived). Conflicts are events too — they record the detection of an inconsistency at a point in time.

The previous plan fought against this by bolting on graph databases, BFT consensus, quorum commits, and complex consolidation jobs. These are mechanisms. The event log is the invariant.

**Impact on Engram:** The entire architecture collapses to: *an append-only event log with projections*. Claims go in. Projections (retrieval index, conflict index, agent stats) are derived views. The log is the source of truth. Everything else is a read model.

### The BFT/Quorum Overengineering

**Sources:** [ResearchGate: Resource-Efficient BFT](https://www.researchgate.net/publication/283444849) (2015), general distributed systems literature

BFT requires 3f+1 replicas to tolerate f faults. For a team of 5-20 engineers running coding agents, this is absurd. The threat model is not Byzantine generals — it's sloppy LLM outputs and occasional bad commits. Rate limiting, content-hash dedup, derivation tracking, and human review (dashboard) are sufficient. BFT and quorum-based commits were removed.

### Git Worktree Isolation as the Industry Direction

**Sources:** [Augment Code](https://www.augmentcode.com/guides/how-to-run-a-multi-agent-coding-workspace) (Mar 2026), [DevSwarm](https://devswarm.ai/blog/why-worktrees-arent-enough) (Mar 2026)

The industry is converging on git worktree isolation for multi-agent coding: each agent works in its own branch, changes merge sequentially. This is the coordination layer. Engram is not a coordination layer — it's a consistency layer that sits alongside this pattern, catching when agents in different worktrees develop contradictory beliefs about the same system.

---

## Competitive Landscape (Updated)

| System | Shared Memory | Conflict Detection | MCP Compatible | Status |
|---|---|---|---|---|
| **Letta** | Yes (blocks) | No | Via adapters | Production |
| **Agent-MCP** | Yes (knowledge graph) | No | Yes (native) | Active OSS |
| **mem0** | No (single-user) | No | Via wrapper | Production (40k+ stars) |
| **shared-memory-mcp** | Yes | No | Yes | Early OSS |
| **Memorix** | Yes (cross-IDE) | No | Partial | Active OSS |
| **SAMEP** | Yes (encrypted) | No | Yes | Research |
| **Engram** | Yes | **Yes** | Yes (native) | **Early development** |

The consistency model remains Engram's unique differentiator. The window is narrowing — Letta has the infrastructure and funding to add conflict detection. Ship fast.

---

## The Unifying Insight

Three rounds of adversarial research converged on a single principle:

> **A fact committed to shared memory is an event. The log of events is the system. Everything else is a projection.**

This is not a metaphor. It is the literal architecture:

- `engram_commit` appends an event to the log
- `engram_query` reads from a retrieval projection (embedding index + BM25 index)
- `engram_conflicts` reads from a consistency projection (NLI-scored pairs)
- The dashboard reads from an analytics projection (agent stats, timelines)

The log never changes. Projections are derived, rebuildable, disposable. This makes the system simple to reason about, simple to federate (sync the log), and simple to extend (add a new projection).

Every component that was removed in Round 3 (graph database, BFT consensus, quorum commits, complex consolidation) was a mechanism that fought against this invariant. Every component that survived (append-only log, NLI cross-encoder, hybrid retrieval, content-hash dedup) reinforces it.
