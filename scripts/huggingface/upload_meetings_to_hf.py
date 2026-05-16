#!/usr/bin/env python3
"""
Upload meeting gold tables to Hugging Face Datasets.

⚠️ NOTE: The consolidated national-level meeting and contact files have been
removed because they are too large for HuggingFace uploads (meetings_transcripts
was 2.8 GB). 

These files are NO LONGER AVAILABLE:
- meetings_calendar.parquet (REMOVED - too large)
- meetings_transcripts.parquet (REMOVED - 2.8 GB)
- meetings_demographics.parquet (REMOVED - too large)
- meetings_topics.parquet (REMOVED - too large)
- meetings_decisions.parquet (REMOVED - too large)
- contacts_local_officials.parquet (REMOVED - too large)
- contacts_meeting_attendance.parquet (REMOVED - too large)

For meeting and contact data, use state-split files instead or query directly
from the database.

This script is kept for reference but will not work without the source files.

Usage:
    # Install requirements
    pip install huggingface_hub datasets pyarrow

    # Set your token (get from https://huggingface.co/settings/tokens)
    export HF_TOKEN="hf_YOUR_TOKEN_HERE"
    
    # Upload all meeting tables
    python scripts/upload_meetings_to_hf.py --all
    
    # Upload specific table
    python scripts/upload_meetings_to_hf.py --table calendar
    
    # Upload to your own repo
    python scripts/upload_meetings_to_hf.py --all --repo "your-username/meetings"
"""

import argparse
import os
from pathlib import Path
import pandas as pd
from datasets import Dataset
from huggingface_hub import login, create_repo, HfApi
from loguru import logger

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logger.warning("python-dotenv not installed. Install with: pip install python-dotenv")


class MeetingHFUploader:
    """Upload meeting gold tables to HuggingFace."""
    
    # Define the 5 meeting gold tables + 3 contacts tables
    MEETING_TABLES = {
        "calendar": {
            "file": "meetings_calendar.parquet",
            "description": "Meeting dates, locations, jurisdictions (153K meetings)",
            "split": "calendar"
        },
        "transcripts": {
            "file": "meetings_transcripts.parquet",
            "description": "Full searchable meeting text (2.8 GB of civic engagement!)",
            "split": "transcripts"
        },
        "demographics": {
            "file": "meetings_demographics.parquet",
            "description": "Census data linked to meetings",
            "split": "demographics"
        },
        "topics": {
            "file": "meetings_topics.parquet",
            "description": "Extracted topics and themes",
            "split": "topics"
        },
        "decisions": {
            "file": "meetings_decisions.parquet",
            "description": "Policy decisions, votes, and resolutions",
            "split": "decisions"
        }
    }
    
    CONTACTS_TABLES = {
        "local_officials": {
            "file": "contacts_local_officials.parquet",
            "description": "Local officials extracted from meeting transcripts",
            "split": "local_officials"
        },
        "meeting_attendance": {
            "file": "contacts_meeting_attendance.parquet",
            "description": "Meeting attendance records (which officials attended which meetings)",
            "split": "meeting_attendance"
        },
        "state_legislators": {
            "file": "contacts_state_legislators.parquet",
            "description": "State legislators from Open States API",
            "split": "state_legislators"
        },
        "school_board": {
            "file": "contacts_school_board.parquet",
            "description": "School board members",
            "split": "school_board"
        }
    }
    
    def __init__(self, repo_name: str = None, token: str = None):
        """
        Initialize uploader.
        
        Args:
            repo_name: HF repo prefix (e.g., "CommunityOne/civic-meetings")
                      Each table will be uploaded to its own dataset:
                      - CommunityOne/civic-meetings-calendar
                      - CommunityOne/civic-meetings-transcripts
                      - etc.
            token: HF token (or set HF_TOKEN environment variable)
        """
        self.repo_prefix = repo_name or "CommunityOne/one-meetings"
        self.contacts_repo_prefix = "CommunityOne/one-contacts"
        self.token = token or os.getenv("HF_TOKEN")
        self.gold_path = Path("data/gold")
        
        if not self.token:
            raise ValueError(
                "Hugging Face token required! "
                "Get it from https://huggingface.co/settings/tokens "
                "and set HF_TOKEN environment variable"
            )
        
        # Login
        login(token=self.token)
        logger.info(f"✅ Logged in to Hugging Face")
        logger.info(f"📦 Meeting datasets prefix: {self.repo_prefix}")
        logger.info(f"📦 Contacts datasets prefix: {self.contacts_repo_prefix}")
    
    def upload_table(self, table_name: str, table_type: str = "meeting"):
        """
        Upload a single table to its own HuggingFace dataset.
        
        Args:
            table_name: Name of table (calendar, transcripts, etc.)
            table_type: Either "meeting" or "contact"
        """
        if table_type == "meeting":
            tables_dict = self.MEETING_TABLES
            repo_prefix = self.repo_prefix
        else:
            tables_dict = self.CONTACTS_TABLES
            repo_prefix = self.contacts_repo_prefix
        
        if table_name not in tables_dict:
            raise ValueError(f"Unknown table: {table_name}. Choose from: {list(tables_dict.keys())}")
        
        table_info = tables_dict[table_name]
        file_path = self.gold_path / table_info["file"]
        
        # Create dataset-specific repo name
        repo_name = f"{repo_prefix}-{table_name.replace('_', '-')}"
        
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            if table_type == "meeting":
                logger.error(f"Run: python scripts/create_all_gold_tables.py --meetings-only")
            else:
                logger.error(f"Run: python pipeline/create_contacts_gold_tables.py")
            return False
        
        # Create repo
        try:
            create_repo(
                repo_id=repo_name,
                repo_type="dataset",
                private=False,
                exist_ok=True
            )
            logger.info(f"✅ Repository ready: https://huggingface.co/datasets/{repo_name}")
        except Exception as e:
            logger.warning(f"Repository may already exist: {e}")
        
        logger.info(f"📤 Uploading {table_name} from {file_path}")
        
        # Load Parquet file
        df = pd.read_parquet(file_path)
        logger.info(f"  Rows: {len(df):,}")
        logger.info(f"  Columns: {len(df.columns)}")
        
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > 1000:
            logger.info(f"  Size: {file_size_mb / 1024:.2f} GB")
        else:
            logger.info(f"  Size: {file_size_mb:.2f} MB")
        
        # Convert to HuggingFace Dataset
        dataset = Dataset.from_pandas(df)
        
        # Upload to table-specific dataset
        logger.info(f"  Pushing to {repo_name}")
        dataset.push_to_hub(
            repo_id=repo_name,
            commit_message=f"Update {table_name} table - {len(df):,} records"
        )
        
        logger.success(f"✅ Uploaded {table_name}: {len(df):,} records")
        logger.success(f"   View at: https://huggingface.co/datasets/{repo_name}")
        
        return True
    
    def upload_all_meetings(self):
        """Upload all meeting gold tables."""
        logger.info("🚀 Uploading all meeting tables to HuggingFace...")
        
        results = {}
        for table_name in self.MEETING_TABLES.keys():
            try:
                success = self.upload_table(table_name, table_type="meeting")
                results[table_name] = "✅ Success" if success else "❌ Failed"
            except Exception as e:
                logger.error(f"Failed to upload {table_name}: {e}")
                results[table_name] = f"❌ Error: {e}"
        
        # Summary
        logger.info("\n📊 Upload Summary:")
        for table_name, status in results.items():
            logger.info(f"  {status}: {table_name}")
        
        logger.success(f"\n🎉 All meeting uploads complete!")
        logger.success(f"   View datasets:")
        for table_name in self.MEETING_TABLES.keys():
            logger.success(f"   - https://huggingface.co/datasets/{self.repo_prefix}-{table_name}")
    
    def upload_all_contacts(self):
        """Upload all contacts gold tables."""
        logger.info("🚀 Uploading all contacts tables to HuggingFace...")
        
        results = {}
        for table_name in self.CONTACTS_TABLES.keys():
            try:
                success = self.upload_table(table_name, table_type="contact")
                results[table_name] = "✅ Success" if success else "❌ Failed"
            except Exception as e:
                logger.error(f"Failed to upload {table_name}: {e}")
                results[table_name] = f"❌ Error: {e}"
        
        # Summary
        logger.info("\n📊 Upload Summary:")
        for table_name, status in results.items():
            logger.info(f"  {status}: {table_name}")
        
        logger.success(f"\n🎉 All contacts uploads complete!")
        logger.success(f"   View datasets:")
        for table_name in self.CONTACTS_TABLES.keys():
            logger.success(f"   - https://huggingface.co/datasets/{self.contacts_repo_prefix}-{table_name.replace('_', '-')}")
    
    def upload_all(self):
        """Upload all tables (meetings + contacts)."""
        self.upload_all_meetings()
        print()  # Blank line
        self.upload_all_contacts()


def main():
    parser = argparse.ArgumentParser(description="Upload meeting and contacts gold tables to HuggingFace")
    parser.add_argument("--all", action="store_true", help="Upload all tables (meetings + contacts)")
    parser.add_argument("--meetings", action="store_true", help="Upload only meeting tables")
    parser.add_argument("--contacts", action="store_true", help="Upload only contacts tables")
    parser.add_argument("--table", help="Upload specific table by name")
    parser.add_argument("--repo", default="CommunityOne/one-meetings", help="HuggingFace repo prefix for meetings")
    
    args = parser.parse_args()
    
    if not args.all and not args.meetings and not args.contacts and not args.table:
        parser.error("Must specify --all, --meetings, --contacts, or --table")
    
    try:
        uploader = MeetingHFUploader(repo_name=args.repo)
        
        if args.all:
            uploader.upload_all()
        elif args.meetings:
            uploader.upload_all_meetings()
        elif args.contacts:
            uploader.upload_all_contacts()
        elif args.table:
            # Determine if it's a meeting or contact table
            if args.table in uploader.MEETING_TABLES:
                uploader.upload_table(args.table, table_type="meeting")
            elif args.table in uploader.CONTACTS_TABLES:
                uploader.upload_table(args.table, table_type="contact")
            else:
                logger.error(f"Unknown table: {args.table}")
                logger.error(f"Available meeting tables: {list(uploader.MEETING_TABLES.keys())}")
                logger.error(f"Available contacts tables: {list(uploader.CONTACTS_TABLES.keys())}")
                return 1
    
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
