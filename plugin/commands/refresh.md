---
description: Restore identity and show current state after /compact or resume (wraps aqua refresh)
---

Run this at the START of every session to restore your agent identity:

```
aqua refresh
```

This command:
1. Restores your agent ID from environment
2. Updates heartbeat to show you're active
3. Shows your current task and unread messages

If aqua is not initialized in this project, the command will fail. Use `/nclaude:status` to check if aqua is available.

Report:
- Agent name and ID
- Current task (if any)
- Unread message count
- Leader status
