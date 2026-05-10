#!/bin/bash
# Launcher script for Service Launcher (FastAPI + Frontend)

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo ""
echo "======================================"
echo "  Service Launcher Launcher"
echo "======================================"
echo ""

# Find and activate virtual environment
echo -e "${BLUE}Activating virtual environment...${NC}"

if [[ -f "$HOME/.venvs/service-launcher/bin/activate" ]]; then
    VENV_DIR="$HOME/.venvs/service-launcher"
elif [[ -f "$(dirname "$0")/venv/bin/activate" ]]; then
    VENV_DIR="$(dirname "$0")/venv"
else
    echo -e "${RED}✗ No virtual environment found.${NC}"
    echo "  Run: bash installation/install.sh   to set everything up automatically."
    exit 1
fi

source "$VENV_DIR/bin/activate"
echo -e "${GREEN}✓ Virtual environment activated ($VENV_DIR)${NC}"

echo ""

# Check if config file exists
if [ ! -f "scripts_config.yaml" ]; then
    echo -e "${RED}✗ scripts_config.yaml not found!${NC}"
    echo "  Please create this file or copy the sample configuration."
    exit 1
fi

echo -e "${GREEN}✓ Configuration file found${NC}"
echo ""

# Get local IP for display
LOCAL_IP=$(hostname -I | awk '{print $1}')

echo "======================================"
echo -e "${GREEN}Starting FastAPI Server...${NC}"
echo "======================================"

echo ""
echo "Access the application at:"
echo "  • Local:   http://localhost:5000"
echo "  • Network: http://${LOCAL_IP}:5000"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the FastAPI application
python3 app.py