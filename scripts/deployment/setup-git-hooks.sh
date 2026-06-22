#!/bin/bash
# Install git hooks (pre-commit + optional pre-push build guard).
# Run once from the repo root after cloning: ./scripts/deployment/setup-git-hooks.sh

set -euo pipefail

# Avoid "setlocale: LC_ALL: cannot change locale (en_US.UTF-8)" in hook subprocesses
# when the host IDE sets en_US.UTF-8 but that locale is not generated.
export LC_ALL="${LC_ALL:-C.UTF-8}"
export LANG="${LANG:-C.UTF-8}"

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

echo "🔧 Setting up git hooks..."
echo ""

# Drop a bad absolute core.hooksPath if something pointed hooks at another clone's
# .git/hooks (breaks worktrees and triggers "No .pre-commit-config.yaml" errors).
if git config --local --get core.hooksPath >/dev/null 2>&1; then
    echo "⚠️  Unsetting local core.hooksPath (use default .git/hooks per clone/worktree)"
    git config --local --unset core.hooksPath
fi

PRE_COMMIT=""
if [ -x ".venv/bin/pre-commit" ]; then
    PRE_COMMIT=".venv/bin/pre-commit"
elif command -v pre-commit >/dev/null 2>&1; then
    PRE_COMMIT="pre-commit"
fi

if [ -n "$PRE_COMMIT" ] && [ -f ".pre-commit-config.yaml" ]; then
    "$PRE_COMMIT" install --install-hooks --allow-missing-config
    echo "✅ Installed pre-commit hooks (nbstripout, gitleaks, detect-private-key)"
elif [ -n "$PRE_COMMIT" ]; then
    "$PRE_COMMIT" install --allow-missing-config
    echo "✅ Installed pre-commit shim (--allow-missing-config; no config in this checkout yet)"
else
    echo "⚠️  pre-commit not found — activate .venv or: uv sync"
fi

# Legacy pre-push build guard (optional; skipped if pre-commit already owns pre-push)
if [ -f ".githooks/pre-push" ] && [ ! -f ".git/hooks/pre-push" ]; then
    mkdir -p .git/hooks
    cp .githooks/pre-push .git/hooks/pre-push
    chmod +x .git/hooks/pre-push
    echo "✅ Installed legacy .githooks/pre-push"
fi

echo ""
echo "To bypass hooks in an emergency: git commit --no-verify  /  git push --no-verify"
echo "To silence hooks when .pre-commit-config.yaml is absent: PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit ..."
