---
description: Show all current file locks (wraps aqua locks)
---

Show all current file locks in the project. Execute:

```
aqua locks
```

This displays:
- Locked file path
- Agent holding the lock
- When the lock was acquired
- Lock age

Use this to:
- Check if a file is available before editing
- See what files other agents are working on
- Identify stale locks from dead agents

If you see a stale lock (agent heartbeat > 5 min old), the lock will auto-release when the agent is marked dead, or the leader can force-unlock it.

Report the locks table.
