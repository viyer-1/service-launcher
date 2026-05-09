#!/bin/bash
# Setup script for Script Runner

echo "==================================="
echo "Script Runner Setup"
echo "==================================="
echo ""

# Check Python version
echo "Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    echo "✓ Python 3 found: $PYTHON_VERSION"
else
    echo "✗ Python 3 not found. Please install Python 3.8 or higher."
    exit 1
fi

echo ""

# Create virtual environment
echo "Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"

echo ""

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✓ Dependencies installed"

echo ""

# Check if config file exists
if [ ! -f "scripts_config.yaml" ]; then
    echo "✗ scripts_config.yaml not found!"
    echo "  Please create this file or copy the sample configuration."
else
    echo "✓ Configuration file found"
fi

echo ""

# Generate secret key
if [ ! -f ".env" ]; then
    echo "Generating secret key..."
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    echo "SECRET_KEY=$SECRET_KEY" > .env
    echo "✓ Secret key generated and saved to .env"
    echo "  Remember to keep this file secure!"
else
    echo "✓ .env file already exists"
fi

echo ""
echo "==================================="
echo "Setup Complete!"
echo "==================================="
echo ""
echo "To start the server:"
echo "  1. Activate the virtual environment: source venv/bin/activate"
echo "  2. Run the server: python3 script_runner.py"
echo ""
echo "To access from other devices:"
echo "  - Find your local IP: hostname -I | awk '{print \$1}'"
echo "  - Access at: http://YOUR_IP:5000"
echo ""
echo "⚠️  Security Reminder:"
echo "  - This server has no authentication by default"
echo "  - Only use on trusted networks"
echo "  - See README.md for security recommendations"
echo ""
