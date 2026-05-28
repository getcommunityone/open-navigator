# Google Colab - Download YouTube Audio
# Copy-paste these cells into Google Colab notebook

# ================================================================================
# CELL 1: Mount Google Drive
# ================================================================================
from google.colab import drive
drive.mount('/content/drive')


# ================================================================================
# CELL 2: Navigate to Project
# ================================================================================
%cd /content/drive/MyDrive/CommunityOne/open-navigator

# Pull latest code
!git config core.hooksPath /dev/null
!git pull origin main


# ================================================================================
# CELL 3: Install Dependencies
# ================================================================================
!pip install -q yt-dlp loguru psycopg2-binary python-dotenv


# ================================================================================
# CELL 4: Set Environment Variables (Database Connection)
# ================================================================================
import os

# Set your database URL (or use Colab secrets)
os.environ['NEON_DATABASE_URL_DEV'] = 'postgresql://user:pass@host:5432/open_navigator'

# Or use Colab secrets:
# from google.colab import userdata
# os.environ['NEON_DATABASE_URL_DEV'] = userdata.get('DATABASE_URL')


# ================================================================================
# CELL 5: Create Output Directory
# ================================================================================
!mkdir -p /content/drive/MyDrive/CommunityOne/youtube_audio


# ================================================================================
# CELL 6: Download Audio - Recent Videos (Last 30 Days)
# ================================================================================
!python packages/scrapers/src/scrapers/youtube/download_audio_to_drive.py \
  --output-dir /content/drive/MyDrive/CommunityOne/youtube_audio \
  --days 30 \
  --limit 50


# ================================================================================
# CELL 7: Download Audio - Specific States
# ================================================================================
!python packages/scrapers/src/scrapers/youtube/download_audio_to_drive.py \
  --output-dir /content/drive/MyDrive/CommunityOne/youtube_audio \
  --states AL,MA,WI \
  --limit 100


# ================================================================================
# CELL 8: Download Audio - Specific Channels
# ================================================================================
!python packages/scrapers/src/scrapers/youtube/download_audio_to_drive.py \
  --output-dir /content/drive/MyDrive/CommunityOne/youtube_audio \
  --channels "Seattle,Portland,Boston" \
  --limit 200


# ================================================================================
# CELL 9: Check Downloaded Files
# ================================================================================
!ls -lh /content/drive/MyDrive/CommunityOne/youtube_audio/

# Count files
!find /content/drive/MyDrive/CommunityOne/youtube_audio -name "*.opus" | wc -l

# List directories
!ls -d /content/drive/MyDrive/CommunityOne/youtube_audio/*/


# ================================================================================
# CELL 10: Download All 2026 Videos (Takes Longer)
# ================================================================================
# WARNING: This will download thousands of files!
# Uncomment to run:

# !python packages/scrapers/src/scrapers/youtube/download_audio_to_drive.py \
#   --output-dir /content/drive/MyDrive/CommunityOne/youtube_audio \
#   --days 180 \
#   --limit 1000


# ================================================================================
# NOTES:
# ================================================================================
# Output Structure:
#   youtube_audio/
#   ├── City-of-Seattle_UCxxx/
#   │   ├── 2026-05-01_City Council Meeting.opus
#   │   ├── 2026-04-28_Planning Commission.opus
#   │   └── ...
#   ├── Portland-City-Hall_UCyyy/
#   │   ├── 2026-05-02_Council Session.opus
#   │   └── ...
#
# Audio Format:
#   - Opus codec (best quality, smallest size)
#   - ~10-20 MB per hour of audio
#   - Audio-only (no video)
#
# Tips:
#   - Files are automatically skipped if already downloaded
#   - Use --limit to test with small batches first
#   - Monitor Google Drive storage quota (15 GB free tier)
#   - Download will continue from where it left off if interrupted
