#!/usr/bin/env python3
"""Hook script for automatic peer message notification in Claude Code.

This script is designed to be run as a UserPromptSubmit hook. It checks for
new messages from paired peer projects and injects them into the conversation
context using Claude Code's additionalContext mechanism.

Usage in ~/.claude/settings.json or .claude/settings.json:
{
  "hooks": {
    "UserPromptSubmit": [{
      "command": "nclaude-hook"
    }]
  }
}

Requires: uv tool install nclaude
"""
import json
import subprocess
import sys


def run_nclaude(*args):
    """Run nclaude command and return parsed JSON output."""
    try:
        result = subprocess.run(
            ["nclaude"] + list(args),
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return None


def get_peers():
    """Get list of peer project names."""
    result = run_nclaude("peers")
    if not result:
        return []
    return result.get("peers", [])


def is_from_peer(message: str, peers: list) -> bool:
    """Check if a message is from a peer project.

    Message formats:
    - Single line: [timestamp] [session_id] message
    - With type: [timestamp] [session_id] [MSG_TYPE] message
    - Multi-line header: <<<[timestamp][session_id][MSG_TYPE]>>>

    Session IDs are typically: {repo_name}-{branch}
    We check if any peer name appears in the session_id portion.
    """
    if not peers:
        return False

    # Extract session_id from message
    # Format: [timestamp] [session_id] ...
    parts = message.split("] [")
    if len(parts) < 2:
        # Try multi-line format: <<<[timestamp][session_id][type]>>>
        if message.startswith("<<<["):
            inner = message[4:].split("]")
            if len(inner) >= 2:
                session_id = inner[1].lstrip("[")
                for peer in peers:
                    if peer in session_id:
                        return True
        return False

    # Extract session_id (second bracketed value)
    session_id = parts[1].split("]")[0]

    for peer in peers:
        if peer in session_id:
            return True

    return False


def format_messages(messages: list) -> str:
    """Format messages for display in context."""
    if not messages:
        return ""

    formatted = []
    for msg in messages:
        # Clean up message for display
        if msg.startswith("<<<["):
            # Multi-line message header - skip the delimiter line
            continue
        if msg == "<<<END>>>":
            continue
        formatted.append(msg)

    return "\n".join(formatted)


def main():
    """Main hook entry point."""
    # Get peers for this project
    peers = get_peers()

    if not peers:
        # No peers configured, nothing to check
        sys.exit(0)

    # Read new messages (quiet mode returns None if no messages)
    read_result = run_nclaude("read", "--quiet")

    if not read_result:
        # No new messages
        sys.exit(0)

    messages = read_result.get("messages", [])
    if not messages:
        sys.exit(0)

    # Filter to peer messages only
    peer_messages = [msg for msg in messages if is_from_peer(msg, peers)]

    if not peer_messages:
        # No messages from peers
        sys.exit(0)

    # Format and output via additionalContext
    formatted = format_messages(peer_messages)
    if not formatted:
        sys.exit(0)

    output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": f"# [nclaude] peer messages\n\n{formatted}"
        }
    }

    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
