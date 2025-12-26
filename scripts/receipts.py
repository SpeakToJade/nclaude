#!/usr/bin/env python3
"""nclaude read receipts - track who read what

Tracks which sessions have acknowledged reading specific messages.
Used by nclaude.py for read receipt functionality.
"""
import json
import os
from pathlib import Path
from datetime import datetime, timezone


def get_receipts_dir():
    """Get receipts directory from nclaude base dir"""
    # Use same logic as nclaude.py for consistency
    nclaude_dir = os.environ.get("NCLAUDE_DIR")
    if nclaude_dir:
        return Path(nclaude_dir) / "receipts"

    # Try git-aware path
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            repo_name = Path(result.stdout.strip()).name
            return Path(f"/tmp/nclaude/{repo_name}/receipts")
    except Exception:
        pass

    return Path("/tmp/nclaude/receipts")


RECEIPTS_DIR = get_receipts_dir()


def init_receipts():
    """Initialize receipts directory"""
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)


def ack(msg_id: str, session_id: str):
    """Acknowledge reading a message

    Args:
        msg_id: Message ID to acknowledge (e.g., "#42" or "abc123")
        session_id: Session acknowledging the read

    Returns:
        dict with ack status
    """
    init_receipts()

    # Normalize msg_id (remove # prefix if present)
    msg_id = msg_id.lstrip("#")

    receipt_file = RECEIPTS_DIR / f"{msg_id}.json"

    # Load existing receipts for this message
    receipts = {"msg_id": msg_id, "read_by": []}
    if receipt_file.exists():
        try:
            receipts = json.loads(receipt_file.read_text())
        except json.JSONDecodeError:
            pass

    # Add this session's read receipt
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    read_entry = {"session": session_id, "timestamp": ts}

    # Check if already acknowledged
    existing = [r for r in receipts["read_by"] if r["session"] == session_id]
    if existing:
        return {
            "status": "already_acked",
            "msg_id": msg_id,
            "session": session_id,
            "first_ack": existing[0]["timestamp"]
        }

    receipts["read_by"].append(read_entry)

    # Save receipts
    receipt_file.write_text(json.dumps(receipts, indent=2))

    return {
        "status": "acked",
        "msg_id": msg_id,
        "session": session_id,
        "timestamp": ts,
        "total_readers": len(receipts["read_by"])
    }


def get_receipts(msg_id: str):
    """Get all read receipts for a message

    Args:
        msg_id: Message ID to check

    Returns:
        dict with readers list or empty if no receipts
    """
    init_receipts()

    msg_id = msg_id.lstrip("#")
    receipt_file = RECEIPTS_DIR / f"{msg_id}.json"

    if not receipt_file.exists():
        return {"msg_id": msg_id, "read_by": [], "count": 0}

    try:
        receipts = json.loads(receipt_file.read_text())
        receipts["count"] = len(receipts.get("read_by", []))
        return receipts
    except json.JSONDecodeError:
        return {"msg_id": msg_id, "read_by": [], "count": 0}


def who_read(msg_id: str):
    """Get list of session IDs who read a message

    Args:
        msg_id: Message ID to check

    Returns:
        list of session IDs
    """
    receipts = get_receipts(msg_id)
    return [r["session"] for r in receipts.get("read_by", [])]


def unread_by(msg_id: str, sessions: list):
    """Check which sessions have NOT read a message

    Args:
        msg_id: Message ID to check
        sessions: List of session IDs to check against

    Returns:
        list of session IDs who haven't read
    """
    readers = set(who_read(msg_id))
    return [s for s in sessions if s not in readers]


# CLI interface for standalone testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: receipts.py <ack|get|who> [args]"}))
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    try:
        if cmd == "ack":
            if len(args) < 2:
                result = {"error": "Usage: receipts.py ack <msg_id> <session_id>"}
            else:
                result = ack(args[0], args[1])
        elif cmd == "get":
            if len(args) < 1:
                result = {"error": "Usage: receipts.py get <msg_id>"}
            else:
                result = get_receipts(args[0])
        elif cmd == "who":
            if len(args) < 1:
                result = {"error": "Usage: receipts.py who <msg_id>"}
            else:
                result = {"msg_id": args[0], "readers": who_read(args[0])}
        else:
            result = {"error": f"Unknown command: {cmd}"}
    except Exception as e:
        result = {"error": str(e)}

    print(json.dumps(result, indent=2))
