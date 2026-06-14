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

# Install the local workspace libraries (packages/*) as editable, top-level
# importable modules. requirements.txt only pins third-party deps; the API
# entrypoint imports agents/ingestion/config/llm/etc. which now live under
# packages/* (there is no top-level agents/ tree anymore), so without this step
# `python main.py serve` fails with `ModuleNotFoundError: No module named
# 'agents'`. --no-deps keeps the dependency closure exactly as requirements.txt
# pins it (these packages' own third-party deps are already installed above).
# This is the full runtime set the Dockerfile installs (eager + lazy imports).
echo ""
echo "Installing local workspace packages (editable)..."
pip install --no-deps \
    -e packages/core -e packages/core-lib -e packages/datamodels \
    -e packages/agents -e packages/scrapers -e packages/ingestion \
    -e packages/llm -e packages/accessibility -e packages/hosting
echo "✓ Workspace packages installed"

# Infrastructure CLIs (Azure CLI + Terraform) for the infra/azure subscriptions
# Terraform. Opt-in — most contributors don't touch it — enable with:
#     INSTALL_INFRA_TOOLS=1 ./install.sh
# Prefers the OS package manager; falls back to a rootless install into .venv
# (azure-cli via pip, terraform binary into .venv/bin) when sudo isn't available.
TERRAFORM_VERSION="${TERRAFORM_VERSION:-1.9.8}"

# Symlink a tool installed inside .venv into ~/.local/bin so it's on PATH without
# activating the venv (the rootless fallback otherwise hides az/terraform). venv
# console scripts use an absolute shebang, so the symlink works from any shell.
link_into_local_bin() {
    local name="$1" target="$2"
    [ -e "$target" ] || return 0
    mkdir -p "$HOME/.local/bin"
    ln -sf "$(pwd)/$target" "$HOME/.local/bin/$name"
    case ":$PATH:" in
        *":$HOME/.local/bin:"*) echo "✓ Linked $name into ~/.local/bin (on PATH)" ;;
        *) echo "⚠ Linked $name into ~/.local/bin — add it to PATH: export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
    esac
}

install_azure_cli() {
    if command -v az &> /dev/null; then
        echo "✓ Azure CLI already installed: $(az version --query '"azure-cli"' -o tsv 2>/dev/null)"
        return 0
    fi
    echo "Installing Azure CLI..."
    if command -v brew &> /dev/null; then
        brew install azure-cli || true
    elif command -v apt-get &> /dev/null; then
        curl -sL https://aka.ms/InstallAzureCLIDeb | run_root bash || true
    elif command -v dnf &> /dev/null; then
        run_root rpm --import https://packages.microsoft.com/keys/microsoft.asc || true
        run_root dnf install -y azure-cli || true
    elif command -v zypper &> /dev/null; then
        run_root zypper install -y azure-cli || true
    fi
    if ! command -v az &> /dev/null; then
        echo "⚠ No system install path; installing azure-cli into .venv via pip (rootless)..."
        if pip install --upgrade azure-cli; then
            link_into_local_bin az ".venv/bin/az"
        else
            echo "⚠ Could not install Azure CLI. Install manually: https://learn.microsoft.com/cli/azure/install-azure-cli"
        fi
    fi
}

install_terraform() {
    if command -v terraform &> /dev/null; then
        echo "✓ Terraform already installed: $(terraform version | head -n 1)"
        return 0
    fi
    echo "Installing Terraform ${TERRAFORM_VERSION}..."
    if command -v brew &> /dev/null; then
        brew tap hashicorp/tap 2>/dev/null && brew install hashicorp/tap/terraform || true
    fi
    if ! command -v terraform &> /dev/null; then
        # Rootless: drop the official binary into .venv/bin (on PATH once activated).
        local os arch url tmp
        os="$(uname -s | tr '[:upper:]' '[:lower:]')"
        arch="$(uname -m)"
        case "$arch" in x86_64) arch=amd64 ;; aarch64 | arm64) arch=arm64 ;; esac
        url="https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_${os}_${arch}.zip"
        tmp="$(mktemp -d)"
        if curl -fsSL "$url" -o "$tmp/terraform.zip"; then
            # Use the venv's python (active here) to unzip — no `unzip` dependency.
            python - "$tmp/terraform.zip" <<'PY' && echo "✓ Terraform installed to .venv/bin"
import os, stat, sys, zipfile
zipfile.ZipFile(sys.argv[1]).extractall(".venv/bin")
p = ".venv/bin/terraform"
os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
PY
            link_into_local_bin terraform ".venv/bin/terraform"
        else
            echo "⚠ Could not download Terraform. Install manually: https://developer.hashicorp.com/terraform/install"
        fi
        rm -rf "$tmp"
    fi
}

if [ "${INSTALL_INFRA_TOOLS:-0}" = "1" ]; then
    echo ""
    echo "Installing infrastructure CLIs (Azure CLI + Terraform) [INSTALL_INFRA_TOOLS=1]..."
    install_azure_cli
    install_terraform
fi

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
if [ "${INSTALL_INFRA_TOOLS:-0}" != "1" ]; then
    echo "Working on infra/azure (Azure subscriptions)? Re-run with the infra CLIs:"
    echo "  INSTALL_INFRA_TOOLS=1 ./install.sh   # installs Azure CLI + Terraform"
    echo ""
fi
