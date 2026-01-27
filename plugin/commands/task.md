---
description: Task queue management - add, claim, done, fail, show (wraps aqua task commands)
---

Manage the Aqua task queue. Parse the subcommand from arguments:

**Add a task:**
```
aqua add "Task title" -p 5
```
Options: `-p N` priority (1-10), `-t tag` add tag, `--depends-on ID` dependency

**Claim next task:**
```
aqua claim
```
Or claim specific: `aqua claim <task-id>`

**Mark task done:**
```
aqua done --summary "What I did"
```

**Mark task failed:**
```
aqua fail --reason "Why it failed"
```

**Show task details:**
```
aqua show <task-id>
```

**List all tasks:**
```
aqua list
```

Usage examples:
- `/nclaude:task add "Fix login bug" -p 8 -t backend`
- `/nclaude:task claim`
- `/nclaude:task done --summary "Fixed auth token refresh"`
- `/nclaude:task fail --reason "Blocked by missing API docs"`
- `/nclaude:task show abc123`
- `/nclaude:task list`

Workflow:
1. `/nclaude:task claim` to get your next task
2. Work on it, using `/nclaude:progress` to report updates
3. `/nclaude:task done` when complete OR `/nclaude:task fail` if blocked

Report the command output showing task status.
