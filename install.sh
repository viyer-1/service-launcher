#!/bin/bash
# Service Launcher — One-shot installer
# Installs as a systemd service that starts automatically on boot.
#
# Usage:
#   bash install.sh              # installs for the current user
#   sudo bash install.sh         # same (uses SUDO_USER if available)
#   bash install.sh --uninstall  # removes the service

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
APP_DIR="$SCRIPT_DIR"

# Determine the real (non-root) user to install for
if [[ -n "${SUDO_USER:-}" ]]; then
    INSTALL_USER="$SUDO_USER"
else
    INSTALL_USER="$USER"
fi
INSTALL_HOME=$(eval echo "~$INSTALL_USER")

VENV_DIR="$INSTALL_HOME/.venvs/service-launcher"
SERVICE_NAME="script-runner"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
PORT=5000

# ─── Argument parsing ────────────────────────────────────────────────────────
UNINSTALL=false
for arg in "$@"; do
    case $arg in
        --uninstall|-u) UNINSTALL=true ;;
        --port=*)       PORT="${arg#*=}" ;;
        --help|-h)
            echo "Usage: bash install.sh [--uninstall] [--port=5000]"
            exit 0
            ;;
    esac
done

# ─── Uninstall ────────────────────────────────────────────────────────────────
if $UNINSTALL; then
    header "Uninstalling Service Launcher"
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        info "Stopping service..."
        sudo systemctl stop "$SERVICE_NAME"
    fi
    if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
        info "Disabling service..."
        sudo systemctl disable "$SERVICE_NAME"
    fi
    if [[ -f "$SERVICE_FILE" ]]; then
        sudo rm "$SERVICE_FILE"
        sudo systemctl daemon-reload
        success "Service removed"
    else
        warn "Service file not found — already uninstalled?"
    fi
    echo ""
    success "Uninstall complete. The app files in $SCRIPT_DIR were NOT deleted."
    exit 0
fi

# ─── Banner ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}Service Launcher — Installer${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  User:        $INSTALL_USER"
echo "  App dir:     $APP_DIR"
echo "  Virtual env: $VENV_DIR"
echo "  Port:        $PORT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ─── Checks ───────────────────────────────────────────────────────────────────
header "1. Checking requirements"

if [[ ! -f "$APP_DIR/app.py" ]]; then
    error "app.py not found at $APP_DIR"
    exit 1
fi
success "App directory found"

if ! command -v systemctl &>/dev/null; then
    error "systemd not found. This installer requires a systemd-based Linux distribution."
    error "Most modern distros (Ubuntu, Debian, Fedora, Arch, etc.) use systemd."
    error "To run manually instead: cd v3 && ./start.sh"
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    error "python3 not found."
    error "Install it via your package manager, e.g.:"
    error "  Debian/Ubuntu:  sudo apt install python3 python3-venv"
    error "  Fedora/RHEL:    sudo dnf install python3"
    error "  Arch:           sudo pacman -S python"
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
    error "python3-venv module not found."
    error "Install it via your package manager, e.g.:"
    error "  Debian/Ubuntu:  sudo apt install python3-venv"
    error "  Fedora/RHEL:    sudo dnf install python3"
    error "  Arch:           (included with python)"
    exit 1
fi

if ! command -v sudo &>/dev/null; then
    error "sudo is required to install the systemd service."
    error "Install sudo or run as root with: su -c 'bash install.sh'"
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

# ─── Systemd service ──────────────────────────────────────────────────────────
header "4. Installing systemd service"

info "Writing service file to $SERVICE_FILE..."
sudo bash -c "cat > $SERVICE_FILE" << EOF
[Unit]
Description=Service Launcher - Web-Based Script Runner
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=$INSTALL_USER
Group=$INSTALL_USER
WorkingDirectory=$APP_DIR

Environment="PATH=$VENV_DIR/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="VIRTUAL_ENV=$VENV_DIR"
Environment="SERVICE_LAUNCHER_PORT=$PORT"

ExecStart=$VENV_DIR/bin/python3 $APP_DIR/app.py

Restart=always
RestartSec=10
TimeoutStopSec=30
KillMode=mixed
KillSignal=SIGTERM

StandardOutput=journal
StandardError=journal
SyslogIdentifier=script-runner
OOMScoreAdjust=-100

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
success "Service file installed"

info "Enabling service to start on boot..."
sudo systemctl enable "$SERVICE_NAME"
success "Service enabled"

# ─── Start ────────────────────────────────────────────────────────────────────
header "5. Starting service"

if systemctl is-active --quiet "$SERVICE_NAME"; then
    info "Restarting running service..."
    sudo systemctl restart "$SERVICE_NAME"
else
    sudo systemctl start "$SERVICE_NAME"
fi

# Wait up to 5 seconds for it to come up
for i in {1..5}; do
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        break
    fi
    sleep 1
done

if systemctl is-active --quiet "$SERVICE_NAME"; then
    success "Service is running"
else
    error "Service failed to start. Check logs with: journalctl -u $SERVICE_NAME -n 50"
    exit 1
fi

# ─── Done ─────────────────────────────────────────────────────────────────────
LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "your-server-ip")

echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}${BOLD}  Installation complete!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "  Open in your browser:"
echo -e "  ${BOLD}http://${LOCAL_IP}:${PORT}${NC}"
echo ""
echo "  Service management:"
echo "    sudo systemctl status $SERVICE_NAME"
echo "    sudo systemctl restart $SERVICE_NAME"
echo "    journalctl -u $SERVICE_NAME -f      # live logs"
echo ""
echo "  To add or edit scripts, use the web UI"
echo "  or edit: $CONFIG_FILE"
echo ""
echo "  To uninstall: bash install.sh --uninstall"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
