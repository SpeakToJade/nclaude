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
    """Manages a single Claude Code session"""

    def __init__(self, session_id: str, cwd: str = None):
        self.session_id = session_id
        self.cwd = cwd or os.getcwd()
        self.process: Optional[subprocess.Popen] = None
        self.output_queue: Queue = Queue()
        self.output_thread: Optional[threading.Thread] = None
        self.running = False

    def start(self, initial_prompt: str = None):
        """Start a Claude Code session in interactive mode"""
        # Always start interactive - we'll send prompt via stdin
        cmd = ["claude"]

        env = os.environ.copy()
        env["NCLAUDE_ID"] = self.session_id
        # Force interactive mode
        env["TERM"] = "dumb"  # Simpler output

        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=self.cwd,
            env=env,
            bufsize=1  # Line buffered
        )

        # If initial prompt provided, send it after a short delay
        if initial_prompt:
            threading.Thread(
                target=self._send_initial_prompt,
                args=(initial_prompt,),
                daemon=True
            ).start()

        self.running = True
        self.output_thread = threading.Thread(
            target=self._read_output,
            daemon=True
        )
        self.output_thread.start()

        return self.process.pid

    def _read_output(self):
        """Background thread to read stdout"""
        try:
            while self.running and self.process:
                line = self.process.stdout.readline()
                if not line:
                    break
                self.output_queue.put(line.rstrip())
        except Exception as e:
            self.output_queue.put(f"[ERROR] {e}")

    def send_input(self, text: str):
        """Send input to the Claude session"""
        if self.process and self.process.stdin:
            self.process.stdin.write(text + "\n")
            self.process.stdin.flush()

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
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()


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
