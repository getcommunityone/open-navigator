#!/usr/bin/env python3
"""
Upload discovery and processed data to Hugging Face Datasets.

This script allows you to store unlimited data for FREE on Hugging Face.

Usage:
    # Install requirements
    pip install huggingface_hub datasets

    # Get your token from https://huggingface.co/settings/tokens
    export HF_TOKEN="hf_YOUR_TOKEN_HERE"
    
    # Upload discovery results
    python scripts/upload_to_huggingface.py --discovery
    
    # Upload meeting data
    python scripts/upload_to_huggingface.py --meetings
    
    # Upload oral health subset
    python scripts/upload_to_huggingface.py --oral-health
"""

import argparse
import os
from pathlib import Path
import pandas as pd
from datasets import Dataset, DatasetDict, Features, Value, Sequence
from huggingface_hub import login, create_repo, HfApi
from loguru import logger

# Configuration
DEFAULT_REPO_NAME = "oral-health-policy-data"


class HuggingFaceUploader:
    """Upload oral health policy data to Hugging Face Datasets."""
    
    def __init__(self, repo_name: str, token: str = None):
        """
        Initialize uploader.
        
        Args:
            repo_name: Hugging Face repo name (e.g., "username/oral-health-policy-data")
            token: HF token (or set HF_TOKEN environment variable)
        """
        self.repo_name = repo_name
        self.token = token or os.getenv("HF_TOKEN")
        
        if not self.token:
            raise ValueError(
                "Hugging Face token required! "
                "Get it from https://huggingface.co/settings/tokens "
                "and set HF_TOKEN environment variable"
            )
        
        # Login
        login(token=self.token)
        logger.info(f"✅ Logged in to Hugging Face")
        
        # Create repo if doesn't exist
        try:
            create_repo(
                repo_id=self.repo_name,
                repo_type="dataset",
                private=False,  # Public = FREE unlimited storage!
                exist_ok=True
            )
            logger.info(f"✅ Repository ready: https://huggingface.co/datasets/{self.repo_name}")
        except Exception as e:
            logger.warning(f"Repository may already exist: {e}")
    
    def upload_discovery_results(self, data_dir: str = "data/bronze/discovered_sources"):
        """
        Upload discovery results to Hugging Face as Parquet.
        
        IMPORTANT: This uploads 1 Parquet file (not thousands of individual files).
        This keeps you under Hugging Face's 100k file limit.
        
        Args:
            data_dir: Directory containing discovery CSV files
        """
        logger.info(f"📤 Uploading discovery results from {data_dir}")
        
        data_path = Path(data_dir)
        if not data_path.exists():
            logger.error(f"Directory not found: {data_dir}")
            return
        
        # Find all CSV files
        csv_files = list(data_path.glob("discovery_*.csv"))
        
        if not csv_files:
            logger.warning(f"No discovery CSV files found in {data_dir}")
            return
        
        # Load and combine all CSVs
        all_data = []
        for csv_file in csv_files:
            logger.info(f"  Loading {csv_file.name}...")
            df = pd.read_csv(csv_file)
            all_data.append(df)
        
        # Combine
        combined = pd.concat(all_data, ignore_index=True)
        
        # Remove duplicates
        combined = combined.drop_duplicates(subset=['name', 'state'], keep='last')
        
        logger.info(f"  Total jurisdictions: {len(combined)}")
        logger.info(f"  Columns: {', '.join(combined.columns)}")
        
        # Save as Parquet locally first (compressed)
        parquet_file = Path("discovery_all.parquet")
        combined.to_parquet(parquet_file, compression='snappy', index=False)
        file_size_mb = parquet_file.stat().st_size / (1024 * 1024)
        logger.info(f"  Parquet file size: {file_size_mb:.2f} MB")
        
        # Convert to Dataset (will be stored as Parquet on HF)
        dataset = Dataset.from_pandas(combined)
        
        # Upload (Hugging Face stores as Parquet internally)
        logger.info(f"  Uploading to Hugging Face as Parquet...")
        dataset.push_to_hub(
            self.repo_name,
            split="discovery",
            commit_message="Update discovery results"
        )
        
        # Clean up local Parquet
        parquet_file.unlink()
        
        logger.success(f"✅ Uploaded {len(combined)} jurisdictions in 1 Parquet file!")
        logger.success(f"   File size: {file_size_mb:.2f} MB (not {len(combined)} individual files)")
        logger.success(f"   View at: https://huggingface.co/datasets/{self.repo_name}")
        
        return dataset
    
    def upload_meeting_data(self, meetings_file: str):
        """
        Upload meeting data to Hugging Face as Parquet.
        
        IMPORTANT: Pass a CSV/JSON with extracted text, NOT individual PDF files.
        This keeps you under Hugging Face's 100k file limit.
        
        Expected columns:
        - jurisdiction: City/county name
        - state: State code
        - date: Meeting date
        - title: Meeting title
        - agenda_text: Extracted text from agenda PDF
        - minutes_text: Extracted text from minutes PDF
        - source_url: Link to original PDF
        - video_url: Link to YouTube (optional)
        
        Args:
            meetings_file: CSV/JSON file with meeting data (text extracted, not PDF bytes)
        """
        logger.info(f"📤 Uploading meeting data from {meetings_file}")
        
        file_path = Path(meetings_file)
        if not file_path.exists():
            logger.error(f"File not found: {meetings_file}")
            return
        
        # Load data
        if file_path.suffix == '.csv':
            df = pd.read_csv(file_path)
        elif file_path.suffix == '.json':
            df = pd.read_json(file_path)
        elif file_path.suffix == '.parquet':
            df = pd.read_parquet(file_path)
        else:
            logger.error(f"Unsupported file type: {file_path.suffix}. Use .csv, .json, or .parquet")
            return
        
        logger.info(f"  Meetings: {len(df)}")
        logger.info(f"  Columns: {', '.join(df.columns)}")
        
        # Validate expected columns
        required_cols = ['jurisdiction', 'state', 'date']
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            logger.warning(f"  Missing recommended columns: {missing}")
        
        # Save as Parquet locally first
        parquet_file = Path("meetings_all.parquet")
        df.to_parquet(parquet_file, compression='snappy', index=False)
        file_size_mb = parquet_file.stat().st_size / (1024 * 1024)
        logger.info(f"  Parquet file size: {file_size_mb:.2f} MB")
        
        # Convert to Dataset (stored as Parquet on HF)
        dataset = Dataset.from_pandas(df)
        
        # Upload
        logger.info(f"  Uploading {len(df):,} meetings as 1 Parquet file...")
        dataset.push_to_hub(
            self.repo_name,
            split="meetings",
            commit_message="Update meeting data"
        )
        
        # Clean up
        parquet_file.unlink()
        
        logger.success(f"✅ Uploaded {len(df):,} meetings in 1 Parquet file!")
        logger.success(f"   File size: {file_size_mb:.2f} MB")
        logger.success(f"   NOT {len(df):,} individual PDF files (would exceed limits)")
        
        return dataset
    
    def upload_oral_health_subset(self, filtered_file: str):
        """
        Upload filtered oral health documents to Hugging Face.
        
        Args:
            filtered_file: CSV/JSON with oral health-related documents
        """
        logger.info(f"📤 Uploading oral health subset from {filtered_file}")
        
        file_path = Path(filtered_file)
        if not file_path.exists():
            logger.error(f"File not found: {filtered_file}")
            return
        
        # Load data
        if file_path.suffix == '.csv':
            df = pd.read_csv(file_path)
        elif file_path.suffix == '.json':
            df = pd.read_json(file_path)
        else:
            logger.error(f"Unsupported file type: {file_path.suffix}")
            return
        
        logger.info(f"  Documents: {len(df)}")
        
        # Convert to Dataset
        dataset = Dataset.from_pandas(df)
        
        # Upload
        dataset.push_to_hub(
            self.repo_name,
            split="oral_health",
            commit_message="Update oral health documents"
        )
        
        logger.success(f"✅ Uploaded {len(df)} oral health documents!")
        
        return dataset
    
    def create_dataset_card(self):
        """Create README.md for the dataset."""
        
        readme = f"""---
license: cc0-1.0
task_categories:
- text-classification
- summarization
language:
- en
tags:
- government
- public-health
- oral-health
- policy
- meeting-minutes
size_categories:
- 10K<n<100K
---

# Oral Health Policy Data

This dataset contains comprehensive data about oral health policy discussions in U.S. government meetings.

## Dataset Description

- **Curated by:** Oral Health Policy Pulse Project
- **Language(s):** English
- **License:** CC0 (Public Domain)

## Dataset Structure

### Discovery Split

Contains information about 22,000+ U.S. jurisdictions (cities and counties), including:

- Official websites
- YouTube channels (with subscriber/video counts)
- Meeting platforms (Legistar, SuiteOne, Granicus, etc.)
- Agenda portals
- Social media accounts
- Completeness scores

**Columns:**
- `name`: Jurisdiction name
- `state`: State code
- `type`: "city" or "county"
- `population`: Population estimate
- `website`: Official website URL
- `youtube_channels`: Number of YouTube channels found
- `meeting_platforms`: Number of meeting platforms detected
- `agenda_portals`: Number of agenda portal URLs
- `completeness`: Completeness score (0-1)

### Meetings Split

Contains processed meeting data including:

- Meeting metadata (date, time, body, location)
- Agenda items
- Minutes/transcripts
- Video URLs
- Source links

### Oral Health Split

Contains filtered subset of meetings/documents that mention oral health topics:

- Fluoridation discussions
- Dental clinic approvals
- Water treatment policy
- School dental programs
- Public health initiatives

## Usage

```python
from datasets import load_dataset

# Load discovery data
discovery = load_dataset("YOUR_USERNAME/oral-health-policy-data", split="discovery")

# Load meeting data
meetings = load_dataset("YOUR_USERNAME/oral-health-policy-data", split="meetings")

# Load oral health subset
oral_health = load_dataset("YOUR_USERNAME/oral-health-policy-data", split="oral_health")

# Filter for specific state
alabama_data = discovery.filter(lambda x: x['state'] == 'AL')

# Find high-quality sources
high_quality = discovery.filter(lambda x: x['completeness'] > 0.8)
```

## Data Collection

Data was collected through:

1. **Automated discovery** across 22,000+ U.S. jurisdictions
2. **Pattern matching** for official websites and social media
3. **API integration** with Legistar, SuiteOne, and other platforms
4. **Web scraping** of public government websites
5. **YouTube channel discovery** using multiple handle patterns
6. **Text extraction** from public PDF documents
7. **Keyword filtering** for oral health topics

## Ethical Considerations

- All data is from public government sources
- No personal information is included
- Documents are public records under Freedom of Information laws
- Dataset helps research community access public policy information

## Citation

If you use this dataset in your research, please cite:

```
@dataset{{oral_health_policy_data,
  author = {{Oral Health Policy Pulse Project}},
  title = {{Oral Health Policy Data}},
  year = {{2026}},
  publisher = {{Hugging Face}},
  url = {{https://huggingface.co/datasets/{self.repo_name}}}
}}
```

## Maintenance

This dataset is actively maintained. Updates are pushed regularly as new data is discovered.

Last updated: {pd.Timestamp.now().strftime('%Y-%m-%d')}
"""
        
        # Upload README
        api = HfApi()
        api.upload_file(
            path_or_fileobj=readme.encode('utf-8'),
            path_in_repo="README.md",
            repo_id=self.repo_name,
            repo_type="dataset",
            token=self.token
        )
        
        logger.success(f"✅ Dataset card created!")


def process_pdfs_to_parquet(pdf_urls: list, output_file: str = "meetings_processed.parquet"):
    """
    CORRECT WAY: Extract text from PDFs and save as Parquet (not individual files).
    
    This function demonstrates the proper workflow:
    1. Download PDF temporarily
    2. Extract text
    3. Store metadata + text in DataFrame
    4. Delete PDF
    5. Save all as single Parquet file
    
    This avoids uploading millions of individual files to Hugging Face.
    
    Args:
        pdf_urls: List of PDF URLs to process
        output_file: Output Parquet file path
    
    Returns:
        DataFrame with processed meetings
    """
    try:
        import httpx
        from PyPDF2 import PdfReader
        import io
        from datetime import datetime
    except ImportError:
        logger.error("Install required packages: pip install httpx PyPDF2")
        return None
    
    logger.info(f"Processing {len(pdf_urls)} PDFs to Parquet format...")
    
    all_meetings = []
    client = httpx.Client(timeout=30)
    
    for i, pdf_url in enumerate(pdf_urls, 1):
        try:
            logger.info(f"  [{i}/{len(pdf_urls)}] Processing {pdf_url}...")
            
            # Download PDF temporarily (don't save to disk)
            response = client.get(pdf_url)
            pdf_bytes = response.content
            
            # Extract text from PDF
            pdf_reader = PdfReader(io.BytesIO(pdf_bytes))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            
            # Store metadata + text (NOT PDF bytes)
            all_meetings.append({
                'source_url': pdf_url,
                'text': text,
                'page_count': len(pdf_reader.pages),
                'file_size_kb': len(pdf_bytes) // 1024,
                'processed_at': datetime.now().isoformat(),
                # Add your metadata extraction here:
                # 'jurisdiction': extract_jurisdiction(text),
                # 'date': extract_date(text),
                # 'title': extract_title(text),
            })
            
            # Delete PDF bytes immediately (free memory!)
            del pdf_bytes
            
        except Exception as e:
            logger.warning(f"  Failed to process {pdf_url}: {e}")
            continue
    
    client.close()
    
    # Convert to DataFrame
    df = pd.DataFrame(all_meetings)
    logger.info(f"Successfully processed {len(df)} PDFs")
    
    # Save as Parquet (compressed)
    df.to_parquet(output_file, compression='snappy', index=False)
    
    file_size_mb = Path(output_file).stat().st_size / (1024 * 1024)
    logger.success(f"✅ Saved to {output_file} ({file_size_mb:.2f} MB)")
    logger.success(f"   This is 1 file, not {len(df)} individual PDFs!")
    
    return df


def main():
    """Main entry point."""
    
    parser = argparse.ArgumentParser(
        description="Upload oral health policy data to Hugging Face"
    )
    parser.add_argument(
        "--repo",
        default=DEFAULT_REPO_NAME,
        help="Hugging Face repo name (e.g., 'username/oral-health-policy-data')"
    )
    parser.add_argument(
        "--discovery",
        action="store_true",
        help="Upload discovery results"
    )
    parser.add_argument(
        "--meetings",
        help="Upload meeting data from CSV/JSON file"
    )
    parser.add_argument(
        "--oral-health",
        help="Upload oral health subset from CSV/JSON file"
    )
    parser.add_argument(
        "--create-card",
        action="store_true",
        help="Create dataset README card"
    )
    parser.add_argument(
        "--process-pdfs",
        help="Process PDF URLs from file and save as Parquet (CORRECT way to handle PDFs)"
    )
    
    args = parser.parse_args()
    
    # Special case: Process PDFs to Parquet first
    if args.process_pdfs:
        logger.info("Processing PDFs to Parquet format (not uploading individual files)...")
        # Load PDF URLs from file
        pdf_urls = []
        with open(args.process_pdfs) as f:
            pdf_urls = [line.strip() for line in f if line.strip()]
        
        # Process to Parquet
        df = process_pdfs_to_parquet(pdf_urls, "meetings_processed.parquet")
        
        if df is not None:
            logger.success("✅ PDFs processed! Now upload the Parquet file:")
            logger.success(f"   python {__file__} --meetings meetings_processed.parquet")
        return
    
    # Initialize uploader
    uploader = HuggingFaceUploader(args.repo)
    
    # Upload based on flags
    if args.discovery:
        uploader.upload_discovery_results()
    
    if args.meetings:
        uploader.upload_meeting_data(args.meetings)
    
    if args.oral_health:
        uploader.upload_oral_health_subset(args.oral_health)
    
    if args.create_card:
        uploader.create_dataset_card()
    
    if not any([args.discovery, args.meetings, args.oral_health, args.create_card]):
        logger.warning("No action specified. Use --discovery, --meetings, or --oral-health")
        parser.print_help()


if __name__ == "__main__":
    main()
