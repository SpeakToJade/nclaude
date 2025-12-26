#!/usr/bin/env python3
"""
nclaude hub - Unix socket server for real-time Claude-to-Claude messaging

Usage:
    python3 hub.py start [--socket /path/to/sock]
    python3 hub.py stop
    python3 hub.py status
"""

import json
import os
import select
import signal
import socket
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

# Default socket path
DEFAULT_SOCKET = Path("/tmp/nclaude/hub.sock")


class MessageHub:
    """Central message routing hub for nclaude"""

    def __init__(self, socket_path: Path = DEFAULT_SOCKET):
        self.socket_path = socket_path
        self.server: Optional[socket.socket] = None
        self.clients: Dict[str, socket.socket] = {}  # session_id -> socket
        self.client_sessions: Dict[socket.socket, str] = {}  # socket -> session_id
        self.running = False
        self.lock = threading.Lock()

    def start(self):
        """Start the hub server"""
        # Ensure directory exists
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)

        # Remove stale socket
        if self.socket_path.exists():
            self.socket_path.unlink()

        # Create Unix socket
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(str(self.socket_path))
        self.server.listen(50)  # Support many concurrent connections
        self.server.setblocking(False)

        self.running = True
        print(json.dumps({
            "status": "started",
            "socket": str(self.socket_path),
            "pid": os.getpid()
        }))

        # Write PID file
        pid_file = self.socket_path.with_suffix(".pid")
        pid_file.write_text(str(os.getpid()))

        # Main event loop
        self._event_loop()

    def _event_loop(self):
        """Main event loop using select"""
        while self.running:
            # Build list of sockets to monitor
            read_sockets = [self.server] + list(self.client_sessions.keys())

            try:
                readable, _, _ = select.select(read_sockets, [], [], 1.0)
            except (ValueError, OSError):
                # Socket closed, rebuild list
                continue

            for sock in readable:
                if sock is self.server:
                    self._accept_client()
                else:
                    self._handle_client(sock)

    def _accept_client(self):
        """Accept new client connection"""
        try:
            client, _ = self.server.accept()
            client.setblocking(False)
            # Client must register with session_id in first message
            with self.lock:
                self.client_sessions[client] = None  # Unregistered
        except Exception as e:
            print(json.dumps({"error": f"Accept failed: {e}"}), file=sys.stderr)

    def _handle_client(self, client: socket.socket):
        """Handle message from client"""
        try:
            data = client.recv(65536)
            if not data:
                self._disconnect_client(client)
                return

            # Parse message(s) - may receive multiple newline-delimited JSON
            for line in data.decode().strip().split("\n"):
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    self._process_message(client, msg)
                except json.JSONDecodeError:
                    self._send_error(client, "Invalid JSON")

        except (ConnectionResetError, BrokenPipeError):
            self._disconnect_client(client)
        except Exception as e:
            print(json.dumps({"error": f"Handle failed: {e}"}), file=sys.stderr)

    def _process_message(self, client: socket.socket, msg: dict):
        """Process incoming message"""
        msg_type = msg.get("type", "MSG")

        # Handle registration
        if msg_type == "REGISTER":
            session_id = msg.get("session_id")
            if session_id:
                with self.lock:
                    # Remove old registration if exists
                    old_sock = self.clients.get(session_id)
                    if old_sock and old_sock != client:
                        self._disconnect_client(old_sock)

                    self.clients[session_id] = client
                    self.client_sessions[client] = session_id

                self._send_to_client(client, {
                    "type": "REGISTERED",
                    "session_id": session_id,
                    "online": list(self.clients.keys())
                })
                self._broadcast({
                    "type": "JOIN",
                    "session_id": session_id,
                    "timestamp": self._timestamp()
                }, exclude={client})
            return

        # Require registration for other messages
        sender = self.client_sessions.get(client)
        if not sender:
            self._send_error(client, "Not registered. Send REGISTER first.")
            return

        # Add metadata
        msg["from"] = sender
        msg["timestamp"] = self._timestamp()
        msg["id"] = f"{sender}-{msg['timestamp'].replace(':', '').replace('-', '')}"

        # Route message
        recipients = msg.get("to", [])
        if isinstance(recipients, str):
            recipients = [recipients]

        if not recipients:
            # Broadcast to all
            self._broadcast(msg, exclude={client})
        else:
            # Route to specific recipients
            for recipient in recipients:
                self._route_to(recipient, msg)

        # Confirm to sender
        self._send_to_client(client, {
            "type": "SENT",
            "id": msg["id"],
            "to": recipients or "broadcast"
        })

    def _route_to(self, session_id: str, msg: dict):
        """Route message to specific session"""
        with self.lock:
            client = self.clients.get(session_id)

        if client:
            self._send_to_client(client, msg)
        else:
            # Queue for offline delivery? For now, just note it
            print(json.dumps({
                "warning": f"Session {session_id} not connected",
                "msg_id": msg.get("id")
            }), file=sys.stderr)

    def _broadcast(self, msg: dict, exclude: Set[socket.socket] = None):
        """Broadcast message to all connected clients"""
        exclude = exclude or set()
        with self.lock:
            targets = [c for c in self.client_sessions.keys() if c not in exclude]

        for client in targets:
            self._send_to_client(client, msg)

    def _send_to_client(self, client: socket.socket, msg: dict):
        """Send message to client"""
        try:
            data = json.dumps(msg) + "\n"
            client.sendall(data.encode())
        except (BrokenPipeError, ConnectionResetError):
            self._disconnect_client(client)

    def _send_error(self, client: socket.socket, error: str):
        """Send error to client"""
        self._send_to_client(client, {"type": "ERROR", "error": error})

    def _disconnect_client(self, client: socket.socket):
        """Clean up disconnected client"""
        with self.lock:
            session_id = self.client_sessions.pop(client, None)
            if session_id:
                self.clients.pop(session_id, None)

        try:
            client.close()
        except:
            pass

        if session_id:
            self._broadcast({
                "type": "LEAVE",
                "session_id": session_id,
                "timestamp": self._timestamp()
            })

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    def stop(self):
        """Stop the hub server"""
        self.running = False
        if self.server:
            self.server.close()
        if self.socket_path.exists():
            self.socket_path.unlink()
        pid_file = self.socket_path.with_suffix(".pid")
        if pid_file.exists():
            pid_file.unlink()


def get_hub_status(socket_path: Path = DEFAULT_SOCKET) -> dict:
    """Check if hub is running"""
    pid_file = socket_path.with_suffix(".pid")

    if not socket_path.exists():
        return {"running": False, "reason": "Socket not found"}

    if not pid_file.exists():
        return {"running": False, "reason": "PID file not found"}

    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)  # Check if process exists
        return {"running": True, "pid": pid, "socket": str(socket_path)}
    except (ProcessLookupError, ValueError):
        return {"running": False, "reason": "Process not running"}


def stop_hub(socket_path: Path = DEFAULT_SOCKET) -> dict:
    """Stop running hub"""
    pid_file = socket_path.with_suffix(".pid")

    if not pid_file.exists():
        return {"error": "Hub not running"}

    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        return {"stopped": True, "pid": pid}
    except (ProcessLookupError, ValueError) as e:
        return {"error": str(e)}


def main():
    if len(sys.argv) < 2:
        print("Usage: hub.py <start|stop|status> [--socket PATH]")
        sys.exit(1)

    cmd = sys.argv[1]

    # Parse --socket flag
    socket_path = DEFAULT_SOCKET
    if "--socket" in sys.argv:
        idx = sys.argv.index("--socket")
        if idx + 1 < len(sys.argv):
            socket_path = Path(sys.argv[idx + 1])

    if cmd == "start":
        hub = MessageHub(socket_path)

        # Handle signals
        def shutdown(sig, frame):
            hub.stop()
            sys.exit(0)

        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)

        hub.start()

    elif cmd == "stop":
        result = stop_hub(socket_path)
        print(json.dumps(result))

    elif cmd == "status":
        result = get_hub_status(socket_path)
        print(json.dumps(result))

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
