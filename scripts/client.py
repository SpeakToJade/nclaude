#!/usr/bin/env python3
"""
nclaude client - Connect to hub for real-time messaging

Usage:
    python3 client.py connect <session_id>
    python3 client.py send <message> [--to @session1 @session2]
    python3 client.py recv [--timeout 5]
"""

import json
import os
import re
import select
import socket
import sys
import threading
import queue
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# Default socket path
DEFAULT_SOCKET = Path("/tmp/nclaude/hub.sock")


class HubClient:
    """Client for connecting to nclaude hub"""

    def __init__(self, session_id: str, socket_path: Path = DEFAULT_SOCKET):
        self.session_id = session_id
        self.socket_path = socket_path
        self.sock: Optional[socket.socket] = None
        self.connected = False
        self.message_queue: queue.Queue = queue.Queue()
        self.recv_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def connect(self) -> dict:
        """Connect to hub and register session"""
        if not self.socket_path.exists():
            return {"error": "Hub not running", "socket": str(self.socket_path)}

        try:
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.connect(str(self.socket_path))
            self.sock.setblocking(False)

            # Register session
            self._send({"type": "REGISTER", "session_id": self.session_id})

            # Wait for registration confirmation
            response = self._recv_one(timeout=5.0)
            if response and response.get("type") == "REGISTERED":
                self.connected = True
                self._start_recv_thread()
                return {
                    "connected": True,
                    "session_id": self.session_id,
                    "online": response.get("online", [])
                }
            else:
                return {"error": "Registration failed", "response": response}

        except Exception as e:
            return {"error": str(e)}

    def disconnect(self):
        """Disconnect from hub"""
        self._stop_event.set()
        if self.recv_thread:
            self.recv_thread.join(timeout=2.0)
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        self.connected = False

    def send(self, body: str, to: List[str] = None, msg_type: str = "MSG") -> dict:
        """Send message through hub"""
        if not self.connected:
            return {"error": "Not connected"}

        msg = {
            "type": msg_type,
            "body": body
        }
        if to:
            msg["to"] = to

        self._send(msg)

        # Wait for confirmation
        try:
            response = self.message_queue.get(timeout=5.0)
            if response.get("type") == "SENT":
                return {"sent": True, "id": response.get("id"), "to": response.get("to")}
            else:
                # It's a received message, put it back
                self.message_queue.put(response)
                return {"sent": True, "id": "unknown"}
        except queue.Empty:
            return {"sent": True, "id": "unconfirmed"}

    def recv(self, timeout: float = 0.0) -> Optional[dict]:
        """Receive next message"""
        try:
            return self.message_queue.get(timeout=timeout if timeout > 0 else None)
        except queue.Empty:
            return None

    def recv_all(self) -> List[dict]:
        """Get all queued messages"""
        messages = []
        while True:
            try:
                messages.append(self.message_queue.get_nowait())
            except queue.Empty:
                break
        return messages

    def _send(self, msg: dict):
        """Send raw message to hub"""
        if self.sock:
            data = json.dumps(msg) + "\n"
            self.sock.sendall(data.encode())

    def _recv_one(self, timeout: float = 1.0) -> Optional[dict]:
        """Receive single message with timeout"""
        if not self.sock:
            return None

        ready, _, _ = select.select([self.sock], [], [], timeout)
        if not ready:
            return None

        try:
            data = self.sock.recv(65536)
            if data:
                line = data.decode().strip().split("\n")[0]
                return json.loads(line)
        except:
            pass
        return None

    def _start_recv_thread(self):
        """Start background receive thread"""
        self._stop_event.clear()
        self.recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self.recv_thread.start()

    def _recv_loop(self):
        """Background loop to receive messages"""
        buffer = ""
        while not self._stop_event.is_set():
            if not self.sock:
                break

            try:
                ready, _, _ = select.select([self.sock], [], [], 0.5)
                if not ready:
                    continue

                data = self.sock.recv(65536)
                if not data:
                    break

                buffer += data.decode()
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line:
                        try:
                            msg = json.loads(line)
                            self.message_queue.put(msg)
                        except json.JSONDecodeError:
                            pass

            except (ConnectionResetError, BrokenPipeError):
                break
            except Exception:
                continue


def parse_mentions(text: str) -> tuple[str, List[str]]:
    """Parse @mentions from message text

    Returns (cleaned_text, list_of_mentions)

    Examples:
        "@claude-a do X" -> ("do X", ["claude-a"])
        "@claude-a @claude-b both do Y" -> ("both do Y", ["claude-a", "claude-b"])
        "everyone do Z" -> ("everyone do Z", [])
    """
    # Find all @mentions
    mentions = re.findall(r'@([\w-]+)', text)

    # Remove mentions from text
    cleaned = re.sub(r'@[\w-]+\s*', '', text).strip()

    return cleaned, mentions


# Global client instance for CLI
_client: Optional[HubClient] = None


def get_client(session_id: str = None) -> HubClient:
    """Get or create client instance"""
    global _client

    if session_id is None:
        # Try to get from environment or auto-detect
        session_id = os.environ.get("NCLAUDE_ID")
        if not session_id:
            # Auto-detect from git like nclaude.py does
            import subprocess
            try:
                repo = subprocess.run(
                    ["git", "rev-parse", "--show-toplevel"],
                    capture_output=True, text=True
                ).stdout.strip()
                branch = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    capture_output=True, text=True
                ).stdout.strip()
                repo_name = Path(repo).name if repo else "unknown"
                session_id = f"{repo_name}-{branch}"
            except:
                session_id = "unknown"

    if _client is None or _client.session_id != session_id:
        _client = HubClient(session_id)

    return _client


def main():
    if len(sys.argv) < 2:
        print("Usage: client.py <connect|send|recv|status> [args]")
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    # Parse --socket flag
    socket_path = DEFAULT_SOCKET
    if "--socket" in args:
        idx = args.index("--socket")
        if idx + 1 < len(args):
            socket_path = Path(args[idx + 1])
            args = args[:idx] + args[idx+2:]

    if cmd == "connect":
        session_id = args[0] if args else None
        client = get_client(session_id)
        client.socket_path = socket_path
        result = client.connect()
        print(json.dumps(result))

    elif cmd == "send":
        if not args:
            print(json.dumps({"error": "No message provided"}))
            sys.exit(1)

        # Join all args as message
        message = " ".join(args)

        # Parse @mentions
        body, mentions = parse_mentions(message)

        client = get_client()
        client.socket_path = socket_path

        if not client.connected:
            result = client.connect()
            if "error" in result:
                print(json.dumps(result))
                sys.exit(1)

        result = client.send(body, to=mentions if mentions else None)
        print(json.dumps(result))

    elif cmd == "recv":
        timeout = 5.0
        if "--timeout" in args:
            idx = args.index("--timeout")
            if idx + 1 < len(args):
                timeout = float(args[idx + 1])

        client = get_client()
        client.socket_path = socket_path

        if not client.connected:
            result = client.connect()
            if "error" in result:
                print(json.dumps(result))
                sys.exit(1)

        msg = client.recv(timeout=timeout)
        if msg:
            print(json.dumps(msg))
        else:
            print(json.dumps({"messages": [], "count": 0}))

    elif cmd == "status":
        client = get_client()
        client.socket_path = socket_path
        print(json.dumps({
            "session_id": client.session_id,
            "connected": client.connected,
            "socket": str(client.socket_path),
            "queued_messages": client.message_queue.qsize()
        }))

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
