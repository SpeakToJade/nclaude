"""Google Chat bridge for nclaude remote messaging.

Provides utilities for formatting and parsing nclaude-tagged messages
in Google Chat for cross-machine Claude session communication.
"""
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

# Message tag pattern: [NCLAUDE:sender_id:type:recipient] content
NCLAUDE_TAG_PATTERN = r"\[NCLAUDE:([^:]+):([^:]+):([^\]]+)\]\s*(.+)"

# Default space (clawdz)
DEFAULT_SPACE = "spaces/AAQAW237SHc"

# State file for tracking last seen message
STATE_FILE = Path.home() / ".nclaude" / "gchat_state.json"


def get_space() -> str:
    """Get configured Google Chat space."""
    return os.environ.get("NCLAUDE_GCHAT_SPACE", DEFAULT_SPACE)


def format_message(
    session_id: str,
    content: str,
    msg_type: str = "MSG",
    recipient: str = "*"
) -> str:
    """Format message with nclaude tag for Google Chat.

    Args:
        session_id: Sender's session ID (cc-xxx format)
        content: Message content
        msg_type: MSG|TASK|REPLY|STATUS|URGENT|ERROR
        recipient: * for broadcast, @alias or @session_id for directed

    Returns:
        Formatted message string
    """
    # Normalize recipient
    if recipient and not recipient.startswith("@") and recipient != "*":
        recipient = f"@{recipient}"

    return f"[NCLAUDE:{session_id}:{msg_type}:{recipient}] {content}"


def parse_message(text: str) -> dict | None:
    """Parse nclaude-tagged message from Google Chat.

    Args:
        text: Raw message text

    Returns:
        Parsed message dict or None if not an nclaude message
    """
    match = re.match(NCLAUDE_TAG_PATTERN, text, re.DOTALL)
    if not match:
        return None

    return {
        "sender": match.group(1),
        "type": match.group(2),
        "recipient": match.group(3),
        "content": match.group(4).strip(),
    }


def is_for_me(msg: dict, my_session_id: str, my_aliases: list[str] | None = None) -> bool:
    """Check if message is addressed to this session.

    Args:
        msg: Parsed message dict
        my_session_id: Current session ID
        my_aliases: List of aliases for current session

    Returns:
        True if message is for this session
    """
    if my_aliases is None:
        my_aliases = []

    recipient = msg["recipient"]

    # Broadcast
    if recipient == "*":
        return True

    # Strip @ prefix for matching
    recipient_clean = recipient.lstrip("@")

    # Exact session ID match
    if recipient_clean == my_session_id:
        return True

    # Alias match
    if recipient_clean in my_aliases:
        return True

    # Partial match (cc-abc123 matches @abc123)
    if my_session_id.endswith(recipient_clean):
        return True

    # Partial match (cc-abc123-def matches @abc123)
    if recipient_clean in my_session_id:
        return True

    return False


def get_state() -> dict:
    """Get gchat bridge state (last seen, etc)."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"last_seen": None, "last_check": None}


def save_state(state: dict) -> None:
    """Save gchat bridge state."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state["last_check"] = datetime.now(timezone.utc).isoformat()
    STATE_FILE.write_text(json.dumps(state, indent=2))


def update_last_seen(message_id: str) -> None:
    """Update last seen message ID."""
    state = get_state()
    state["last_seen"] = message_id
    save_state(state)


def get_last_seen() -> str | None:
    """Get ID of last seen message."""
    return get_state().get("last_seen")


# Message type constants
class MsgType:
    MSG = "MSG"          # General message
    TASK = "TASK"        # Work assignment, SYN
    REPLY = "REPLY"      # Response, ACK/NACK
    STATUS = "STATUS"    # Progress update, RELEASE
    URGENT = "URGENT"    # Priority, CLAIM
    ERROR = "ERROR"      # Problems
