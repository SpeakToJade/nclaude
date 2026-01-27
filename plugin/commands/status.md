---
description: Show nclaude chat status, active sessions, and Aqua coordination info
---

Check both nclaude messaging and Aqua coordination status.

**nclaude messaging status:**
```
nclaude status
```

**Aqua coordination status (if initialized):**
```
aqua status
```

Report:
- nclaude: message count, session ID, log path
- Aqua (if available):
  - Leader and term
  - Active agents and their tasks
  - Task counts (pending/claimed/done/failed)
  - File locks
  - Recent activity

If Aqua is not initialized in this project, only show nclaude status.
