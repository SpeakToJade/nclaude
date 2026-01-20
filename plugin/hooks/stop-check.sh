#!/bin/bash
# Stop hook: Check for messages before Claude stops
# Uses Claude Code's session_id for unique identification

# Read JSON input from stdin
INPUT=$(cat)

# Extract Claude Code's session_id
CC_SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty' 2>/dev/null)

if [ -n "$CC_SESSION_ID" ]; then
    SHORT_ID=$(echo "$CC_SESSION_ID" | cut -c1-12)
    export NCLAUDE_ID="cc-${SHORT_ID}"
fi

# Get messages for this session
MESSAGES=$(nclaude check --for-me --json 2>/dev/null)
COUNT=$(echo "$MESSAGES" | jq -r '.new_count // 0' 2>/dev/null)

if [ "$COUNT" -gt 0 ]; then
    # Extract message summaries
    MSG_LIST=$(echo "$MESSAGES" | jq -r '.messages[]' 2>/dev/null | head -5)

    # Block the stop - Claude must respond to messages
    cat << EOF
{
  "decision": "block",
  "reason": "You have $COUNT new message(s) from other Claude sessions. Please read and respond:\n$MSG_LIST"
}
EOF
    exit 0
fi

# No messages, allow stop
exit 0
