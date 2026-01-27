---
description: Reply to a specific message by ID (wraps aqua reply)
---

Reply to a specific message. Parse arguments for message ID and response:

```
aqua reply $ARGUMENTS
```

Usage:
- `/nclaude:reply 42 "Yes, that approach looks good"`
- `/nclaude:reply 15 "I'll handle the frontend, you take backend"`

Arguments:
- First argument: message ID (number)
- Rest: the reply text

The reply is linked to the original message via `reply_to` field, enabling:
- Threaded conversations
- Blocking `aqua ask` to receive the answer
- Clear conversation history

To find message IDs, use `/nclaude:check` which shows message IDs in the output.

Report the sent reply confirmation with timestamp.
