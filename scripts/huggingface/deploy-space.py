#!/usr/bin/env python3
"""
Deploy to HuggingFace Spaces using Hub API

This bypasses git push issues with binary files in history.

Usage:
    python scripts/huggingface/deploy-space.py
    python scripts/huggingface/deploy-space.py --dry-run
"""

import os
import sys
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv
import argparse

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load environment
load_dotenv()

def main():
    parser = argparse.ArgumentParser(description="Deploy to HuggingFace Spaces")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be uploaded")
    parser.add_argument("--space-id", default="CommunityOne/open-navigator", help="Space ID")
    args = parser.parse_args()
    
    token = os.getenv('HF_TOKEN')
    if not token:
        logger.error("❌ HF_TOKEN not set in environment")
        logger.error("   Add it to .env file or export it")
        sys.exit(1)
    
    logger.info("=" * 70)
    logger.info("DEPLOYING TO HUGGINGFACE SPACES")
    logger.info("=" * 70)
    logger.info(f"Space ID: {args.space_id}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info("=" * 70)
    
    try:
        from huggingface_hub import HfApi, upload_folder
    except ImportError:
        logger.error("❌ huggingface_hub not installed")
        logger.error("   Run: pip install huggingface_hub")
        sys.exit(1)
    
    api = HfApi(token=token)
    
    # Patterns to ignore
    ignore_patterns = [
        ".git/*",
        ".git",
        ".gitignore",
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
        "data",
        "logs/*",
        "logs",
        ".env*",
        "__pycache__/*",
        "**/__pycache__/*",
        "*.pyc",
        ".vscode/*",
        ".idea/*",
        "*.log",
        ".cache/*",
        "**/.cache/*",
        "*.swp",
        "*.swo",
        "*~",
        ".DS_Store",
        "gold_old/*",
        "gold_backup_*/*",
        ".VSCodeCounter/*",
        "website/node_modules/*",
        "frontend/node_modules/*",
        "*.egg-info/*",
    ]
    
    logger.info(f"Uploading files to {args.space_id}...")
    logger.info(f"Ignoring patterns: {len(ignore_patterns)} patterns")
    logger.debug(f"  Examples: {', '.join(ignore_patterns[:5])}")
    
    if args.dry_run:
        logger.info("\n🔍 DRY RUN - Would upload these files:")
        # Count files that would be uploaded
        from pathlib import Path
        import fnmatch
        
        total_files = 0
        total_size = 0
        
        for file_path in Path(".").rglob("*"):
            if file_path.is_file():
                # Check if file matches ignore patterns
                rel_path = str(file_path.relative_to("."))
                should_ignore = False
                
                for pattern in ignore_patterns:
                    pattern = pattern.rstrip("/*")
                    if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(rel_path, f"{pattern}/*"):
                        should_ignore = True
                        break
                
                if not should_ignore:
                    total_files += 1
                    total_size += file_path.stat().st_size
                    if total_files <= 50:  # Show first 50 files
                        logger.info(f"  - {rel_path}")
        
        logger.info(f"\nWould upload {total_files} files ({total_size / (1024*1024):.1f} MB)")
        logger.info("Run without --dry-run to actually deploy")
        return
    
    try:
        logger.info("\n📤 Uploading to HuggingFace...")
        
        upload_folder(
            folder_path=".",
            repo_id=args.space_id,
            repo_type="space",
            token=token,
            ignore_patterns=ignore_patterns,
            commit_message="Deploy: Consolidated gold tables, fixed nginx docs routing"
        )
        
        logger.success(f"\n✅ Successfully deployed to {args.space_id}")
        logger.info(f"🌐 View at: https://www.communityone.com")
        logger.info(f"📊 Build logs: https://huggingface.co/spaces/{args.space_id}")
        
    except Exception as e:
        logger.error(f"\n❌ Deployment failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
