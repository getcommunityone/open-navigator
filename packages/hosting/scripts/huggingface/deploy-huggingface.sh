#!/bin/bash

# Quick deployment script for Hugging Face Spaces
# Deploys all three apps: Documentation, Frontend, and API
#
# Pre-deployment checks:
# 1. Docusaurus build verification (catches config errors early)
# 2. Docker build test (validates full deployment)
#
# Usage:
#   ./deploy-huggingface.sh                    # Deploy with all tests
#   ./deploy-huggingface.sh --skip-test        # Skip tests (not recommended)

set -e

# --- Run in an isolated clone so the LIVE serving checkout is never touched ----
# This script does destructive git surgery (orphan branch, `rm --cached`, autostash,
# force-push). The deployment panel/orchestrator launches it from the SAME checkout
# the dev servers (API :8000, Vite :5173) run from, so doing that surgery in place
# yanks files out from under the running site and crashes it. Re-exec inside a
# throwaway local clone instead: the deploy publishes committed `main` (not your
# uncommitted work), so a `--local` clone reproduces exactly what would be deployed
# while leaving the live checkout — and the running servers — completely alone.
if [ -z "$HF_DEPLOY_ISOLATED" ]; then
    SRC_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || SRC_ROOT=""
    if [ -n "$SRC_ROOT" ]; then
        CLONE_DIR=$(mktemp -d -t hf-deploy-XXXXXX)
        trap 'rm -rf "$CLONE_DIR" 2>/dev/null || true' EXIT
        echo "🧬 Isolating deploy in a throwaway clone (live checkout untouched):"
        echo "   $CLONE_DIR"
        echo ""
        # --local hardlinks objects (fast, cheap) and carries all committed history.
        git clone --quiet --local "$SRC_ROOT" "$CLONE_DIR"
        # Carry over gitignored .env so HF_USERNAME / HF_TOKEN are available in the clone.
        [ -f "$SRC_ROOT/.env" ] && cp "$SRC_ROOT/.env" "$CLONE_DIR/.env"
        cd "$CLONE_DIR"
        set +e
        HF_DEPLOY_ISOLATED=1 bash "packages/hosting/scripts/huggingface/deploy-huggingface.sh" "$@"
        rc=$?
        set -e
        exit $rc
    fi
fi

# Load environment variables from .env file if it exists
if [ -f ".env" ]; then
    echo "📝 Loading environment variables from .env..."
    set -a  # automatically export all variables
    source .env
    set +a
    echo ""
fi

# Parse command line arguments
SKIP_TEST=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-test)
            SKIP_TEST=true
            shift
            ;;
        *)
            HF_USERNAME_ARG="$1"
            shift
            ;;
    esac
done

echo "🚀 Open Navigator - Hugging Face Deployment"
echo "==========================================================="
echo ""

# Check if HF username is provided (env var or argument)
if [ -z "$HF_USERNAME" ] && [ -z "$HF_USERNAME_ARG" ]; then
    echo "❌ Error: Hugging Face username required"
    echo ""
    echo "Usage Option 1 (.env file - RECOMMENDED):"
    echo "  Add to .env file: HF_USERNAME=your_username"
    echo "  ./deploy-huggingface.sh"
    echo ""
    echo "Usage Option 2 (Environment Variable):"
    echo "  export HF_USERNAME=your_username"
    echo "  ./deploy-huggingface.sh"
    echo ""
    echo "Usage Option 3 (Command Argument):"
    echo "  ./deploy-huggingface.sh YOUR_HF_USERNAME"
    echo ""
    echo "Usage Option 4 (Skip Docker test - not recommended):"
    echo "  ./deploy-huggingface.sh YOUR_HF_USERNAME --skip-test"
    echo ""
    echo "Example:"
    echo "  echo 'HF_USERNAME=CommunityOne' >> .env"
    echo "  ./deploy-huggingface.sh"
    echo ""
    exit 1
fi

# Use argument if provided, otherwise use env var
if [ -n "$HF_USERNAME_ARG" ]; then
    HF_USERNAME="$HF_USERNAME_ARG"
fi

# Deploy to the Space with custom domain configured
SPACE_NAME="open-navigator"
HF_REPO="https://huggingface.co/spaces/${HF_USERNAME}/${SPACE_NAME}"
HF_REMOTE="hf-www"  # Use hf-www remote for custom domain Space

echo "📋 Deployment Configuration"
echo "  Username: $HF_USERNAME"
echo "  Space: $SPACE_NAME"
echo "  Remote: $HF_REMOTE"
echo "  URL: $HF_REPO"
echo "  Custom Domain: https://www.communityone.com"
echo ""

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    echo "🔧 Activating virtual environment..."
    source .venv/bin/activate
fi

# Check if huggingface-hub is installed
if ! command -v hf &> /dev/null; then
    echo "📦 Installing huggingface-hub..."
    pip install huggingface-hub
fi

# Authenticate with HuggingFace
echo "🔐 Checking Hugging Face authentication..."
if ! hf whoami &> /dev/null; then
    # Not logged in - try to login with token from .env
    if [ -n "$HF_TOKEN" ]; then
        echo "🔑 Logging in with HF_TOKEN from .env..."
        if hf auth login --token "$HF_TOKEN" --add-to-git-credential; then
            echo "✅ Successfully authenticated with token from .env"
        else
            echo "❌ Failed to authenticate with HF_TOKEN"
            echo "Please check your token in .env file"
            exit 1
        fi
    else
        echo "❌ Not logged in to Hugging Face"
        echo ""
        echo "Option 1: Add HF_TOKEN to .env file (RECOMMENDED)"
        echo "  Get token from: https://huggingface.co/settings/tokens"
        echo "  Add to .env: HF_TOKEN=hf_..."
        echo ""
        echo "Option 2: Login manually"
        echo "  hf auth login"
        echo ""
        exit 1
    fi
else
    echo "✅ Already authenticated as: $(hf whoami)"
fi
echo ""

# Clean up old Docker artifacts to prevent disk space issues
echo "🧹 Cleaning up old Docker artifacts..."
docker stop open-navigator-test-container 2>/dev/null || true
docker rm open-navigator-test-container 2>/dev/null || true
docker rmi open-navigator-hf-test 2>/dev/null || true
echo ""

# Verify Docusaurus build before Docker (faster feedback on config errors)
echo "📚 Verifying Docusaurus build..."
echo "This catches configuration errors before the slow Docker build"
echo ""

if [ -d "web_docs/node_modules" ]; then
    echo "✅ Node modules already installed"
else
    echo "📦 Installing web_docs dependencies..."
    cd web_docs
    npm ci --prefer-offline --no-audit || npm install --prefer-offline --no-audit
    cd ..
fi
echo ""

echo "🔨 Building documentation site..."
if (cd web_docs && npm run build); then
    echo ""
    echo "✅ Docusaurus build succeeded!"
    echo ""
else
    echo ""
    echo "❌ Docusaurus build failed!"
    echo ""
    echo "Common issues:"
    echo "  - Duplicate plugin configurations (e.g., gtag in both preset and themeConfig)"
    echo "  - Invalid frontmatter in .md files"
    echo "  - Broken internal links"
    echo "  - Missing dependencies"
    echo ""
    echo "Fix the errors above before deploying."
    echo "Test locally with: cd web_docs && npm run build"
    echo ""
    exit 1
fi

# Run Docker build test before deployment (unless skipped)
if [ "$SKIP_TEST" = true ]; then
    echo "⚠️  Skipping pre-deployment Docker build test (--skip-test flag)"
    echo ""
else
    echo "🧪 Running pre-deployment Docker build test..."
    echo "This ensures the build works before pushing to Hugging Face"
    echo ""

    if [ -f "./test-huggingface-build.sh" ]; then
        chmod +x ./test-huggingface-build.sh
        
        if ./test-huggingface-build.sh; then
            echo ""
            echo "✅ Pre-deployment test passed!"
            echo ""
        else
            echo ""
            echo "❌ Pre-deployment test failed!"
            echo ""
            echo "Please fix the Docker build issues before deploying."
            echo "Run './test-huggingface-build.sh' to test locally."
            echo ""
            echo "To deploy anyway (not recommended), use:"
            echo "  ./deploy-huggingface.sh $HF_USERNAME --skip-test"
            echo ""
            exit 1
        fi
    else
        echo "⚠️  Warning: test-huggingface-build.sh not found"
        echo "Skipping pre-deployment test"
        echo ""
    fi
fi

# Ask to create space if it doesn't exist
echo "🌟 Creating Hugging Face Space (if it doesn't exist)..."
# hf CLI (huggingface_hub >= 0.30) uses `--repo-type` + `--space_sdk` with a
# positional repo_id; the old `--type`/`--space-sdk` flags were huggingface-cli.
hf repo create "${HF_USERNAME}/${SPACE_NAME}" --repo-type space --space_sdk docker --exist-ok || true
echo ""

# Update cache-bust timestamps to force fresh build
echo "🔄 Updating cache-bust timestamps to force fresh build..."
TIMESTAMP=$(date +%Y-%m-%d-%H-%M)
COMMIT_HASH=$(git rev-parse --short HEAD)
CACHE_BUST="${TIMESTAMP}-${COMMIT_HASH}"

echo "  Timestamp: $TIMESTAMP"
echo "  Commit: $COMMIT_HASH"
echo "  Cache-bust: $CACHE_BUST"

# Update Docusaurus cache-bust
sed -i.bak "s/ARG CACHE_BUST=.*/ARG CACHE_BUST=${CACHE_BUST}/" Dockerfile
sed -i.bak "s/echo \"Cache bust: .*/echo \"Cache bust: ${CACHE_BUST}\" \&\&/" Dockerfile

# Update Frontend cache-bust  
sed -i.bak "s/ARG CACHE_BUST_FRONTEND=.*/ARG CACHE_BUST_FRONTEND=${CACHE_BUST}/" Dockerfile
sed -i.bak "s/echo \"Frontend build cache bust: .*/echo \"Frontend build cache bust: \$CACHE_BUST_FRONTEND\" \&\& npm run build/" Dockerfile

# Remove backup files
rm -f Dockerfile.bak

echo "✅ Cache-bust timestamps updated to: $CACHE_BUST"
echo ""

# Create deployment branch
echo "🔧 Preparing deployment branch (clean, no binary history)..."

# This script does heavy git surgery (orphan branch, `rm --cached`, force-push)
# and the deployment orchestrator launches it from whatever branch you're on —
# frequently with uncommitted changes. A bare `git checkout main` aborts on a
# dirty tree, so record where we started, stash any local work (incl. untracked),
# and restore it on exit even if a later step fails.
ORIGINAL_REF=$(git symbolic-ref --short -q HEAD || git rev-parse HEAD)
STASH_REF=""
if ! git diff --quiet || ! git diff --cached --quiet \
        || [ -n "$(git ls-files --others --exclude-standard)" ]; then
    echo "📦 Stashing local changes before deployment branch surgery..."
    git stash push --include-untracked -m "deploy-huggingface autostash" >/dev/null
    STASH_REF=$(git rev-parse -q --verify "stash@{0}")
fi

restore_working_state() {
    local rc=$?
    echo ""
    echo "♻️  Restoring original working state (${ORIGINAL_REF})..."
    # The orphan-branch surgery leaves a staged/half-conflicted index, so a plain
    # `git checkout` refuses to switch and silently leaves us stranded on the
    # deploy branch. Hard-reset the index/worktree first, THEN force back to the
    # original ref — this works no matter what broken state a crash left behind.
    git reset -q --hard >/dev/null 2>&1 || true
    git checkout --force "$ORIGINAL_REF" >/dev/null 2>&1 || true
    # Drop the throwaway deploy branch so the next run starts from a clean slate.
    git branch -D huggingface-deploy >/dev/null 2>&1 || true
    if [ -n "$STASH_REF" ]; then
        if git stash pop >/dev/null 2>&1; then
            echo "✅ Restored your branch (${ORIGINAL_REF}) and uncommitted changes."
        else
            echo "⚠️  Could not auto-pop the deploy stash; recover with: git stash list && git stash pop"
        fi
    else
        echo "✅ Restored your branch (${ORIGINAL_REF})."
    fi
    return $rc
}
trap restore_working_state EXIT

# Make sure we're on main
git checkout main

# Create a new orphan branch (no history) to avoid binary file issues
git branch -D huggingface-deploy 2>/dev/null || true
git checkout --orphan huggingface-deploy

# Copy Dockerfile for HF (they look for "Dockerfile" not "Dockerfile.huggingface")
echo "📝 Configuring Dockerfile..."
cp Dockerfile.huggingface Dockerfile

# Copy README for Space description
echo "📝 Configuring README..."
cp .huggingface/README.md README_HF.md

# Remove large binary files from being staged
# (HF Spaces rejects large binary files in git)
echo "📝 Optimizing deployment (excluding binary files)..."

# Reset index to avoid staging unwanted files
git rm -rf --cached . 2>/dev/null || true

# Add deployment config files (small, safe to force)
git add -f Dockerfile README_HF.md .huggingface/ .gitignore .dockerignore

# Add source code WITHOUT -f to respect .gitignore (excludes node_modules automatically)
# Only add directories that exist — some top-level trees were relocated into packages/
# during the scripts/ -> packages/ refactor, and `git add` aborts (exit 128) on any
# pathspec that matches zero files.
for d in agents api config discovery extraction packages pipeline scripts tests visualization \
         databricks examples models neon notebooks; do
    [ -d "$d" ] && git add "$d"
done
# Add top-level files. Use nullglob so unmatched globs expand to nothing
# (a bare `git add *.yaml` with no match would otherwise abort with exit 128),
# and guard each literal so a since-removed file (e.g. INTEL_ARC_QUICKSTART.md)
# can't fail the whole deploy.
shopt -s nullglob
for f in requirements*.txt *.sh *.md *.yml *.yaml \
         setup.py main.py Makefile \
         CITATIONS.md CONTRIBUTING.md LICENSE INTEL_ARC_QUICKSTART.md; do
    [ -e "$f" ] && git add "$f"
done
shopt -u nullglob

# Add web_app/web_docs source EXCLUDING node_modules (gitignore handles this)
echo "🧹 Adding web_app/web_docs sources (node_modules auto-excluded by .gitignore)..."
git add web_app/ web_docs/

# Verify node_modules are NOT staged
NODE_MODULES_COUNT=$(git diff --cached --name-only | grep "node_modules" | wc -l)
if [ "$NODE_MODULES_COUNT" -gt 0 ]; then
    echo "❌ ERROR: node_modules were staged ($NODE_MODULES_COUNT files)"
    echo "This should not happen. Check .gitignore configuration."
    exit 1
fi
echo "✅ Verified: No node_modules in staging area"

# HF Spaces reject non-LFS files > 10 MiB (pre-receive hook). Drop any oversized
# staged file so the push isn't declined — this is a "clean deployment without
# binary files", so large assets (e.g. api/static/wikicommons/*.jpg) don't belong.
echo "🧹 Dropping any staged files larger than 10 MiB (HF hard limit)..."
_oversized=0
while IFS= read -r f; do
    [ -n "$f" ] || continue
    sz=$(git cat-file -s ":$f" 2>/dev/null || echo 0)
    if [ "$sz" -gt 10485760 ]; then
        echo "   ⚠️  Excluding $((sz / 1048576)) MB file: $f"
        git rm --cached --quiet -- "$f" 2>/dev/null || true
        _oversized=$((_oversized + 1))
    fi
done < <(git diff --cached --name-only)
echo "✅ Oversized files excluded: ${_oversized}"

# HF (Xet) rejects RAW binary files of any size — to keep them you'd need LFS/Xet.
# This is a "clean deployment without binary files", and every binary asset here
# lives under public/ or static/ (served by path, never import-ed into the build),
# so dropping them is build-safe; only some runtime images/favicon go missing.
# git flags binary blobs as '-\t-' in numstat — use that, extension-agnostic.
echo "🧹 Dropping staged binary files (HF Xet rejects raw binaries)..."
_bin=0
while IFS=$'\t' read -r add del path; do
    if [ "$add" = "-" ] && [ "$del" = "-" ] && [ -n "$path" ]; then
        git rm --cached --quiet -- "$path" 2>/dev/null || true
        _bin=$((_bin + 1))
    fi
done < <(git diff --cached --numstat)
echo "✅ Binary files excluded: ${_bin}"

echo "💾 Committing clean deployment (no git history)..."
git commit -m "Clean HuggingFace deployment without binary files" --allow-empty

# Push to Hugging Face — token-authenticated, NON-interactive.
# Without an embedded token git falls back to an interactive credential prompt
# (e.g. VSCode's GIT_ASKPASS asking "Username for https://huggingface.co"), which
# hangs FOREVER in a non-TTY deploy job. Require HF_TOKEN, embed it in the push
# URL, and disable any prompt so a missing/invalid token fails fast instead.
if [ -z "$HF_TOKEN" ]; then
    echo "❌ Error: HF_TOKEN is not set — cannot push to the Space non-interactively."
    echo "   Add HF_TOKEN to .env (or the environment) and re-run."
    exit 1
fi
export GIT_TERMINAL_PROMPT=0
export GIT_ASKPASS=/bin/echo
export GIT_CONFIG_PARAMETERS="'credential.helper='"  # ignore any interactive helper
PUSH_URL="https://${HF_USERNAME}:${HF_TOKEN}@huggingface.co/spaces/${HF_USERNAME}/${SPACE_NAME}"

echo ""
echo "📤 Pushing to Hugging Face Spaces..."
echo "This will trigger a build (takes ~10-15 minutes)"
echo ""
git push "$PUSH_URL" huggingface-deploy:main --force

echo ""
echo "✅ Deployment initiated!"
echo ""
echo "==========================================================="
echo "🎉 Next Steps:"
echo "==========================================================="
echo ""
echo "1. View your Space:"
echo "   https://huggingface.co/spaces/${HF_USERNAME}/${SPACE_NAME}"
echo ""
echo "2. Configure hardware (REQUIRED for Docker):"
echo "   - Go to Settings → Resource configuration"
echo "   - Select 'CPU Basic' (~\$22/month minimum)"
echo ""
echo "3. Add API keys as secrets:"
echo "   - Go to Settings → Variables and secrets"
echo "   - Add these secrets:"
echo "     • OPENAI_API_KEY"
echo "     • ANTHROPIC_API_KEY"
echo "     • HF_TOKEN"
echo ""
echo "4. Monitor build progress:"
echo "   - Click 'Logs' tab in your Space"
echo "   - Build takes ~10-15 minutes"
echo ""
echo "5. Access your apps:"
echo "   - Main App: https://www.communityone.com/"
echo "   - Documentation: https://www.communityone.com/docs/"
echo "   - API: https://www.communityone.com/api/docs"
echo ""
echo "   (Also available at: https://${HF_USERNAME}-${SPACE_NAME//./-}.hf.space/)"
echo ""
echo "==========================================================="
echo ""
echo "📖 Full guide: ./HUGGINGFACE_DEPLOYMENT.md"
echo ""
