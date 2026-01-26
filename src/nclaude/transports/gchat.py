"""Google Chat transport for nclaude.

Uses an outbox/inbox file-based approach:
- CLI writes to outbox, skill syncs to Google Chat via MCP
- Skill writes to inbox after fetching from Google Chat
- CLI reads from inbox

This keeps the Python CLI free of MCP/API dependencies.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Default space (clawdz)
DEFAULT_SPACE = "spaces/AAQAW237SHc"
DEFAULT_SPACE_NAME = "clawdz"

# File locations
NCLAUDE_DIR = Path.home() / ".nclaude"
OUTBOX_FILE = NCLAUDE_DIR / "gchat_outbox.jsonl"
INBOX_FILE = NCLAUDE_DIR / "gchat_inbox.jsonl"
STATE_FILE = NCLAUDE_DIR / "gchat_state.json"

# Message tag pattern
TAG_PATTERN = r"\[NCLAUDE:([^:]+):([^:]+):([^\]]+)\]\s*(.+)"


class GChatTransport:
    """Google Chat transport using outbox/inbox files."""

    def __init__(self, space: str = DEFAULT_SPACE):
        self.space = space
        NCLAUDE_DIR.mkdir(parents=True, exist_ok=True)

    def format_tag(
        self,
        session_id: str,
        msg_type: str,
        recipient: str,
        content: str,
    ) -> str:
        """Format message with nclaude tag."""
        if recipient and not recipient.startswith("@") and recipient != "*":
            recipient = f"@{recipient}"
        return f"[NCLAUDE:{session_id}:{msg_type}:{recipient or '*'}] {content}"

    def parse_tag(self, text: str) -> Optional[dict]:
        """Parse nclaude tag from message text."""
        match = re.match(TAG_PATTERN, text, re.DOTALL)
        if not match:
            return None
        return {
            "sender": match.group(1),
            "type": match.group(2),
            "recipient": match.group(3),
            "content": match.group(4).strip(),
        }

    def queue_send(
        self,
        session_id: str,
        message: str,
        msg_type: str = "MSG",
        recipient: Optional[str] = None,
    ) -> dict:
        """Queue a message for sending to Google Chat.

        The message is written to the outbox file. The /nclaude:gchat skill
        will pick it up and send via MCP.
        """
        tagged = self.format_tag(session_id, msg_type, recipient or "*", message)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "message": message,
            "type": msg_type,
            "recipient": recipient or "*",
            "tagged": tagged,
            "sent": False,
        }

        with OUTBOX_FILE.open("a") as f:
            f.write(json.dumps(entry) + "\n")

        return {
            "status": "queued",
            "transport": "gchat",
            "space": self.space,
            "tagged": tagged,
            "hint": "Run /nclaude:gchat sync to send queued messages",
        }

    def read_inbox(self, session_id: str, my_aliases: Optional[list] = None) -> list:
        """Read messages from inbox that are addressed to this session."""
        if not INBOX_FILE.exists():
            return []

        if my_aliases is None:
            my_aliases = []

        messages = []
        for line in INBOX_FILE.read_text().strip().split("\n"):
            if not line:
                continue
            try:
                msg = json.loads(line)
                if self._is_for_me(msg, session_id, my_aliases):
                    messages.append(msg)
            except json.JSONDecodeError:
                continue

        return messages

    def get_outbox_pending(self) -> list:
        """Get unsent messages from outbox."""
        if not OUTBOX_FILE.exists():
            return []

        pending = []
        for line in OUTBOX_FILE.read_text().strip().split("\n"):
            if not line:
                continue
            try:
                entry = json.loads(line)
                if not entry.get("sent", False):
                    pending.append(entry)
            except json.JSONDecodeError:
                continue

        return pending

    def mark_sent(self, timestamp: str) -> None:
        """Mark a message as sent in the outbox."""
        if not OUTBOX_FILE.exists():
            return

        lines = OUTBOX_FILE.read_text().strip().split("\n")
        updated = []
        for line in lines:
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("timestamp") == timestamp:
                    entry["sent"] = True
                updated.append(json.dumps(entry))
            except json.JSONDecodeError:
                updated.append(line)

        OUTBOX_FILE.write_text("\n".join(updated) + "\n")

    def add_to_inbox(self, message: dict) -> None:
        """Add a message to the inbox (called by skill after fetching)."""
        with INBOX_FILE.open("a") as f:
            f.write(json.dumps(message) + "\n")

    def clear_outbox(self) -> int:
        """Clear sent messages from outbox. Returns count cleared."""
        if not OUTBOX_FILE.exists():
            return 0

        lines = OUTBOX_FILE.read_text().strip().split("\n")
        unsent = []
        cleared = 0
        for line in lines:
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("sent", False):
                    cleared += 1
                else:
                    unsent.append(line)
            except json.JSONDecodeError:
                unsent.append(line)

        if unsent:
            OUTBOX_FILE.write_text("\n".join(unsent) + "\n")
        else:
            OUTBOX_FILE.unlink()

        return cleared

    def _is_for_me(
        self, msg: dict, session_id: str, aliases: list
    ) -> bool:
        """Check if message is addressed to this session."""
        recipient = msg.get("recipient", "*")

        # Broadcast
        if recipient == "*":
            return True

        # Strip @ prefix
        recipient_clean = recipient.lstrip("@")

        # Exact match
        if recipient_clean == session_id:
            return True

        # Alias match
        if recipient_clean in aliases:
            return True

        # Partial match (cc-abc123 matches @abc123)
        if session_id.endswith(recipient_clean):
            return True

        return False

    def status(self) -> dict:
        """Get gchat transport status."""
        pending = len(self.get_outbox_pending())
        inbox_count = 0
        if INBOX_FILE.exists():
            inbox_count = len([
                l for l in INBOX_FILE.read_text().strip().split("\n") if l
            ])

        return {
            "transport": "gchat",
            "space": self.space,
            "outbox_pending": pending,
            "inbox_messages": inbox_count,
            "outbox_file": str(OUTBOX_FILE),
            "inbox_file": str(INBOX_FILE),
        }
