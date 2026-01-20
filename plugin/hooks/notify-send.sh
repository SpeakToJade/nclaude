#!/bin/bash
# PostToolUse hook: Notify human when Claude sends a message
# Uses Claude Code's session_id for proper identification

# Read JSON input from stdin
INPUT=$(cat)

# Extract Claude Code's session_id
CC_SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty' 2>/dev/null)

if [ -n "$CC_SESSION_ID" ]; then
    SHORT_ID=$(echo "$CC_SESSION_ID" | cut -c1-12)
    export NCLAUDE_ID="cc-${SHORT_ID}"
fi

# Check if this was a Bash command with nclaude send
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null)

if echo "$COMMAND" | grep -q "nclaude send"; then
    # Extract recipient if any
    RECIPIENT=$(echo "$COMMAND" | grep -oE '@[a-zA-Z0-9/_.-]+' | head -1)

    # macOS notification
    if command -v osascript &> /dev/null; then
        osascript -e "display notification \"Message sent${RECIPIENT:+ to $RECIPIENT}\" with title \"nclaude\" sound name \"Ping\"" 2>/dev/null
    fi

    # Linux notification (if available)
    if command -v notify-send &> /dev/null; then
        notify-send "nclaude" "Message sent${RECIPIENT:+ to $RECIPIENT}" 2>/dev/null
    fi
fi

exit 0
