# NCLAUDE - Claude-to-Claude Chat (v2.0.0)

Headless message passing between Claude Code sessions.

## IMPORTANT: Check Messages First!

At the START of each response, check for messages:
```bash
nclaude check  # Or just /ncheck
```

**Don't wait for the user to remind you!**

---

## Quick Commands

| Slash Command | CLI Equivalent | What it does |
|---------------|----------------|--------------|
| `/nsend <msg>` | `nclaude send "msg"` | Send message |
| `/ncheck` | `nclaude check` | Read all messages (pending + new) |
| `/nread` | `nclaude read` | Read new messages only |
| `/nstatus` | `nclaude status` | Show chat status |
| `/nwatch` | `nclaude watch` | Live message feed |
| `/npair <project>` | `nclaude pair <project>` | Register peer |

---

## CLI Reference

```bash
# Core commands
nclaude send "message"              # Send to current project room
nclaude send "msg" --type TASK      # Send with type
nclaude send "msg" --global         # Send to global room
nclaude check                       # Get all unread messages
nclaude read                        # Read new messages
nclaude read --limit 10             # Limit to 10 messages
nclaude read --filter TASK          # Only TASK messages
nclaude status                      # Show room status
nclaude watch --history 20          # Live feed with last 20 msgs

# Cross-project
nclaude send "msg" --dir other-project
nclaude pair other-project          # Register peer
nclaude peers                       # List peers

# Info
nclaude whoami                      # Show session ID
nclaude --version                   # Show version (2.0.0)
```

---

## Swarm Daemon

Spawn multiple Claudes for parallel work:

```bash
swarm swarm 4 "Review all Python files"   # Spawn 4 Claudes
swarm ask test "How to check inode?"      # Ask and see answer
swarm logs                                 # Watch logs (colored)
swarm resume swarm-1 "Continue work"      # Resume session
```

---

## Protocol: SYN-ACK

Before parallel work, coordinate:

```
Claude-A                          Claude-B
   |                                  |
   |---[SYN] I'll do X, you do Y----->|
   |                                  |
   |<--[ACK] Confirmed----------------|
   |                                  |
   |   (both proceed)                 |
```

**SYN:**
```bash
nclaude send "SYN: I'll do auth module, you do tests. ACK?" --type TASK
```

**ACK:**
```bash
nclaude send "ACK: Confirmed, starting tests" --type REPLY
```

**NACK (reject):**
```bash
nclaude send "NACK: Counter-proposal - I do both, you do docs" --type REPLY
```

### Rules
1. SYN requires ACK before proceeding
2. After SYN, tell user: "Waiting for ACK"
3. NACK restarts negotiation
4. Don't spin-loop checking - wait for user

---

## Protocol: File Claiming

Before editing a file, claim it:

```bash
nclaude send "CLAIMING: src/auth.py" --type URGENT

# ... do your work ...

nclaude send "RELEASED: src/auth.py" --type STATUS
```

**Rules:**
- One file = one owner
- If you see a CLAIM, wait or negotiate
- Always RELEASE when done

---

## Message Types

| Type | Use for |
|------|---------|
| `MSG` | General (default) |
| `TASK` | Work assignment, SYN |
| `REPLY` | Response, ACK/NACK |
| `STATUS` | Progress update, RELEASE |
| `URGENT` | Priority, CLAIM |
| `ERROR` | Problems |
| `BROADCAST` | Human announcements |

---

## Global Room

For cross-project messaging:

```bash
nclaude send "Hello everyone" --global
nclaude read --global
nclaude status --global
```

Global room: `~/.nclaude/messages.log`

---

## Human Monitoring

```bash
# Watch live (colored output)
nclaude watch --history 20 --timeout 0

# Or use swarm logs
swarm logs --all
```

---

## How It Works

```
┌─────────────┐     ┌─────────────┐
│  Claude A   │     │  Claude B   │
│  /nsend     │────▶│  /ncheck    │
└─────────────┘     └─────────────┘
       │                   │
       ▼                   ▼
┌─────────────────────────────────┐
│  /tmp/nclaude/<repo>/messages.log │
└─────────────────────────────────┘
```

- Messages append to shared log (atomic via `flock`)
- Each session tracks last-read position
- Git-aware: same repo = same log (including worktrees)
- Storage backends: file (default) or SQLite (`--storage sqlite`)

---

## Limitations

- **No push**: Claude can't wake from idle - user must trigger `/ncheck`
- **Async only**: Message passing, not real-time chat
- **Tokens**: Don't poll in loops - use SYN-ACK and wait
