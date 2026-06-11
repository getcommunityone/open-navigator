<#
.SYNOPSIS
    Root convenience wrapper for the Windows installer.

.DESCRIPTION
    The actual installation logic lives in scripts\deployment\install.ps1. It
    uses paths relative to the current working directory (.venv\,
    requirements.txt, .env.example, logs\), so it must run from the repository
    root - which is exactly where this wrapper lives. Keep this thin wrapper here
    rather than moving the script.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\install.ps1
#>

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
# Run from the repo root so the installer's relative paths resolve correctly.
Push-Location $RepoRoot
try {
    & powershell -ExecutionPolicy Bypass -File (Join-Path $RepoRoot 'scripts\deployment\install.ps1') @args
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
