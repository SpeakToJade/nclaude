---
description: Ask a blocking question to another agent and wait for reply (wraps aqua ask)
---

Ask a question and wait for a reply. This is a BLOCKING call that polls until answered.

Parse arguments to extract question text, recipient, and optional timeout:

```
aqua ask "$ARGUMENTS"
```

Common patterns:
- `/nclaude:ask "Is this the right approach?" --to @leader`
- `/nclaude:ask "Should I merge?" --to worker-2 --timeout 120`
- `/nclaude:ask "Ready to integrate?" --to @all`

Options:
- `--to NAME` - Target agent (required). Use `@leader` for the current leader
- `--timeout N` - Wait N seconds (default: 60)
- `--poll N` - Check every N seconds (default: 5)

The command will:
1. Send the question as a message
2. Poll for a reply to that message
3. Return when answered or timeout

If the question times out, consider:
- The agent may be idle (try `/nclaude:wake @peer`)
- The agent may be busy with a task
- Increase timeout for complex questions

Report the answer when received, or indicate timeout.
