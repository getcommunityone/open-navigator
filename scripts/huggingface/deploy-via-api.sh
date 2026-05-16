#!/bin/bash
#
# Deploy to HuggingFace Spaces using Hub API (bypasses git binary file issues)
#
# Usage:
#   ./scripts/huggingface/deploy-via-api.sh
#

set -e

echo "🚀 Deploying to HuggingFace Spaces via Hub API"
echo "=============================================="

# Check for HF token
if [ -z "$HF_TOKEN" ]; then
    echo "❌ Error: HF_TOKEN not set"
    echo "   Export it: export HF_TOKEN=your_token"
    exit 1
fi

# Configuration
SPACE_ID="CommunityOne/open-navigator"
LOCAL_DIR="."

# Files/directories to upload
UPLOAD_PATTERNS=(
    ".huggingface/*"
    "api/*"
    "agents/*"
    "config/*"
    "discovery/*"
    "extraction/*"
    "frontend/dist/*"
    "website/build/*"
    "Dockerfile.huggingface"
    "requirements.txt"
    "README.md"
)

echo "📦 Space: $SPACE_ID"
echo ""

# Use huggingface-cli to upload
python << 'PYTHON_SCRIPT'
import os
import sys
from pathlib import Path
from huggingface_hub import HfApi, upload_folder
from loguru import logger

token = os.getenv('HF_TOKEN')
space_id = os.getenv('SPACE_ID', 'CommunityOne/open-navigator')

if not token:
    logger.error("HF_TOKEN not set")
    sys.exit(1)

logger.info(f"Uploading to Space: {space_id}")

api = HfApi(token=token)

# Upload entire directory but ignore certain patterns
ignore_patterns = [
    ".git/*",
    ".git",
    ".venv/*",
    ".venv",
    ".venv-intel/*",
    ".venv-intel",
    "venv/*",
    "venv",
    "node_modules/*",
    "**/node_modules/*",
    "node_modules",
    "data/*",  # Don't upload data files
    "data/gold_old/*",
    "logs/*",
    ".env",
    ".env.*",
    "__pycache__/*",
    "**/__pycache__/*",
    "*.pyc",
    ".vscode/*",
    ".idea/*",
    "*.log",
    ".cache/*",
    "**/.cache/*",
    "website/node_modules/*",
    "frontend/node_modules/*",
    "*.swp",
    "*.swo",
    "*~",
    ".DS_Store",
]

logger.info("Uploading files...")
logger.info(f"Ignoring: {', '.join(ignore_patterns[:5])}...")

try:
    upload_folder(
        folder_path=".",
        repo_id=space_id,
        repo_type="space",
        token=token,
        ignore_patterns=ignore_patterns,
        commit_message="Deploy updated application via Hub API"
    )
    
    logger.success(f"✅ Successfully deployed to {space_id}")
    logger.info(f"View at: https://huggingface.co/spaces/{space_id}")
    
except Exception as e:
    logger.error(f"❌ Deployment failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYTHON_SCRIPT

echo ""
echo "✅ Deployment complete!"
echo "🌐 View your Space at: https://www.communityone.com"
echo "📊 Check build logs at: https://huggingface.co/spaces/$SPACE_ID"
