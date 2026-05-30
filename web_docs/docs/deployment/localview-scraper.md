---
sidebar_position: 5
---

# LocalView Scraper Setup

Run the LocalView scrapers locally to keep municipal meeting data updated with 2025/2026 meetings.

## Quick Start

### 1. Install Dependencies

```bash
cd /home/developer/projects/open-navigator
source .venv/bin/activate
pip install google-api-python-client youtube-transcript-api
```

### 2. Get YouTube API Key

1. Visit [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create a new project or select existing
3. Enable **YouTube Data API v3**
4. Create credentials → API key
5. Add to `.env`:

```bash
YOUTUBE_API_KEY=your_api_key_here
```

### 3. Run the Scraper

```bash
# Update all channels (last 30 days)
python scripts/localview/scrape_youtube_channels.py --update

# Extract transcripts
python scripts/localview/extract_transcripts.py --year 2026

# Or run everything at once
./scripts/localview/update_all.sh
```

## What Gets Scraped

The scraper collects:
- **Video metadata**: Title, date, duration, view count
- **Meeting type**: City Council, Planning, School Board, etc.
- **Transcripts**: Auto-generated captions (if available)
- **Timestamps**: Segment-level timestamps for search

## Output Files

All data is saved to `data/cache/localview/`:

```
data/cache/localview/
├── municipality_channels.csv    # List of YouTube channels
├── videos_2026.csv              # Video metadata by year
└── transcripts/                 # Transcript text files
    ├── abc123.txt              # Plain text transcript
    └── abc123.json             # Timestamped segments
```

## Adding New Channels

### Method 1: Manual Add

```bash
python scripts/localview/update_municipality_list.py \
  --add "Birmingham, AL" "UCXzJ0f8fVRv42jOqVXlQ8jA" "AL"
```

### Method 2: Search and Add

```bash
# Search for channels
python scripts/localview/update_municipality_list.py \
  --cities "Montgomery,Mobile,Huntsville"
```

Then manually edit `data/cache/localview/municipality_channels.csv` to add found channels.

### Method 3: Direct CSV Edit

Edit `data/cache/localview/municipality_channels.csv`:

```csv
municipality,channel_id,state,population,added_date
"Your City, ST",UCyourchannelidhere,ST,100000,2026-05-03
```

## Finding Municipal YouTube Channels

**Search patterns:**
- Google: "[City Name] [State] government YouTube"
- YouTube search: "[City] city council meetings"
- Check official city website for video archive links

**Common channel name patterns:**
- `@[cityname]gov`
- `[CityName]Government`
- `[cityname]tv`

**Example channels:**
- Seattle: `UCMFAKdxL6sATpkRqLdJyKUg`
- Boston: `UCiMB3gH6PLe-JMDhxX4ZsmA`
- Atlanta: `UCMdVz77sRLkqJe5NLVB7uTQ`

## Automation

### Weekly Cron Job

```bash
# Add to crontab
0 2 * * 0 cd /home/developer/projects/open-navigator && ./scripts/localview/update_all.sh
```

This runs every Sunday at 2 AM to scrape new meetings.

### GitHub Actions (Recommended)

Create `.github/workflows/localview-update.yml`:

```yaml
name: Update LocalView Data

on:
  schedule:
    - cron: '0 2 * * 0'  # Weekly on Sunday
  workflow_dispatch:      # Manual trigger

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install google-api-python-client youtube-transcript-api polars
      
      - name: Scrape videos
        env:
          YOUTUBE_API_KEY: ${{ secrets.YOUTUBE_API_KEY }}
        run: |
          python scripts/localview/scrape_youtube_channels.py --update
      
      - name: Extract transcripts
        run: |
          python scripts/localview/extract_transcripts.py --year 2026
      
      - name: Commit updates
        run: |
          git config user.name "LocalView Bot"
          git config user.email "bot@communityone.com"
          git add data/cache/localview/
          git commit -m "Update LocalView data ($(date +%Y-%m-%d))" || true
          git push
```

## API Quota Management

YouTube Data API has daily quotas:
- **Default**: 10,000 units/day
- **Search**: 100 units per request
- **Video details**: 1 unit per request

**Tips to stay within quota:**
- Use `--since-days` to limit date range
- Scrape incrementally (daily/weekly) instead of all at once
- Consider multiple API keys for high-volume scraping

## Integration with Open Navigator

After scraping, the data flows through:

1. **Raw data** → `data/cache/localview/`
2. **Bronze layer** → `discovery/localview_ingestion.py`
3. **Gold tables** → `pipeline/create_events_gold_tables.py`
4. **API** → Available via `/api/meetings` endpoint
5. **Frontend** → Searchable in dashboard

Run the full pipeline:

```bash
# Scrape new data
./scripts/localview/update_all.sh

# Load into database
python scripts/discovery/localview_ingestion.py
python pipeline/create_events_gold_tables.py
```

## Troubleshooting

**API key not found:**
```
ValueError: YOUTUBE_API_KEY environment variable required
```
→ Add `YOUTUBE_API_KEY` to `.env` file

**Quota exceeded:**
```
HttpError 403: quotaExceeded
```
→ Wait until tomorrow or use different API key

**No captions available:**
- Some videos don't have captions enabled
- Check `has_captions` field before extracting
- Captions may be disabled by municipality

**Channel not found:**
- Verify channel ID is correct
- Channel may have been deleted or made private
- Search for alternate official channel

## Historical Data

For meetings before 2025, download from Harvard Dataverse:
- **URL**: https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/NJTBEM
- **Download manually** (requires browser)
- **Save to**: `data/cache/localview/`

Files to download:
- `municipalities.csv` - Municipality URLs
- `meetings.csv` - Meeting metadata (2006-2024)
- `videos.csv` - Video URLs

## Next Steps

- [LocalView Integration Guide](../../../docs/LOCALVIEW_INTEGRATION_GUIDE.md)
- [Meetings API Documentation](../api/meetings.md)
- [Event Schema](../data-sources/data-model-erd.md#events)
