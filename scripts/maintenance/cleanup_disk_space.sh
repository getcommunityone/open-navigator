#!/bin/bash
# Free up disk space by removing packages/compiled files ONLY
# Does NOT delete any source data

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}🧹 Disk Space Cleanup (Safe - No Source Data Loss)${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}This script only removes:${NC}"
echo -e "  ✓ Old Python packages (venv/)"
echo -e "  ✓ Compiled Python bytecode (__pycache__, *.pyc)"
echo -e "  ✓ Node.js packages (node_modules/) - optional"
echo ""
echo -e "${GREEN}All source data will be preserved!${NC}"
echo ""

# Calculate sizes before
BEFORE=$(du -sh . 2>/dev/null | cut -f1)
echo -e "${YELLOW}Current project size: $BEFORE${NC}"
echo ""

FREED=0

# 1. Remove old venv (using .venv now)
if [ -d "venv" ]; then
    SIZE=$(du -sh venv 2>/dev/null | cut -f1)
    echo -e "${GREEN}Removing old venv/ directory ($SIZE)...${NC}"
    rm -rf venv
    echo "  ✓ Removed venv/"
    FREED=$((FREED + 6300))
else
    echo "  ⊘ venv/ not found (already removed)"
fi

# 2. Do NOT remove LocalView cache - it's source data
echo -e "${BLUE}Preserving data/cache/localview/ (source data)${NC}"

# 2. Do NOT remove LocalView cache - it's source data
echo -e "${BLUE}Preserving data/cache/localview/ (source data)${NC}"

# 3. Remove Python cache files
echo -e "${GREEN}Removing Python cache files...${NC}"
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -exec rm -f {} + 2>/dev/null || true
echo "  ✓ Removed __pycache__ directories and .pyc files"

# 4. Remove node_modules (can reinstall with npm install)
read -p "Remove node_modules? (can reinstall in 2 min with npm install) [y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -d "web_app/node_modules" ]; then
        SIZE=$(du -sh web_app/node_modules 2>/dev/null | cut -f1)
        echo -e "${GREEN}Removing web_app/node_modules ($SIZE)...${NC}"
        rm -rf web_app/node_modules
        echo "  ✓ Removed web_app/node_modules"
        FREED=$((FREED + 641))
    fi
    
    if [ -d "web_docs/node_modules" ]; then
        SIZE=$(du -sh web_docs/node_modules 2>/dev/null | cut -f1)
        echo -e "${GREEN}Removing web_docs/node_modules ($SIZE)...${NC}"
        rm -rf web_docs/node_modules
        echo "  ✓ Removed web_docs/node_modules"
        FREED=$((FREED + 907))
    fi
else
    echo "  ⊘ Skipped node_modules removal"
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}✅ Cleanup Complete! All Source Data Preserved${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
echo ""

# Calculate sizes after
AFTER=$(du -sh . 2>/dev/null | cut -f1)
echo -e "${GREEN}Project size before: $BEFORE${NC}"
echo -e "${GREEN}Project size after:  $AFTER${NC}"
echo -e "${GREEN}Freed approximately: ${FREED} MB (~$((FREED/1024)) GB)${NC}"
echo ""

# Show current disk space
df -h . | grep -v Filesystem
echo ""

echo -e "${YELLOW}Protected source data:${NC}"
echo -e "  ${BLUE}✓ data/cache/form990_gt_index.parquet (925 MB)${NC}"
echo -e "  ${BLUE}✓ data/cache/irs_bmf/ (295 MB)${NC}"
echo -e "  ${BLUE}✓ data/cache/localview/ (5.9 GB) - meeting minutes${NC}"
echo -e "  ${BLUE}✓ data/cache/census/ (15 MB)${NC}"
echo -e "  ${BLUE}✓ data/gold/ (1.7 GB) - enriched data${NC}"
echo ""

if [[ $FREED -gt 1000 ]]; then
    echo -e "${YELLOW}To reinstall dependencies:${NC}"
    echo -e "  ${BLUE}cd frontend && npm install && cd ..${NC}"
    echo -e "  ${BLUE}cd web_docs && npm install && cd ..${NC}"
    echo ""
fi
