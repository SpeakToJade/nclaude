# Swarm Daemon

Spawn and manage multiple Claude sessions for parallel work.

## Quick Start

```bash
# Spawn 4 Claudes to divide a task
swarm swarm 4 "Review all Python files in scripts/"

# Watch their work
swarm logs

# Ask a quick question
swarm ask test "How to check file inode in bash?"
```

---

## Commands

| Command | Description |
|---------|-------------|
| `swarm spawn <name> <prompt>` | Spawn single Claude session |
| `swarm resume <name> <prompt>` | Resume existing session |
| `swarm ask <name> <question>` | Ask and show answer |
| `swarm swarm <n> <task>` | Spawn N Claudes for task |
| `swarm list` | Show registered sessions |
| `swarm logs` | Watch logs with colors |
| `swarm watch` | Auto-resume on new messages |

---

## Usage Patterns

### Divide and Conquer

```bash
# Spawn a swarm for code review
swarm swarm 4 "Review all Python files. Divide by directory."

# Claudes will negotiate via SYN-ACK:
# "SYN: I'll take scripts/, you take src/, etc. ACK?"
```

### Parallel Research

```bash
# Each Claude researches a different aspect
swarm spawn research-security "Research OAuth2 security best practices"
swarm spawn research-performance "Research caching strategies for APIs"
swarm spawn research-testing "Research integration testing patterns"
```

### Ask and Answer

```bash
# Quick question to a specific session
swarm ask research-security "What's the recommended token expiry time?"

# Answer appears directly in terminal
```

---

## Watching Logs

```bash
# Colored log output
swarm logs

# Or use tail directly
tail -f /tmp/nclaude/*/messages.log
```

Log format:
```
[2026-01-20T19:28:09] [nclaude-main] [TASK] Review src/auth.py
[2026-01-20T19:28:15] [nclaude-feat] [REPLY] ACK: Starting review
```

---

## Session Management

### List Active Sessions

```bash
swarm list
```

Output:
```json
{
  "sessions": [
    {"name": "swarm-1", "pid": 12345, "status": "running"},
    {"name": "swarm-2", "pid": 12346, "status": "running"}
  ]
}
```

### Resume a Session

```bash
swarm resume swarm-1 "Continue reviewing, focus on error handling"
```

---

## Auto-Watch Mode

Start a watcher that resumes sessions on new messages:

```bash
swarm watch
```

This monitors the message log and automatically resumes idle sessions when they receive new messages.

---

## Presets (with nclaude-tmux)

```bash
# GCP/GKE infrastructure
nclaude-tmux -c gcp-k8s

# Code review (author vs reviewer)
nclaude-tmux -c review

# TDD pair (implement vs test)
nclaude-tmux -c test
```

### Preset Details

| Preset | Claude A | Claude B |
|--------|----------|----------|
| `gcp-k8s` | Terragrunt, GKE, IAM, networking | DNS, certs, ingress, monitoring |
| `review` | Code author/defender | Code reviewer/critic |
| `test` | Implement features | Write tests |

All presets include SYN-ACK coordination and file claiming protocols.

---

## Tips

1. **Start small** - 2-3 Claudes is usually enough
2. **Clear task division** - Let Claudes negotiate via SYN-ACK
3. **Monitor with logs** - Watch for conflicts and progress
4. **Use message types** - TASK for assignments, STATUS for updates
