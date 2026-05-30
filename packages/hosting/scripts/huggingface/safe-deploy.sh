#!/bin/bash

# Safe deployment script that runs CI checks before deploying
# This prevents broken builds from being pushed to production

echo "🛡️  SAFE DEPLOYMENT TO HUGGINGFACE SPACES"
echo "=========================================="
echo ""

# Store the project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

FAILED=false
CHECKS_PASSED=0
TOTAL_CHECKS=4

echo "Running pre-deployment safety checks..."
echo ""

# Check 1: Frontend TypeScript type checking
echo "📝 Check 1/$TOTAL_CHECKS: Frontend TypeScript type checking..."
cd frontend
if npx tsc --noEmit > /tmp/tsc-output.log 2>&1; then
    echo "✅ TypeScript types OK"
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
else
    echo "❌ TypeScript errors found!"
    echo ""
    echo "Errors:"
    cat /tmp/tsc-output.log
    FAILED=true
fi
cd "$PROJECT_ROOT"
echo ""

# Check 2: Frontend build test
echo "🏗️  Check 2/$TOTAL_CHECKS: Frontend build test..."
cd frontend
if npm run build > /tmp/frontend-build.log 2>&1; then
    echo "✅ Frontend builds successfully"
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
else
    echo "❌ Frontend build failed!"
    echo ""
    echo "Last 20 lines of build output:"
    tail -20 /tmp/frontend-build.log
    FAILED=true
fi
cd "$PROJECT_ROOT"
echo ""

# Check 3: Documentation build test
echo "📚 Check 3/$TOTAL_CHECKS: Documentation build test..."
cd website
if npm run build > /tmp/docs-build.log 2>&1; then
    echo "✅ Documentation builds successfully"
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
else
    echo "❌ Documentation build failed!"
    echo ""
    echo "Last 20 lines of build output:"
    tail -20 /tmp/docs-build.log
    FAILED=true
fi
cd "$PROJECT_ROOT"
echo ""

# Check 4: Python syntax check
echo "🐍 Check 4/$TOTAL_CHECKS: Python syntax check..."
if python -m py_compile main.py api/main.py 2>&1; then
    echo "✅ Python syntax OK"
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
else
    echo "❌ Python syntax errors found!"
    FAILED=true
fi
echo ""

# Summary
echo "=========================================="
if [ "$FAILED" = true ]; then
    echo "❌ DEPLOYMENT BLOCKED"
    echo "=========================================="
    echo ""
    echo "Checks passed: $CHECKS_PASSED/$TOTAL_CHECKS"
    echo ""
    echo "Please fix the errors above before deploying to production."
    echo ""
    echo "These same checks run in GitHub Actions CI, but running them"
    echo "locally catches errors faster and prevents production outages."
    echo ""
    echo "💡 Tip: Fix errors and run this script again:"
    echo "   ./scripts/huggingface/safe-deploy.sh"
    echo ""
    exit 1
else
    echo "✅ ALL CHECKS PASSED ($CHECKS_PASSED/$TOTAL_CHECKS)"
    echo "=========================================="
    echo ""
    echo "Proceeding with deployment..."
    echo ""
    
    # Run the actual deployment
    .venv/bin/python scripts/huggingface/deploy-space.py
    
    echo ""
    echo "=========================================="
    echo "🎉 DEPLOYMENT COMPLETE"
    echo "=========================================="
    echo ""
    echo "🌐 Live at: https://www.communityone.com"
    echo "📊 Build logs: https://huggingface.co/spaces/CommunityOne/open-navigator"
    echo ""
    echo "Note: HuggingFace Space will rebuild (~5-10 min)"
    echo "Monitor the build logs link above to see when it's live."
    echo ""
fi
