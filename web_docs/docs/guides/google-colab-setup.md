---
sidebar_position: 5
---

# Google Colab Setup Guide

Run Open Navigator data processing workflows in Google Colab with GPU/TPU acceleration and Google Drive storage.

## 🎯 When to Use Google Colab

- ✅ Process large datasets without local compute resources
- ✅ Access free GPU/TPU for ML tasks (Gemini AI analysis, embeddings)
- ✅ Bypass local disk space limitations
- ✅ Run long-running jobs without keeping laptop on
- ✅ Share notebooks with collaborators

## 📋 Prerequisites

- Google account
- Google Drive with available storage (15 GB free tier)
- GitHub account (for cloning repository)

## 🚀 Quick Start

### Step 1: Create New Colab Notebook

1. Go to [Google Colab](https://colab.research.google.com/)
2. Click **File** → **New Notebook**
3. Rename notebook: `open-navigator-processing.ipynb`

### Step 2: Mount Google Drive

```python
from google.colab import drive
drive.mount('/content/drive')

# Verify mount
!ls /content/drive/MyDrive/
```

**Authorization:**
1. Click the link that appears
2. Choose your Google account
3. Click "Allow" to give Colab access to Drive
4. Copy the authorization code
5. Paste into Colab input box

### Step 3: Clone Repository

```python
# Navigate to Google Drive
%cd /content/drive/MyDrive/

# Clone repository (only needed first time)
# Skip git hooks to avoid permission issues on Google Drive
!git clone --no-checkout https://github.com/getcommunityone/open-navigator.git
%cd open-navigator
!git config core.hooksPath /dev/null
!git checkout main

# Install Git LFS and pull large files (images, etc.)
!apt-get install -y git-lfs
!git lfs install
!git lfs pull

# Verify clone
!ls -lh
```

**Subsequent runs:**
```python
# Just navigate to existing directory
%cd /content/drive/MyDrive/open-navigator

# Pull latest changes (skip hooks)
!git config core.hooksPath /dev/null
!git pull origin main
!git lfs pull
```

**⚠️ Common Issues:**

**"Permission denied" on git hooks:**
```python
# Fix hook permissions
!git config core.hooksPath /dev/null
# This disables git hooks which don't work on Google Drive
```

**"Files should have been pointers" (Git LFS):**
```python
# Install Git LFS
!apt-get install -y git-lfs
!git lfs install

# Pull actual files (replaces pointers with real files)
!git lfs pull

# Verify images loaded correctly
!ls -lh frontend/public/*.png
```

### Step 4: Install Dependencies

```python
# Install Python packages
!pip install -q -r requirements.txt

# Verify installation
!pip list | grep pandas
!pip list | grep psycopg2
```

### Step 5: Configure Environment

```python
# Create .env file with secrets
import os

# Database connection
os.environ['NEON_DATABASE_URL_DEV'] = 'postgresql://user:pass@host:5432/dbname'

# API keys
os.environ['YOUTUBE_API_KEY'] = 'your_youtube_api_key_here'
os.environ['GEMINI_API_KEY'] = 'your_gemini_api_key_here'

# Verify
!echo "Environment configured"
```

**Or upload .env file:**
```python
from google.colab import files

# Upload .env from your computer
uploaded = files.upload()

# Move to project root
!mv .env /content/drive/MyDrive/open-navigator/
```

## 📊 Common Workflows

### Load YouTube Videos to Bronze

```python
%cd /content/drive/MyDrive/open-navigator

# Load recent videos (last 180 days)
!python packages/scrapers/src/scrapers/youtube/load_youtube_events_to_postgres.py \
  --days 180 \
  --max-videos 200 \
  --skip-transcripts \
  --states AL,MA,WI,GA,IN,WA
```

### Process with Gemini AI

```python
%cd /content/drive/MyDrive/open-navigator

# Analyze meetings with Gemini (uses GPU if available)
!python scripts/datasources/gemini/load_meeting_transcripts.py \
  --meetings-per-channel 10 \
  --delay 3
```

### Run dbt Models

```python
%cd /content/drive/MyDrive/open-navigator/dbt_project

# Install dbt if needed
!pip install -q dbt-postgres

# Run models
!dbt run --select tag:bronze
!dbt run --select tag:ai-extraction
```

### Download YouTube Audio to Google Drive

```python
%cd /content/drive/MyDrive/CommunityOne/open-navigator

# Install yt-dlp if needed
!pip install -q yt-dlp

# Download audio from recent videos (last 30 days)
!python packages/scrapers/src/scrapers/youtube/download_audio_to_drive.py \
  --output-dir /content/drive/MyDrive/CommunityOne/youtube_audio \
  --days 30 \
  --limit 50

# Download from specific channels
!python packages/scrapers/src/scrapers/youtube/download_audio_to_drive.py \
  --output-dir /content/drive/MyDrive/CommunityOne/youtube_audio \
  --channels "City of Seattle,Portland" \
  --limit 100

# Download from specific states
!python packages/scrapers/src/scrapers/youtube/download_audio_to_drive.py \
  --output-dir /content/drive/MyDrive/CommunityOne/youtube_audio \
  --states AL,MA,WI \
  --limit 200
```

**Output Structure:**
```
youtube_audio/
├── City-of-Seattle_UCxxx/
│   ├── 2026-05-01_City Council Meeting.opus
│   ├── 2026-04-28_Planning Commission.opus
│   └── ...
├── Portland-City-Hall_UCyyy/
│   ├── 2026-05-02_Council Session.opus
│   └── ...
```

**Audio Format:**
- Opus codec (best quality, smallest size ~10-20 MB/hour)
- Audio-only (no video)
- Organized by channel → date_title.opus

### Export Data to Google Drive

```python
# Create output directory in Drive
!mkdir -p /content/drive/MyDrive/open-navigator-exports

# Export query results
import pandas as pd
from sqlalchemy import create_engine

engine = create_engine(os.environ['NEON_DATABASE_URL_DEV'])

df = pd.read_sql("""
    SELECT * FROM bronze.bronze_event_youtube
    WHERE event_date >= '2026-01-01'
""", engine)

# Save to Drive
df.to_parquet('/content/drive/MyDrive/open-navigator-exports/youtube_2026.parquet')
df.to_csv('/content/drive/MyDrive/open-navigator-exports/youtube_2026.csv', index=False)

print(f"✅ Exported {len(df):,} rows to Google Drive")
```

## ⚙️ Advanced Configuration

### Use GPU Runtime

1. Click **Runtime** → **Change runtime type**
2. Select **GPU** from Hardware accelerator dropdown
3. Choose **T4** or **A100** (paid tier)
4. Click **Save**

**Verify GPU:**
```python
import torch
print(f"GPU available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU name: {torch.cuda.get_device_name(0)}")
```

### Increase RAM

For large datasets:
1. **Runtime** → **Change runtime type**
2. Select **High-RAM** from Runtime shape
3. Click **Save**

### Keep Session Alive

Colab disconnects after ~90 minutes of inactivity:

```python
# Add to notebook cell
import time
from IPython.display import clear_output

while True:
    print("❤️ Keeping session alive...")
    time.sleep(60)  # Ping every minute
    clear_output(wait=True)
```

**Or use browser extension:**
- [Colab Auto Reconnect](https://chrome.google.com/webstore/detail/colab-auto-reconnect)

### Monitor Progress

```python
# Install progress bars
!pip install -q tqdm

# Use in Python scripts
from tqdm import tqdm
import time

for i in tqdm(range(100), desc="Processing"):
    time.sleep(0.1)
```

## 📁 Organize Google Drive

**Recommended folder structure:**

```
MyDrive/
├── open-navigator/              # Git repository
│   ├── scripts/
│   ├── dbt_project/
│   └── .env
├── open-navigator-exports/      # Output files
│   ├── youtube_2026.parquet
│   └── reports/
└── open-navigator-cache/        # Large cache files
    └── gemini/
```

**Create structure:**
```python
!mkdir -p /content/drive/MyDrive/open-navigator-exports
!mkdir -p /content/drive/MyDrive/open-navigator-cache
```

## 🔒 Security Best Practices

### Don't Hardcode Secrets

❌ **Bad:**
```python
api_key = "AIzaSyABC123..."  # Visible in notebook history!
```

✅ **Good:**
```python
from google.colab import userdata
api_key = userdata.get('GEMINI_API_KEY')
```

**Store secrets in Colab:**
1. Click 🔑 (Secrets) in left sidebar
2. Click **Add new secret**
3. Name: `GEMINI_API_KEY`, Value: your key
4. Click **Save**

### Use Read-Only Database Credentials

For analytics/exports, use read-only credentials:

```python
# Read-only user (safer for Colab)
os.environ['DATABASE_URL_READONLY'] = 'postgresql://readonly:pass@host:5432/db'
```

## 🐛 Troubleshooting

### Git Hooks Permission Error

**Error:**
```
fatal: cannot exec '/content/drive/MyDrive/.../open-navigator/.git/hooks/post-checkout': Permission denied
```

**Fix:**
```python
%cd /content/drive/MyDrive/open-navigator

# Disable git hooks (they don't work on Google Drive FUSE filesystem)
!git config core.hooksPath /dev/null

# Verify
!git config --get core.hooksPath
# Should output: /dev/null
```

**Why this happens:**
- Google Drive FUSE filesystem doesn't preserve execute permissions
- Git hooks need executable permissions to run
- Solution: Disable hooks entirely (they're for pre-commit checks, not needed in Colab)

### Git LFS Files Missing (Image Pointers)

**Error:**
```
Encountered 20 file(s) that should have been pointers, but weren't:
    frontend/public/communityone_logo.jpg
    website/static/img/favicon.ico
    ...
```

**Fix:**
```python
# Install Git LFS
!apt-get update -qq
!apt-get install -y git-lfs

# Initialize Git LFS for this repository
%cd /content/drive/MyDrive/open-navigator
!git lfs install

# Pull actual files (replaces text pointers with real binary files)
!git lfs pull

# Verify images loaded correctly
!file frontend/public/communityone_logo.jpg
# Should say: "JPEG image data", not "ASCII text"
```

**Why this happens:**
- Repository uses Git LFS (Large File Storage) for images/binaries
- Plain `git clone` downloads text pointers instead of actual files
- Need `git lfs pull` to fetch the real files

**To avoid this in future clones:**
```python
# Install Git LFS BEFORE cloning
!apt-get install -y git-lfs
!git lfs install

# Then clone (will automatically fetch LFS files)
!git clone https://github.com/getcommunityone/open-navigator.git
```

### "No module named 'xyz'"

```python
# Install missing package
!pip install xyz

# Or reinstall all requirements
!pip install -q -r requirements.txt --force-reinstall
```

### "Permission denied" when writing to Drive

```python
# Remount Drive
from google.colab import drive
drive.flush_and_unmount()
drive.mount('/content/drive')
```

### "Runtime disconnected"

- Save work frequently: **Ctrl+S** or **File** → **Save**
- Download important outputs: `files.download('output.csv')`
- Use checkpoints in long-running scripts

### "Out of memory"

```python
# Clear Python variables
import gc
gc.collect()

# Or restart runtime
# Runtime → Restart runtime
```

## 📝 Example Notebook Template

```python
# ========================================
# Open Navigator - Google Colab Workflow
# ========================================

# 1. Mount Google Drive
from google.colab import drive
drive.mount('/content/drive')

# 2. Navigate to project
%cd /content/drive/MyDrive/open-navigator

# 3. Pull latest code (if repo exists)
!git pull origin main

# 4. Install dependencies
!pip install -q -r requirements.txt

# 5. Set environment variables
from google.colab import userdata
import os

os.environ['NEON_DATABASE_URL_DEV'] = userdata.get('DATABASE_URL')
os.environ['GEMINI_API_KEY'] = userdata.get('GEMINI_API_KEY')

# 6. Run data processing
print("🚀 Starting data load...")
!python packages/scrapers/src/scrapers/youtube/load_youtube_events_to_postgres.py \
  --days 30 \
  --max-videos 100 \
  --skip-transcripts

print("✅ Data load complete!")

# 7. Export results
import pandas as pd
from sqlalchemy import create_engine

engine = create_engine(os.environ['NEON_DATABASE_URL_DEV'])

df = pd.read_sql("""
    SELECT COUNT(*) as total_videos, 
           MAX(event_date) as latest_date
    FROM bronze.bronze_event_youtube
""", engine)

print(df)
```

## 🔗 Related Resources

- [Google Colab Documentation](https://colab.research.google.com/notebooks/intro.ipynb)
- [Colab Pro Features](https://colab.research.google.com/signup) - Faster GPUs, longer runtimes
- [Colab Tips & Tricks](https://medium.com/@oribarel/colab-tricks-7e8c07b9e4c6)

## 💡 Tips

- **Save notebooks in Drive** - File → Save a copy in Drive
- **Use markdown cells** - Document your workflow
- **Share notebooks** - Click Share button, send link
- **Schedule runs** - Use [Colab Pro+](https://colab.research.google.com/signup/pricing) background execution
- **Download outputs** - `files.download('filename')` before session ends
- **Check quotas** - Free tier has usage limits, upgrade to Pro if needed

## 🆘 Getting Help

If you encounter issues:

1. Check [Common Errors](#-troubleshooting) above
2. Search [Colab FAQ](https://research.google.com/colaboratory/faq.html)
3. Ask in [GitHub Discussions](https://github.com/getcommunityone/open-navigator/discussions)
4. File bug report with notebook link
