# YouTube Audio Downloader for Google Drive

## Meeting audio to Google Drive (`download_meeting_audio`, #1255, #1270)

The newer CLI downloads a scoped set of meetings and stores them in the owner's personal **Google Drive**
folder `CommunityOne/youtube_audio` through rclone, one file at a time, without filling the local disk.
Never write through the Drive-for-desktop mount (`I:\My Drive`, `/mnt/i`): its cache is on the full C: disk.
Why YouTube, and the limits every run keeps: `web_docs/docs/development/meeting-audio-source-decision.md`.

One-time setup, by the owner (browser sign-in to the personal Google account):

```bash
~/.local/bin/rclone config create gdrive drive scope=drive
~/.local/bin/rclone lsd gdrive:CommunityOne      # the existing youtube_audio folder
~/.local/bin/rclone about gdrive:                # free space (~45 GB needed for the 2026 scope)
```

Run:

```bash
# What is in scope, what we already hold (by location), and hours/GB left to download
python -m scrapers.youtube.download_meeting_audio --data-centers-2026 --dry-run

# Three files as a test, then the rest (polite: 8 s + jitter between videos)
python -m scrapers.youtube.download_meeting_audio --data-centers-2026 --limit 3
python -m scrapers.youtube.download_meeting_audio --data-centers-2026
```

- **Never downloads twice.** Before anything else it inventories the Google Drive folder (`rclone lsf -R`,
  any audio extension), the bronze tracking columns and `data/cache/youtube_audio` (read only), keyed by
  `video_id`. A `video_id` anywhere in a filename counts as held; so do legacy
  `YYYY-MM-DD_<title>.opus` names and tracked paths. Held locally only → the existing file is uploaded.
  Matches are saved to `bronze.bronze_meeting_audio_inventory` and the tracking columns.
- **Where:** `gdrive:CommunityOne/youtube_audio/<state>/<channel_slug>_<channel_id>/YYYY-MM-DD_<title> [<video_id>].opus`
  (the legacy layout plus the id). `--source suiteone|granicus` picks a sibling folder;
  `--remote`, `--community-root` and `--remote-root` override the names.
- **Targets:** `--target rclone` (default; remote `--remote gdrive`, folder `--remote-root CommunityOne/youtube_audio`), `local` or `drive` (a folder, with `--output-dir`).
- **Size:** re-encoded to 64 kbps Opus (~28 MB/h, ~2.5 CPU-minutes per audio hour); `--no-transcode` keeps
  YouTube's ~120 kbps stream.
- **Stops on blocks:** 403/429/bot checks double the pause; three in a row exit with code 3.
- Records `audio_downloaded_at`, `audio_file_path` (the rclone path) and `audio_file_size_mb` on
  `bronze.bronze_event_youtube`.

---

## Legacy: Google Drive downloader (`download_audio_to_drive.py`)

Download audio-only files from YouTube videos in `bronze_event_youtube` table, organized by channel and date.

## ✨ Features

- 🎵 Audio-only downloads (opus format; YouTube's stream is ~120 kbps ≈ 50 MB/hour unless re-encoded)
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
- **Size**: ~50 MB per hour as YouTube serves it (~120 kbps); ~28 MB per hour re-encoded to 64 kbps
- **Quality**: `--opus-bitrate` is ignored when yt-dlp copies an Opus stream; `download_meeting_audio` re-encodes
- **Container**: .opus file

## 📊 Database Query

The script queries `bronze.bronze_event_youtube`:

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
FROM bronze.bronze_event_youtube
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
- Verify database has data: `SELECT COUNT(*) FROM bronze.bronze_event_youtube;`
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
