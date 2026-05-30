---
sidebar_position: 4
---

# Meeting Data Loading Summary

## 📊 Current Status

Based on the analysis of your data for the 6 priority states (AL, GA, IN, MA, WA, WI):

### ✅ What You Have

**OpenStates Legislative Events** (Already Loaded):
- **Alabama**: 1,372 event participants
- **Georgia**: 2,578 event participants
- **Indiana**: 1,420 event participants
- **Massachusetts**: 1,287 event participants
- **Washington**: 2,854 event participants
- **Wisconsin**: 1,907 event participants

**Location**: `data/gold/states/{STATE}/events_participants.parquet`

**Type**: Legislative committee hearings, sessions, bill discussions

### ⚠️ What You're Missing

**LocalView Municipal Meetings** (NOT loaded yet):
- No historical meeting data (2006-2023)
- No scraped YouTube video transcripts (2024-2026)
- No local government meetings (city council, county boards)

**YouTube Channels** (Discovered but not scraped):
- 10 municipal channels identified across 6 states
- Birmingham, Montgomery, Atlanta, Indianapolis, Boston, Cambridge, Seattle, Madison
- Videos not yet downloaded/processed

## 🎯 Three Options to Get Meeting Data

### Option 1: Use Existing OpenStates Data Only (Easiest)

If you only need legislative data (state legislators, committee hearings):

```bash
# Query existing data
python -c "
import polars as pl
df = pl.read_parquet('data/gold/states/AL/events_participants.parquet')
print(f'Alabama: {len(df):,} legislative event participants')
print(df.head())
"
```

**Pros**: Already loaded, no setup needed  
**Cons**: Only state-level legislative events, no municipal meetings

---

### Option 2: Download LocalView Historical Dataset (2006-2023)

Get 153K+ municipal meeting transcripts from Harvard Dataverse.

**Steps:**

1. **Download manually** (Harvard Dataverse requires browser):
   - Visit: https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/NJTBEM
   - Download: `municipalities.csv`, `meetings.csv`, `transcripts.csv`
   - Save to: `data/cache/localview/`

2. **Run ingestion script**:
   ```bash
   ./scripts/localview/load_priority_states.sh --localview
   ```

3. **Query the data**:
   ```bash
   python -c "
   import polars as pl
   df = pl.read_parquet('data/gold/meetings/meetings_transcripts.parquet')
   al = df.filter(pl.col('state') == 'AL')
   print(f'Alabama meetings: {len(al):,}')
   "
   ```

**Pros**: Comprehensive historical data, 1000+ jurisdictions  
**Cons**: Manual download required, data ends in 2023

---

### Option 3: Scrape Recent YouTube Videos (2024-2026)

Get latest meetings from municipal YouTube channels.

**Steps:**

1. **Get YouTube API Key**:
   - Go to: https://console.cloud.google.com/apis/credentials
   - Create project → Enable YouTube Data API v3
   - Create credentials → API Key
   - Add to `.env`: `YOUTUBE_API_KEY=your_key_here`

2. **Run scraper**:
   ```bash
   ./scripts/localview/load_priority_states.sh --scrape
   ```

3. **What this does**:
   - Scrapes 10 municipal YouTube channels
   - Downloads video metadata and auto-captions
   - Extracts meeting transcripts
   - Identifies speakers and attendees
   - Saves to `data/gold/states/{STATE}/meetings_local.parquet`

**Pros**: Most recent data (2024-2026), automated extraction  
**Cons**: Requires API key, quota limits (~3,000 videos/day)

---

## 🚀 Quick Start Commands

### Check Current Status
```bash
python scripts/localview/check_meeting_data.py
```

### Load Historical Data (if downloaded)
```bash
./scripts/localview/load_priority_states.sh --localview
```

### Scrape Recent Meetings (if API key configured)
```bash
./scripts/localview/load_priority_states.sh --scrape
```

### Query OpenStates Events (already loaded)
```bash
python -c "
import polars as pl

states = ['AL', 'GA', 'IN', 'MA', 'WA', 'WI']
for state in states:
    df = pl.read_parquet(f'data/gold/states/{state}/events_participants.parquet')
    print(f'{state}: {len(df):,} participants')
"
```

## 📁 Data Structure After Loading

```
data/gold/
├── states/
│   ├── AL/
│   │   ├── events_events.parquet               # OpenStates legislative events ✅
│   │   ├── events_participants.parquet   # Event participants ✅
│   │   ├── meetings_local.parquet              # LocalView/YouTube meetings ⏳
│   │   └── contact_official.parquet          # All contacts (state + local) ⏳
│   ├── GA/
│   │   └── ... (same structure)
│   └── ... (IN, MA, WA, WI)
│
└── meetings/                                    # Cross-state aggregated data
    ├── meetings_transcripts.parquet            # All 153K meeting transcripts ⏳
    ├── contacts_local_officials.parquet        # All local officials ⏳
    └── contacts_meeting_attendance.parquet     # Attendance records ⏳
```

Legend:
- ✅ Already loaded
- ⏳ Requires loading (Option 2 or 3)

## 🔍 Use Cases

### Find All Events for a State
```python
import polars as pl

# OpenStates legislative events
events = pl.read_parquet('data/gold/states/AL/events_participants.parquet')
print(events.head())
```

### Search Meeting Transcripts (after loading LocalView)
```python
import polars as pl

# Load all meeting transcripts
meetings = pl.read_parquet('data/gold/meetings/meetings_transcripts.parquet')

# Search for oral health mentions
oral_health = meetings.filter(
    pl.col('caption_text').str.contains('(?i)dental|fluoride|oral health')
)

# Group by state
by_state = oral_health.group_by('state').count()
print(by_state)
```

### Find Officials Attending Meetings (after loading)
```python
import polars as pl

# Load attendance
attendance = pl.read_parquet('data/gold/meetings/contacts_meeting_attendance.parquet')

# Filter by state
al_attendance = attendance.filter(pl.col('jurisdiction').str.contains('AL'))
print(f"Alabama meeting attendance records: {len(al_attendance):,}")
```

## 📚 Related Documentation

- **LocalView Integration**: See full integration guide in docs
- **Contacts Workflow**: Contact management documentation
- **Data Sources**: Complete data sources overview

## ❓ FAQ

**Q: Why are event counts showing as 0?**  
A: The events files have timezone parsing issues with Polars. The participant data is complete. Use pandas instead:
```python
import pandas as pd
df = pd.read_parquet('data/gold/states/AL/events_events.parquet')
print(len(df))
```

**Q: Can I skip LocalView and just use OpenStates?**  
A: Yes! OpenStates has legislative events. LocalView adds municipal/local meetings. Choose based on your needs.

**Q: How much does YouTube API cost?**  
A: Free tier: 10,000 units/day (~3,000 videos). More than enough for testing. Production may need quota increase.

**Q: How long does scraping take?**  
A: ~5-10 minutes per 100 videos. For 10 channels × 50 videos = ~25-50 minutes total.

**Q: Can I run this in production?**  
A: Yes! Set up GitHub Actions to run `load_priority_states.sh --scrape` weekly. Videos will auto-update.

## 🎯 Recommended Next Step

**For Development/Testing**: Use existing OpenStates data
```bash
python -c "
import polars as pl
df = pl.read_parquet('data/gold/states/AL/events_participants.parquet')
print(df.head())
"
```

**For Full Feature**: Download LocalView dataset and scrape YouTube
```bash
# 1. Download LocalView from Harvard (manual)
# 2. Run: ./scripts/localview/load_priority_states.sh --localview
# 3. Get YouTube API key
# 4. Run: ./scripts/localview/load_priority_states.sh --scrape
```
