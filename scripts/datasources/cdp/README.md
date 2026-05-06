# Council Data Project (CDP) Data Integration

Integrate meeting events, sessions, and transcripts from [Council Data Project](https://councildataproject.org/) instances into Open Navigator's bronze tables.

## ⚠️ PYTHON VERSION REQUIREMENT

**cdp-data requires Python 3.10 or 3.11** (NOT 3.12+)

Your current environment uses Python 3.12, which has pandas version conflicts with cdp-data.

### Quick Setup (Python 3.11)

```bash
# Install Python 3.11
sudo apt install python3.11 python3.11-venv

# Create isolated environment
python3.11 -m venv cdp-env
source cdp-env/bin/activate

# Install cdp-data
pip install cdp-data

# Test it works
python scripts/datasources/cdp/example_fetch.py
```

## 🌐 About CDP

Council Data Project provides infrastructure to index, archive, and make searchable city council meetings. CDP instances are deployed in major cities across the United States.

**✅ CDP is ONLINE and ACTIVE** (verified May 2026)

**Documentation:** https://councildataproject.github.io/cdp-data/  
**Website:** https://councildataproject.org/  
**Status:** ✅ All major instances operational

## 📋 Available CDP Instances

| Instance | City/County | State | URL | Status |
|----------|------------|-------|-----|--------|
| `seattle` | Seattle | WA | https://councildataproject.org/seattle | ✅ Online |
| `portland` | Portland | OR | https://councildataproject.org/portland | ✅ Online |
| `boston` | Boston | MA | https://councildataproject.org/boston | ✅ Online |
| `denver` | Denver | CO | https://councildataproject.org/denver | ✅ Online |
| `king-county` | King County | WA | https://councildataproject.org/king-county | ✅ Online |
| `alameda` | Alameda County | CA | https://councildataproject.org/alameda | ✅ Online |
| `oakland` | Oakland | CA | https://councildataproject.org/oakland | ✅ Online |
| `charlotte` | Charlotte | NC | https://councildataproject.org/charlotte | ✅ Online |
| `san-jose` | San José | CA | https://councildataproject.org/san-jose | ✅ Online |

## 🚀 Integration Options

### Option 1: Using cdp-data Package (Recommended)

The `cdp-data` Python package provides direct access to CDP datasets.

**⚠️ Requirements:**
- Python 3.10-3.11 (not 3.12+ due to pandas dependency conflicts)
- Or use a separate conda environment

```bash
# Create isolated environment for CDP
python3.11 -m venv cdp-env
source cdp-env/bin/activate
pip install cdp-data pandas

# Fetch sessions
python scripts/datasources/cdp/load_cdp_events.py \
  --instance seattle \
  --start-date 2024-01-01
```

**See:** `load_cdp_events.py` for full implementation

### Option 2: Manual Data Export

1. **Visit CDP instance website** (e.g., https://councildataproject.org/seattle)
2. **Browse events** and filter by date range
3. **Export data** using CDP's web interface or API
4. **Load exported data** to bronze tables

### Option 3: Web Scraping (Future)

We can develop custom scrapers for CDP's web interfaces if needed.

## 📊 Data Schema Compatibility

Open Navigator's bronze schema is **fully compatible** with CDP's data model:

### Event Fields Mapping

| CDP Field | Our Bronze Field | Description |
|-----------|------------------|-------------|
| `event_datetime` | `event_datetime` | Meeting date/time |
| `body.name` | `body_name` | "City Council", etc. |
| `body.description` | `body_description` | Body description |
| `agenda_uri` | `agenda_url` | Agenda PDF link |
| `minutes_uri` | `minutes_url` | Minutes PDF link |
| `session_id` | `external_source_id` | CDP session ID |
| `session.video_uri` | `video_url` | Video URL |
| `session_content_hash` | `session_content_hash` | Deduplication hash |

### Database Tables

Data from CDP should be loaded to:
- **bronze.bronze_events_search** - Event metadata
- **bronze.bronze_events_text_ai** - Transcripts (if available)

## 💡 Quick Start Example

### Simple Fetch (Python script)

```bash
# Run the example script
python scripts/datasources/cdp/example_fetch.py
```

This will fetch Seattle sessions from 2024 and show you the data structure.

### Python Code Example

**⚠️ Important:** This is Python code - run it in a Python script or interpreter, NOT directly in bash!

```python
# In a Python file or interactive shell:
from cdp_data import CDPInstances, datasets

ds = datasets.get_session_dataset(
    infrastructure_slug=CDPInstances.Seattle,
    start_datetime="2024-01-01",
    store_transcript=False,
)

print(f"Fetched {len(ds)} sessions")
print(ds.head())
```

### Common Mistake

❌ **DON'T** run Python code directly in bash:
```bash
# This will give "command not found" error:
from cdp_data import CDPInstances  # ❌ Wrong!
```

✅ **DO** run it with Python:
```bash
# Correct way:
python -c "from cdp_data import CDPInstances, datasets; print('Works!')"
```

## 💡 Example: Using cdp-data Package

### Load Last Year's Meetings

```bash
# Seattle meetings from 2025
python scripts/datasources/cdp/load_cdp_events.py \
  --instance seattle \
  --start-date 2025-01-01

# Multiple cities (run separately)
for city in seattle portland boston denver; do
  python scripts/datasources/cdp/load_cdp_events.py \
    --instance $city \
    --start-date 2024-01-01
done
```

### Load with Transcripts for Analysis

```bash
# Get Denver meetings with full transcripts
python scripts/datasources/cdp/load_cdp_events.py \
  --instance denver \
  --start-date 2024-01-01 \
  --store-transcripts
```

Transcripts are stored as:
- JSON files: `transcript.json` (CDP native format)
- CSV files: `transcript.csv` (converted for analysis)

## 🔧 Configuration

### Environment Variables

```bash
export POSTGRES_PASSWORD=your_password  # PostgreSQL password
```

### Database Connection

Default: `postgresql://postgres:password@localhost:5433/open_navigator`

Data loaded to:
- **Schema:** `bronze`
- **Tables:** `bronze_events_search`, `bronze_events_text_ai`

## 📈 Processing Transcripts

CDP transcripts can be loaded and processed:

```python
from cdp_backend.pipeline.transcript_model import Transcript

# Read CDP transcript
with open("transcript.json", "r") as f:
    transcript = Transcript.from_json(f.read())

# Process sentences
for sentence in transcript.sentences:
    print(f"{sentence.start_time}: {sentence.text}")
```

Or convert to DataFrame:

```python
from cdp_data import datasets

sentences_df = datasets.convert_transcript_to_dataframe(transcript)
```

## 🎯 Next Steps

After loading CDP data to bronze:

1. **Run dbt models** to transform to staging/marts:
   ```bash
   cd dbt_project
   dbt run --select stg_bronze_events_search events_search
   ```

2. **Verify data**:
   ```sql
   SELECT COUNT(*), source 
   FROM bronze.bronze_events_search 
   WHERE source = 'cdp'
   GROUP BY source;
   ```

3. **Check transcripts** (if loaded):
   ```sql
   SELECT COUNT(*) 
   FROM bronze.bronze_events_text_ai 
   WHERE source = 'cdp';
   ```

## 📚 Resources

- **CDP Documentation:** https://councildataproject.github.io/cdp-data/
- **CDP Backend Models:** https://councildataproject.org/cdp-backend/database_models.html
- **Open Navigator CDP Compatibility:** `/website/docs/data-sources/council-data-project-compatibility.md`

## ⚠️ Notes

- CDP instances update regularly - run periodically to get new meetings
- Transcripts can be large - only use `--store-transcripts` when needed
- Each instance has different data availability dates
- Check instance websites for specific coverage dates
