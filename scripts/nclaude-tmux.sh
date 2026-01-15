#!/bin/bash
# nclaude-tmux.sh - Launch 2 Claude sessions + log watcher in tmux
#
# Usage: nclaude-tmux [options] [project-dir]
#        nclaude-tmux                                    # manual mode
#        nclaude-tmux -a "prompt A" -b "prompt B"        # auto-start with prompts
#        nclaude-tmux --config gcp-k8s                   # use preset config

set -e

show_help() {
    cat << 'EOF'
nclaude-tmux - Multi-Claude workspace launcher

Usage: nclaude-tmux [options] [project-dir]

Options:
  -a, --prompt-a "prompt"   Prompt for Claude A (auto-starts claude)
  -b, --prompt-b "prompt"   Prompt for Claude B (auto-starts claude)
  -c, --config NAME         Use preset config (see below)
  -h, --help                Show this help

Preset Configs:
  gcp-k8s     GCP/GKE/Terragrunt infrastructure work
  review      Code review with two perspectives
  test        One writes code, one writes tests

Layout:
  ┌─────────────┬─────────────┐
  │  Claude A   │  Claude B   │
  ├─────────────┴─────────────┤
  │      Message Logs         │
  └───────────────────────────┘

Examples:
  nclaude-tmux                                    # Manual start
  nclaude-tmux -c gcp-k8s                         # GCP/k8s preset
  nclaude-tmux -a "Fix auth bug" -b "Write tests" # Custom prompts

Keybindings:
  Ctrl-b + arrow  - Switch panes
  Ctrl-b + d      - Detach
  Ctrl-b + z      - Zoom pane

Reattach: tmux attach -t nclaude-<repo>
EOF
    exit 0
}

# Parse args
PROMPT_A=""
PROMPT_B=""
PROJECT_DIR=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help|help)
            show_help
            ;;
        -a|--prompt-a)
            PROMPT_A="$2"
            shift 2
            ;;
        -b|--prompt-b)
            PROMPT_B="$2"
            shift 2
            ;;
        -c|--config)
            CONFIG="$2"
            shift 2
            ;;
        *)
            PROJECT_DIR="$1"
            shift
            ;;
    esac
done

# Apply preset configs
case "$CONFIG" in
    gcp-k8s)
        PROMPT_A='You are CLAUDE-A working on GCP/GKE/Terragrunt infrastructure.

CRITICAL: Before ANY infrastructure changes:
1. Run: ~/.local/bin/nclaude check
2. Coordinate with CLAUDE-B using SYN-ACK protocol
3. CLAIM files before editing: nclaude send "CLAIMING: path/to/file" --type URGENT

Your focus areas:
- Terragrunt/Terraform configurations
- GKE cluster management
- IAM and service accounts
- Network policies

CLAUDE-B handles: DNS, certs, ingress, monitoring

Protocol example:
  nclaude send "SYN: I will update GKE node pools, you handle ingress. ACK?" --type TASK
  # Wait for ACK before proceeding

After each significant change:
  nclaude send "STATUS: Updated node pool to n2-standard-4" --type STATUS

Start by checking messages: ~/.local/bin/nclaude check'

        PROMPT_B='You are CLAUDE-B working on GCP/GKE/Terragrunt infrastructure.

CRITICAL: Before ANY infrastructure changes:
1. Run: ~/.local/bin/nclaude check
2. Coordinate with CLAUDE-A using SYN-ACK protocol
3. CLAIM files before editing: nclaude send "CLAIMING: path/to/file" --type URGENT

Your focus areas:
- DNS and Cloud DNS zones
- SSL/TLS certificates (cert-manager)
- Ingress controllers and load balancers
- Monitoring and alerting (Cloud Monitoring)

CLAUDE-A handles: Terragrunt, GKE clusters, IAM, networking

Protocol example:
  nclaude send "ACK: Confirmed, starting ingress config" --type REPLY

After each significant change:
  nclaude send "STATUS: Configured SSL cert for api.example.com" --type STATUS

Start by checking messages: ~/.local/bin/nclaude check'
        ;;
    review)
        PROMPT_A='You are CLAUDE-A - the code author/defender.
Check messages first: ~/.local/bin/nclaude check
Coordinate changes with CLAUDE-B via nclaude send/check'

        PROMPT_B='You are CLAUDE-B - the code reviewer/critic.
Check messages first: ~/.local/bin/nclaude check
Send feedback via: nclaude send "REVIEW: ..." --type TASK'
        ;;
    test)
        PROMPT_A='You are CLAUDE-A - implement features.
Check messages first: ~/.local/bin/nclaude check
Tell CLAUDE-B what to test: nclaude send "IMPLEMENTED: ..." --type STATUS'

        PROMPT_B='You are CLAUDE-B - write tests for what CLAUDE-A builds.
Check messages first: ~/.local/bin/nclaude check
Ask for clarification: nclaude send "QUESTION: ..." --type TASK'
        ;;
esac

PROJECT_DIR="${PROJECT_DIR:-$(pwd)}"
SESSION_NAME="nclaude-$(basename "$PROJECT_DIR")"

# Ensure nclaude log dir exists
REPO_NAME=$(basename "$PROJECT_DIR")
LOG_DIR="/tmp/nclaude/$REPO_NAME"
mkdir -p "$LOG_DIR"
touch "$LOG_DIR/messages.log"

# Kill existing session if exists
tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true

# Create new session
tmux new-session -d -s "$SESSION_NAME" -c "$PROJECT_DIR"

# Split horizontally (top/bottom)
tmux split-window -v -t "$SESSION_NAME" -c "$PROJECT_DIR"

# Split top pane vertically (left/right)
tmux split-window -h -t "$SESSION_NAME:0.0" -c "$PROJECT_DIR"

# Pane layout:
# 0.0 = Claude A (top-left)
# 0.1 = Claude B (top-right)
# 0.2 = Logs (bottom)

# Set up log watcher in bottom pane
tmux send-keys -t "$SESSION_NAME:0.2" "echo '=== nclaude message log ===' && tail -f $LOG_DIR/messages.log" C-m

# Resize: give more space to Claude panes
tmux resize-pane -t "$SESSION_NAME:0.2" -y 12

# Start Claude sessions or show instructions
if [[ -n "$PROMPT_A" ]]; then
    # Escape quotes for shell
    ESCAPED_A=$(printf '%s' "$PROMPT_A" | sed "s/'/'\\\\''/g")
    tmux send-keys -t "$SESSION_NAME:0.0" "claude -p '$ESCAPED_A'" C-m
else
    tmux send-keys -t "$SESSION_NAME:0.0" "# Claude A - run: claude" C-m
    tmux send-keys -t "$SESSION_NAME:0.0" "# Or with prompt: claude -p 'your task'" C-m
fi

if [[ -n "$PROMPT_B" ]]; then
    ESCAPED_B=$(printf '%s' "$PROMPT_B" | sed "s/'/'\\\\''/g")
    tmux send-keys -t "$SESSION_NAME:0.1" "claude -p '$ESCAPED_B'" C-m
else
    tmux send-keys -t "$SESSION_NAME:0.1" "# Claude B - run: claude" C-m
    tmux send-keys -t "$SESSION_NAME:0.1" "# Or with prompt: claude -p 'your task'" C-m
fi

# Focus on Claude A pane
tmux select-pane -t "$SESSION_NAME:0.0"

# Attach to session
exec tmux attach-session -t "$SESSION_NAME"
