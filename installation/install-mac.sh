#!/bin/bash
# Service Launcher — macOS Installer
# Registers a LaunchAgent so the app starts automatically at login.
#
# Usage:
#   bash installation/install-mac.sh              # installs for the current user
#   bash installation/install-mac.sh --uninstall  # removes the service
#   bash installation/install-mac.sh --port=8080  # install on a custom port

set -euo pipefail

# ─── Colours ────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${BLUE}→${NC} $*"; }
success() { echo -e "${GREEN}✓${NC} $*"; }
warn()    { echo -e "${YELLOW}⚠${NC} $*"; }
error()   { echo -e "${RED}✗${NC} $*" >&2; }
header()  { echo -e "\n${BOLD}$*${NC}"; }

# ─── Resolve paths ──────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"

INSTALL_USER="$(whoami)"
INSTALL_HOME="$HOME"

VENV_DIR="$INSTALL_HOME/.venvs/service-launcher"
PLIST_LABEL="com.service-launcher"
PLIST_DIR="$INSTALL_HOME/Library/LaunchAgents"
PLIST_FILE="$PLIST_DIR/${PLIST_LABEL}.plist"
PORT=5000

# ─── Argument parsing ────────────────────────────────────────────────────────
UNINSTALL=false
for arg in "$@"; do
    case $arg in
        --uninstall|-u) UNINSTALL=true ;;
        --port=*)       PORT="${arg#*=}" ;;
        --help|-h)
            echo "Usage: bash installation/install-mac.sh [--uninstall] [--port=5000]"
            exit 0
            ;;
    esac
done

# ─── Uninstall ───────────────────────────────────────────────────────────────
if $UNINSTALL; then
    header "Uninstalling Service Launcher"
    if launchctl list | grep -q "$PLIST_LABEL" 2>/dev/null; then
        info "Stopping service..."
        launchctl unload "$PLIST_FILE" 2>/dev/null || true
        success "Service stopped"
    else
        info "Service not currently running"
    fi
    if [[ -f "$PLIST_FILE" ]]; then
        rm "$PLIST_FILE"
        success "LaunchAgent removed: $PLIST_FILE"
    else
        warn "LaunchAgent not found — already uninstalled?"
    fi
    echo ""
    success "Uninstall complete. App files in $SCRIPT_DIR were NOT deleted."
    exit 0
fi

# ─── Banner ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}Service Launcher — macOS Installer${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  User:        $INSTALL_USER"
echo "  App dir:     $APP_DIR"
echo "  Virtual env: $VENV_DIR"
echo "  Port:        $PORT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ─── Checks ───────────────────────────────────────────────────────────────────
header "1. Checking requirements"

if [[ ! -d "$APP_DIR" ]]; then
    error " directory not found at $APP_DIR"
    error "Run this script from the service-launcher repository root."
    exit 1
fi
success "App directory found"

if ! command -v python3 &>/dev/null; then
    error "python3 not found."
    error "Install Python 3 via Homebrew:  brew install python3"
    error "Or download from:               https://www.python.org/downloads/"
    exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if [[ "$PY_MAJOR" -lt 3 || ("$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 8) ]]; then
    error "Python 3.8 or higher required (found $PY_VERSION)"
    exit 1
fi
success "Python $PY_VERSION"

if ! python3 -c "import venv" &>/dev/null; then
    error "python3 venv module not available."
    error "Try: brew install python3"
    exit 1
fi

# ─── Virtual environment ──────────────────────────────────────────────────────
header "2. Setting up virtual environment"

if [[ -d "$VENV_DIR" ]]; then
    success "Virtual env already exists at $VENV_DIR"
else
    info "Creating virtual environment at $VENV_DIR..."
    mkdir -p "$(dirname "$VENV_DIR")"
    python3 -m venv "$VENV_DIR"
    success "Virtual environment created"
fi

info "Installing/updating dependencies..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"
success "Dependencies installed"

# ─── Config file ─────────────────────────────────────────────────────────────
header "3. Configuration"

CONFIG_FILE="$APP_DIR/scripts_config.yaml"
EXAMPLE_FILE="$APP_DIR/scripts_config.yaml.example"

if [[ ! -f "$CONFIG_FILE" ]]; then
    if [[ -f "$EXAMPLE_FILE" ]]; then
        cp "$EXAMPLE_FILE" "$CONFIG_FILE"
        success "Created scripts_config.yaml from example"
        warn "Edit $CONFIG_FILE to add your own scripts"
    else
        error "scripts_config.yaml not found and no example file available"
        exit 1
    fi
else
    success "scripts_config.yaml already exists"
fi

# ─── LaunchAgent plist ────────────────────────────────────────────────────────
header "4. Installing LaunchAgent (auto-start at login)"

mkdir -p "$PLIST_DIR"

# Unload any existing instance cleanly
if launchctl list | grep -q "$PLIST_LABEL" 2>/dev/null; then
    info "Stopping existing instance..."
    launchctl unload "$PLIST_FILE" 2>/dev/null || true
fi

cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_LABEL}</string>

    <key>ProgramArguments</key>
    <array>
        <string>${VENV_DIR}/bin/python3</string>
        <string>${APP_DIR}/app.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>${APP_DIR}</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>SERVICE_LAUNCHER_PORT</key>
        <string>${PORT}</string>
        <key>VIRTUAL_ENV</key>
        <string>${VENV_DIR}</string>
        <key>PATH</key>
        <string>${VENV_DIR}/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>

    <!-- Start automatically at login -->
    <key>RunAtLoad</key>
    <true/>

    <!-- Restart automatically if it crashes -->
    <key>KeepAlive</key>
    <true/>

    <!-- Log output -->
    <key>StandardOutPath</key>
    <string>${APP_DIR}/script_runner.log</string>
    <key>StandardErrorPath</key>
    <string>${APP_DIR}/script_runner.log</string>
</dict>
</plist>
EOF

success "LaunchAgent installed: $PLIST_FILE"

# ─── Start ────────────────────────────────────────────────────────────────────
header "5. Starting service"

launchctl load -w "$PLIST_FILE"

# Give it a moment to come up
sleep 2

if launchctl list | grep -q "$PLIST_LABEL" 2>/dev/null; then
    success "Service is running"
else
    warn "Service may still be starting. Check logs:"
    warn "  tail -f $APP_DIR/script_runner.log"
fi

# ─── Done ─────────────────────────────────────────────────────────────────────
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null \
    || ipconfig getifaddr en1 2>/dev/null \
    || echo "your-mac-ip")

echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}${BOLD}  Installation complete!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "  Open in your browser:"
echo -e "  ${BOLD}http://localhost:${PORT}${NC}"
echo -e "  ${BOLD}http://${LOCAL_IP}:${PORT}${NC}   (from other devices on the network)"
echo ""
echo "  Service management:"
echo "    launchctl start  $PLIST_LABEL"
echo "    launchctl stop   $PLIST_LABEL"
echo "    tail -f $APP_DIR/script_runner.log   # live logs"
echo ""
echo "  Config file (hot-reloaded — no restart needed):"
echo "    $APP_DIR/scripts_config.yaml"
echo ""
echo "  To uninstall: bash installation/install-mac.sh --uninstall"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
