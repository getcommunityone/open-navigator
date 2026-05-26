#!/bin/bash
set -e

echo "🦷 CommunityOne Open Navigatory - Installation Script"
echo "=================================================="
echo ""

# Install system-level OCR dependency when possible
echo "Checking for Tesseract OCR..."
if command -v tesseract &> /dev/null; then
    echo "✓ Tesseract already installed: $(tesseract --version | head -n 1)"
else
    echo "Tesseract not found. Attempting automatic install..."
    if command -v apt-get &> /dev/null; then
        if [ "$(id -u)" -eq 0 ]; then
            apt-get update && apt-get install -y tesseract-ocr
        elif command -v sudo &> /dev/null; then
            sudo apt-get update && sudo apt-get install -y tesseract-ocr
        else
            echo "⚠ Could not auto-install Tesseract (no root/sudo)."
            echo "  Install manually: apt-get install -y tesseract-ocr"
        fi
    elif command -v brew &> /dev/null; then
        brew install tesseract || true
    else
        echo "⚠ Unsupported package manager for automatic Tesseract install."
        echo "  Install manually, then re-run setup."
    fi

    if command -v tesseract &> /dev/null; then
        echo "✓ Tesseract installed: $(tesseract --version | head -n 1)"
    else
        echo "⚠ Tesseract is still missing. OCR fallback will remain disabled."
    fi
fi

# Check Python version
echo "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "✓ Found Python $PYTHON_VERSION"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
if [ -d "venv" ]; then
    echo "⚠ Virtual environment already exists. Removing old one..."
    rm -rf venv
fi

python3 -m venv venv
echo "✓ Virtual environment created"

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"

# Upgrade pip
echo ""
echo "Upgrading pip..."
python -m pip install --upgrade pip
echo "✓ pip upgraded"

# Install dependencies
echo ""
echo "Installing dependencies (this may take a few minutes)..."
# Use CPU-only requirements if available, otherwise use full requirements
if [ -f "requirements-cpu.txt" ]; then
    echo "Using CPU-only requirements (no GPU needed)..."
    pip install -r requirements-cpu.txt
else
    pip install -r requirements.txt
fi
echo "✓ Dependencies installed"

# Create .env file if it doesn't exist
echo ""
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✓ .env file created"
    echo ""
    echo "⚠ IMPORTANT: Please edit .env and add your API keys:"
    echo "   - OPENAI_API_KEY"
    echo "   - DATABRICKS_HOST"
    echo "   - DATABRICKS_TOKEN"
else
    echo "✓ .env file already exists"
fi

# Create logs directory
echo ""
echo "Creating logs directory..."
mkdir -p logs
echo "✓ logs directory created"

# Installation complete
echo ""
echo "=================================================="
echo "✅ Installation Complete!"
echo "=================================================="
echo ""
echo "To activate the virtual environment, run:"
echo "  source venv/bin/activate"
echo ""
echo "Then you can use the CLI:"
echo "  python main.py --help"
echo "  python main.py serve"
echo ""
echo "Or run the example workflow:"
echo "  python examples/example_workflow.py"
echo ""
echo "Don't forget to configure your .env file with API keys!"
echo ""
