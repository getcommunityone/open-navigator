#!/usr/bin/env python3
"""
Upload nonprofit gold tables to Hugging Face Datasets.

This uploads the 4 nonprofit gold tables (1.9M+ organizations from IRS EO-BMF):
- nonprofits_organizations.parquet (main org data)
- nonprofits_financials.parquet (financial details)
- nonprofits_programs.parquet (program activities)
- nonprofits_locations.parquet (geographic data)

Usage:
    # Install requirements
    pip install huggingface_hub datasets pyarrow

    # Set your token (get from https://huggingface.co/settings/tokens)
    export HF_TOKEN="hf_YOUR_TOKEN_HERE"
    
    # Upload all nonprofit tables
    python scripts/upload_nonprofits_to_hf.py --all
    
    # Upload specific table
    python scripts/upload_nonprofits_to_hf.py --table organizations
    
    # Upload to your own repo
    python scripts/upload_nonprofits_to_hf.py --all --repo "your-username/nonprofits"
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


class NonprofitHFUploader:
    """Upload nonprofit gold tables to HuggingFace."""
    
    # Define the 5 nonprofit gold tables
    NONPROFIT_TABLES = {
        "organizations": {
            "file": "nonprofits_organizations.parquet",
            "description": "Main nonprofit organization data (1.9M+ orgs from IRS EO-BMF)",
            "split": "organizations"
        },
        "financials": {
            "file": "nonprofits_financials.parquet",
            "description": "Financial details (assets, income, revenue)",
            "split": "financials"
        },
        "programs": {
            "file": "nonprofits_programs.parquet",
            "description": "Program activities and services",
            "split": "programs"
        },
        "locations": {
            "file": "nonprofits_locations.parquet",
            "description": "Geographic locations (address, city, state, ZIP)",
            "split": "locations"
        },
        "fundraisers": {
            "file": "nonprofits_fundraisers.parquet",
            "description": "Fundraising campaigns and donation info (Every.org enriched data)",
            "split": "fundraisers"
        }
    }
    
    def __init__(self, repo_name: str = None, token: str = None):
        """
        Initialize uploader.
        
        Args:
            repo_name: HF repo prefix (e.g., "CommunityOne/oral-health-nonprofits")
                      Each table will be uploaded to its own dataset:
                      - CommunityOne/oral-health-nonprofits-organizations
                      - CommunityOne/oral-health-nonprofits-financials
                      - CommunityOne/oral-health-nonprofits-programs
                      - CommunityOne/oral-health-nonprofits-locations
            token: HF token (or set HF_TOKEN environment variable)
        """
        self.repo_prefix = repo_name or "CommunityOne/one-nonprofits"
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
        logger.info(f"📦 Dataset prefix: {self.repo_prefix}")
    
    def upload_table(self, table_name: str):
        """
        Upload a single nonprofit table to its own HuggingFace dataset.
        
        Args:
            table_name: Name of table (organizations, financials, programs, locations)
        """
        if table_name not in self.NONPROFIT_TABLES:
            raise ValueError(f"Unknown table: {table_name}. Choose from: {list(self.NONPROFIT_TABLES.keys())}")
        
        table_info = self.NONPROFIT_TABLES[table_name]
        file_path = self.gold_path / table_info["file"]
        
        # Create dataset-specific repo name
        repo_name = f"{self.repo_prefix}-{table_name}"
        
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            logger.error(f"Run: python scripts/create_all_gold_tables.py --nonprofits-only --use-irs --download-all-irs")
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
        logger.info(f"  Size: {file_path.stat().st_size / (1024 * 1024):.2f} MB")
        
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
    
    def upload_all(self):
        """Upload all nonprofit gold tables."""
        logger.info("🚀 Uploading all nonprofit tables to HuggingFace...")
        
        results = {}
        for table_name in self.NONPROFIT_TABLES.keys():
            try:
                success = self.upload_table(table_name)
                results[table_name] = "✅ Success" if success else "❌ Failed"
            except Exception as e:
                logger.error(f"Failed to upload {table_name}: {e}")
                results[table_name] = f"❌ Error: {e}"
        
        # Summary
        logger.info("\n📊 Upload Summary:")
        for table_name, status in results.items():
            logger.info(f"  {status}: {table_name}")
        
        logger.success(f"\n🎉 All uploads complete!")
        logger.success(f"   View datasets:")
        for table_name in self.NONPROFIT_TABLES.keys():
            logger.success(f"   - https://huggingface.co/datasets/{self.repo_prefix}-{table_name}")
        
        # Don't create README - each dataset will have its own auto-generated one
    
    def create_readme(self):
        """Create README.md for the dataset."""
        readme = f"""---
license: cc0-1.0
task_categories:
- text-classification
- question-answering
size_categories:
- 1M<n<10M
---

# U.S. Nonprofit Organizations Dataset

Comprehensive dataset of **1.9M+ U.S. tax-exempt nonprofit organizations** from IRS EO-BMF (Exempt Organizations Business Master File).

## Dataset Structure

This dataset contains 4 tables (splits):

### 1. **organizations** (Main Table)
- **Records:** 1.9M+ organizations
- **Source:** IRS EO-BMF (April 2026)
- **Columns:** EIN, name, NTEE code, subsection, tax-exempt status, etc.
- **Use cases:** Finding nonprofits by category, state, or keyword

### 2. **financials**
- **Records:** Financial data for organizations
- **Columns:** Assets, income, revenue, ruling date, tax period
- **Use cases:** Financial analysis, trend tracking

### 3. **programs**
- **Records:** Program activities and services
- **Columns:** Activity codes, group affiliation
- **Use cases:** Understanding nonprofit missions

### 4. **locations**
- **Records:** Geographic information
- **Columns:** Address, city, state, ZIP code
- **Use cases:** Mapping, geographic analysis

## Quick Start

### Load in Python

```python
from datasets import load_dataset

# Load all splits
dataset = load_dataset("{self.repo_name}")

# Access specific tables
orgs = dataset["organizations"]
financials = dataset["financials"]

# Convert to pandas
import pandas as pd
df = pd.DataFrame(orgs)

# Filter by state
alabama_nonprofits = df[df['state'] == 'AL']
print(f"Alabama nonprofits: {{len(alabama_nonprofits):,}}")

# Filter by NTEE category (E = Health)
health_orgs = df[df['ntee_code'].str.startswith('E', na=False)]
print(f"Health organizations: {{len(health_orgs):,}}")
```

### Query via REST API (No Auth Required!)

```bash
# Get first 100 organizations
curl "https://datasets-server.huggingface.co/rows?dataset={self.repo_name}&config=default&split=organizations&offset=0&length=100"

# Search for specific term
curl "https://datasets-server.huggingface.co/search?dataset={self.repo_name}&config=default&split=organizations&query=dental"
```

### Use in JavaScript/TypeScript

```typescript
// Fetch organizations from HuggingFace Datasets Server API
async function fetchNonprofits(offset = 0, limit = 100) {{
  const url = `https://datasets-server.huggingface.co/rows?dataset={self.repo_name}&config=default&split=organizations&offset=${{offset}}&length=${{limit}}`;
  
  const response = await fetch(url);
  const data = await response.json();
  
  return data.rows.map(row => row.row);
}}

// Example: Get first 100 nonprofits
const nonprofits = await fetchNonprofits(0, 100);
console.log(`Loaded ${{nonprofits.length}} nonprofits`);
```

## NTEE Codes (National Taxonomy of Exempt Entities)

Major categories included:
- **E** - Health Organizations (80,000+)
- **P** - Human Services (200,000+)
- **X** - Religion-Related (300,000+ churches)
- **B** - Education
- **C** - Environment
- **And 20+ more categories**

## Data Source

**Official IRS Data:**
- Source: [IRS EO-BMF](https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf)
- Updated: Monthly by IRS
- Coverage: All U.S. tax-exempt organizations with EIN
- License: Public domain (U.S. government data)

## Use Cases

- 🏥 **Health Policy Research:** Find dental clinics, community health centers
- 🙏 **Faith-Based Organizations:** Map churches by denomination
- 📊 **Nonprofit Analysis:** Financial trends, geographic distribution
- 🗺️ **GIS Mapping:** Visualize nonprofit density by region
- 🔍 **Grant Research:** Identify potential partners or funding recipients

## Citation

```bibtex
@misc{{irs_eobmf_2026,
  title = {{Exempt Organizations Business Master File Extract (EO-BMF)}},
  author = {{{{Internal Revenue Service}}}},
  year = {{2026}},
  month = {{April}},
  url = {{https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf}},
  note = {{Record count: 1,952,238 organizations. Updated monthly.}}
}}
```

## License

**Public Domain (CC0-1.0)** - U.S. government data is not subject to copyright.

## Maintainer

Created and maintained by [Open Navigator](https://github.com/getcommunityone/open-navigator)
"""
        
        # Upload README
        try:
            api = HfApi()
            api.upload_file(
                path_or_fileobj=readme.encode('utf-8'),
                path_in_repo="README.md",
                repo_id=self.repo_name,
                repo_type="dataset",
                token=self.token
            )
            logger.success("✅ README.md created!")
        except Exception as e:
            logger.warning(f"Failed to create README: {e}")


def main():
    parser = argparse.ArgumentParser(description="Upload nonprofit gold tables to HuggingFace")
    parser.add_argument("--all", action="store_true", help="Upload all tables")
    parser.add_argument("--table", choices=["organizations", "financials", "programs", "locations"], help="Upload specific table")
    parser.add_argument("--repo", default="CommunityOne/one-nonprofits", help="HuggingFace repo name")
    
    args = parser.parse_args()
    
    if not args.all and not args.table:
        parser.error("Must specify --all or --table")
    
    try:
        uploader = NonprofitHFUploader(repo_name=args.repo)
        
        if args.all:
            uploader.upload_all()
        elif args.table:
            uploader.upload_table(args.table)
    
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
