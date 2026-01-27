---
description: Lock a file for exclusive editing (wraps aqua lock)
---

Lock a file to prevent concurrent edits. Execute:

```
aqua lock $ARGUMENTS
```

Usage:
- `/nclaude:lock src/api.py`
- `/nclaude:lock config/settings.json`

This provides ATOMIC file locking via SQLite:
- Only one agent can hold a lock at a time
- Locks auto-expire if the agent dies (5 min heartbeat timeout)
- Other agents will see who holds the lock

If the file is already locked:
- The command will fail with the lock holder's name
- Wait for them to finish or coordinate via `/nclaude:ask`

ALWAYS unlock when done with `/nclaude:unlock <file>`.

This replaces the old CLAIMING/RELEASED protocol with atomic guarantees.

Report:
- Success: "Locked <file>"
- Failure: "<file> is locked by <agent>"
