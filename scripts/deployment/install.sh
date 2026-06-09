#!/bin/bash
set -e

echo "🦷 CommunityOne Open Navigator - Installation Script"
echo "=================================================="
echo ""

# Install system-level dependencies when possible.
#
# Two things need OS packages, not just pip:
#   - Tesseract OCR        (runtime, for the OCR fallback)
#   - libxml2 + libxslt    (build-time headers for lxml — pip compiles lxml
#                           from source on distros without a matching wheel,
#                           e.g. a fresh Fedora, and the build fails without
#                           the *-devel/*-dev headers + a C compiler)
#
# run_root: run a privileged command as root directly, via sudo, or warn.
run_root() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    elif command -v sudo &> /dev/null; then
        sudo "$@"
    else
        echo "⚠ Need root to run: $*"
        echo "  Re-run as root, or run that command manually, then re-run setup."
        return 1
    fi
}

echo "Checking system dependencies (Tesseract OCR + libxml2/libxslt headers)..."
if command -v apt-get &> /dev/null; then
    # Debian/Ubuntu. libxslt1-dev pulls in libxml2-dev; build-essential gives the compiler.
    run_root apt-get update || true
    run_root apt-get install -y tesseract-ocr libxml2-dev libxslt1-dev build-essential || \
        echo "⚠ Could not auto-install system deps via apt-get; install them manually if pip fails on lxml."
elif command -v dnf &> /dev/null; then
    # Fedora/RHEL/CentOS Stream.
    run_root dnf install -y tesseract libxml2-devel libxslt-devel gcc python3-devel || \
        echo "⚠ Could not auto-install system deps via dnf; install them manually if pip fails on lxml."
elif command -v yum &> /dev/null; then
    # Older RHEL/CentOS.
    run_root yum install -y tesseract libxml2-devel libxslt-devel gcc python3-devel || \
        echo "⚠ Could not auto-install system deps via yum; install them manually if pip fails on lxml."
elif command -v pacman &> /dev/null; then
    # Arch.
    run_root pacman -Sy --noconfirm tesseract libxml2 libxslt gcc || \
        echo "⚠ Could not auto-install system deps via pacman; install them manually if pip fails on lxml."
elif command -v zypper &> /dev/null; then
    # openSUSE.
    run_root zypper install -y tesseract-ocr libxml2-devel libxslt-devel gcc python3-devel || \
        echo "⚠ Could not auto-install system deps via zypper; install them manually if pip fails on lxml."
elif command -v brew &> /dev/null; then
    # macOS. Homebrew ships lxml wheels via pip normally, but keep the libs handy.
    brew install tesseract libxml2 libxslt || true
else
    echo "⚠ Unsupported package manager. Install these manually before continuing:"
    echo "    - tesseract (OCR)"
    echo "    - libxml2 + libxslt development headers (libxml2-devel/libxslt-devel or libxml2-dev/libxslt1-dev)"
    echo "    - a C compiler (gcc) + Python development headers"
fi

if command -v tesseract &> /dev/null; then
    echo "✓ Tesseract available: $(tesseract --version | head -n 1)"
else
    echo "⚠ Tesseract is still missing. OCR fallback will remain disabled."
fi

# Check Python version
echo "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "✓ Found Python $PYTHON_VERSION"

# Python 3.14+ compatibility: some transitive deps (e.g. `whenever`) build a
# Rust extension via PyO3, which currently supports up to Python 3.13. On 3.14+
# that build hard-fails ("configured Python interpreter version is newer than
# PyO3's maximum supported version"). Tell those packages to skip the Rust
# extension and fall back to their (slower) pure-Python implementation so the
# install still succeeds.
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f2)
if [ "${PYTHON_MINOR:-0}" -ge 14 ]; then
    echo "⚠ Python $PYTHON_VERSION detected — newer than PyO3's max supported (3.13)."
    echo "  Forcing pure-Python builds for Rust-backed deps (whenever) to avoid build failures."
    export WHENEVER_NO_BUILD_RUST_EXT=1
    # Belt-and-suspenders: if a dep still tries to compile against the stable ABI,
    # let PyO3 build forward-compatibly instead of erroring out.
    export PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1
fi

# Create virtual environment
echo ""
echo "Creating virtual environment..."
if [ -d ".venv" ]; then
    echo "⚠ Virtual environment already exists. Removing old one..."
    rm -rf .venv
fi

python3 -m venv .venv
echo "✓ Virtual environment created"

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source .venv/bin/activate
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
echo "  source .venv/bin/activate"
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
