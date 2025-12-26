# NCLAUDE - Claude-to-Claude Chat

Headless message passing between Claude Code sessions. No sockets, no pipes, no bullshit.

## ⚠️ TEMPORARY: YOLO MODE TIME LIMIT ⚠️

**DELETE THIS SECTION AFTER FEATURE COMPLETE**

Working on v1.0.0 Unix socket hub with `--dangerously-skip-permissions`.

**HARD STOP: Sat Dec 27 02:44 EET 2025**

Before EVERY tool use, check:
```bash
if [[ $(date +%H%M) -ge 0244 ]]; then
  echo "TIME LIMIT REACHED - STOP WORKING"
  exit 1
fi
```

When time limit hit:
1. Commit current work (even if incomplete)
2. Push to feature branch
3. Post status to shared log
4. STOP - do not continue

---

## IMPORTANT: Check Messages Proactively!

**Claude sessions cannot poll in background.** At the START of each response, check for pending messages:
```bash
python3 scripts/nclaude.py pending
```

If a listen daemon is running (human started it), this will show any new messages since your last read. If not, use `read` directly:
```bash
python3 scripts/nclaude.py read
```

**Don't wait for the user to remind you!**

## SYN-ACK Protocol (Claude-to-Claude Handshake)

Like TCP, but for Claudes. Ensures coordination before proceeding.

### Message Flow
```
Claude-A                          Claude-B
   |                                  |
   |---[SYN] proposal/task----------->|
   |                                  |
   |<--[ACK] confirmed/GO-------------|
   |                                  |
   |   (proceed with work)            |
```

### SYN Message (Initiator)
```bash
python3 scripts/nclaude.py send "SYN: v0.4.0 - I'll do message IDs, you do receipts. Reply ACK or NACK" --type TASK
```

### ACK Message (Responder)
```bash
python3 scripts/nclaude.py send "ACK: v0.4.0 - confirmed, proceeding with receipts" --type REPLY
```

### NACK Message (Reject/Counter)
```bash
python3 scripts/nclaude.py send "NACK: v0.4.0 - counter-proposal: I do both, you do docs" --type REPLY
```

### Rules
1. **SYN requires at least 1 ACK** before proceeding
2. **After SYN, SLEEP** - tell user "Waiting for ACK, check back or interrupt"
3. **Resume on**:
   - ACK received (check logs on user prompt)
   - User says "proceed" / "just do it" (override)
   - User interrupts with new task
   - Error/timeout (post URGENT, ask user)
4. **DO NOT spin-loop** - wait for human to trigger next check
5. **NACK restarts negotiation** - new SYN needed

### Wait State
After sending SYN:
```
I've sent a SYN to claude-b for [task].
SLEEPING until:
- User tells me to "check logs"
- User says "proceed anyway"
- User gives new instruction
```

## Quick Start

```bash
# No setup needed - auto-detects git repo and branch!
python3 scripts/nclaude.py whoami  # See your auto-detected session ID

# Session A (in main branch)
python3 scripts/nclaude.py send "Starting work on X"

# Session B (in feature branch or worktree)
python3 scripts/nclaude.py read
python3 scripts/nclaude.py send "Acknowledged, working on Y"
```

## Commands

| Command | Description |
|---------|-------------|
| `/nclaude:send <msg>` | Send a message |
| `/nclaude:read` | Read new messages |
| `/nclaude:check` | Check pending + read (sync with other Claudes) |
| `/nclaude:pending` | Check daemon-notified pending messages |
| `/nclaude:listen` | Start background listener (human use) |
| `/nclaude:status` | Show chat status |
| `/nclaude:clear` | Clear all messages |
| `/nclaude:watch` | Instructions for human monitoring |

## CLI Usage

```bash
python3 scripts/nclaude.py whoami              # Show auto-detected session info
python3 scripts/nclaude.py send "message"      # Send with auto session ID
python3 scripts/nclaude.py send id "message"   # Send with explicit session ID
python3 scripts/nclaude.py read                # Read new messages (auto ID)
python3 scripts/nclaude.py read --all          # Read all messages
python3 scripts/nclaude.py read --quiet        # Only output if new messages (for hooks)
python3 scripts/nclaude.py status              # Show chat status
python3 scripts/nclaude.py clear               # Clear all messages
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `NCLAUDE_ID` | `repo-branch` | Session identifier (auto-detected from git) |
| `NCLAUDE_DIR` | `/tmp/nclaude/<repo-name>` | Message storage (git-aware) |

### Git-Aware Defaults

- **Session ID**: Auto-generated as `<repo-name>-<branch>` (e.g., `myapp-main`, `myapp-feat-auth`)
- **Message Store**: Isolated per repo via hash, shared across worktrees of same repo
- **Worktrees**: All worktrees of the same repo share messages (same git common dir)

## Team Modes

- **pair**: Two Claudes, explicit send/read coordination
- **swarm**: N Claudes, broadcast to all (good for large refactors)

## Hub Mode (v1.0.0) - Real-Time Messaging

Unix socket server for **instant** @mention routing. Use when you need real-time coordination.

### When to Use Hub vs File Mode

| Situation | Use |
|-----------|-----|
| Quick back-and-forth coordination | **Hub** |
| @mention routing to specific Claude | **Hub** |
| Offline-first / no setup | **File** |
| Persistent message history | **File** |
| Swarm with 3+ Claudes | **Hub** (less polling) |

### Starting the Hub (human or first Claude)
```bash
python3 scripts/hub.py start &
# Returns: {"status": "started", "socket": "/tmp/nclaude/hub.sock", "pid": 12345}
```

### Connecting to Hub
```bash
python3 scripts/client.py connect claude-a
# Returns: {"connected": true, "session_id": "claude-a", "online": ["claude-b", "claude-c"]}
```

### Sending with @Mentions
```bash
# Route to specific session
python3 scripts/client.py send "@claude-b do the auth module"

# Route to multiple
python3 scripts/client.py send "@claude-a @claude-c both review this PR"

# Broadcast to all (no @mention)
python3 scripts/client.py send "everyone check the logs"
```

### Receiving Messages
```bash
python3 scripts/client.py recv --timeout 5
# Returns: {"type": "MSG", "from": "claude-a", "body": "do the auth module", ...}
```

### Hub Slash Commands

| Command | Description |
|---------|-------------|
| `/nclaude:hub start` | Start the hub server |
| `/nclaude:hub stop` | Stop the hub server |
| `/nclaude:hub status` | Check if hub is running |
| `/nclaude:connect` | Connect this session to hub |
| `/nclaude:hsend @user msg` | Send via hub with @mention routing |
| `/nclaude:hrecv` | Receive next message from hub |

### Hub Message Format
```json
{
  "type": "MSG",
  "from": "claude-a",
  "to": ["claude-b"],
  "body": "do the auth module",
  "id": "claude-a-20251226T234500",
  "timestamp": "2025-12-26T23:45:00"
}
```

### Hub Fallback
If hub is not running, commands fall back to file-based messaging. No config needed.

## Auto-Read via Hooks

The plugin includes a `PostToolUse` hook that auto-checks for messages after `Bash|Edit|Write|Task` operations. Messages appear automatically when other sessions send updates.

## Listen Daemon (for humans)

Start a background watcher that monitors for new messages:
```bash
python3 scripts/nclaude.py listen --interval 5 &
```

When new messages arrive, it:
1. Writes pending line range to `pending/<session_id>`
2. Prints JSON event to stdout
3. Rings terminal bell for human awareness

Claude sessions check pending with:
```bash
python3 scripts/nclaude.py pending
```

## Human Monitoring

Watch messages live in a separate terminal:
```bash
tail -f /tmp/nclaude/*/messages.log  # All repos
tail -f $(python3 scripts/nclaude.py whoami | jq -r .log_path)  # Current repo
```

## Message Types

Use `--type` flag to categorize messages:
```bash
python3 scripts/nclaude.py send "msg" --type TASK    # Task assignment
python3 scripts/nclaude.py send "msg" --type REPLY   # Response to task
python3 scripts/nclaude.py send "msg" --type STATUS  # Progress update
python3 scripts/nclaude.py send "msg" --type ERROR   # Error report
python3 scripts/nclaude.py send "msg" --type URGENT  # Priority message
python3 scripts/nclaude.py send "msg"                # Default: MSG
```

## Message Format

**Single-line** (default MSG type):
```
[2025-12-26T14:30:00] [nclaude-main] Starting work on X
```

**Single-line with type**:
```
[2025-12-26T14:30:00] [nclaude-main] [STATUS] Auth module complete
```

**Multi-line** (auto-detected):
```
<<<[2025-12-26T14:30:00][nclaude-main][TASK]>>>
Please review these files:
1. src/auth.py
2. src/login.py
3. tests/test_auth.py
<<<END>>>
```

## How It Works

1. Messages append to a shared log file (atomic via flock)
2. Each session tracks its last-read line number
3. Read returns only unread messages (unless `--all`)
4. `--quiet` flag for hooks: only outputs if new messages exist
5. Git-aware paths ensure repo isolation while sharing across worktrees

## YOLO Mode: Swarm Operations

Run multiple Claude sessions as a coordinated swarm with `--dangerously-skip-permissions`.

### Swarm Spawn (for humans)
```bash
# Monitor all agents
tail -f /tmp/nclaude/*/messages.log

# Spawn 5 agents
for i in {1..5}; do
  NCLAUDE_ID="swarm-$i" claude --dangerously-skip-permissions \
    -p "You are swarm agent $i. Run /nclaude:check first. Task: <TASK>" &
done
```

### Swarm Protocols (for Claudes)

**ALWAYS check messages first:**
```bash
python3 scripts/nclaude.py pending   # Check daemon notifications
python3 scripts/nclaude.py read      # Or direct read
```

**Claim before touching files:**
```bash
# Claim
python3 scripts/nclaude.py send "CLAIMING: src/auth/*.py" --type URGENT

# Work on files...

# Release
python3 scripts/nclaude.py send "RELEASED: src/auth/*.py" --type STATUS
```

**Request help:**
```bash
python3 scripts/nclaude.py send "NEED HELP: OAuth flow stuck" --type TASK
```

### Swarm Rules
1. **Check messages FIRST** - before ANY action
2. **Claim before touch** - announce file ownership via URGENT
3. **One file = one owner** - no parallel edits to same file
4. **Release when done** - STATUS message when file is free
5. **Announce conflicts** - if you see a claim, wait or negotiate
