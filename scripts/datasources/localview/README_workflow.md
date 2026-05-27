# LocalView Scraper Scripts

Scripts for downloading and updating municipal meeting videos and transcripts from LocalView sources.

## Overview

LocalView tracks municipal government meetings across the U.S. This directory contains scrapers to:
- Download meeting videos from YouTube channels
- Extract transcripts and captions
- Update the dataset with 2025/2026 meetings
- Keep data current with ongoing meetings

## Data Sources

1. **Historical Data** (2006-2024): Harvard Dataverse
   - URL: https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/NJTBEM
   - Download CSV files manually and place in `data/cache/localview/`

2. **Current Data** (2025+): YouTube scraper
   - Scrape specific municipal YouTube channels
   - Extract captions/transcripts automatically
   - Update weekly/monthly

## Scripts

### `download_dataverse_dataset.py` - Download Historical Data

Downloads the LocalView dataset from Harvard Dataverse (requires manual auth).

```bash
# Interactive download with browser authentication
python scripts/localview/download_dataverse_dataset.py
```

### `scrape_youtube_channels.py` - Scrape Current Meetings

Scrapes municipal YouTube channels for new meeting videos.

```bash
# Scrape all known channels
python scripts/localview/scrape_youtube_channels.py --update

# Scrape specific channels
python scripts/localview/scrape_youtube_channels.py --channels "UCxxxxx,UCyyyyy"

# Scrape by state
python scripts/localview/scrape_youtube_channels.py --states CA,MA,TX
```

**Features:**
- Uses YouTube Data API v3
- Downloads video metadata
- Extracts captions/transcripts
- Detects meeting type (council, planning, etc.)
- Stores in LocalView format

### `extract_transcripts.py` - Download Captions

Extracts transcripts from YouTube videos using captions.

```bash
# Extract from all videos in cache
python scripts/localview/extract_transcripts.py

# Extract from specific videos
python scripts/localview/extract_transcripts.py --video-ids "abc123,def456"
```

### `update_municipality_list.py` - Update Channel List

Updates the list of municipal YouTube channels by searching for city government channels.

```bash
# Search for new municipal channels
python scripts/localview/update_municipality_list.py --states AL,GA,IN,MA,WA,WI
```

## Setup

### 1. Install Dependencies

```bash
pip install youtube-transcript-api google-api-python-client
```

### 2. Get YouTube API Key

1. Go to: https://console.cloud.google.com/apis/credentials
2. Create a new API key
3. Enable YouTube Data API v3
4. Add to `.env`:

```bash
YOUTUBE_API_KEY=your_api_key_here
```

### 3. Download Historical Data

Visit the Harvard Dataverse and download CSV files:
- https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/NJTBEM

Save to: `data/cache/localview/`

## Output Format

All scrapers output to the LocalView standard format:

**Municipalities** (`data/cache/localview/municipalities.csv`):
```csv
municipality_name,state,county,population,website_url,youtube_channel_id
```

**Videos** (`data/cache/localview/videos_{year}.csv`):
```csv
video_id,municipality_name,meeting_date,meeting_type,video_url,platform,duration_minutes,has_captions,transcript_available
```

**Transcripts** (`data/cache/localview/transcripts/{video_id}.txt`):
- Plain text transcripts
- One file per video
- Timestamps preserved in separate JSON

## Automation

### Weekly Update Cron Job

```bash
# Add to crontab for weekly updates
0 2 * * 0 cd /home/developer/projects/open-navigator && source .venv/bin/activate && python scripts/localview/scrape_youtube_channels.py --update
```

### Manual Update

```bash
# Update all data sources
./scripts/localview/update_all.sh
```

## Integration

After scraping, load data into Open Navigator:

```bash
# Load into bronze/gold tables
python pipeline/create_events_gold_tables.py
```

## Municipality Channels

Common patterns for finding municipal YouTube channels:
- Search: "[City Name] [State] government meetings"
- URL patterns: 
  - youtube.com/@[cityname]gov
  - youtube.com/c/[CityName]Government
  - youtube.com/user/[cityname]tv

## Troubleshooting

**API Quota Exceeded:**
- YouTube API has daily quota limits
- Use `--delay` flag to slow down requests
- Consider multiple API keys for high volume

**Missing Captions:**
- Not all videos have captions enabled
- Some municipalities use third-party platforms (Granicus, Archive.org)
- Check `has_captions` field before attempting extraction

**Authentication Issues:**
- Dataverse requires JavaScript/cookies
- Download manually in browser
- Cannot automate without institutional access
