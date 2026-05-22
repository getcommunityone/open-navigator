---
sidebar_position: 8
---

# Loading Meeting Data for Priority States

Guide to loading existing LocalView meeting data and updating with recent scraping for AL, GA, IN, MA, WA, WI.

## 📊 Current Meeting Data Status

### What You Have Now

**OpenStates Legislative Events** (Already loaded):
- Alabama (AL): Legislative committee hearings
- Georgia (GA): Legislative events  
- Indiana (IN): Legislative events
- Massachusetts (MA): Legislative events
- Washington (WA): Legislative events
- Wisconsin (WI): Legislative events

**Location**: `data/gold/states/{STATE}/events_events.parquet`

**What's Missing**: Municipal/local government meetings (city council, county boards, school boards)

## 🎯 Three-Step Process

### Step 1: Check What LocalView Data Exists

LocalView is a Harvard dataset with 153K+ municipal meeting transcripts from YouTube.

```bash
# Check if you have LocalView data downloaded
ls -lh data/cache/localview/

# If you only see municipality_channels.csv with demo data, 
# you need to download the actual LocalView dataset
```

### Step 2: Download LocalView Dataset (Optional)

If you want the full historical dataset (2006-2023):

**Manual Download from Harvard Dataverse:**

1. Visit: https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/NJTBEM
2. Download these files to `data/cache/localview/`:
   - `municipalities.csv` (list of 1000+ jurisdictions)
   - `meetings.csv` (153K meeting metadata)
   - `transcripts.csv` (video transcripts with captions)
3. Run ingestion script:

```bash
python scripts/datasources/localview/localview_ingestion.py
```

**What This Gives You:**
- 153,452 meeting transcripts (2006-2023)
- 1,000+ municipalities across all states
- Full text search of meeting discussions
- Speaker identification and attendance tracking

### Step 3: Scrape Recent Meetings (2024-2026)

The LocalView dataset ends in 2023. To get 2024-2026 data, scrape YouTube directly.

#### A. Find Municipal YouTube Channels

First, you need to discover YouTube channels for municipalities in your 6 states.

**Option 1: Use Discovery Scripts**

```bash
# Discover government URLs for priority states
python scripts/discovery/discover_jurisdictions.py \
    --states AL,GA,IN,MA,WA,WI \
    --types city,county \
    --output data/discovered_urls.json

# Extract YouTube channels from discovered sites
python scripts/localview/update_municipality_list.py \
    --states AL,GA,IN,MA,WA,WI
```

**Option 2: Manual Research**

For major cities in each state:
1. Go to city's official website
2. Look for "Meetings", "City Council", "Agendas"
3. Check if they have YouTube channel link
4. Add to `data/cache/localview/municipality_channels.csv`

Example format:
```csv
municipality,channel_id,state,population,added_date
Birmingham AL,UCxxxxxxxxxxxxxxxxxx,AL,200000,2026-05-03
Atlanta GA,UCyyyyyyyyyyyyyyyyyy,GA,500000,2026-05-03
Indianapolis IN,UCzzzzzzzzzzzzzzzzzz,IN,880000,2026-05-03
```

#### B. Run YouTube Scraper

**Setup:**

```bash
# Get YouTube API key from Google Cloud Console
# https://console.cloud.google.com/apis/credentials

# Add to .env
echo "YOUTUBE_API_KEY=your_key_here" >> .env
```

**Scrape by State:**

```bash
# Scrape all 6 priority states
python scripts/localview/scrape_youtube_channels.py \
    --states AL,GA,IN,MA,WA,WI \
    --since 2024-01-01

# Or scrape specific channels
python scripts/localview/scrape_youtube_channels.py \
    --channels "UCxxxxx,UCyyyyy" \
    --max-videos 100
```

**What This Does:**
1. Gets recent videos from municipal YouTube channels
2. Downloads auto-generated captions/transcripts
3. Extracts meeting metadata (date, title, description)
4. Saves to `data/cache/localview/videos_{STATE}_{date}.parquet`

#### C. Process Transcripts

Extract speaker names and meeting details:

```bash
# Extract transcripts from videos
python scripts/localview/extract_transcripts.py \
    --states AL,GA,IN,MA,WA,WI \
    --output data/gold/meetings/

# Extract contact information from transcripts
python scripts/manage_contacts.py extract \
    --states AL,GA,IN,MA,WA,WI \
    --batch-size 1000
```

## 📁 Final Data Structure

After completing all steps:

```
data/gold/
├── states/
│   ├── AL/
│   │   ├── events_events.parquet          # OpenStates legislative events
│   │   ├── events_participants.parquet
│   │   ├── meetings_local.parquet         # LocalView municipal meetings
│   │   └── contact_official.parquet     # Legislators + local officials
│   ├── GA/
│   │   ├── events_events.parquet
│   │   ├── meetings_local.parquet
│   │   └── contact_official.parquet
│   └── ... (IN, MA, WA, WI)
│
└── meetings/                              # Cross-state meeting data
    ├── meetings_transcripts.parquet       # All 153K transcripts
    ├── contacts_local_officials.parquet   # Aggregated local officials
    └── contacts_meeting_attendance.parquet # Attendance records
```

## 🔍 Querying Meeting Data

### Find Meetings by State

```python
import polars as pl

# Load Alabama meetings
al_meetings = pl.read_parquet('data/gold/states/AL/meetings_local.parquet')

# Filter by date range
recent = al_meetings.filter(
    pl.col('meeting_date') >= '2024-01-01'
)

print(f"Found {len(recent)} Alabama meetings since 2024")
```

### Search Meeting Transcripts

```python
# Load all transcripts
transcripts = pl.read_parquet('data/gold/meetings/meetings_transcripts.parquet')

# Search for oral health mentions
oral_health = transcripts.filter(
    pl.col('caption_text').str.contains('(?i)dental|teeth|oral health|fluoride')
)

# Group by state
by_state = oral_health.group_by('state').count()
print(by_state)
```

### Find Officials Attending Meetings

```python
# Load attendance records
attendance = pl.read_parquet('data/gold/meetings/contacts_meeting_attendance.parquet')

# Find all meetings for a specific official
officials_meetings = attendance.filter(
    pl.col('name') == 'Stephanie Briggs'
)

print(f"Stephanie Briggs attended {len(officials_meetings)} meetings")
```

## 🚀 Quick Start for Development

If you just want to test with sample data:

```bash
# 1. Use existing OpenStates events (already loaded)
python -c "
import polars as pl
df = pl.read_parquet('data/gold/states/AL/events_events.parquet')
print(f'Alabama legislative events: {len(df)}')
print(df.head())
"

# 2. Scrape a single city for testing
python scripts/localview/scrape_youtube_channels.py \
    --channels "UCMFAKdxL6sATpkRqLdJyKUg" \
    --max-videos 10

# 3. Process and view results
python scripts/localview/extract_transcripts.py --latest
```

## 📚 Related Documentation

- [LocalView Integration Guide](../../docs/LOCALVIEW_INTEGRATION_GUIDE.md)
- [Contacts & Meetings Workflow](../../docs/CONTACTS_MEETINGS_WORKFLOW.md)
- [Data Sources](../../docs/DATA_SOURCES.md)

## ⚠️ Important Notes

### API Quotas

YouTube API has daily quotas:
- **10,000 units/day** (free tier)
- Fetching 1 video = ~3 units
- Can scrape ~3,000 videos/day

**Strategy**: Prioritize high-population cities, scrape incrementally

### Storage Requirements

- Full LocalView dataset: ~3 GB compressed
- Transcripts with embeddings: ~10 GB
- Videos (if downloading): ~500 GB (not recommended)

**Recommendation**: Store transcripts only, not videos

### Data Freshness

- OpenStates: Updated weekly (legislative sessions)
- YouTube scraping: Run weekly/monthly for new meetings
- LocalView dataset: Historical data only (2006-2023)

## 🐛 Troubleshooting

### "YOUTUBE_API_KEY not found"

```bash
# Get API key from Google Cloud Console
# Enable YouTube Data API v3
# Create credentials -> API Key
echo "YOUTUBE_API_KEY=your_key_here" >> .env
```

### "No videos found for channel"

- Verify channel ID is correct (starts with "UC")
- Check channel has public videos
- Ensure videos have captions enabled

### "Transcript not available"

- Only videos with auto-captions or manual captions work
- Some cities disable captions (can't extract text)
- Fallback: Use video metadata (title, description)

### "Out of API quota"

```bash
# Check quota usage at:
# https://console.cloud.google.com/apis/api/youtube.googleapis.com/quotas

# Solutions:
# 1. Wait 24 hours for reset
# 2. Request quota increase
# 3. Use multiple API keys (rotate daily)
```
