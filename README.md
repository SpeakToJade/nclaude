# nclaude 🐍⚡

Headless Claude-to-Claude chat via files. No sockets, no pipes, no bullshit.

## Origin Story

Tried to sync two machines running Claude Code sessions. Netcat didn't cut it (limitations or skill issue, who knows). So we built this 1337 prototype using file-based messaging with `flock` for atomic writes.

## Install

```bash
# Clone
git clone https://github.com/gyrusdentatus/nclaude.git
cd nclaude

# That's it. No dependencies. Pure Python stdlib.
```

## Usage

```bash
# Session A
python3 scripts/nclaude.py send "claude-a" "Starting work on X"
python3 scripts/nclaude.py send "claude-a" "Auth module done" --type STATUS

# Session B
python3 scripts/nclaude.py read "claude-b"
python3 scripts/nclaude.py send "claude-b" "Got it, working on Y" --type REPLY

# Human monitoring
tail -f /tmp/nclaude/*/messages.log
```

### Message Types
`--type MSG|TASK|REPLY|STATUS|ERROR|URGENT` (default: MSG)

Multi-line messages auto-detected and wrapped with delimiters.

## Claude Code Plugin

Install as plugin for slash commands:
```bash
claude plugin install ./nclaude --scope project
```

### Slash Commands
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

## How It Works

1. Messages append to `/tmp/nclaude/<repo>/messages.log` (atomic via flock)
2. Each session tracks last-read line number
3. Git-aware: same repo = same message log, including worktrees

## Hub Mode (v1.0.0) - Real-Time Messaging

Unix socket server for instant @mention routing. No more polling.

### Architecture
```
         ┌─────────┐
         │   HUB   │ ← Unix socket server
         └────┬────┘
    ┌─────────┼─────────┐
    ▼         ▼         ▼
claude-a  claude-b  claude-c
```

### Quick Start

```bash
# Terminal 1 - Start hub (human)
python3 scripts/hub.py start &

# Terminal 2 - Claude A
python3 scripts/client.py connect claude-a
python3 scripts/client.py send "@claude-b do the auth module"

# Terminal 3 - Claude B
python3 scripts/client.py connect claude-b
python3 scripts/client.py recv --timeout 5  # Gets: "do the auth module"
```

### Slash Commands (Hub Mode)
| Command | Description |
|---------|-------------|
| `/nclaude:hub start` | Start the hub server |
| `/nclaude:hub stop` | Stop the hub server |
| `/nclaude:hub status` | Check if hub is running |
| `/nclaude:connect` | Connect this session to hub |
| `/nclaude:hsend @user msg` | Send via hub with @mention routing |
| `/nclaude:hrecv` | Receive next message from hub |

### @Mention Routing

```bash
# Route to specific session(s)
python3 scripts/client.py send "@claude-a do X"
python3 scripts/client.py send "@claude-a @claude-b both review PR"

# Broadcast to all (no @mention)
python3 scripts/client.py send "everyone check logs"
```

### Message Format

Messages are JSON with auto-generated IDs:
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

### Hub vs File Mode

| Feature | File Mode | Hub Mode |
|---------|-----------|----------|
| Latency | ~seconds (polling) | Instant |
| @mentions | Manual parsing | Auto-routed |
| Offline | Always works | Requires hub |
| Setup | Zero | Start hub first |

**Fallback**: File mode still works as backup. Hub mode is opt-in.

## Limitations

**No push notifications** - Claude sessions cannot wake from idle. Messages queue until:
- User types "check logs" or runs `/nclaude:check`
- User interrupts with any input
- See [Issue #2](https://github.com/gyrusdentatus/nclaude/issues/2) for future push support

**Polling burns tokens** - Don't spin-loop checking messages. Use SYN-ACK protocol and sleep.

**No real-time** - This is async message passing, not chat. Expect latency.

## Real-World Usage

Two Claudes built nclaude together using nclaude:

```bash
# claude-a proposes work division
python3 scripts/nclaude.py send "SYN: v0.4.0 - I do message IDs, you do receipts" --type TASK

# claude-a sleeps, user switches to claude-b terminal
# user: "check logs"

# claude-b sees proposal, responds
python3 scripts/nclaude.py send "ACK: v0.4.0 - confirmed, creating receipts.py" --type REPLY

# claude-b works on receipts.py while claude-a waits
# user switches back to claude-a: "check logs"

# claude-a sees ACK, proceeds with message IDs
```

Key patterns:
- **SYN-ACK** for coordination before parallel work
- **CLAIMING/RELEASED** for file ownership in swarms
- **User as router** - switches between sessions to relay "check logs"

## YOLO Mode: Swarm Testing

Run multiple Claude Code sessions as a coordinated swarm. No permission prompts, pure autonomous chaos.

### Setup (2-5 Claudes)
```bash
# Terminal 1 - Human monitoring
tail -f /tmp/nclaude/*/messages.log

# Terminal 2-N - Spawn Claude swarm
for i in {1..5}; do
  NCLAUDE_ID="swarm-$i" claude --dangerously-skip-permissions \
    -p "You are swarm agent $i. Check /nclaude:read first. Coordinate with other agents via /nclaude:send. Task: <YOUR_TASK>" &
done
```

### Swarm Protocols
```bash
# Announce yourself
python3 scripts/nclaude.py send "swarm-1" "ONLINE. Claiming: auth module" --type STATUS

# Claim work (prevent conflicts)
python3 scripts/nclaude.py send "swarm-1" "CLAIMING: src/auth/*.py - DO NOT TOUCH" --type URGENT

# Release work
python3 scripts/nclaude.py send "swarm-1" "RELEASED: src/auth/*.py - ready for review" --type STATUS

# Request help
python3 scripts/nclaude.py send "swarm-1" "NEED HELP: stuck on OAuth flow, any agent available?" --type TASK
```

### Scaling to 20+ Agents
```bash
# Use tmux/screen for terminal management
# Each agent gets unique NCLAUDE_ID
for i in {1..20}; do
  tmux new-window -t swarm -n "agent-$i" \
    "NCLAUDE_ID=swarm-$i claude --dangerously-skip-permissions -p 'Swarm agent $i...'"
done
```

### Coordination Rules for Swarm
1. **Check messages FIRST** - before any action
2. **Claim before touch** - announce file ownership
3. **One file = one owner** - no parallel edits
4. **Release when done** - let others know
5. **Use message types** - URGENT for conflicts, TASK for requests

## License

MIT
