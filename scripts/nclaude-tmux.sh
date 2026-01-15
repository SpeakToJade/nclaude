#!/bin/bash
# nclaude-tmux.sh - Launch 2 Claude sessions + log watcher in tmux
#
# Usage: nclaude-tmux.sh [project-dir]
#        nclaude-tmux.sh              # uses $PWD
#        nclaude-tmux.sh /path/to/repo

set -e

if [[ "$1" == "-h" || "$1" == "--help" || "$1" == "help" ]]; then
    cat << 'EOF'
nclaude-tmux - Multi-Claude workspace launcher

Usage: nclaude-tmux [project-dir]

Creates a tmux session with:
  - Top-left:  Claude A terminal
  - Top-right: Claude B terminal
  - Bottom:    Message log watcher

After launch:
  1. Run 'claude' in each top pane
  2. Use 'nclaude send "msg"' to communicate
  3. Use 'nclaude check' to read messages
  4. Watch the bottom pane for all traffic

Keybindings (tmux defaults):
  Ctrl-b + arrow  - Switch panes
  Ctrl-b + d      - Detach (session keeps running)
  Ctrl-b + z      - Zoom current pane

Reattach: tmux attach -t nclaude-<repo>
EOF
    exit 0
fi

PROJECT_DIR="${1:-$(pwd)}"
SESSION_NAME="nclaude-$(basename "$PROJECT_DIR")"

# Ensure nclaude log dir exists
REPO_NAME=$(basename "$PROJECT_DIR")
LOG_DIR="/tmp/nclaude/$REPO_NAME"
mkdir -p "$LOG_DIR"
touch "$LOG_DIR/messages.log"

# Kill existing session if exists
tmux kill-session -t "$SESSION_NAME" 2>/dev/null

# Create new session with 3 panes:
#   ┌─────────────┬─────────────┐
#   │  Claude A   │  Claude B   │
#   │             │             │
#   ├─────────────┴─────────────┤
#   │      Message Logs         │
#   └───────────────────────────┘

tmux new-session -d -s "$SESSION_NAME" -c "$PROJECT_DIR"

# Split horizontally (top/bottom)
tmux split-window -v -t "$SESSION_NAME" -c "$PROJECT_DIR"

# Split top pane vertically (left/right)
tmux split-window -h -t "$SESSION_NAME:0.0" -c "$PROJECT_DIR"

# Pane 0: Claude A (top-left)
# Pane 1: Claude B (top-right)
# Pane 2: Logs (bottom)

# Set up log watcher in bottom pane
tmux send-keys -t "$SESSION_NAME:0.2" "echo '=== nclaude message log ===' && tail -f $LOG_DIR/messages.log" C-m

# Set pane titles (if terminal supports it)
tmux select-pane -t "$SESSION_NAME:0.0" -T "Claude-A"
tmux select-pane -t "$SESSION_NAME:0.1" -T "Claude-B"
tmux select-pane -t "$SESSION_NAME:0.2" -T "Logs"

# Resize: give more space to Claude panes
tmux resize-pane -t "$SESSION_NAME:0.2" -y 10

# Instructions in Claude panes
tmux send-keys -t "$SESSION_NAME:0.0" "# Claude A - run: claude" C-m
tmux send-keys -t "$SESSION_NAME:0.0" "# Then use: nclaude send 'msg' && nclaude check" C-m
tmux send-keys -t "$SESSION_NAME:0.1" "# Claude B - run: claude" C-m
tmux send-keys -t "$SESSION_NAME:0.1" "# Then use: nclaude check && nclaude send 'reply'" C-m

# Focus on Claude A pane
tmux select-pane -t "$SESSION_NAME:0.0"

# Attach to session
tmux attach-session -t "$SESSION_NAME"
