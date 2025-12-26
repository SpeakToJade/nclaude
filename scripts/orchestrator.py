#!/usr/bin/env python3
"""
Multi-Claude Orchestrator

Spawns multiple Claude Code sessions and routes messages between them.
Human stays in the loop via a central terminal.

Usage:
    python3 orchestrator.py spawn claude-a claude-b claude-c
    python3 orchestrator.py send claude-a "do the auth module"
    python3 orchestrator.py broadcast "everyone check logs"
"""

import json
import os
import pty
import select
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue, Empty
from typing import Dict, Optional, List

# ANSI colors for different sessions
COLORS = {
    'claude-a': '\033[94m',  # Blue
    'claude-b': '\033[92m',  # Green
    'claude-c': '\033[93m',  # Yellow
    'claude-d': '\033[95m',  # Magenta
    'claude-e': '\033[96m',  # Cyan
    'human': '\033[91m',     # Red
    'reset': '\033[0m'
}


class ClaudeSession:
    """Manages a single Claude Code session using PTY for full interactivity"""

    def __init__(self, session_id: str, cwd: str = None):
        self.session_id = session_id
        self.cwd = cwd or os.getcwd()
        self.pid: Optional[int] = None
        self.master_fd: Optional[int] = None
        self.output_queue: Queue = Queue()
        self.output_thread: Optional[threading.Thread] = None
        self.running = False

    def start(self, initial_prompt: str = None):
        """Start a Claude Code session with PTY"""
        # Create pseudo-terminal
        master, slave = pty.openpty()

        pid = os.fork()
        if pid == 0:
            # Child process - becomes Claude
            os.setsid()
            os.dup2(slave, 0)  # stdin
            os.dup2(slave, 1)  # stdout
            os.dup2(slave, 2)  # stderr
            os.close(master)
            os.close(slave)

            # Set environment
            os.environ["NCLAUDE_ID"] = self.session_id
            os.environ["TERM"] = "xterm-256color"

            # Change directory
            if self.cwd:
                os.chdir(self.cwd)

            # Exec claude
            os.execlp("claude", "claude")
        else:
            # Parent process
            os.close(slave)
            self.pid = pid
            self.master_fd = master
            self.running = True

            # Start output reader thread
            self.output_thread = threading.Thread(
                target=self._read_output,
                daemon=True
            )
            self.output_thread.start()

            # Send initial prompt after startup
            if initial_prompt:
                threading.Thread(
                    target=self._send_initial_prompt,
                    args=(initial_prompt,),
                    daemon=True
                ).start()

            return pid

    def _send_initial_prompt(self, prompt: str):
        """Send initial prompt after Claude starts up"""
        time.sleep(4)  # Wait for Claude to initialize
        self.send_input(prompt)

    def _read_output(self):
        """Background thread to read PTY output"""
        try:
            while self.running and self.master_fd:
                r, _, _ = select.select([self.master_fd], [], [], 0.1)
                if r:
                    try:
                        data = os.read(self.master_fd, 4096)
                        if data:
                            # Strip ANSI codes for cleaner output
                            text = data.decode(errors="replace")
                            # Split by newlines and queue each line
                            for line in text.split("\n"):
                                clean = self._strip_ansi(line).strip()
                                if clean:
                                    self.output_queue.put(clean)
                    except OSError:
                        break
        except Exception as e:
            self.output_queue.put(f"[ERROR] {e}")

    def _strip_ansi(self, text: str) -> str:
        """Remove ANSI escape codes"""
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

    def send_input(self, text: str):
        """Send input to the Claude session via PTY"""
        if self.master_fd:
            try:
                # Use \r\n for PTY - some terminals need carriage return
                os.write(self.master_fd, (text + "\r\n").encode())
            except OSError as e:
                self.output_queue.put(f"[ERROR sending input] {e}")

    def get_output(self, timeout: float = 0.1) -> List[str]:
        """Get any available output"""
        lines = []
        try:
            while True:
                line = self.output_queue.get(timeout=timeout)
                lines.append(line)
        except Empty:
            pass
        return lines

    def stop(self):
        """Stop the session"""
        self.running = False
        if self.master_fd:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
        if self.pid:
            try:
                os.kill(self.pid, 9)
                os.waitpid(self.pid, 0)
            except (OSError, ChildProcessError):
                pass


class Orchestrator:
    """Manages multiple Claude sessions"""

    def __init__(self):
        self.sessions: Dict[str, ClaudeSession] = {}
        self.message_log: List[dict] = []
        self.running = False

    def spawn(self, session_id: str, initial_prompt: str = None) -> int:
        """Spawn a new Claude session"""
        if session_id in self.sessions:
            print(f"Session {session_id} already exists")
            return -1

        # Default prompt instructs Claude to check nclaude messages
        if not initial_prompt:
            initial_prompt = f"You are {session_id}. First, check /nclaude:read for any messages."

        session = ClaudeSession(session_id)
        pid = session.start(initial_prompt)
        self.sessions[session_id] = session

        self._log_message("SYSTEM", f"Spawned {session_id} (PID: {pid})")
        return pid

    def send(self, session_id: str, message: str):
        """Send a message to a specific session"""
        if session_id not in self.sessions:
            print(f"Session {session_id} not found")
            return

        session = self.sessions[session_id]
        session.send_input(message)
        self._log_message("human", f"@{session_id}: {message}")

    def broadcast(self, message: str):
        """Send a message to all sessions"""
        for session_id in self.sessions:
            self.send(session_id, message)

    def _log_message(self, sender: str, message: str):
        """Log a message"""
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        color = COLORS.get(sender, '')
        reset = COLORS['reset']
        print(f"[{ts}] {color}[{sender}]{reset} {message}")

        self.message_log.append({
            "timestamp": ts,
            "sender": sender,
            "message": message
        })

    def monitor(self):
        """Monitor all session outputs"""
        self.running = True
        print("Monitoring sessions... (Ctrl+C to stop)")

        try:
            while self.running:
                for session_id, session in self.sessions.items():
                    lines = session.get_output(timeout=0.05)
                    for line in lines:
                        self._log_message(session_id, line)
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nStopping...")

    def interactive(self):
        """Interactive mode - human sends commands"""
        self.running = True

        # Start monitoring in background
        monitor_thread = threading.Thread(
            target=self._background_monitor,
            daemon=True
        )
        monitor_thread.start()

        print("\n=== Multi-Claude Orchestrator ===")
        print("Commands:")
        print("  @<session> <message>  - Send to specific session")
        print("  @all <message>        - Broadcast to all")
        print("  /spawn <id>           - Spawn new session")
        print("  /list                 - List sessions")
        print("  /quit                 - Exit")
        print()

        try:
            while self.running:
                try:
                    cmd = input(f"{COLORS['human']}[human]{COLORS['reset']} ")
                except EOFError:
                    break

                if not cmd.strip():
                    continue

                if cmd.startswith("/"):
                    self._handle_command(cmd)
                elif cmd.startswith("@"):
                    self._handle_mention(cmd)
                else:
                    print("Use @<session> to send messages")

        except KeyboardInterrupt:
            pass

        self.running = False
        self.shutdown()

    def _background_monitor(self):
        """Background monitoring of session outputs"""
        while self.running:
            for session_id, session in list(self.sessions.items()):
                lines = session.get_output(timeout=0.02)
                for line in lines:
                    self._log_message(session_id, line)
            time.sleep(0.05)

    def _handle_command(self, cmd: str):
        """Handle / commands"""
        parts = cmd.split()
        command = parts[0].lower()

        if command == "/spawn" and len(parts) >= 2:
            session_id = parts[1]
            prompt = " ".join(parts[2:]) if len(parts) > 2 else None
            self.spawn(session_id, prompt)

        elif command == "/list":
            print("Active sessions:")
            for sid, session in self.sessions.items():
                status = "running" if session.running else "stopped"
                print(f"  {sid}: {status}")

        elif command == "/quit":
            self.running = False

        else:
            print(f"Unknown command: {command}")

    def _handle_mention(self, cmd: str):
        """Handle @mention messages"""
        if cmd.startswith("@all "):
            message = cmd[5:]
            self.broadcast(message)
        elif " " in cmd:
            target, message = cmd[1:].split(" ", 1)
            if target in self.sessions:
                self.send(target, message)
            else:
                print(f"Unknown session: {target}")
        else:
            print("Usage: @<session> <message>")

    def shutdown(self):
        """Stop all sessions"""
        print("Shutting down sessions...")
        for session in self.sessions.values():
            session.stop()
        print("Done.")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  orchestrator.py interactive          - Interactive mode")
        print("  orchestrator.py spawn <id> [id2...]  - Spawn sessions then monitor")
        sys.exit(1)

    orch = Orchestrator()

    if sys.argv[1] == "interactive":
        orch.interactive()

    elif sys.argv[1] == "spawn":
        if len(sys.argv) < 3:
            print("Usage: orchestrator.py spawn <session_id> [session_id2...]")
            sys.exit(1)

        for session_id in sys.argv[2:]:
            orch.spawn(session_id)

        orch.monitor()
        orch.shutdown()

    else:
        print(f"Unknown command: {sys.argv[1]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
