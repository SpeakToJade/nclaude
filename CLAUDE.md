# NCLAUDE - Claude-to-Claude Chat (v3.1.0)

Headless message passing between Claude Code sessions, now with **Aqua** backend for multi-agent coordination.

## New in v3.1.0

- **Aqua integration** - Uses [aqua-coord](https://github.com/vignesh07/aqua) as messaging/coordination backend
- **Atomic file locking** - `/nclaude:lock` replaces CLAIMING/RELEASED protocol
- **Blocking ask/reply** - `/nclaude:ask` waits for answer, `/nclaude:reply` responds to message ID
- **Task queue** - `/nclaude:task` for add/claim/done/fail operations
- **Progress reporting** - `/nclaude:progress` for heartbeat + breadcrumbs
- **Session refresh** - `/nclaude:refresh` restores identity after /compact

## New in v3.0.0

- **Stop hook enhancements** - Detects stuck patterns, suggests topic-specific peers
- **Rules system** - Configure peer suggestions via `~/.claude/nclaude-rules.yaml`
- **Session resume** - `nclaude wake @peer` to wake idle sessions
- **PreCompact hook** - Saves session state before context compaction
- **SubagentStop hook** - Announces when subagents complete

## IMPORTANT: Check Messages First!

At the START of each response, check for messages:
```bash
nclaude check  # Or just /nclaude:check
```

**Don't wait for the user to remind you!**

---

## Quick Commands

### Messaging (nclaude native)

| Slash Command | CLI Equivalent | What it does |
|---------------|----------------|--------------|
| `/nclaude:send <msg>` | `nclaude send "msg"` | Send message |
| `/nclaude:check` | `nclaude check` | Read all messages (pending + new) |
| `/nclaude:read` | `nclaude read` | Read new messages only |
| `/nclaude:wait [timeout]` | `nclaude wait 30` | Block until message arrives |
| `/nclaude:status` | `nclaude status` | Show chat + aqua status |
| `/nclaude:watch` | `nclaude watch` | Live message feed |
| `/nclaude:pair <project>` | `nclaude pair <project>` | Register peer |
| `/nclaude:alias [name]` | `nclaude alias myname` | Create alias for current session |
| `/nclaude:whoami` | `nclaude whoami` | Show current session ID |
| `/nclaude:wake @peer` | `nclaude wake @peer` | Wake idle peer session |
| `/nclaude:gchat send` | - | Send to Google Chat (remote peers) |
| `/nclaude:gchat check` | - | Check Google Chat for messages |

### Coordination (aqua backend)

| Slash Command | CLI Equivalent | What it does |
|---------------|----------------|--------------|
| `/nclaude:refresh` | `aqua refresh` | Restore identity after /compact |
| `/nclaude:progress <msg>` | `aqua progress "msg"` | Report progress + heartbeat |
| `/nclaude:ask <q> --to @peer` | `aqua ask "q" --to peer` | Blocking question, wait for reply |
| `/nclaude:reply <id> <msg>` | `aqua reply <id> "msg"` | Reply to specific message |
| `/nclaude:lock <file>` | `aqua lock <file>` | Atomic file lock |
| `/nclaude:unlock <file>` | `aqua unlock <file>` | Release file lock |
| `/nclaude:locks` | `aqua locks` | Show all current locks |
| `/nclaude:task <cmd>` | `aqua <cmd>` | Task queue (add/claim/done/fail) |

---

## CLI Reference

```bash
# Core commands
nclaude send "message"              # Send to current project room
nclaude send "msg" --type TASK      # Send with type
nclaude send "msg" --to @alice      # Send to specific recipient
nclaude check                       # Get all unread messages
nclaude wait 30                     # Block until message arrives (30s timeout)
nclaude read                        # Read new messages
nclaude read --limit 10             # Limit to 10 messages
nclaude read --filter TASK          # Only TASK messages
nclaude status                      # Show room status
nclaude watch --history 20          # Live feed with last 20 msgs

# Cross-project
nclaude send "msg" --dir other-project
nclaude pair other-project          # Register peer
nclaude peers                       # List peers

# Aliases
nclaude alias                       # List all aliases
nclaude alias k8s                   # Create alias @k8s for current session
nclaude alias k8s cc-abc123         # Create alias @k8s -> cc-abc123

# Info
nclaude whoami                      # Show session ID
nclaude --version                   # Show version (3.0.1)

# Session management (v3.0)
nclaude wake @peer                  # Wake idle peer session
nclaude wake @k8s tmux              # Wake in new tmux window
nclaude wake @k8s info              # Show session info only
nclaude sessions                    # List saved session states
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
2. After SYN, use `nclaude wait 30` to block until reply arrives
3. NACK restarts negotiation
4. Don't spin-loop checking - use `wait` command instead

---

## File Locking (v3.1+)

Use atomic file locks instead of the old CLAIMING protocol:

```bash
/nclaude:lock src/auth.py      # Acquire lock
# ... do your work ...
/nclaude:unlock src/auth.py    # Release lock
```

**Benefits over CLAIMING:**
- Atomic (SQLite-backed, no race conditions)
- Auto-recovery (locks expire if agent dies)
- Queryable (`/nclaude:locks` shows all locks)

### Legacy Protocol: File Claiming (deprecated)

The old message-based claiming still works but lacks atomicity:

```bash
nclaude send "CLAIMING: src/auth.py" --type URGENT
nclaude send "RELEASED: src/auth.py" --type STATUS
```

Use `/nclaude:lock` instead for new workflows.

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

## Aqua Workflow (v3.1+)

When working with multiple agents, follow this pattern:

```
1. /nclaude:refresh        # Restore identity, see state
2. /nclaude:task claim     # Get a task from queue
3. /nclaude:lock <file>    # Lock files before editing
4. /nclaude:progress "msg" # Report progress frequently
5. /nclaude:unlock <file>  # Release locks when done
6. /nclaude:task done      # Complete the task
7. Repeat from step 2
```

**Key commands:**
- `aqua status` - See all agents, tasks, and locks
- `aqua ps` - Quick view of active agents
- `aqua logs` - Tail the event stream

---

## How It Works

```
┌───────────────────────────────────────────────────────────┐
│                    Claude Code Session                     │
│  ┌─────────────────────────────────────────────────────┐  │
│  │              nclaude plugin (interface)              │  │
│  │  • Hooks (UserPromptSubmit, Stop, SessionStart)     │  │
│  │  • Skills (/nclaude:send, /nclaude:lock, etc.)      │  │
│  │  • Google Chat bridge (cross-machine)               │  │
│  │  • Aliases (@k8s, @frontend)                        │  │
│  └─────────────────────┬───────────────────────────────┘  │
└────────────────────────┼──────────────────────────────────┘
                         │ calls
                         ▼
┌───────────────────────────────────────────────────────────┐
│                   Aqua backend (CLI)                       │
│  • Messaging (threading, read receipts, ask/reply)        │
│  • Task queue (priority, dependencies, atomic claiming)   │
│  • File locking (atomic, auto-recovery)                   │
│  • Crash recovery (5-min heartbeat)                       │
│  • Leader election                                        │
└───────────────────────────────────────────────────────────┘
```

**Storage:**
- nclaude: `~/.nclaude/messages.db` (global, cross-project)
- Aqua: `.aqua/aqua.db` (per-project coordination)

- Git-aware: same repo = same room (including worktrees)
- @mention routing with recipient field
- UserPromptSubmit hook injects message count on every prompt

---

## Peer Suggestion Rules (v3.0)

Configure peer suggestions via `~/.claude/nclaude-rules.yaml`:

```yaml
rules:
  - name: k8s-topic
    enabled: true
    event: stop
    match:
      field: transcript
      pattern: "kubectl|kubernetes|helm"
    peer: "@k8s"
    message: "@k8s specializes in Kubernetes."
```

Copy the template from `plugin/config/nclaude-rules.yaml`.

Built-in suggestions (no config needed):
- **Stuck detection** - Repeated errors suggest asking a peer
- **Topic routing** - k8s, docker, security, database, frontend, infra

---

## Future Work

### Container-Use Security (aqua)

Reference: https://container-use.com/

When running agents in background/autonomous mode with `--dangerously-skip-permissions`:
- Wrap bash commands in container-use sandboxes
- Config in `.aqua/config.yml`:
  ```yaml
  security:
    container_use:
      enabled: true
      image: "python:3.11-slim"
      network: "none"
  ```
- Add `aqua spawn --container` flag

**Status:** Deferred - requires container-use to mature

---

## Development

### Plugin Symlink (for instant updates)

The installed plugin at `~/.claude/plugins/cache/dial0ut/nclaude/3.1.0` is symlinked to the dev directory:

```bash
~/.claude/plugins/cache/dial0ut/nclaude/3.1.0 -> /Users/hans/development/vipernauts/nclaude/plugin
```

This means changes to `plugin/` are instantly available without reinstalling. To recreate:

```bash
rm -rf ~/.claude/plugins/cache/dial0ut/nclaude/3.1.0
ln -s /Users/hans/development/vipernauts/nclaude/plugin ~/.claude/plugins/cache/dial0ut/nclaude/3.1.0
```

### Marketplace

The `dial0ut` marketplace is configured as a local directory source:
- Source: `/Users/hans/development/vipernauts/nclaude`
- To reinstall (copies files): `/plugin install nclaude@dial0ut`

---

## Limitations

- **No push**: Claude can't wake from idle - use `wait` command or UserPromptSubmit hook
- **Async only**: Message passing, not real-time chat
- **Tokens**: Don't poll in loops - use `wait` command with timeout
