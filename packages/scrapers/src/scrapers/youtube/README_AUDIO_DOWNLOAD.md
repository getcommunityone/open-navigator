# YouTube Audio Downloader for Google Drive

Download audio-only files from YouTube videos in `bronze_events_youtube` table, organized by channel and date.

## ✨ Features

- 🎵 Audio-only downloads (opus format, ~10-20 MB/hour)
- 📁 Organized by channel → `YYYY-MM-DD_title.opus`
- ⏭️ Skips already downloaded files
- 📊 Progress tracking and resumable
- ☁️ Works seamlessly with Google Drive (Colab)

## 🚀 Quick Start (Google Colab)

### 1. Copy Example Notebook
See [`download_audio_colab_example.py`](download_audio_colab_example.py) for copy-paste cells.

### 2. Mount Google Drive
```python
from google.colab import drive
drive.mount('/content/drive')
```

### 3. Navigate to Project
```python
%cd /content/drive/MyDrive/CommunityOne/open-navigator
```

### 4. Install Dependencies
```python
!pip install -q yt-dlp loguru psycopg2-binary python-dotenv
```

### 5. Run Download Script
```python
# Download recent videos (last 30 days, limit 50)
!python packages/scrapers/src/scrapers/youtube/download_audio_to_drive.py \
  --output-dir /content/drive/MyDrive/CommunityOne/youtube_audio \
  --days 30 \
  --limit 50
```

## 📋 Command Line Options

```bash
--output-dir PATH        # Output directory (default: Google Drive path)
--limit N                # Max videos to download
--channels "A,B,C"       # Filter by channel names (partial match)
--states "AL,MA,WI"      # Filter by state codes
--days N                 # Only videos from last N days
--no-skip-existing       # Re-download existing files
--database-url URL       # Database connection string
```

## 💡 Examples

### Download from Specific States
```bash
python download_audio_to_drive.py \
  --output-dir /content/drive/MyDrive/CommunityOne/youtube_audio \
  --states AL,MA,WI \
  --limit 100
```

### Download from Specific Channels
```bash
python download_audio_to_drive.py \
  --output-dir /content/drive/MyDrive/CommunityOne/youtube_audio \
  --channels "Seattle,Portland,Boston" \
  --limit 200
```

### Download All 2026 Videos
```bash
python download_audio_to_drive.py \
  --output-dir /content/drive/MyDrive/CommunityOne/youtube_audio \
  --days 180 \
  --limit 1000
```

## 📂 Output Structure

```
youtube_audio/
├── City-of-Seattle_UCxxx123/
│   ├── 2026-05-01_City Council Meeting.opus
│   ├── 2026-04-28_Planning Commission.opus
│   └── 2026-04-15_Public Hearing.opus
├── Portland-City-Council_UCyyy456/
│   ├── 2026-05-02_Council Session.opus
│   └── 2026-04-30_Budget Discussion.opus
└── Boston-City-Hall_UCzzz789/
    └── 2026-05-03_Town Hall Meeting.opus
```

## 🎵 Audio Format

- **Codec**: Opus (best quality/size ratio)
- **Size**: ~10-20 MB per hour of audio
- **Quality**: 128 kbps
- **Container**: .opus file

## 📊 Database Query

The script queries `bronze.bronze_events_youtube`:

```sql
SELECT 
    id,
    video_id,
    video_url,
    title,
    event_date,
    channel_id,
    jurisdiction_name,
    state_code
FROM bronze.bronze_events_youtube
WHERE video_url IS NOT NULL
ORDER BY event_date DESC, channel_id
LIMIT 100;
```

## ⚠️ Important Notes

### Google Drive Storage
- Free tier: **15 GB**
- Typical file: **15-30 MB** (1 hour meeting)
- Estimate: **500-1000 files** fit in free tier

### Download Speed
- Depends on network connection
- ~2-5 MB/s typical on Colab
- ~30-60 seconds per file

### Resumable
- Already downloaded files are **automatically skipped**
- Can interrupt and resume without re-downloading
- Use `--no-skip-existing` to force re-download

## 🐛 Troubleshooting

### "ModuleNotFoundError: No module named 'yt_dlp'"
```python
!pip install yt-dlp
```

### "Permission denied" on Google Drive
```python
# Remount Drive
from google.colab import drive
drive.flush_and_unmount()
drive.mount('/content/drive')
```

### "No videos found matching criteria"
Check your filters:
- Verify database has data: `SELECT COUNT(*) FROM bronze.bronze_events_youtube;`
- Try without filters first
- Check states/channels spelling

### Download failed: "Video unavailable"
- Video may have been deleted or made private
- Script will skip and continue with next video

## 🔗 Related Scripts

- [`load_youtube_events_to_postgres.py`](load_youtube_events_to_postgres.py) - Load video metadata to bronze table
- [`download_audio_colab_example.py`](download_audio_colab_example.py) - Copy-paste Colab cells

## 📝 Next Steps

After downloading audio:

1. **Transcribe with Whisper** (OpenAI or local model)
2. **Analyze with Gemini AI** for decisions/topics
3. **Store transcripts** in `bronze.bronze_transcripts_raw`
4. **Extract entities** with dbt models

See [Google Colab Setup Guide](../../../website/docs/guides/google-colab-setup.md) for full workflow.
