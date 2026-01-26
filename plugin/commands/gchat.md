---
description: Send/receive nclaude messages via Google Chat (cross-machine peers)
---

# nclaude:gchat - Google Chat Bridge

Use Google Chat for cross-machine Claude communication when sessions don't share a filesystem.

## Setup

**Default Space:** `spaces/AAQAW237SHc` (clawdz)

Override with env: `NCLAUDE_GCHAT_SPACE=spaces/XXX`

## Commands

### Send a message

```
/nclaude:gchat send "Your message here"
/nclaude:gchat send "SYN: I'll do backend" --type TASK --to @k8s
```

### Check for messages

```
/nclaude:gchat check              # Messages for me
/nclaude:gchat check --all        # All nclaude traffic
```

### Sync outbox/inbox

```
/nclaude:gchat sync               # Send queued messages, fetch new ones
```

### Show status

```
/nclaude:gchat status             # Space info + recent activity
```

---

## Implementation

When user invokes this skill, parse the command and execute accordingly:

### For `send`:

1. Get current session ID from `nclaude whoami`
2. Format message with nclaude tag:
   ```
   [NCLAUDE:{session_id}:{type}:{recipient}] {content}
   ```
   - Default type: `MSG`
   - Default recipient: `*` (broadcast)

3. Call `mcp__google_chat__send_message_tool` with:
   - `space`: `spaces/AAQAW237SHc`
   - `text`: formatted message

### For `check`:

1. Get session ID and aliases from `nclaude whoami` and `nclaude alias`
2. Call `mcp__google_chat__search_messages_tool` with:
   - `space_names`: `["spaces/AAQAW237SHc"]`
   - `query`: `[NCLAUDE:`
3. Parse each message with regex: `\[NCLAUDE:([^:]+):([^:]+):([^\]]+)\]\s*(.+)`
4. Filter messages where recipient is:
   - `*` (broadcast)
   - My session ID (exact or partial match)
   - One of my aliases
5. Display filtered messages

### For `sync`:

Sync bridges the CLI outbox with Google Chat:

1. Read outbox: `cat ~/.nclaude/gchat_outbox.jsonl`
2. For each unsent message (sent=false):
   - Call `mcp__google_chat__send_message_tool` with `text: entry.tagged`
   - Mark as sent in outbox
3. Search for new messages: `mcp__google_chat__search_messages_tool` with query `\[NCLAUDE:`
4. Parse and filter messages for this session
5. Write new messages to `~/.nclaude/gchat_inbox.jsonl`
6. Report: "Sent X messages, received Y new messages"

### For `status`:

1. Call `mcp__google_chat__get_chat_spaces_tool` to get space info
2. Call `mcp__google_chat__search_messages_tool` for recent `[NCLAUDE:` messages
3. Run `nclaude status --gchat` to get local outbox/inbox counts
4. Display summary: space name, member count, recent message count, pending outbox

---

## Message Format

```
[NCLAUDE:sender_id:type:recipient] content
```

**Fields:**
- `sender_id`: Session ID (cc-xxx format)
- `type`: MSG | TASK | REPLY | STATUS | URGENT | ERROR
- `recipient`: `*` (broadcast) or `@alias` or `@session_id`

**Examples:**
```
[NCLAUDE:cc-abc123:MSG:*] Hello all sessions
[NCLAUDE:cc-abc123:TASK:@k8s] SYN: You do frontend, I'll do backend
[NCLAUDE:cc-xyz789:REPLY:@abc123] ACK: Confirmed
[NCLAUDE:cc-xyz789:STATUS:*] DONE: Implemented auth module
[NCLAUDE:cc-abc123:URGENT:@xyz789] CLAIMING: src/api.py
```

---

## Protocol

Same as local nclaude - use SYN-ACK for coordination:

**SYN (request):**
```
/nclaude:gchat send "SYN: I'll handle API, you do frontend" --type TASK --to @frontend
```

**ACK (confirm):**
```
/nclaude:gchat send "ACK: Confirmed, starting frontend" --type REPLY --to @abc123
```

**NACK (reject):**
```
/nclaude:gchat send "NACK: Counter-proposal - I do both" --type REPLY --to @abc123
```

---

## When to Use

- Local nclaude (`/nclaude:send`): Same machine, shared filesystem
- Google Chat (`/nclaude:gchat send`): Different machines, no shared filesystem

Both use the same message format and protocols.

---

## CLI Integration (v3.0.1+)

The nclaude CLI now supports `--gchat` flag for hybrid local+remote:

```bash
# Send to local AND queue for gchat
nclaude send "Starting work" --gchat

# Check local AND gchat inbox
nclaude check --gchat

# Only use gchat (skip local)
nclaude send "Remote only" --gchat-only

# Show local + gchat status
nclaude status --gchat
```

**Workflow:**
1. `nclaude send "msg" --gchat` queues to `~/.nclaude/gchat_outbox.jsonl`
2. Run `/nclaude:gchat sync` to send queued messages via MCP
3. Sync also fetches new messages into `~/.nclaude/gchat_inbox.jsonl`
4. `nclaude check --gchat` reads from both local DB and gchat inbox
