#!/bin/bash

echo "=================================="
echo "Hypnonyx Multi-Agent System Setup"
echo "=================================="

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate || . venv/Scripts/activate

echo "✓ Virtual environment created"

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "✓ Dependencies installed"

# Create .env if not exists
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env file from example..."
    cp .env.example .env
    echo "✓ .env created - Please edit it with your configuration"
fi

# Create necessary directories
echo ""
echo "Creating directories..."
mkdir -p memory docs projects

echo "✓ Directories created"

# Check for MQTT
echo ""
echo "Checking for MQTT broker..."
if command -v mosquitto &> /dev/null; then
    echo "✓ Mosquitto found"
else
    echo "⚠ Mosquitto not found - system will use in-memory fallback"
    echo "  To install: sudo apt-get install mosquitto (Ubuntu/Debian)"
    echo "            : brew install mosquitto (macOS)"
fi

echo ""
echo "=================================="
echo "Setup Complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "1. Activate venv: source venv/bin/activate"
echo "2. Run: python main.py --project my_first_project"
echo ""
