<#
.SYNOPSIS
    Start all three Open Navigator services on Windows (PowerShell).

.DESCRIPTION
    Windows-native equivalent of start-all.sh. start-all.sh uses tmux, which is
    not available on Windows, so this launches each service in its own
    PowerShell window instead:
      - API Backend   (FastAPI)   http://localhost:8000
      - React App     (Vite)      http://localhost:5173
      - Documentation (Docusaurus) http://localhost:3000

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\start-all.ps1
#>

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

Write-Host "Starting Open Navigator"
Write-Host "=========================================="
Write-Host ""

# --- Locate the virtual environment ------------------------------------------
# install.ps1 / Makefile create `venv`; start-all.sh / some docs use `.venv`.
# Accept whichever exists.
$venvDir = $null
foreach ($candidate in @("venv", ".venv")) {
    if (Test-Path (Join-Path $RepoRoot "$candidate\Scripts\python.exe")) {
        $venvDir = $candidate
        break
    }
}
if ($null -eq $venvDir) {
    Write-Host "[!] Virtual environment not found. Run .\install.ps1 first." -ForegroundColor Yellow
    exit 1
}
$venvActivate = Join-Path $RepoRoot "$venvDir\Scripts\Activate.ps1"

# --- Ensure frontend deps are installed --------------------------------------
if (-not (Test-Path "web_app\node_modules")) {
    Write-Host "Installing web_app dependencies..." -ForegroundColor Yellow
    Push-Location web_app; npm install; Pop-Location
}
if (-not (Test-Path "web_docs\node_modules")) {
    Write-Host "Installing documentation site dependencies..." -ForegroundColor Yellow
    Push-Location web_docs; npm install; Pop-Location
}
Write-Host "[OK] Dependencies OK"
Write-Host ""

# --- Free the ports we need --------------------------------------------------
Write-Host "Checking for processes on ports 3000/5173/8000..."
foreach ($port in @(3000, 5173, 8000)) {
    try {
        $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        foreach ($conn in $conns) {
            $procId = $conn.OwningProcess
            if ($procId -and $procId -ne 0) {
                Write-Host "[!] Killing process on port $port (PID: $procId)" -ForegroundColor Yellow
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            }
        }
    } catch {
        # Get-NetTCPConnection unavailable (rare) — skip; the dev servers will
        # report the port conflict themselves.
    }
}
Write-Host "[OK] Ports cleared"
Write-Host ""

# --- Launch each service in its own window -----------------------------------
function Start-ServiceWindow {
    param([string]$Title, [string]$Command)
    # -NoExit keeps the window open so logs/errors stay visible.
    Start-Process powershell -ArgumentList @(
        '-NoExit', '-Command',
        "`$Host.UI.RawUI.WindowTitle = '$Title'; $Command"
    )
}

Write-Host "Launching services in separate windows..."

Start-ServiceWindow -Title "Open Navigator - API" `
    -Command "Set-Location '$RepoRoot'; & '$venvActivate'; Write-Host 'Starting API Backend...'; python main.py serve"

Start-ServiceWindow -Title "Open Navigator - App" `
    -Command "Set-Location '$RepoRoot\web_app'; Write-Host 'Starting React Dashboard...'; npm run dev"

Start-ServiceWindow -Title "Open Navigator - Docs" `
    -Command "Set-Location '$RepoRoot\web_docs'; Write-Host 'Starting Documentation Site...'; npm start"

Write-Host ""
Write-Host "[OK] All services launched!"
Write-Host ""
Write-Host "Services:"
Write-Host "  - MAIN APP:       http://localhost:5173 (Open Navigator - search, filters, heatmap)"
Write-Host "  - Documentation:  http://localhost:3000 (Docusaurus - guides & tutorials)"
Write-Host "  - API Backend:    http://localhost:8000 (FastAPI)"
Write-Host "  - API Docs:       http://localhost:8000/docs"
Write-Host ""
Write-Host "Start here: http://localhost:5173"
Write-Host ""
Write-Host "To stop: close the three service windows (or use stop-all on each port)."
Write-Host ""

$reply = Read-Host "Open main application in browser? [Y/n]"
if ($reply -notmatch '^[Nn]') {
    Start-Sleep -Seconds 3  # give the dev server a moment
    Start-Process "http://localhost:5173"
}
