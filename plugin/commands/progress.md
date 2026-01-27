---
description: Report progress on current task (wraps aqua progress)
---

Report progress on your current task. Execute:

```
aqua progress "$ARGUMENTS"
```

This command:
1. Saves a progress message with timestamp
2. Updates your heartbeat (shows you're alive)
3. Other agents can see your progress via `aqua status`

Use this frequently (every 5-10 minutes of work) to:
- Show you're making progress
- Leave breadcrumbs for crash recovery
- Help the leader track parallel work

Examples:
- `/nclaude:progress "Investigating auth module"`
- `/nclaude:progress "Found the bug, writing fix"`
- `/nclaude:progress "Tests passing, preparing PR"`

Report the progress update confirmation.
