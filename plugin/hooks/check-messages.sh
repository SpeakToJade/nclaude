#!/bin/bash
# Hook to check nclaude messages using Claude Code's session_id

# Read JSON input from stdin
INPUT=$(cat)

# Extract Claude Code's session_id from hook input
CC_SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty' 2>/dev/null)

if [ -n "$CC_SESSION_ID" ]; then
    # Use Claude Code's session_id as nclaude ID (shortened for readability)
    SHORT_ID=$(echo "$CC_SESSION_ID" | cut -c1-12)
    NCLAUDE_ID="cc-${SHORT_ID}" nclaude check --for-me --quiet 2>/dev/null
else
    # Fallback to default
    nclaude check --quiet 2>/dev/null
fi

exit 0
