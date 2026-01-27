---
description: Release a file lock (wraps aqua unlock)
---

Release a file lock after editing. Execute:

```
aqua unlock $ARGUMENTS
```

Usage:
- `/nclaude:unlock src/api.py`

You can only unlock files YOU locked. Attempting to unlock another agent's file will fail.

If you need to force-unlock a dead agent's file, use `aqua unlock --force <file>` (requires being the leader or the file's owner).

IMPORTANT: Always unlock files when done to avoid blocking other agents.

Report the unlock confirmation.
