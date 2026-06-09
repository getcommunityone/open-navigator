<#
.SYNOPSIS
    CommunityOne Open Navigator - Windows installation script (PowerShell).

.DESCRIPTION
    Windows-native equivalent of scripts/deployment/install.sh. Creates the
    Python virtual environment, installs the backend dependencies from
    requirements.txt (NOT `uv sync` — see the note below), seeds .env, and
    creates the logs directory.

    Why pip + requirements.txt and not `uv sync`:
      The root pyproject.toml is a *uv workspace* whose members are only
      packages/*. `uv sync` installs those workspace libraries but does NOT
      install the top-level requirements.txt — so the dev tooling
      (pytest/black/ruff) and runtime deps like yt-dlp are left out. The
      backend is installed from requirements.txt, which is the complete set.

    Run from the repository root (paths are relative to the CWD):
        powershell -ExecutionPolicy Bypass -File scripts\deployment\install.ps1
    or via the thin root wrapper:
        .\install.ps1
#>

$ErrorActionPreference = 'Stop'

Write-Host "CommunityOne Open Navigator - Installation Script (Windows)"
Write-Host "=================================================="
Write-Host ""

# --- Resolve a Python launcher ------------------------------------------------
# Prefer the `py` launcher (ships with python.org installers), fall back to
# `python` on PATH. We need a real CPython, not the Windows Store stub.
function Resolve-Python {
    foreach ($candidate in @(
        @{ Exe = 'py';     Args = @('-3') },
        @{ Exe = 'python'; Args = @() }
    )) {
        $cmd = Get-Command $candidate.Exe -ErrorAction SilentlyContinue
        if ($null -eq $cmd) { continue }
        try {
            $ver = & $candidate.Exe @($candidate.Args + '--version') 2>&1
            if ($ver -match 'Python\s+3\.\d+') {
                return [pscustomobject]@{ Exe = $candidate.Exe; Args = $candidate.Args; Version = "$ver".Trim() }
            }
        } catch { }
    }
    return $null
}

Write-Host "Checking Python version..."
$py = Resolve-Python
if ($null -eq $py) {
    Write-Host "[X] Error: Python 3 is not installed (or only the Windows Store stub is present)." -ForegroundColor Red
    Write-Host "    Install Python 3.11-3.13 from https://www.python.org/downloads/windows/"
    Write-Host "    (tick 'Add python.exe to PATH' in the installer), then re-run this script."
    exit 1
}

# Parse MAJOR.MINOR from e.g. "Python 3.12.3"
$pyVersion = ($py.Version -replace '^Python\s+', '')
$verParts  = $pyVersion.Split('.')
$pyMajor   = [int]$verParts[0]
$pyMinor   = [int]$verParts[1]
Write-Host "[OK] Found Python $pyMajor.$pyMinor (via '$($py.Exe)')"

# Python 3.14+ compatibility: some transitive deps (e.g. `whenever`) build a
# Rust extension via PyO3, which currently supports up to Python 3.13. On 3.14+
# that build hard-fails. Tell those packages to skip the Rust extension and use
# their (slower) pure-Python implementation so the install still succeeds.
if ($pyMinor -ge 14) {
    Write-Host "[!] Python $pyMajor.$pyMinor detected - newer than PyO3's max supported (3.13)." -ForegroundColor Yellow
    Write-Host "    Forcing pure-Python builds for Rust-backed deps (whenever) to avoid build failures."
    $env:WHENEVER_NO_BUILD_RUST_EXT = "1"
    $env:PYO3_USE_ABI3_FORWARD_COMPATIBILITY = "1"
}

# --- Optional system dependency: Tesseract OCR --------------------------------
# Unlike Linux, lxml ships Windows wheels, so no libxml2/libxslt headers are
# needed. The only optional native tool is Tesseract (OCR fallback). Try winget,
# then Chocolatey; otherwise tell the user how to get it. Never fatal.
Write-Host ""
Write-Host "Checking optional system dependency (Tesseract OCR)..."
if (Get-Command tesseract -ErrorAction SilentlyContinue) {
    Write-Host "[OK] Tesseract available: $((tesseract --version 2>&1 | Select-Object -First 1))"
} elseif (Get-Command winget -ErrorAction SilentlyContinue) {
    Write-Host "Installing Tesseract via winget..."
    try {
        winget install --id UB-Mannheim.TesseractOCR --accept-source-agreements --accept-package-agreements -e
    } catch {
        Write-Host "[!] winget could not install Tesseract; OCR fallback will stay disabled." -ForegroundColor Yellow
    }
} elseif (Get-Command choco -ErrorAction SilentlyContinue) {
    Write-Host "Installing Tesseract via Chocolatey..."
    try { choco install -y tesseract } catch {
        Write-Host "[!] choco could not install Tesseract; OCR fallback will stay disabled." -ForegroundColor Yellow
    }
} else {
    Write-Host "[!] Tesseract not found and no winget/choco available." -ForegroundColor Yellow
    Write-Host "    OCR is optional. To enable it, install the UB-Mannheim Tesseract build:"
    Write-Host "    https://github.com/UB-Mannheim/tesseract/wiki"
}

# --- Virtual environment ------------------------------------------------------
Write-Host ""
Write-Host "Creating virtual environment..."
if (Test-Path ".venv") {
    Write-Host "[!] Virtual environment already exists. Removing old one..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force ".venv"
}
& $py.Exe @($py.Args + @('-m', 'venv', '.venv'))
Write-Host "[OK] Virtual environment created"

# Use the venv's interpreter directly (robust regardless of activation state /
# ExecutionPolicy). All subsequent pip calls go through this python.exe.
$venvPython = Join-Path (Get-Location) ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "[X] Expected venv interpreter not found at $venvPython" -ForegroundColor Red
    exit 1
}

# --- pip + dependencies -------------------------------------------------------
Write-Host ""
Write-Host "Upgrading pip..."
& $venvPython -m pip install --upgrade pip
Write-Host "[OK] pip upgraded"

Write-Host ""
Write-Host "Installing dependencies (this may take a few minutes)..."
# Prefer CPU-only requirements (no GPU needed) when present, matching install.sh.
if (Test-Path "requirements-cpu.txt") {
    Write-Host "Using CPU-only requirements (no GPU needed)..."
    & $venvPython -m pip install -r requirements-cpu.txt
} else {
    & $venvPython -m pip install -r requirements.txt
}
Write-Host "[OK] Dependencies installed"

# --- .env ---------------------------------------------------------------------
Write-Host ""
if (-not (Test-Path ".env")) {
    Write-Host "Creating .env file from template..."
    Copy-Item ".env.example" ".env"
    Write-Host "[OK] .env file created"
    Write-Host ""
    Write-Host "[!] IMPORTANT: edit .env and set at least NEON_DATABASE_URL_DEV" -ForegroundColor Yellow
    Write-Host "    (points the API at the local Postgres warehouse on localhost:5433)."
} else {
    Write-Host "[OK] .env file already exists"
}

# --- logs ---------------------------------------------------------------------
Write-Host ""
Write-Host "Creating logs directory..."
New-Item -ItemType Directory -Force -Path "logs" | Out-Null
Write-Host "[OK] logs directory created"

# --- Done ---------------------------------------------------------------------
Write-Host ""
Write-Host "=================================================="
Write-Host "Installation Complete!"
Write-Host "=================================================="
Write-Host ""
Write-Host "To activate the virtual environment, run:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host ""
Write-Host "Then you can use the CLI:"
Write-Host "  python main.py --help"
Write-Host "  python main.py serve"
Write-Host ""
Write-Host "Install the frontend, then launch all three services:"
Write-Host "  cd web_app;  npm install; cd .."
Write-Host "  cd web_docs; npm install; cd .."
Write-Host "  .\start-all.ps1"
Write-Host ""
Write-Host "Don't forget to configure your .env file with API keys!"
Write-Host ""
