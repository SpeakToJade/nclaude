# Claude-to-Claude Protocol

Coordination protocols for multi-Claude workflows.

## SYN-ACK Handshake

Before parallel work, Claudes must agree on task division:

```
Claude-A                          Claude-B
   |                                  |
   |---[SYN] I'll do X, you do Y----->|
   |                                  |
   |<--[ACK] Confirmed----------------|
   |                                  |
   |   (both proceed in parallel)     |
```

### Example

```bash
# Claude A proposes
/send "SYN: I'll do auth module, you do tests. ACK?" --type TASK

# Claude B confirms
/send "ACK: Confirmed, starting tests" --type REPLY

# Or rejects with counter-proposal
/send "NACK: Counter-proposal - I do both auth and tests, you do docs" --type REPLY
```

### Rules

1. **SYN requires ACK** before proceeding
2. After SYN, tell user: "Waiting for ACK from peer"
3. **NACK restarts negotiation** - propose alternative
4. Don't spin-loop checking - wait for user to trigger `/check`

---

## File Claiming

Prevent edit conflicts by claiming files before modification:

```
Claude-A                          Claude-B
   |                                  |
   |---[CLAIMING: src/auth.py]------->|
   |                                  |
   |   (Claude-B sees claim, waits)   |
   |                                  |
   |   (Claude-A edits file)          |
   |                                  |
   |---[RELEASED: src/auth.py]------->|
   |                                  |
   |   (Claude-B can now edit)        |
```

### Example

```bash
# Before editing
/send "CLAIMING: src/auth.py" --type URGENT

# ... do your work ...

# After done
/send "RELEASED: src/auth.py" --type STATUS
```

### Rules

1. **One file = one owner** at a time
2. If you see a CLAIM, **wait or negotiate**
3. **Always RELEASE** when done
4. Use `URGENT` type for claims (high priority)

---

## Message Types

| Type | Use For | Priority |
|------|---------|----------|
| `MSG` | General chat | Normal |
| `TASK` | Work assignments, SYN | Normal |
| `REPLY` | Responses, ACK/NACK | Normal |
| `STATUS` | Progress, RELEASE | Normal |
| `URGENT` | CLAIM, conflicts | High |
| `ERROR` | Problems, failures | High |
| `BROADCAST` | Human announcements | High |

---

## Broadcast Protocol (Human → Claudes)

Humans can broadcast to multiple Claude sessions:

```
Human                         Claude Sessions
  |                                |
  |--[BROADCAST @targets msg]----->| (hook triggers)
  |                                |
  |<--[ACK from each]--------------|
  |                                |
  |<--[Work/Response]--------------|
```

### Example

```bash
# Human broadcasts to all peers
nclaude broadcast "standup in 5 min" --all-peers

# Human broadcasts to specific sessions
nclaude broadcast "@main @feat-xyz review PR #42"

# True broadcast (all sessions see it)
nclaude broadcast "@all emergency: server down"
```

### Claude Response Pattern

When a Claude receives a BROADCAST:

```bash
# Check messages (auto via hook or manual)
/check --for-me

# Acknowledge receipt
/send "ACK: Received broadcast, starting review" --type REPLY

# Complete and report
/send "Done: PR #42 reviewed, 3 comments added" --type STATUS
```

---

## Swarm Coordination

When multiple Claudes work on the same task:

### Division Pattern

```bash
# Human spawns swarm
swarm swarm 4 "Review all Python files"

# Swarm leader divides work
/send "SYN: Division - Claude1: scripts/, Claude2: src/, Claude3: tests/, Claude4: docs/. ACK?" --type TASK

# Each member ACKs
/send "ACK: Taking scripts/" --type REPLY
```

### Progress Updates

```bash
# Regular status updates
/send "STATUS: 3/10 files reviewed in scripts/" --type STATUS

# Completion
/send "DONE: scripts/ review complete, 5 issues found" --type STATUS
```

### Conflict Resolution

```bash
# If two Claudes claim same file
/send "CONFLICT: Both claimed src/api.py. I'll defer." --type URGENT

# Or negotiate
/send "NACK: I'm already 50% done with src/api.py, please take src/routes.py instead" --type REPLY
```

---

## Best Practices

### DO

- Use SYN-ACK before parallel work
- Claim files before editing
- Release files when done
- Send regular status updates
- ACK broadcasts from humans

### DON'T

- Spin-loop checking for messages (wastes tokens)
- Edit files without claiming
- Ignore NACK - always negotiate
- Leave files claimed indefinitely
- Start work without ACK on division
