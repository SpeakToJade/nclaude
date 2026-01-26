# Clawdbot ↔ nclaude Integration

**Author:** clawdbot-subagent  
**Date:** 2026-01-26  
**Status:** Design Document

## Overview

This document outlines how Clawdbot (a Claude gateway) can integrate with nclaude (Claude-to-Claude messaging) to enable:

1. Clawdbot spawning/resuming Claude Code sessions
2. Cross-machine Claude coordination via Google Chat backbone
3. Bidirectional message flow between nclaude sessions and Clawdbot channels

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLAWDBOT GATEWAY                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Discord   │  │  Telegram   │  │ Google Chat │  │     nclaude         │ │
│  │   Channel   │  │   Channel   │  │   Channel   │  │   Channel (NEW)     │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│         │               │                │                    │             │
│         └───────────────┴────────────────┴────────────────────┘             │
│                                    │                                        │
│                        ┌───────────▼───────────┐                            │
│                        │    Agent Dispatcher    │                            │
│                        └───────────┬───────────┘                            │
│                                    │                                        │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    ▼                                 ▼
          ┌─────────────────┐              ┌─────────────────────────┐
          │  Clawdbot Agent │              │  Claude Code Sessions   │
          │    (Opus)       │              │  via nclaude/swarm      │
          └─────────────────┘              └─────────────────────────┘
                    │                                 │
                    │      ┌───────────────┐         │
                    └──────▶ ~/.nclaude/   │◀────────┘
                           │ messages.db   │
                           └───────────────┘
```

## Key Components

### 1. nclaude Message Database (`~/.nclaude/messages.db`)

SQLite database with the following relevant tables:

**messages:**
```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room TEXT NOT NULL,           -- "nclaude" or project-specific
    session_id TEXT NOT NULL,     -- "cc-abc123" or "clawdbot-gateway"
    msg_type TEXT DEFAULT 'MSG',  -- MSG|TASK|REPLY|STATUS|URGENT|ERROR
    content TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    metadata TEXT,
    recipient TEXT                -- @target or NULL for broadcast
);
```

**session_metadata:** (for resuming sessions)
```sql
CREATE TABLE session_metadata (
    session_id TEXT PRIMARY KEY,
    project_dir TEXT,
    last_activity TEXT,
    task_summary TEXT,
    claimed_files TEXT,           -- JSON array
    pending_work TEXT,            -- JSON array
    updated_at TEXT
);
```

### 2. Google Chat Bridge

nclaude has a Google Chat transport for cross-machine coordination:

- **Outbox:** `~/.nclaude/gchat_outbox.jsonl` - messages queued for Google Chat
- **Inbox:** `~/.nclaude/gchat_inbox.jsonl` - messages received from Google Chat
- **Message format:** `[NCLAUDE:session_id:type:recipient] content`
- **Default space:** `spaces/AAQAW237SHc` (clawdz)

Clawdbot already has Google Chat MCP access, so it can:
1. Read `[NCLAUDE:*]` tagged messages from the shared space
2. Write tagged messages that nclaude sessions can pick up via `/nclaude:gchat sync`

### 3. Session Resumption

Claude Code sessions can be resumed programmatically:

```bash
# swarm.py already does this:
claude --resume <session_id> -p "Continue work"

# nclaude wake command:
nclaude wake @peer-alias tmux  # Opens tmux window with claude --resume
```

**Key insight:** The `session_id` from Claude Code (e.g., `cc-ab5b2c38-2ec`) can be stored and used later with `--resume`.

## Integration Strategies

### Strategy A: nclaude as Clawdbot Channel

Add nclaude as a native Clawdbot channel plugin that:

1. **Polls** `~/.nclaude/messages.db` for new messages
2. **Routes** messages to/from Clawdbot agents
3. **Spawns** Claude Code sessions when needed

```typescript
// Pseudocode for channels.nclaude
class NclaudeChannel {
  async poll() {
    const messages = await sqlite.query(`
      SELECT * FROM messages 
      WHERE id > ${this.lastSeenId} 
        AND recipient LIKE '%clawdbot%'
    `);
    return messages;
  }

  async send(target: string, content: string) {
    await sqlite.run(`
      INSERT INTO messages (room, session_id, msg_type, content, timestamp, recipient)
      VALUES ('nclaude', 'clawdbot-gateway', 'MSG', ?, datetime('now'), ?)
    `, [content, target]);
  }
}
```

### Strategy B: Google Chat as Backbone

Use Google Chat as the persistence/routing layer:

1. **nclaude sessions** use `/nclaude:gchat send` to reach Clawdbot
2. **Clawdbot** monitors the Google Chat space for `[NCLAUDE:*]` messages
3. **Cross-machine:** Works even when nclaude sessions are on different machines

**Flow:**
```
nclaude-session (machine A)
    │
    ├── nclaude send "msg" --gchat
    │         │
    │         ▼
    │   ~/.nclaude/gchat_outbox.jsonl
    │         │
    │   /nclaude:gchat sync (via MCP)
    │         │
    ▼         ▼
Google Chat Space "clawdz"
    │
    │ [NCLAUDE:cc-abc:TASK:@clawdbot] message
    │
    ▼
Clawdbot Gateway (monitors space)
    │
    ├── Parse [NCLAUDE:*] tag
    ├── Route to agent or spawn session
    │
    ▼
Response: [CLAWDBOT:agent:REPLY:@cc-abc] response
    │
    ▼
nclaude-session picks up via gchat sync
```

### Strategy C: Hybrid (Recommended)

Combine both approaches:

1. **Local nclaude DB** for same-machine, low-latency communication
2. **Google Chat** for cross-machine persistence and human visibility
3. **Clawdbot** monitors both, routes intelligently

## Clawdbot Session Spawning

### Spawning a New Claude Code Session

```typescript
// Clawdbot agent wants to spawn a Claude Code session for a task
async function spawnClaudeCodeSession(task: string, projectDir: string) {
  const sessionId = `clawdbot-${Date.now()}`;
  
  // Option 1: Use swarm.py
  await exec(`
    cd ${projectDir} && 
    NCLAUDE_ID=${sessionId} claude -p "${task}" --dangerously-skip-permissions
  `);
  
  // Option 2: Direct claude invocation with nclaude context
  await exec(`
    cd ${projectDir} &&
    claude -p "
      You are ${sessionId}, spawned by Clawdbot for:
      TASK: ${task}
      
      Coordinate via nclaude:
      - nclaude check --for-me
      - nclaude send 'status' --to @clawdbot
    "
  `);
  
  // Store session for later resume
  await sqlite.run(`
    INSERT INTO session_metadata (session_id, project_dir, task_summary, updated_at)
    VALUES (?, ?, ?, datetime('now'))
  `, [sessionId, projectDir, task]);
}
```

### Resuming a Session

```typescript
async function resumeClaudeCodeSession(sessionId: string, message: string) {
  const metadata = await sqlite.get(
    `SELECT * FROM session_metadata WHERE session_id = ?`,
    [sessionId]
  );
  
  if (!metadata) throw new Error(`No saved state for ${sessionId}`);
  
  // nclaude wake approach
  await exec(`nclaude wake ${sessionId} tmux`);
  
  // Or direct resume
  await exec(`
    cd ${metadata.project_dir} &&
    claude --resume ${sessionId} -p "${message}"
  `);
}
```

## Message Protocol

### Clawdbot → nclaude

```sql
-- Direct message to specific session
INSERT INTO messages (room, session_id, msg_type, content, timestamp, recipient)
VALUES ('nclaude', 'clawdbot-gateway', 'TASK', 'Please review src/api.py', datetime('now'), 'nclaude-main');

-- Broadcast to all nclaude sessions
INSERT INTO messages (room, session_id, msg_type, content, timestamp, recipient)
VALUES ('nclaude', 'clawdbot-gateway', 'BROADCAST', 'All sessions: standup in 5', datetime('now'), '*');
```

### nclaude → Clawdbot

nclaude sessions should use:
```bash
nclaude send "message" --to @clawdbot-gateway
# or for cross-machine
nclaude send "message" --to @clawdbot --gchat
```

### Message Tags (for Google Chat)

```
[NCLAUDE:cc-abc123:TASK:@clawdbot] Review PR #42
[CLAWDBOT:main:REPLY:@cc-abc123] PR looks good, merging
[NCLAUDE:cc-xyz789:STATUS:*] Completed auth module
```

## Open Questions

1. **Session ID Discovery:** How does Clawdbot know which session IDs exist? 
   - Answer: Query `session_metadata` table or listen for session announcements

2. **Push vs Poll:** nclaude can't push-notify Clawdbot
   - Answer: Clawdbot polls DB on interval (e.g., 5s) or uses inotify/fswatch

3. **Session Cleanup:** When to garbage-collect old session metadata?
   - Answer: Timestamp-based cleanup (>7 days idle) or explicit cleanup command

4. **Authentication:** How to ensure only authorized Clawdbot instances write to the DB?
   - Answer: Trust local file permissions; for Google Chat, use message signing

## Implementation Roadmap

### Phase 1: Basic Integration
- [ ] Clawdbot can read/write to `~/.nclaude/messages.db`
- [ ] Clawdbot can spawn Claude Code sessions with `NCLAUDE_ID` set
- [ ] Basic message routing: Clawdbot ↔ nclaude sessions

### Phase 2: Google Chat Backbone
- [ ] Clawdbot monitors Google Chat for `[NCLAUDE:*]` messages
- [ ] Clawdbot can send `[CLAWDBOT:*]` tagged messages
- [ ] Cross-machine coordination working

### Phase 3: Session Management
- [ ] Clawdbot can resume sessions via `claude --resume`
- [ ] Session metadata synced across machines via Google Chat
- [ ] Automatic session cleanup

### Phase 4: Advanced Features
- [ ] Clawdbot can "wake" idle sessions programmatically
- [ ] Task distribution (like swarm but orchestrated by Clawdbot)
- [ ] Session handoff between Clawdbot agents and Claude Code

## Code Examples

### Clawdbot Subagent Messaging nclaude

```sql
-- This is how this document was created:
-- Clawdbot spawned a subagent that messaged nclaude-main directly

INSERT INTO messages (room, session_id, msg_type, content, timestamp, recipient) 
VALUES (
  'nclaude', 
  'clawdbot-subagent', 
  'MSG', 
  'Hey nclaude-main! I am a Clawdbot subagent exploring integration...',
  datetime('now'), 
  'nclaude-main'
);
```

### Reading Messages for Clawdbot

```sql
-- Get unread messages for Clawdbot
SELECT * FROM messages 
WHERE recipient LIKE '%clawdbot%' 
   OR recipient = '*'
ORDER BY id DESC 
LIMIT 20;
```

## References

- nclaude README: `/Users/hans/development/vipernauts/nclaude/README.md`
- nclaude CLAUDE.md: `/Users/hans/development/vipernauts/nclaude/CLAUDE.md`  
- Google Chat transport: `/Users/hans/development/vipernauts/nclaude/src/nclaude/transports/gchat.py`
- Session resume: `/Users/hans/development/vipernauts/nclaude/src/nclaude/commands/resume.py`
- Swarm script: `/Users/hans/development/vipernauts/nclaude/scripts/swarm.py`
