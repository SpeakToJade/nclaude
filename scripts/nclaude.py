#!/usr/bin/env python3
"""nclaude - headless Claude-to-Claude chat

A simple file-based message queue for communication between Claude Code sessions.
No sockets, no pipes, no bullshit.
"""
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def get_git_info():
    """Get git repo info for smart defaults"""
    try:
        # Get git common dir (works for worktrees too)
        git_common = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, timeout=5
        )
        if git_common.returncode != 0:
            return None, None, None

        common_dir = Path(git_common.stdout.strip()).resolve()

        # Get repo root (for regular repos, parent of .git; for worktrees, the main worktree)
        repo_root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5
        )
        repo_name = Path(repo_root.stdout.strip()).name if repo_root.returncode == 0 else "unknown"

        # Get current branch
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5
        )
        branch_name = branch.stdout.strip() if branch.returncode == 0 else "detached"

        return common_dir, repo_name, branch_name
    except Exception:
        return None, None, None


def get_base_dir():
    """Get nclaude base directory, git-aware if possible"""
    # Explicit override always wins
    if "NCLAUDE_DIR" in os.environ:
        return Path(os.environ["NCLAUDE_DIR"])

    # Try git-aware path
    git_common, repo_name, _ = get_git_info()
    if git_common and repo_name:
        # Use /tmp/nclaude/<repo-hash> for isolation
        repo_hash = hashlib.md5(str(git_common).encode()).hexdigest()[:8]
        return Path(f"/tmp/nclaude/{repo_name}-{repo_hash}")

    # Fallback
    return Path("/tmp/nclaude")


def get_auto_session_id():
    """Generate session ID from git context"""
    if "NCLAUDE_ID" in os.environ:
        return os.environ["NCLAUDE_ID"]

    _, repo_name, branch_name = get_git_info()
    if repo_name and branch_name:
        # Sanitize branch name (replace / with -)
        branch_safe = branch_name.replace("/", "-")
        return f"{repo_name}-{branch_safe}"

    return "claude"


# Initialize paths
BASE = get_base_dir()
LOG = BASE / "messages.log"
LOCK = BASE / ".lock"
SESSIONS = BASE / "sessions"


def init():
    """Initialize workspace"""
    SESSIONS.mkdir(parents=True, exist_ok=True)
    LOG.touch()
    LOCK.touch()
    return {"status": "ok", "path": str(BASE)}


def send(session_id: str, message: str):
    """Send a message (atomic append with flock)"""
    init()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    line = f"[{ts}] [{session_id}] {message}\n"

    with open(LOCK, "r") as lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        with open(LOG, "a") as f:
            f.write(line)
    return {"sent": message, "session": session_id, "timestamp": ts}


def read(session_id: str, all_messages: bool = False, quiet: bool = False):
    """Read new messages since last read

    Args:
        session_id: Session identifier
        all_messages: If True, read all messages, not just new ones
        quiet: If True, only output if there are new messages (for hooks)
    """
    init()
    pointer_file = SESSIONS / session_id

    # Get last read position
    last_line = 0
    if pointer_file.exists() and not all_messages:
        try:
            last_line = int(pointer_file.read_text().strip() or "0")
        except ValueError:
            last_line = 0

    # Read log
    if not LOG.exists():
        if quiet:
            return None  # Signal no output needed
        return {"messages": [], "new_count": 0, "total": 0}

    lines = LOG.read_text().splitlines()
    new_lines = lines[last_line:]

    # Update pointer
    pointer_file.write_text(str(len(lines)))

    # In quiet mode, only return if there are new messages
    if quiet and len(new_lines) == 0:
        return None

    return {
        "messages": new_lines,
        "new_count": len(new_lines),
        "total": len(lines)
    }


def status():
    """Get chat status"""
    if not BASE.exists() or not LOG.exists():
        return {"active": False, "message_count": 0, "sessions": [], "log_path": str(LOG)}

    lines = LOG.read_text().splitlines()
    sessions = []
    if SESSIONS.exists():
        sessions = [f.name for f in SESSIONS.iterdir() if f.is_file()]

    return {
        "active": True,
        "message_count": len(lines),
        "sessions": sessions,
        "log_path": str(LOG)
    }


def clear():
    """Clear all messages and session data"""
    if BASE.exists():
        shutil.rmtree(BASE)
    return {"status": "cleared"}


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: nclaude.py <init|send|read|status|clear|whoami> [args]"}))
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    # Parse flags
    quiet = "--quiet" in args or "-q" in args
    all_msgs = "--all" in args

    # Get non-flag args
    positional = [a for a in args if not a.startswith("-")]

    try:
        if cmd == "init":
            result = init()
        elif cmd == "whoami":
            # Show auto-detected session info
            result = {
                "session_id": get_auto_session_id(),
                "base_dir": str(BASE),
                "log_path": str(LOG)
            }
        elif cmd == "send":
            # Use auto session ID if not provided
            if len(positional) >= 2:
                session_id = positional[0]
                message = " ".join(positional[1:])
            elif len(positional) == 1:
                session_id = get_auto_session_id()
                message = positional[0]
            else:
                session_id = get_auto_session_id()
                message = ""

            if not message:
                result = {"error": "No message provided"}
            else:
                result = send(session_id, message)
        elif cmd == "read":
            session_id = positional[0] if positional else get_auto_session_id()
            result = read(session_id, all_msgs, quiet)
        elif cmd == "status":
            result = status()
        elif cmd == "clear":
            result = clear()
        else:
            result = {"error": f"Unknown command: {cmd}"}
    except Exception as e:
        result = {"error": str(e)}

    # In quiet mode, only print if there's something to say
    if result is not None:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
