# Multi-Claude Chat Architecture

## Reverse Engineering Findings

### CLI.js Location
```
~/.claude/local/node_modules/@anthropic-ai/claude-code/cli.js
```
- ~5000 lines minified but readable JavaScript
- NOT compiled like opcode's Rust wrapper

### Session Storage
```
~/.claude/projects/<project-path>/<session-id>.jsonl  # Conversation history
~/.claude/projects/<project-path>/<session-id>/tool-results/  # Tool outputs
~/.claude/session-env/<session-id>/  # Runtime environment
```

### Hook System (The Injection Point)
Unlike opcode's `stdin = Stdio::null()`, Claude Code has a rich hook system:

| Hook | Trigger | Injection Capability |
|------|---------|---------------------|
| `UserPromptSubmit` | User sends prompt | stdout -> Claude context |
| `PreToolUse` | Before tool executes | Can modify/block |
| `PostToolUse` | After tool completes | Can inject follow-up |
| `SessionStart` | Session begins | Initial context injection |
| `Stop` | Before response ends | Continue conversation |

**Key**: Exit code 0 from hook = stdout shown to Claude!

### How to Inject Messages

```bash
# .claude/settings.json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "command": "python3 /path/to/nclaude/scripts/nclaude.py pending"
      }
    ]
  }
}
```

When user sends any prompt:
1. Hook fires BEFORE prompt reaches Claude
2. nclaude checks for pending messages
3. Messages injected into Claude's context via stdout
4. Claude sees: original prompt + injected messages

## Multi-Claude Architecture

```
                    ┌─────────────────┐
                    │   HUMAN (hub)   │
                    │  tail -f + send │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │ claude-a │  │ claude-b │  │ claude-c │
        │  (hook)  │  │  (hook)  │  │  (hook)  │
        └────┬─────┘  └────┬─────┘  └────┬─────┘
             │              │              │
             └──────────────┼──────────────┘
                            │
                    ┌───────▼───────┐
                    │  messages.log │
                    │ (file-based)  │
                    └───────────────┘
                            OR
                    ┌───────▼───────┐
                    │   hub.sock    │
                    │ (socket-based)│
                    └───────────────┘
```

## Implementation Options

### Option 1: File-Based (Current nclaude)
- Hooks check `/tmp/nclaude/<repo>/messages.log`
- Atomic writes via `flock`
- Human polls with `tail -f`
- **Pro**: Simple, works offline
- **Con**: Polling latency

### Option 2: Hub-Based (hub.py)
- Central Unix socket server
- @mention routing
- Real-time delivery
- **Pro**: Instant messages
- **Con**: Requires hub running

### Option 3: Hybrid (Best)
```python
# UserPromptSubmit hook
def check_messages():
    # 1. Try hub first (real-time)
    hub_msgs = hub_client.recv(timeout=0.1)
    if hub_msgs:
        return hub_msgs

    # 2. Fallback to file (always works)
    return nclaude.pending()
```

## How to Launch Multiple Claudes

### Terminal Approach (Current)
```bash
# Terminal 1
NCLAUDE_ID="claude-a" claude

# Terminal 2
NCLAUDE_ID="claude-b" claude

# Terminal 3 (Human)
tail -f /tmp/nclaude/nclaude/messages.log
```

### Programmatic Approach (Like Opcode)
```javascript
// spawn_claudes.js
const { spawn } = require('child_process');

function spawnClaude(sessionId, prompt) {
    const claude = spawn('claude', ['-p', prompt], {
        env: { ...process.env, NCLAUDE_ID: sessionId },
        stdio: ['inherit', 'pipe', 'pipe']  // We CAN use stdin!
    });
    return claude;
}

// Launch swarm
const agents = ['claude-a', 'claude-b', 'claude-c'];
agents.forEach(id => spawnClaude(id, `You are ${id}. Run /nclaude:check first.`));
```

### GUI Approach (tmux/screen)
```bash
#!/bin/bash
# swarm.sh - Launch multi-Claude swarm

tmux new-session -d -s swarm

for i in {a..c}; do
    tmux new-window -t swarm -n "claude-$i" \
        "NCLAUDE_ID=claude-$i claude -p 'You are claude-$i. Check /nclaude:read first.'"
done

# Human monitoring window
tmux new-window -t swarm -n "monitor" "tail -f /tmp/nclaude/*/messages.log"

tmux attach -t swarm
```

## The Missing Piece: stdin Injection

Opcode uses `stdin = Stdio::null()` but WE DON'T HAVE TO!

When spawning Claude ourselves:
```javascript
const claude = spawn('claude', args, {
    stdin: 'pipe',  // We control stdin!
    stdout: 'pipe',
    stderr: 'pipe'
});

// Inject message mid-session
claude.stdin.write('check /nclaude:read\n');
```

This would allow:
1. Spawning multiple Claude sessions
2. Capturing their output
3. Injecting prompts (like "check messages")
4. Routing between sessions

## Next Steps

1. **Test stdin injection** - Can we write to claude's stdin after spawn?
2. **Build orchestrator** - Node.js app that spawns/manages multiple Claudes
3. **Create GUI** - Simple web UI showing all sessions + chat
4. **Integrate hub** - Real-time message routing

## Files

- `scripts/nclaude.py` - File-based messaging
- `scripts/hub.py` - Unix socket server
- `scripts/client.py` - Hub client
- `commands/*.md` - Slash commands for each function
