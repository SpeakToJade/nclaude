#!/bin/sh
# nclaude-tmux.sh - Launch 2 Claude sessions + log watcher in tmux
# POSIX-compliant for macOS/Linux

set -e

# === Error handling ===
die() {
    printf "ERROR: %s\n" "$1" >&2
    exit 1
}

warn() {
    printf "WARNING: %s\n" "$1" >&2
}

# === Dependency check ===
command -v tmux >/dev/null 2>&1 || die "tmux not found. Install it first."

# === Help ===
show_help() {
    cat << 'EOF'
nclaude-tmux - Multi-Claude workspace launcher

Usage: nclaude-tmux [options] [project-dir]

Options:
  -r, --resume [NAME]       Resume existing session (interactive picker if multiple)
  -a, --prompt-a "prompt"   Prompt for Claude A (auto-starts claude)
  -b, --prompt-b "prompt"   Prompt for Claude B (auto-starts claude)
  -c, --config NAME         Use preset config: gcp-k8s, review, test
  -l, --list                List existing nclaude sessions
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
  nclaude-tmux -r                                 # Resume (pick from list)
  nclaude-tmux -c gcp-k8s                         # GCP/k8s preset
  nclaude-tmux -a "Fix auth bug" -b "Write tests" # Custom prompts

Keybindings:
  Ctrl-b + arrow  - Switch panes
  Ctrl-b + d      - Detach
  Ctrl-b + z      - Zoom pane
EOF
    exit 0
}

# === List sessions ===
list_sessions() {
    SESSIONS=$(tmux list-sessions -F '#{session_name}' 2>/dev/null | grep '^nclaude-' || true)
    if [ -z "$SESSIONS" ]; then
        echo "No nclaude sessions found."
        return 1
    fi
    echo "nclaude sessions:"
    echo "$SESSIONS" | sed 's/^/  /'
    return 0
}

# === Interactive session picker ===
pick_session() {
    SESSIONS=$(tmux list-sessions -F '#{session_name}' 2>/dev/null | grep '^nclaude-' || true)

    if [ -z "$SESSIONS" ]; then
        die "No nclaude sessions found. Start one with: nclaude-tmux"
    fi

    SESSION_COUNT=$(printf "%s\n" "$SESSIONS" | wc -l | tr -d ' ')

    if [ "$SESSION_COUNT" -eq 1 ]; then
        echo "Resuming: $SESSIONS"
        exec tmux attach-session -t "$SESSIONS"
    fi

    # Multiple sessions - show picker
    echo "Select session to resume:"
    echo ""

    # Number each session
    i=1
    printf "%s\n" "$SESSIONS" | while read -r session; do
        printf "  %d) %s\n" "$i" "$session"
        i=$((i + 1))
    done
    echo ""

    # Prompt
    printf "Enter number [1-%d]: " "$SESSION_COUNT"
    read -r choice

    # Validate input
    case "$choice" in
        ''|*[!0-9]*)
            die "Invalid selection: '$choice'"
            ;;
    esac

    if [ "$choice" -lt 1 ] || [ "$choice" -gt "$SESSION_COUNT" ]; then
        die "Selection out of range: $choice (must be 1-$SESSION_COUNT)"
    fi

    # Get the selected session
    SELECTED=$(printf "%s\n" "$SESSIONS" | sed -n "${choice}p")

    if [ -z "$SELECTED" ]; then
        die "Failed to get session at position $choice"
    fi

    echo "Resuming: $SELECTED"
    exec tmux attach-session -t "$SELECTED"
}

# === Resume specific session ===
resume_session() {
    target="$1"

    if [ -z "$target" ]; then
        pick_session
        return
    fi

    # Check if session exists
    if tmux has-session -t "$target" 2>/dev/null; then
        echo "Resuming: $target"
        exec tmux attach-session -t "$target"
    else
        echo "Session '$target' not found."
        echo ""
        list_sessions || true
        exit 1
    fi
}

# === Parse arguments ===
PROMPT_A=""
PROMPT_B=""
PROJECT_DIR=""
RESUME=""
RESUME_TARGET=""
CONFIG=""
LIST_ONLY=""

while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help|help)
            show_help
            ;;
        -l|--list)
            LIST_ONLY="yes"
            shift
            ;;
        -r|--resume)
            RESUME="yes"
            shift
            # Check if next arg is a session name (not a flag)
            if [ $# -gt 0 ]; then
                case "$1" in
                    -*) ;;  # It's a flag, don't consume
                    *)
                        RESUME_TARGET="$1"
                        shift
                        ;;
                esac
            fi
            ;;
        -a|--prompt-a)
            [ $# -lt 2 ] && die "-a requires an argument"
            PROMPT_A="$2"
            shift 2
            ;;
        -b|--prompt-b)
            [ $# -lt 2 ] && die "-b requires an argument"
            PROMPT_B="$2"
            shift 2
            ;;
        -c|--config)
            [ $# -lt 2 ] && die "-c requires an argument (gcp-k8s, review, test)"
            CONFIG="$2"
            shift 2
            ;;
        -*)
            die "Unknown option: $1"
            ;;
        *)
            PROJECT_DIR="$1"
            shift
            ;;
    esac
done

# === Handle list mode ===
if [ "$LIST_ONLY" = "yes" ]; then
    list_sessions
    exit $?
fi

# === Handle resume mode ===
if [ "$RESUME" = "yes" ]; then
    resume_session "$RESUME_TARGET"
    exit 0
fi

# === Validate config ===
if [ -n "$CONFIG" ]; then
    case "$CONFIG" in
        gcp-k8s|review|test) ;;
        *) die "Unknown config: '$CONFIG'. Valid options: gcp-k8s, review, test" ;;
    esac
fi

# === Apply preset configs ===
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

# === Setup paths ===
PROJECT_DIR="${PROJECT_DIR:-$(pwd)}"

if [ ! -d "$PROJECT_DIR" ]; then
    die "Directory not found: $PROJECT_DIR"
fi

REPO_NAME=$(basename "$PROJECT_DIR")
SESSION_NAME="nclaude-${REPO_NAME}"
LOG_DIR="/tmp/nclaude/$REPO_NAME"

# === Create log directory ===
mkdir -p "$LOG_DIR" || die "Failed to create log directory: $LOG_DIR"
touch "$LOG_DIR/messages.log" || die "Failed to create messages.log"

# === Check for existing session ===
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "Session '$SESSION_NAME' already exists."
    printf "Kill and recreate? [y/N]: "
    read -r confirm
    case "$confirm" in
        [yY]|[yY][eE][sS])
            tmux kill-session -t "$SESSION_NAME"
            ;;
        *)
            echo "Use 'nclaude-tmux -r $SESSION_NAME' to resume."
            exit 0
            ;;
    esac
fi

# === Create tmux session ===
echo "Creating session: $SESSION_NAME"

tmux new-session -d -s "$SESSION_NAME" -c "$PROJECT_DIR" || die "Failed to create tmux session"

# Split horizontally (top/bottom)
tmux split-window -v -t "$SESSION_NAME" -c "$PROJECT_DIR" || die "Failed to split window"

# Split top pane vertically (left/right)
tmux split-window -h -t "$SESSION_NAME:0.0" -c "$PROJECT_DIR" || die "Failed to split pane"

# Pane layout:
# 0.0 = Claude A (top-left)
# 0.1 = Claude B (top-right)
# 0.2 = Logs (bottom)

# === Set up log watcher ===
tmux send-keys -t "$SESSION_NAME:0.2" "echo '=== nclaude message log [$REPO_NAME] ===' && tail -f $LOG_DIR/messages.log" C-m

# Resize log pane
tmux resize-pane -t "$SESSION_NAME:0.2" -y 12

# === Start Claude sessions ===
if [ -n "$PROMPT_A" ]; then
    # Escape single quotes for shell
    ESCAPED_A=$(printf '%s' "$PROMPT_A" | sed "s/'/'\\\\''/g")
    tmux send-keys -t "$SESSION_NAME:0.0" "claude -p '$ESCAPED_A'" C-m
else
    tmux send-keys -t "$SESSION_NAME:0.0" "# Claude A - run: claude" C-m
    tmux send-keys -t "$SESSION_NAME:0.0" "# Or with prompt: claude -p 'your task'" C-m
fi

if [ -n "$PROMPT_B" ]; then
    ESCAPED_B=$(printf '%s' "$PROMPT_B" | sed "s/'/'\\\\''/g")
    tmux send-keys -t "$SESSION_NAME:0.1" "claude -p '$ESCAPED_B'" C-m
else
    tmux send-keys -t "$SESSION_NAME:0.1" "# Claude B - run: claude" C-m
    tmux send-keys -t "$SESSION_NAME:0.1" "# Or with prompt: claude -p 'your task'" C-m
fi

# Focus on Claude A pane
tmux select-pane -t "$SESSION_NAME:0.0"

# === Attach ===
echo "Attaching to session..."
exec tmux attach-session -t "$SESSION_NAME"
