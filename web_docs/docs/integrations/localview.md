# 📚 LocalView Integration Guide

## Overview

**LocalView** is a Harvard University dataset containing **1,000-10,000 municipality URLs** with meeting videos and transcripts. It's the **largest known database of municipal meeting video archives**.

**Challenge**: The Harvard Dataverse requires JavaScript and may have CAPTCHA verification, so we need to download the files manually.

---

## Step-by-Step Download Instructions

### 1. Visit the Harvard Dataverse Website

**URL**: https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/NJTBEM

### 2. Navigate to the Files Section

Once the page loads:
1. Scroll down to the **"Files"** section
2. Look for downloadable CSV/TAB files with names like:
   - `municipalities.csv` or `municipalities.tab`
   - `meetings.csv` or `meetings.tab`
   - `videos.csv` or `videos.tab`
   - Or similar naming patterns

### 3. Download the Files

Click the **"Download"** button for each file:
- Download all CSV/TAB files related to municipalities, meetings, and videos
- Save them to: `/home/developer/projects/open-navigator/data/cache/localview/`

**Expected files** (names may vary):
```
data/cache/localview/
├── municipalities.csv     # List of municipalities with URLs
├── meetings.csv           # Meeting metadata
├── videos.csv             # Video URLs and metadata
└── README.txt             # Dataset documentation (if available)
```

### 4. Expected Data Structure

The LocalView dataset typically includes:

**Municipalities file** (municipalities.csv):
- `municipality_name` - City/town name
- `state` - Two-letter state code
- `county` - County name
- `population` - Population count
- `website_url` - Official government website
- `meeting_page_url` - Link to meetings/agendas page
- `video_archive_url` - Link to video archive

**Meetings file** (meetings.csv):
- `meeting_id` - Unique identifier
- `municipality_name` - City/town name
- `meeting_date` - Date of meeting
- `meeting_type` - Type (Council, Planning, etc.)
- `video_url` - Direct link to video
- `transcript_available` - Boolean flag
- `transcript_url` - Link to transcript (if available)

**Videos file** (videos.csv):
- `video_id` - Unique identifier
- `video_url` - Direct video link
- `platform` - Platform (YouTube, Granicus, etc.)
- `duration_minutes` - Video length
- `has_captions` - Caption availability

---

## Integration Script Usage

### After Downloading Files

Once you've downloaded the files to `data/cache/localview/`, run:

```bash
cd /home/developer/projects/open-navigator
source venv/bin/activate

# Run the ingestion script
python scripts/discovery/localview_ingestion.py
```

### What the Script Does

1. **Reads downloaded CSV files** from cache directory
2. **Parses municipality data** - Names, states, URLs
3. **Extracts video URLs** - Direct links to meeting videos
4. **Identifies platforms** - YouTube, Granicus, Vimeo, Archive.org
5. **Writes to Bronze layer** - `bronze/localview_municipalities` and `bronze/localview_videos`

### Expected Output

```
[INFO] Loading LocalView data from cache...
[INFO] Found 1,247 municipalities
[INFO] Found 8,453 meeting videos
[INFO] Platforms detected:
  - YouTube: 3,421 videos
  - Granicus: 2,876 videos
  - Vimeo: 1,234 videos
  - Other: 922 videos
[SUCCESS] ✓ Written 1,247 municipalities to bronze/localview_municipalities
[SUCCESS] ✓ Written 8,453 videos to bronze/localview_videos
```

---

## Alternative: API Access (If Available)

**Check if LocalView provides API access:**

Some Harvard Dataverse datasets offer API access. Try:

```bash
# Check for API availability
curl -I "https://dataverse.harvard.edu/api/datasets/:persistentId/?persistentId=doi:10.7910/DVN/NJTBEM"
```

If successful, we can update the script to use the API instead of manual download.

---

## Troubleshooting

### Problem: Can't Find CSV Files

**Solution**: The files might be in TAB format. The ingestion script handles both CSV and TAB files automatically.

### Problem: Files Have Different Names

**Solution**: Edit the `EXPECTED_FILES` dictionary in `discovery/localview_ingestion.py` to match the actual filenames.

### Problem: Data Format is Different

**Solution**: Check the README.txt or dataset documentation on Harvard Dataverse. Update the column mappings in the script to match.

### Problem: CAPTCHA Blocks Download

**Solution**: 
1. Use a web browser (not curl/wget)
2. Complete the CAPTCHA verification
3. Download files manually through the browser
4. Save to `data/cache/localview/`

---

## Data Quality & Coverage

### Expected Coverage

Based on the LocalView research paper:

- **1,000-1,500 municipalities** with verified meeting archives
- **5,000-10,000 meeting videos** with URLs
- **Coverage**: Major cities + medium-sized municipalities
- **Time range**: 2015-2024 (approximately)
- **Focus states**: CA, MA, TX, NY, FL, IL (highest coverage)

### Quality Indicators

- ✅ **Academic validation** - Harvard research project
- ✅ **Human verification** - URLs manually verified
- ✅ **Transcript availability** - Many include automated transcripts
- ✅ **Continuous updates** - Dataset may be updated periodically

---

## Next Steps After Integration

### 1. Combine with Other Sources

```bash
# After running LocalView ingestion
python scripts/discovery/meetingbank_ingestion.py      # 1,366 meetings
python scripts/datasources/cityscrapers/city_scrapers_urls.py         # 100-500 agencies
python scripts/discovery/openstates_sources.py         # 50+ legislatures

# Total: 7,000-12,000 verified URLs!
```

### 2. Deduplicate URLs

Create a deduplication script to merge URLs from all sources:

```python
# discovery/url_deduplication.py
from pyspark.sql.functions import col, count, first

# Read all source tables
localview = spark.read.format("delta").load("bronze/localview_videos")
meetingbank = spark.read.format("delta").load("bronze/meetingbank_meetings")
city_scrapers = spark.read.format("delta").load("bronze/city_scrapers_urls")

# Deduplicate by URL
unique_urls = (
    localview.select("url", "platform", "municipality", "state")
    .union(meetingbank.select("url", "platform", "municipality", "state"))
    .union(city_scrapers.select("url", "platform", "municipality", "state"))
    .dropDuplicates(["url"])
)

print(f"Total unique URLs: {unique_urls.count()}")
```

### 3. Priority Scraping

Use LocalView data to prioritize which municipalities to scrape first:

```sql
-- Find municipalities with the most videos
SELECT municipality, state, COUNT(*) as video_count
FROM bronze.localview_videos
GROUP BY municipality, state
ORDER BY video_count DESC
LIMIT 100
```

---

## Documentation Links

- **Harvard Dataverse**: https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/NJTBEM
- **LocalView Research Paper**: Search for "LocalView municipal meetings dataset" on Google Scholar
- **Harvard Mellon Urbanism Initiative**: https://www.gsd.harvard.edu/project/localview/

---

## Expected Timeline

| Step | Time Required | Priority |
|------|---------------|----------|
| Download files from Harvard Dataverse | 5-10 min | 🔥 HIGH |
| Run ingestion script | 2-5 min | 🔥 HIGH |
| Verify data quality | 5 min | 🟡 MEDIUM |
| Deduplication with other sources | 10 min | 🟡 MEDIUM |

**Total time**: ~30 minutes for complete integration

---

## Questions?

If you encounter issues:

1. Check the dataset documentation on Harvard Dataverse
2. Look at example data in the first few rows
3. Update column mappings in the script accordingly
4. Run with `--sample` flag first to test: `python scripts/discovery/localview_ingestion.py --sample`
