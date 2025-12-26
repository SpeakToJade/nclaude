#!/usr/bin/env python3
"""
Test if we can inject stdin into Claude Code process
"""
import subprocess
import sys
import time
import select
import os

def test_stdin_injection():
    """Spawn claude and try to inject via stdin"""

    print("Spawning claude with stdin=PIPE...")

    # Spawn claude in non-interactive mode with a simple prompt
    proc = subprocess.Popen(
        ["claude", "-p", "Say just 'HELLO' and nothing else"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "NCLAUDE_ID": "test-stdin"}
    )

    print(f"Claude PID: {proc.pid}")

    # Wait a bit then try to inject
    time.sleep(2)

    print("Attempting stdin injection: 'now say GOODBYE'")
    try:
        proc.stdin.write("now say GOODBYE\n")
        proc.stdin.flush()
    except Exception as e:
        print(f"Stdin write failed: {e}")

    # Wait for output
    try:
        stdout, stderr = proc.communicate(timeout=30)
        print(f"STDOUT:\n{stdout}")
        if stderr:
            print(f"STDERR:\n{stderr}")
    except subprocess.TimeoutExpired:
        proc.kill()
        print("Process timed out")

    return proc.returncode

def test_echo_pipe():
    """Simple test - pipe input to claude"""
    print("\nTest 2: Echo pipe to claude...")

    result = subprocess.run(
        ["echo", "Say INJECTED if you see this | claude -p 'What is 2+2?'"],
        capture_output=True,
        text=True,
        shell=True
    )
    print(f"Result: {result.stdout}")


if __name__ == "__main__":
    print("=== STDIN INJECTION TEST ===\n")
    test_stdin_injection()
