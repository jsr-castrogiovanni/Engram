"""Vercel ASGI entrypoint — serves the landing page only.

Self-contained — no dependency on the engram package — so
Vercel only needs starlette in requirements.txt.
"""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.routing import Route


def _render_landing() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Engram — Shared memory for your team's agents</title>
  <meta name="description" content="Shared memory for your team's agents. Zero setup. You own your data.">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
      line-height: 1.6;
      color: #1a1a1a;
      background: #ffffff;
    }
    
    .container {
      max-width: 900px;
      margin: 0 auto;
      padding: 0 24px;
    }
    
    /* Header */
    header {
      padding: 20px 0;
      border-bottom: 1px solid #e5e5e5;
    }
    
    .header-content {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    
    .logo {
      font-size: 24px;
      font-weight: 700;
      color: #059669;
      text-decoration: none;
    }
    
    .nav-links {
      display: flex;
      gap: 24px;
      align-items: center;
    }
    
    .nav-links a {
      color: #666;
      text-decoration: none;
      font-size: 15px;
      transition: color 0.2s;
    }
    
    .nav-links a:hover {
      color: #059669;
    }
    
    /* Hero */
    .hero {
      padding: 80px 0 60px;
      text-align: center;
    }
    
    .badges {
      display: flex;
      gap: 8px;
      justify-content: center;
      margin-bottom: 32px;
      flex-wrap: wrap;
    }
    
    .badge {
      display: inline-block;
      background: #f3f4f6;
      color: #666;
      padding: 4px 12px;
      border-radius: 4px;
      font-size: 13px;
      font-weight: 500;
    }
    
    .badge.green { background: #ecfdf5; color: #059669; }
    .badge.blue { background: #eff6ff; color: #2563eb; }
    .badge.purple { background: #f5f3ff; color: #7c3aed; }
    
    h1 {
      font-size: 42px;
      font-weight: 700;
      line-height: 1.2;
      margin-bottom: 20px;
      color: #1a1a1a;
    }
    
    .subtitle {
      font-size: 18px;
      color: #666;
      max-width: 700px;
      margin: 0 auto 16px;
      line-height: 1.7;
    }
    
    .quote {
      font-style: italic;
      color: #666;
      max-width: 700px;
      margin: 24px auto 0;
      padding: 16px 24px;
      border-left: 3px solid #059669;
      background: #f9fafb;
      text-align: left;
    }
    
    /* Install */
    .install {
      padding: 60px 0;
      background: #f9fafb;
    }
    
    .section-title {
      font-size: 28px;
      font-weight: 700;
      margin-bottom: 24px;
    }
    
    .code-block {
      background: #1a1a1a;
      color: #e5e5e5;
      padding: 20px;
      border-radius: 8px;
      font-family: 'Courier New', monospace;
      font-size: 15px;
      margin-bottom: 16px;
      position: relative;
    }
    
    .code-block .copy-btn {
      position: absolute;
      top: 12px;
      right: 12px;
      background: #374151;
      color: #e5e5e5;
      border: none;
      padding: 6px 12px;
      border-radius: 4px;
      cursor: pointer;
      font-size: 12px;
    }
    
    .code-block .copy-btn:hover {
      background: #4b5563;
    }
    
    .note {
      font-size: 14px;
      color: #666;
      line-height: 1.6;
    }
    
    /* Content sections */
    .section {
      padding: 60px 0;
    }
    
    .section p {
      font-size: 16px;
      color: #4b5563;
      line-height: 1.8;
      margin-bottom: 16px;
    }
    
    .section ul {
      margin: 16px 0 16px 24px;
    }
    
    .section li {
      font-size: 16px;
      color: #4b5563;
      line-height: 1.8;
      margin-bottom: 8px;
    }
    
    /* Tools table */
    .tools-table {
      width: 100%;
      border-collapse: collapse;
      margin: 24px 0;
    }
    
    .tools-table th {
      text-align: left;
      padding: 12px;
      background: #f9fafb;
      border-bottom: 2px solid #e5e5e5;
      font-weight: 600;
      font-size: 14px;
    }
    
    .tools-table td {
      padding: 12px;
      border-bottom: 1px solid #e5e5e5;
      font-size: 15px;
    }
    
    .tools-table code {
      background: #f3f4f6;
      padding: 2px 6px;
      border-radius: 3px;
      font-family: 'Courier New', monospace;
      font-size: 14px;
    }
    
    /* Footer */
    footer {
      padding: 48px 0;
      border-top: 1px solid #e5e5e5;
      text-align: center;
    }
    
    .footer-content {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 24px;
    }
    
    .footer-links {
      display: flex;
      gap: 24px;
    }
    
    .footer-links a {
      color: #666;
      text-decoration: none;
      font-size: 14px;
    }
    
    .footer-links a:hover {
      color: #059669;
    }
    
    .footer-tagline {
      font-size: 13px;
      color: #999;
      font-style: italic;
    }
    
    /* Responsive */
    @media (max-width: 768px) {
      h1 { font-size: 32px; }
      .subtitle { font-size: 16px; }
      .hero { padding: 48px 0 32px; }
      .section { padding: 40px 0; }
      .install { padding: 40px 0; }
      .footer-content { flex-direction: column; text-align: center; }
    }
  </style>
</head>
<body>
  <!-- Header -->
  <header>
    <div class="container">
      <div class="header-content">
        <a href="/" class="logo">engram</a>
        <nav class="nav-links">
          <a href="https://github.com/Agentscreator/Engram" target="_blank">GitHub</a>
          <a href="https://github.com/Agentscreator/Engram/blob/main/CONTRIBUTING.md" target="_blank">Contributing</a>
        </nav>
      </div>
    </div>
  </header>

  <!-- Hero -->
  <section class="hero">
    <div class="container">
      <div class="badges">
        <span class="badge green">Core: Shipped</span>
        <span class="badge green">Dashboard: Shipped</span>
        <span class="badge green">Federation: Shipped</span>
        <span class="badge blue">License: Apache 2.0</span>
        <span class="badge purple">MCP Compatible</span>
        <span class="badge">Python 3.11+</span>
      </div>
      
      <h1>Shared memory for your team's agents.<br>Zero setup. You own your data.</h1>
      
      <p class="subtitle">
        Engram gives your team's agents a shared, persistent memory that survives across sessions 
        and detects when two agents develop contradictory beliefs about the same codebase.
      </p>
      
      <p class="subtitle">You bring your own database. Engram never owns your data.</p>
      
      <div class="quote">
        Individual agent memory is solved. Engram solves what happens when multiple agents need to agree on what's true.
      </div>
    </div>
  </section>

  <!-- How it works -->
  <section class="section">
    <div class="container">
      <h2 class="section-title">How it works</h2>
      <p>
        Every agent on your team connects to the same knowledge base. When one agent discovers something — 
        a hidden side effect, a failed approach, an undocumented constraint — it commits that fact. 
        Every other agent on the team can query it instantly.
      </p>
      <p>
        When two agents develop incompatible beliefs about the same system, Engram detects the contradiction 
        and surfaces it for review. No silent divergence.
      </p>
    </div>
  </section>

  <!-- Install -->
  <section class="install">
    <div class="container">
      <h2 class="section-title">Install</h2>
      <div class="code-block">
        <button class="copy-btn" onclick="copyCode('install-cmd')">Copy</button>
        <div id="install-cmd">pip install engram-mcp<br>engram install</div>
      </div>
      <p class="note">
        <code>engram install</code> auto-detects your MCP client (Claude Code, Cursor, Windsurf) and adds the config. 
        Restart your editor and open a new chat — your agent handles everything else.
      </p>
    </div>
  </section>

  <!-- What happens after install -->
  <section class="section">
    <div class="container">
      <h2 class="section-title">What happens after install</h2>
      <p>
        Your agent calls <code>engram_status()</code> on its first tool use and walks you through setup. 
        No docs to read. No JSON to edit.
      </p>
      <p><strong>Setting up a new workspace (team founder):</strong></p>
      <p>
        The agent asks if you're joining or creating. You say "new". It asks for a database connection string 
        (you can get a free PostgreSQL database at neon.tech, supabase.com, or railway.app). 
        Once set, it generates an Invite Key — that's all teammates need.
      </p>
      <p><strong>Joining a workspace (teammate):</strong></p>
      <p>
        The agent asks for your Invite Key. You paste it. Done. The workspace ID and database connection 
        are encrypted inside it and extracted automatically.
      </p>
      <p>
        <strong>Every session after that:</strong> the agent connects silently, queries before every task, 
        commits after every discovery. Engram is invisible infrastructure.
      </p>
    </div>
  </section>

  <!-- You own your data -->
  <section class="section" style="background: #f9fafb;">
    <div class="container">
      <h2 class="section-title">You own your data</h2>
      <p>
        Engram connects to a PostgreSQL database you provide. Your facts, conflicts, and agent history 
        live in your database — not ours.
      </p>
      <ul>
        <li>Use Neon, Supabase, Railway, or any PostgreSQL instance</li>
        <li>Self-host if you want zero third-party involvement</li>
        <li>The database URL is never stored by Engram — only in <code>~/.engram/workspace.json</code> on your machine (mode 600)</li>
        <li>The invite key carries the database URL encrypted inside it — teammates never see it in plaintext</li>
      </ul>
    </div>
  </section>

  <!-- Tools -->
  <section class="section">
    <div class="container">
      <h2 class="section-title">Tools</h2>
      <p>Engram exposes seven MCP tools. The first three handle setup; the last four are the knowledge layer.</p>
      
      <table class="tools-table">
        <thead>
          <tr>
            <th>Tool</th>
            <th>Purpose</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><code>engram_status</code></td>
            <td>Check setup state. Returns next_prompt — the agent says it to you.</td>
          </tr>
          <tr>
            <td><code>engram_init</code></td>
            <td>Create a new workspace (founder). Generates Team ID + Invite Key.</td>
          </tr>
          <tr>
            <td><code>engram_join</code></td>
            <td>Join a workspace with just an Invite Key. Extracts workspace ID + db URL automatically.</td>
          </tr>
          <tr>
            <td><code>engram_query</code></td>
            <td>Pull what your team's agents collectively know about a topic.</td>
          </tr>
          <tr>
            <td><code>engram_commit</code></td>
            <td>Persist a verified discovery — fact, constraint, decision, failed approach.</td>
          </tr>
          <tr>
            <td><code>engram_conflicts</code></td>
            <td>Surface pairs of facts that semantically contradict each other.</td>
          </tr>
          <tr>
            <td><code>engram_resolve</code></td>
            <td>Settle a disagreement: pick a winner, merge both sides, or dismiss.</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>

  <!-- Footer -->
  <footer>
    <div class="container">
      <div class="footer-content">
        <div class="footer-links">
          <span style="font-weight: 600; color: #1a1a1a;">engram</span>
          <a href="https://github.com/Agentscreator/Engram" target="_blank">GitHub</a>
          <a href="https://github.com/Agentscreator/Engram/blob/main/LICENSE" target="_blank">Apache 2.0</a>
          <a href="https://github.com/Agentscreator/Engram/blob/main/CONTRIBUTING.md" target="_blank">Contributing</a>
        </div>
      </div>
      <p class="footer-tagline">An engram is the physical trace a memory leaves in the brain — the actual unit of stored knowledge.</p>
    </div>
  </footer>

  <script>
    function copyCode(id) {
      const el = document.getElementById(id);
      const text = el.textContent.replace(/\n/g, ' && ').trim();
      navigator.clipboard.writeText(text).then(() => {
        const btn = event.target;
        btn.textContent = 'Copied!';
        setTimeout(() => btn.textContent = 'Copy', 2000);
      });
    }
  </script>
</body>
</html>"""


def _render_dashboard_placeholder() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Dashboard — Engram</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #f9fafb;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      padding: 24px;
    }
    .card {
      max-width: 500px;
      background: white;
      padding: 48px;
      border-radius: 12px;
      border: 1px solid #e5e5e5;
      text-align: center;
    }
    h1 {
      font-size: 24px;
      margin-bottom: 16px;
      color: #1a1a1a;
    }
    p {
      color: #666;
      line-height: 1.6;
      margin-bottom: 24px;
    }
    .code-box {
      background: #1a1a1a;
      color: #e5e5e5;
      padding: 16px;
      border-radius: 8px;
      font-family: 'Courier New', monospace;
      font-size: 14px;
      text-align: left;
      margin-bottom: 24px;
    }
    a {
      color: #059669;
      text-decoration: none;
      font-weight: 500;
    }
    a:hover {
      text-decoration: underline;
    }
  </style>
</head>
<body>
  <div class="card">
    <h1>Dashboard needs a running server</h1>
    <p>Start your local Engram instance, then open the dashboard there.</p>
    <div class="code-box">
      pip install engram-mcp<br>
      engram install<br>
      engram serve --http
    </div>
    <p>Then visit <a href="http://localhost:7474/dashboard">localhost:7474/dashboard</a></p>
    <p><a href="/">← Back to home</a></p>
  </div>
</body>
</html>"""


async def landing(request: Request) -> HTMLResponse:
    return HTMLResponse(_render_landing())


async def dashboard_placeholder(request: Request) -> HTMLResponse:
    return HTMLResponse(_render_dashboard_placeholder())


app = Starlette(
    routes=[
        Route("/", landing, methods=["GET"]),
        Route("/dashboard", dashboard_placeholder, methods=["GET"]),
        Route("/dashboard/{path:path}", dashboard_placeholder, methods=["GET"]),
    ],
)
