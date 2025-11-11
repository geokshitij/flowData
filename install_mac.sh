#!/bin/bash

# USGS Data Downloader - Mac Installation Script
# This script sets up the Python environment and installs all dependencies

echo "=========================================="
echo "USGS Data Downloader - Mac Installation"
echo "=========================================="
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null
then
    echo "❌ Python 3 is not installed."
    echo "Please install Python 3 from https://www.python.org/downloads/"
    echo "Or use Homebrew: brew install python3"
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"
echo ""

# Check if pip is installed
if ! command -v pip3 &> /dev/null
then
    echo "❌ pip3 is not installed."
    echo "Installing pip..."
    python3 -m ensurepip --upgrade
fi

echo "✅ pip3 found: $(pip3 --version)"
echo ""

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📥 Installing Python dependencies..."
pip install -r requirements.txt

echo ""
echo "=========================================="
echo "✅ Installation Complete!"
echo "=========================================="
echo ""
echo "To run the application:"
echo "  1. Activate the virtual environment:"
echo "     source venv/bin/activate"
echo ""
echo "  2. Run the application:"
echo "     python3 app.py"
echo ""
echo "  3. Open your browser and go to:"
echo "     http://127.0.0.1:5001"
echo ""
echo "To deactivate the virtual environment later, type:"
echo "     deactivate"
echo ""
