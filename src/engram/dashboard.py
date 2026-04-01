"""Phase 7 — Dashboard: server-rendered HTML with HTMX.

Co-located with the MCP server on the same process. Endpoint: /dashboard.
Views: knowledge base, conflict queue, timeline, agent activity,
point-in-time, expiring facts.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

from engram.storage import Storage

logger = logging.getLogger("engram")


def build_dashboard_routes(storage: Storage) -> list[Route]:
    """Build all dashboard routes."""

    async def index(request: Request) -> HTMLResponse:
        facts_count = await storage.count_facts(current_only=True)
        total_facts = await storage.count_facts(current_only=False)
        open_conflicts = await storage.count_conflicts("open")
        resolved_conflicts = await storage.count_conflicts("resolved")
        agents = await storage.get_agents()
        expiring = await storage.get_expiring_facts(days_ahead=7)

        return HTMLResponse(_render_index(
            facts_count=facts_count,
            total_facts=total_facts,
            open_conflicts=open_conflicts,
            resolved_conflicts=resolved_conflicts,
            agents=agents,
            expiring_count=len(expiring),
        ))

    async def knowledge_base(request: Request) -> HTMLResponse:
        scope = request.query_params.get("scope")
        fact_type = request.query_params.get("fact_type")
        as_of = request.query_params.get("as_of")
        facts = await storage.get_current_facts_in_scope(
            scope=scope, fact_type=fact_type, as_of=as_of, limit=100
        )
        conflict_ids = await storage.get_open_conflict_fact_ids()
        return HTMLResponse(_render_facts_table(facts, conflict_ids))

    async def conflict_queue(request: Request) -> HTMLResponse:
        scope = request.query_params.get("scope")
        status = request.query_params.get("status", "open")
        conflicts = await storage.get_conflicts(scope=scope, status=status)
        return HTMLResponse(_render_conflicts_table(conflicts))

    async def timeline(request: Request) -> HTMLResponse:
        scope = request.query_params.get("scope")
        facts = await storage.get_fact_timeline(scope=scope, limit=100)
        return HTMLResponse(_render_timeline(facts))

    async def agents_view(request: Request) -> HTMLResponse:
        agents = await storage.get_agents()
        feedback = await storage.get_detection_feedback_stats()
        return HTMLResponse(_render_agents(agents, feedback))

    async def expiring_view(request: Request) -> HTMLResponse:
        days = int(request.query_params.get("days", "7"))
        facts = await storage.get_expiring_facts(days_ahead=days)
        return HTMLResponse(_render_expiring(facts, days))

    return [
        Route("/dashboard", index, methods=["GET"]),
        Route("/dashboard/facts", knowledge_base, methods=["GET"]),
        Route("/dashboard/conflicts", conflict_queue, methods=["GET"]),
        Route("/dashboard/timeline", timeline, methods=["GET"]),
        Route("/dashboard/agents", agents_view, methods=["GET"]),
        Route("/dashboard/expiring", expiring_view, methods=["GET"]),
    ]


# ── HTML rendering ───────────────────────────────────────────────────

_HTMX_SCRIPT = '<script src="https://unpkg.com/htmx.org@2.0.4"></script>'

_STYLE = """
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: #0d1117; color: #c9d1d9; line-height: 1.5; }
  .container { max-width: 1200px; margin: 0 auto; padding: 1rem; }
  h1 { color: #58a6ff; margin-bottom: 0.5rem; font-size: 1.5rem; }
  h2 { color: #8b949e; font-size: 1.1rem; margin: 1rem 0 0.5rem; }
  .stats { display: flex; gap: 1rem; flex-wrap: wrap; margin: 1rem 0; }
  .stat { background: #161b22; border: 1px solid #30363d; border-radius: 6px;
          padding: 1rem; min-width: 150px; }
  .stat-value { font-size: 1.8rem; font-weight: 600; color: #58a6ff; }
  .stat-label { font-size: 0.85rem; color: #8b949e; }
  nav { display: flex; gap: 0.5rem; margin: 1rem 0; flex-wrap: wrap; }
  nav a, nav button { background: #21262d; color: #c9d1d9; border: 1px solid #30363d;
         border-radius: 6px; padding: 0.4rem 0.8rem; text-decoration: none;
         cursor: pointer; font-size: 0.85rem; }
  nav a:hover, nav button:hover { background: #30363d; }
  table { width: 100%; border-collapse: collapse; margin: 0.5rem 0; }
  th, td { text-align: left; padding: 0.5rem; border-bottom: 1px solid #21262d;
           font-size: 0.85rem; }
  th { color: #8b949e; font-weight: 500; }
  .badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 12px;
           font-size: 0.75rem; font-weight: 500; }
  .badge-high { background: #da363340; color: #f85149; }
  .badge-medium { background: #d2992240; color: #d29922; }
  .badge-low { background: #23883040; color: #3fb950; }
  .badge-open { background: #da363340; color: #f85149; }
  .badge-resolved { background: #23883040; color: #3fb950; }
  .badge-dismissed { background: #8b949e30; color: #8b949e; }
  .badge-verified { background: #23883040; color: #3fb950; }
  .badge-unverified { background: #d2992240; color: #d29922; }
  .content-cell { max-width: 400px; overflow: hidden; text-overflow: ellipsis;
                  white-space: nowrap; }
  .timeline-bar { height: 8px; border-radius: 4px; background: #58a6ff; min-width: 4px; }
  .timeline-bar.superseded { background: #8b949e; opacity: 0.5; }
  input, select { background: #0d1117; color: #c9d1d9; border: 1px solid #30363d;
                  border-radius: 6px; padding: 0.4rem; font-size: 0.85rem; }
  #content { min-height: 200px; }
  .filter-bar { display: flex; gap: 0.5rem; align-items: center; margin: 0.5rem 0;
                flex-wrap: wrap; }
</style>
"""


def _layout(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} — Engram Dashboard</title>
  {_HTMX_SCRIPT}
  {_STYLE}
</head>
<body>
  <div class="container">
    <h1>Engram Dashboard</h1>
    <nav>
      <a href="/dashboard">Overview</a>
      <a href="/dashboard/facts">Knowledge Base</a>
      <a href="/dashboard/conflicts">Conflicts</a>
      <a href="/dashboard/timeline">Timeline</a>
      <a href="/dashboard/agents">Agents</a>
      <a href="/dashboard/expiring">Expiring</a>
    </nav>
    {body}
  </div>
</body>
</html>"""


def _render_index(
    facts_count: int,
    total_facts: int,
    open_conflicts: int,
    resolved_conflicts: int,
    agents: list[dict],
    expiring_count: int,
) -> str:
    body = f"""
    <div class="stats">
      <div class="stat">
        <div class="stat-value">{facts_count}</div>
        <div class="stat-label">Current Facts</div>
      </div>
      <div class="stat">
        <div class="stat-value">{total_facts}</div>
        <div class="stat-label">Total Facts (all time)</div>
      </div>
      <div class="stat">
        <div class="stat-value">{open_conflicts}</div>
        <div class="stat-label">Open Conflicts</div>
      </div>
      <div class="stat">
        <div class="stat-value">{resolved_conflicts}</div>
        <div class="stat-label">Resolved Conflicts</div>
      </div>
      <div class="stat">
        <div class="stat-value">{len(agents)}</div>
        <div class="stat-label">Registered Agents</div>
      </div>
      <div class="stat">
        <div class="stat-value">{expiring_count}</div>
        <div class="stat-label">Expiring Soon (7d)</div>
      </div>
    </div>
    <h2>Recent Agents</h2>
    <table>
      <tr><th>Agent</th><th>Engineer</th><th>Commits</th><th>Flagged</th><th>Last Seen</th></tr>
      {"".join(_agent_row(a) for a in agents[:10])}
    </table>
    """
    return _layout("Overview", body)


def _agent_row(a: dict) -> str:
    total = a.get("total_commits", 0)
    flagged = a.get("flagged_commits", 0)
    ratio = f"{flagged}/{total}" if total else "0/0"
    return (
        f"<tr><td>{_esc(a['agent_id'])}</td><td>{_esc(a.get('engineer', ''))}</td>"
        f"<td>{total}</td><td>{ratio}</td>"
        f"<td>{_esc(a.get('last_seen', '') or '')}</td></tr>"
    )


def _render_facts_table(facts: list[dict], conflict_ids: set[str]) -> str:
    rows = []
    for f in facts:
        has_conflict = f["id"] in conflict_ids
        verified = f.get("provenance") is not None
        conflict_badge = '<span class="badge badge-open">conflict</span>' if has_conflict else ""
        ver_badge = (
            '<span class="badge badge-verified">verified</span>'
            if verified
            else '<span class="badge badge-unverified">unverified</span>'
        )
        rows.append(
            f"<tr><td class='content-cell'>{_esc(f['content'])}</td>"
            f"<td>{_esc(f['scope'])}</td>"
            f"<td>{f['confidence']:.2f}</td>"
            f"<td>{_esc(f['fact_type'])}</td>"
            f"<td>{_esc(f['agent_id'])}</td>"
            f"<td>{conflict_badge} {ver_badge}</td>"
            f"<td>{_esc(f.get('committed_at', '')[:19])}</td></tr>"
        )
    body = f"""
    <h2>Knowledge Base</h2>
    <div class="filter-bar">
      <form method="get" action="/dashboard/facts" style="display:flex;gap:0.5rem;flex-wrap:wrap;">
        <input name="scope" placeholder="Scope filter" value="">
        <select name="fact_type">
          <option value="">All types</option>
          <option value="observation">observation</option>
          <option value="inference">inference</option>
          <option value="decision">decision</option>
        </select>
        <input name="as_of" placeholder="as_of (ISO 8601)" value="">
        <button type="submit">Filter</button>
      </form>
    </div>
    <table>
      <tr><th>Content</th><th>Scope</th><th>Confidence</th><th>Type</th>
          <th>Agent</th><th>Status</th><th>Committed</th></tr>
      {"".join(rows)}
    </table>
    <p style="color:#8b949e;font-size:0.8rem;">Showing {len(facts)} fact(s)</p>
    """
    return _layout("Knowledge Base", body)


def _render_conflicts_table(conflicts: list[dict]) -> str:
    rows = []
    for c in conflicts:
        sev = c.get("severity", "low")
        status = c.get("status", "open")
        sev_badge = f'<span class="badge badge-{sev}">{sev}</span>'
        status_badge = f'<span class="badge badge-{status}">{status}</span>'
        rows.append(
            f"<tr><td>{_esc(c['id'][:12])}...</td>"
            f"<td class='content-cell'>{_esc(c.get('fact_a_content', ''))}</td>"
            f"<td class='content-cell'>{_esc(c.get('fact_b_content', ''))}</td>"
            f"<td>{_esc(c.get('detection_tier', ''))}</td>"
            f"<td>{sev_badge}</td>"
            f"<td>{status_badge}</td>"
            f"<td>{_esc(c.get('detected_at', '')[:19])}</td></tr>"
        )
    body = f"""
    <h2>Conflict Queue</h2>
    <div class="filter-bar">
      <form method="get" action="/dashboard/conflicts" style="display:flex;gap:0.5rem;">
        <input name="scope" placeholder="Scope filter" value="">
        <select name="status">
          <option value="open">Open</option>
          <option value="resolved">Resolved</option>
          <option value="dismissed">Dismissed</option>
          <option value="all">All</option>
        </select>
        <button type="submit">Filter</button>
      </form>
    </div>
    <table>
      <tr><th>ID</th><th>Fact A</th><th>Fact B</th><th>Tier</th>
          <th>Severity</th><th>Status</th><th>Detected</th></tr>
      {"".join(rows)}
    </table>
    <p style="color:#8b949e;font-size:0.8rem;">Showing {len(conflicts)} conflict(s)</p>
    """
    return _layout("Conflicts", body)


def _render_timeline(facts: list[dict]) -> str:
    rows = []
    for f in facts:
        is_superseded = f.get("valid_until") is not None
        bar_class = "timeline-bar superseded" if is_superseded else "timeline-bar"
        valid_range = f.get("valid_from", "")[:10]
        if is_superseded:
            valid_range += f" → {f['valid_until'][:10]}"
        else:
            valid_range += " → current"
        rows.append(
            f"<tr><td class='content-cell'>{_esc(f['content'][:80])}</td>"
            f"<td>{_esc(f['scope'])}</td>"
            f"<td>{_esc(f['agent_id'])}</td>"
            f"<td>{valid_range}</td>"
            f"<td><div class='{bar_class}' style='width:60px;'></div></td></tr>"
        )
    body = f"""
    <h2>Timeline</h2>
    <div class="filter-bar">
      <form method="get" action="/dashboard/timeline" style="display:flex;gap:0.5rem;">
        <input name="scope" placeholder="Scope filter" value="">
        <button type="submit">Filter</button>
      </form>
    </div>
    <table>
      <tr><th>Content</th><th>Scope</th><th>Agent</th><th>Validity</th><th>Window</th></tr>
      {"".join(rows)}
    </table>
    """
    return _layout("Timeline", body)


def _render_agents(agents: list[dict], feedback: dict[str, int]) -> str:
    rows = []
    for a in agents:
        total = a.get("total_commits", 0)
        flagged = a.get("flagged_commits", 0)
        reliability = f"{(1 - flagged / total) * 100:.0f}%" if total > 0 else "N/A"
        rows.append(
            f"<tr><td>{_esc(a['agent_id'])}</td>"
            f"<td>{_esc(a.get('engineer', ''))}</td>"
            f"<td>{total}</td>"
            f"<td>{flagged}</td>"
            f"<td>{reliability}</td>"
            f"<td>{_esc(a.get('registered_at', '')[:19])}</td>"
            f"<td>{_esc(a.get('last_seen', '') or '')[:19]}</td></tr>"
        )
    tp = feedback.get("true_positive", 0)
    fp = feedback.get("false_positive", 0)
    body = f"""
    <h2>Agent Activity</h2>
    <div class="stats">
      <div class="stat">
        <div class="stat-value">{len(agents)}</div>
        <div class="stat-label">Total Agents</div>
      </div>
      <div class="stat">
        <div class="stat-value">{tp}</div>
        <div class="stat-label">True Positive Feedback</div>
      </div>
      <div class="stat">
        <div class="stat-value">{fp}</div>
        <div class="stat-label">False Positive Feedback</div>
      </div>
    </div>
    <table>
      <tr><th>Agent</th><th>Engineer</th><th>Commits</th><th>Flagged</th>
          <th>Reliability</th><th>Registered</th><th>Last Seen</th></tr>
      {"".join(rows)}
    </table>
    """
    return _layout("Agents", body)


def _render_expiring(facts: list[dict], days: int) -> str:
    rows = []
    for f in facts:
        rows.append(
            f"<tr><td class='content-cell'>{_esc(f['content'])}</td>"
            f"<td>{_esc(f['scope'])}</td>"
            f"<td>{f.get('ttl_days', '')}</td>"
            f"<td>{_esc(f.get('valid_until', '')[:19])}</td>"
            f"<td>{_esc(f['agent_id'])}</td></tr>"
        )
    body = f"""
    <h2>Expiring Facts (next {days} days)</h2>
    <div class="filter-bar">
      <form method="get" action="/dashboard/expiring" style="display:flex;gap:0.5rem;">
        <input name="days" type="number" value="{days}" min="1" max="90" style="width:60px;">
        <button type="submit">Update</button>
      </form>
    </div>
    <table>
      <tr><th>Content</th><th>Scope</th><th>TTL (days)</th><th>Expires</th><th>Agent</th></tr>
      {"".join(rows)}
    </table>
    <p style="color:#8b949e;font-size:0.8rem;">{len(facts)} fact(s) expiring within {days} day(s)</p>
    """
    return _layout("Expiring Facts", body)


def _esc(s: Any) -> str:
    """HTML-escape a string."""
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
