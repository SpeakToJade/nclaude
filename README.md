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

# Session B
python3 scripts/nclaude.py read "claude-b"
python3 scripts/nclaude.py send "claude-b" "Got it, working on Y"

# Human monitoring
tail -f /tmp/nclaude/*/messages.log
```

## Claude Code Plugin

Install as plugin for slash commands:
```bash
claude plugin install ./nclaude --scope project
```

Then use `/nclaude:send`, `/nclaude:read`, etc.

## How It Works

1. Messages append to `/tmp/nclaude/<repo>/messages.log` (atomic via flock)
2. Each session tracks last-read line number
3. Git-aware: same repo = same message log, including worktrees

## License

MIT
