# Onboarding Flow Guide - next_prompt Strings

This document catalogs all `next_prompt` strings in the Engram MCP tools, serving as a contributor guide to understand the user onboarding flow.

## Overview

The `next_prompt` field in Engram's MCP tool responses tells the AI assistant exactly what to say to the user verbatim. This creates a guided conversational onboarding experience.

---

## Tool: engram_status

### Status: unconfigured (Lines 143-154)
```
Welcome to Engram — shared memory for your team's agents.

Do you have an Invite Key to join an existing workspace, or are you setting up a new one?

If setting up a new workspace, you'll need a PostgreSQL database. You can either:
  • Use your existing app database (Engram creates a separate 'engram' schema)
  • Get a free dedicated database at neon.tech, supabase.com, or railway.app
```

**Trigger:** No workspace.json and no ENGRAM_DB_URL in environment.

---

### Status: db_url_detected (Lines 130-141)
```
I detected a database connection string in your environment.

Do you have an Invite Key to join an existing workspace, or are you setting up a new one?

Note: Engram will create its tables in a separate 'engram' schema in your database, so it won't interfere with your application tables.
```

**Trigger:** ENGRAM_DB_URL exists in environment but no workspace.json.

---

### Status: Disconnected (Lines 90, _DISCONNECTED_NEXT_PROMPT)
```
Your Engram client has been temporarily disconnected due to a security key reset.

The workspace creator has issued a new invite key. To reconnect:

1. Obtain the new invite key from your workspace creator.
2. Call engram_join with the new invite key.
3. Restart your MCP client (Claude Code / Claude Desktop / IDE extension).

Until you reconnect, Engram operations are suspended for your agent.
```

**Trigger:** Key generation mismatch (security reset detected).

---

## Tool: engram_init

### Status: awaiting_db (Lines 194-213)
```
To set up Engram, add your database connection string to your environment.

[If .env exists:]
I see you have a .env file at {env_file}. Add this line:

  ENGRAM_DB_URL='postgres://user:password@host:port/database'

[If .env doesn't exist:]
Create a .env file in your project root with:

  ENGRAM_DB_URL='postgres://user:password@host:port/database'

Or set it in your shell config (.bashrc, .zshrc, etc.):

  export ENGRAM_DB_URL='postgres://user:password@host:port/database'

IMPORTANT: Don't paste your database URL in this chat for security reasons.

You can:
  • Use your existing app database (Engram creates a separate 'engram' schema)
  • Get a free dedicated database at neon.tech, supabase.com, or railway.app

Once set, restart this chat and I'll detect it automatically.
```

**Trigger:** ENGRAM_DB_URL not set in environment.

---

### Status: initialized (Lines 264-276)
```
Your team workspace is ready.

Engram tables are in the '{schema}' schema in your database — completely isolated from your application tables.

Share this with teammates via iMessage, WhatsApp, Slack, or any channel:

  Invite Key: {invite_key}

That's all they need. They install Engram, start a chat, paste the key, and their agent handles the rest.

This invite key can be used {invite_uses} times and expires in {invite_expires_days} days.

Your workspace ID (for your own reference): {engram_id}
```

**Trigger:** Successfully initialized workspace with engram_init.

---

## Tool: engram_join

### Status: error - invalid key (Lines 305-311)
```
That invite key isn't valid: {error_message}

Please double-check it with the person who set up the workspace.
```

**Trigger:** Invite key decoding fails (invalid format or corrupted).

---

### Status: error - revoked (Lines 322-329)
```
This invite key has been revoked or used up. Ask the workspace creator to generate a new one with engram_reset_invite_key.
```

**Trigger:** Invite key not found in database or uses exhausted.

---

### Status: joined (Lines 349-355)
```
You're in. Your agent is now connected to the team's shared memory.

Engram tables are in the '{schema}' schema — isolated from your app.

I'll query team knowledge before starting any task and commit discoveries after. You don't need to think about Engram — it's just there.
```

**Trigger:** Successfully joined workspace with engram_join.

---

## Tool: engram_reset_invite_key

### Status: error - no workspace (Lines 395-398)
```
No team workspace is configured. Only usable in team mode.
```

**Trigger:** No workspace.json or no db_url in workspace.

---

### Status: error - not creator (Lines 401-407)
```
Only the workspace creator can reset the invite key. If you set up this workspace, check that your workspace.json has is_creator=true.
```

**Trigger:** Workspace exists but is_creator is false.

---

### Status: error - storage (Lines 409-413)
```
Storage not initialized. Restart the Engram server and try again.
```

**Trigger:** _storage is None (server not properly initialized).

---

### Status: reset (Lines 461-472)
```
Security reset complete. All existing invite keys have been revoked.

Key generation is now {new_gen}. All members have been temporarily disconnected — they will see a message asking them to reconnect.

Share this new invite key with your team via a secure channel (iMessage, WhatsApp, Slack DM, etc.):

  Invite Key: {invite_key}

Members rejoin by calling engram_join with this key, then restarting their MCP client. This key can be used {invite_uses} times and expires in {invite_expires_days} days.
```

**Trigger:** Successfully reset invite key as workspace creator.

---

## Flow Diagram

```
                    ┌─────────────────┐
                    │  engram_status  │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
       ┌────────────┐ ┌─────────────┐ ┌────────────┐
       │unconfigured│ │db_url_detect│ │disconnected│
       └─────┬──────┘ └──────┬──────┘ └────────────┘
             │                │              │
             ▼                ▼              ▼
        "Join or new?"   "Join or new?"  "Get new key"
             │                │              │
             ▼                ▼              ▼
    ┌───────────────┐ ┌───────────────┐
    │engram_init    │ │engram_join    │
    └───────┬───────┘ └───────┬───────┘
            │                  │
    ┌───────┴───────┐  ┌───────┴───────┐
    ▼               ▼  ▼               ▼
awaiting_db   initialized  invalid/revoked  joined
    │               │         │              │
    ▼               ▼         ▼              ▼
"Set DB URL"   "Share key"  "Error msg"    "Welcome!"
```

---

## Key Design Patterns

1. **Self-contained invites**: The invite key contains everything needed (encrypted DB URL, workspace ID, schema, key_generation)

2. **Security by default**: Key generation counter prevents old keys from working after reset

3. **Isolated schemas**: Engram always uses a separate schema to avoid conflicts with user apps

4. **No secrets in prompts**: DB URLs never appear in next_prompt strings (handled internally)

5. **Guided flow**: Each next_prompt tells the agent exactly what to say and what options to present

---

## Contributing Notes

When modifying next_prompt strings:
- Keep tone conversational and helpful
- Include actionable next steps
- Don't expose internal implementation details
- Test the flow end-to-end before merging
- Document any new prompts in this guide