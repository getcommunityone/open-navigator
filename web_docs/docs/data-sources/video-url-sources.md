---
title: Video URL Sources
---

# 🎯 Integration Status: URL Sources with Video Links

## Summary: Partially Integrated, Need to Add Video URLs

| Source | Status | What We Have | What's Missing | Priority |
|--------|--------|--------------|----------------|----------|
| **MeetingBank** | ⚠️ Partial | Transcripts & summaries | **YouTube/Vimeo URLs** | 🔥 **HIGH** |
| **City Scrapers / Documenters** | ❌ Missing | Event schemas only | **Actual URL database** | 🔥 **HIGH** |
| **Open States** | ❌ Missing | Nothing | **State & local video sources** | 🟡 MEDIUM |

---

## 1. MeetingBank (PARTIALLY INTEGRATED)

### ✅ What We Already Have:
- **Dataset**: `huuuyeah/meetingbank` - 1,366 meetings with transcripts & summaries
- **Integration**: [`discovery/meetingbank_ingestion.py`](../discovery/meetingbank_ingestion.py)
- **Status**: Working, can download and ingest now

### ❌ What's Missing: VIDEO URLs!
The user is correct - MeetingBank has **YouTube and Vimeo URLs** that we're NOT extracting yet!

**Two MeetingBank datasets exist**:
1. `huuuyeah/meetingbank` - Main dataset (what we use now)
2. `lytang/MeetingBank-transcript` - 6,892 transcript segments

Both contain **URLs dictionaries** with:
- YouTube video IDs
- Vimeo links
- Archive.org links

**Archive.org Video Collections**:
- https://archive.org/details/meetingbank-alameda
- https://archive.org/details/meetingbank-boston
- https://archive.org/details/meetingbank-denver
- https://archive.org/details/meetingbank-long-beach
- https://archive.org/details/meetingbank-king-county
- https://archive.org/details/meetingbank-seattle

### 🔥 ACTION NEEDED:
Update `meetingbank_ingestion.py` to extract video URLs:

```python
# Add to meetingbank_ingestion.py

def extract_video_urls_from_meetingbank(meetingbank: dict) -> List[Dict]:
    """
    Extract YouTube and Vimeo URLs from MeetingBank dataset.
    
    MeetingBank stores URLs in the 'urls' field of each meeting instance.
    """
    video_urls = []
    
    for split in ['train', 'validation', 'test']:
        for instance in meetingbank[split]:
            # Extract URL dictionary
            urls = instance.get('urls', {})
            
            # YouTube URLs
            if 'youtube_id' in urls:
                youtube_url = f"https://www.youtube.com/watch?v={urls['youtube_id']}"
                video_urls.append({
                    "meeting_id": instance['id'],
                    "video_url": youtube_url,
                    "platform": "youtube",
                    "city": extract_city_from_id(instance['id'])['name'],
                    "state": extract_city_from_id(instance['id'])['state']
                })
            
            # Vimeo URLs
            if 'vimeo_id' in urls:
                vimeo_url = f"https://vimeo.com/{urls['vimeo_id']}"
                video_urls.append({
                    "meeting_id": instance['id'],
                    "video_url": vimeo_url,
                    "platform": "vimeo",
                    "city": extract_city_from_id(instance['id'])['name'],
                    "state": extract_city_from_id(instance['id'])['state']
                })
            
            # Archive.org URLs
            if 'archive_url' in urls:
                video_urls.append({
                    "meeting_id": instance['id'],
                    "video_url": urls['archive_url'],
                    "platform": "archive_org",
                    "city": extract_city_from_id(instance['id'])['name'],
                    "state": extract_city_from_id(instance['id'])['state']
                })
    
    return video_urls
```

### Also Check: `lytang/MeetingBank-transcript`
This is a companion dataset with 6,892 transcript segments. Load it too:

```python
from datasets import load_dataset

# Load both datasets
meetingbank_main = load_dataset("huuuyeah/meetingbank")
meetingbank_transcripts = load_dataset("lytang/MeetingBank-transcript")

# MeetingBank-transcript has more detailed segment-level data
# Each row has: meeting_id, segment_id, transcript, summary, urls
```

---

## 2. City Scrapers / Documenters.org (NOT INTEGRATED)

### ❌ What We Have:
- Only their **code patterns** (event schema, testing framework)
- We have NOT integrated their **actual URL database**

### What They Have (That We Need):
**Documenters.org** maintains a **centralized database** of meeting URLs for dozens of cities.

### Where the Data Lives:

1. **City Scrapers GitHub Repos** (5 deployments):
   - https://github.com/city-scrapers/city-scrapers (Chicago ~100 agencies)
   - https://github.com/city-scrapers/city-scrapers-pitt (Pittsburgh)
   - https://github.com/city-scrapers/city-scrapers-detroit (Detroit)
   - https://github.com/city-scrapers/city-scrapers-cle (Cleveland)
   - https://github.com/city-scrapers/city-scrapers-la (Los Angeles)

2. **Each Spider File** contains:
   ```python
   # Example: city_scrapers/spiders/chi_board_of_health.py
   class ChiBoardOfHealthSpider(CityScrapersSpider):
       name = "chi_board_of_health"
       agency = "Chicago Board of Health"
       start_urls = ["https://www.chicago.gov/city/en/depts/cdph/provdrs/board_of_health.html"]
       
       # This spider extracts:
       # - Meeting URLs
       # - Video links (often Granicus ViewPublisher with YouTube embeds)
       # - Agenda PDFs
       # - Minutes PDFs
   ```

3. **Granicus "Video" Button Pattern**:
   ```python
   # Many City Scrapers extract Granicus video pages
   # Granicus embeds YouTube/Vimeo in their ViewPublisher interface
   # Pattern: https://city.granicus.com/ViewPublisher.php?view_id=XXX
   # This page contains <iframe src="https://www.youtube.com/embed/VIDEO_ID">
   ```

### 🔥 ACTION NEEDED:
Create `scripts/datasources/cityscrapers/city_scrapers_urls.py`:

```python
"""
Extract URLs from City Scrapers spider files.

City Scrapers maintains 100-500 validated agency URLs across 5 cities.
Each spider file contains start_urls and scraping logic for meeting pages.
"""
import re
import requests
from pathlib import Path
from typing import List, Dict

CITY_SCRAPERS_REPOS = [
    {
        "city": "Chicago",
        "state": "IL",
        "repo": "https://github.com/city-scrapers/city-scrapers",
        "spiders_path": "city_scrapers/spiders"
    },
    {
        "city": "Pittsburgh",
        "state": "PA",
        "repo": "https://github.com/city-scrapers/city-scrapers-pitt",
        "spiders_path": "city_scrapers_pitt/spiders"
    },
    {
        "city": "Detroit",
        "state": "MI",
        "repo": "https://github.com/city-scrapers/city-scrapers-detroit",
        "spiders_path": "city_scrapers_det/spiders"
    },
    {
        "city": "Cleveland",
        "state": "OH",
        "repo": "https://github.com/city-scrapers/city-scrapers-cle",
        "spiders_path": "city_scrapers_cle/spiders"
    },
    {
        "city": "Los Angeles",
        "state": "CA",
        "repo": "https://github.com/city-scrapers/city-scrapers-la",
        "spiders_path": "city_scrapers_la/spiders"
    }
]

def extract_start_urls_from_spider_file(spider_file_content: str) -> List[str]:
    """
    Extract start_urls from a City Scrapers spider file.
    
    Pattern matches:
    - start_urls = ["https://..."]
    - start_urls = ['https://...']
    """
    urls = []
    
    # Match start_urls = [...]
    pattern = r'start_urls\s*=\s*\[(.*?)\]'
    matches = re.findall(pattern, spider_file_content, re.DOTALL)
    
    for match in matches:
        # Extract quoted strings
        url_pattern = r'["\']([^"\']+)["\']'
        found_urls = re.findall(url_pattern, match)
        urls.extend(found_urls)
    
    return urls

def clone_and_extract_city_scrapers_urls() -> List[Dict]:
    """
    Clone all City Scrapers repos and extract URLs from spider files.
    
    Returns list of dicts with:
    - url: Meeting page URL
    - city: City name
    - state: State code
    - agency: Agency name (from spider file)
    - source: "city_scrapers"
    """
    import subprocess
    import tempfile
    
    all_urls = []
    
    with tempfile.TemporaryDirectory() as tmpdir:
        for repo_info in CITY_SCRAPERS_REPOS:
            # Clone repo
            repo_path = Path(tmpdir) / repo_info['city']
            subprocess.run([
                "git", "clone", "--depth", "1",
                repo_info['repo'], str(repo_path)
            ])
            
            # Find spider files
            spiders_path = repo_path / repo_info['spiders_path']
            if not spiders_path.exists():
                continue
            
            for spider_file in spiders_path.glob("*.py"):
                if spider_file.name.startswith("_"):
                    continue
                
                # Read spider file
                content = spider_file.read_text()
                
                # Extract start_urls
                urls = extract_start_urls_from_spider_file(content)
                
                # Extract agency name from spider class
                agency_pattern = r'agency\s*=\s*["\']([^"\']+)["\']'
                agency_match = re.search(agency_pattern, content)
                agency = agency_match.group(1) if agency_match else spider_file.stem
                
                for url in urls:
                    all_urls.append({
                        "url": url,
                        "city": repo_info['city'],
                        "state": repo_info['state'],
                        "agency": agency,
                        "source": "city_scrapers"
                    })
    
    return all_urls
```

### Expected Results:
- **100-500 agency URLs** with validated meeting pages
- **Granicus video page URLs** (many contain YouTube embeds)
- **Legistar URLs** (with API access)
- **PDF agendas and minutes** (publicly accessible)

---

## 3. Open States (NOT INTEGRATED)

### What It Is:
**Open States** (now part of **Plural**) is the most comprehensive state legislative data project.

**Website**: https://openstates.org  
**API**: https://openstates.org/api/  
**Data**: https://data.openstates.org/

### What They Have:
- **State legislatures**: All 50 states + DC + Puerto Rico
- **Local jurisdictions**: Expanding to city councils
- **Sources field**: Contains YouTube channel URLs, Vimeo profiles
- **Video archives**: Many states host videos on YouTube

### API Example:
```python
import requests

# Get jurisdiction info
response = requests.get(
    "https://v3.openstates.org/jurisdictions",
    headers={"X-API-KEY": "YOUR_API_KEY"}  # Free tier: 50k requests/month
)

# Each jurisdiction has:
# - sources: [{"url": "https://youtube.com/@CALegislature"}]
# - legislative_sessions: with video URLs
# - people: legislators with social media
```

### 🔥 ACTION NEEDED:
Create `discovery/openstates_sources.py`:

```python
"""
Extract video sources from Open States API.

Open States tracks video URLs in their 'sources' field for:
- State legislatures (50+ YouTube channels)
- City councils (expanding coverage)
- County boards (select jurisdictions)
"""
import requests
from typing import List, Dict

OPENSTATES_API = "https://v3.openstates.org"

def get_openstates_jurisdictions(api_key: str) -> List[Dict]:
    """
    Fetch all jurisdictions from Open States API.
    
    Returns list of jurisdictions with video sources.
    """
    response = requests.get(
        f"{OPENSTATES_API}/jurisdictions",
        headers={"X-API-KEY": api_key}
    )
    
    jurisdictions = response.json()['results']
    
    video_sources = []
    
    for jurisdiction in jurisdictions:
        # Extract sources field
        sources = jurisdiction.get('sources', [])
        
        for source in sources:
            url = source.get('url', '')
            
            # Check if it's a video platform
            if any(platform in url for platform in ['youtube', 'vimeo', 'granicus']):
                video_sources.append({
                    "jurisdiction_id": jurisdiction['id'],
                    "jurisdiction_name": jurisdiction['name'],
                    "classification": jurisdiction.get('classification', ''),
                    "video_url": url,
                    "platform": extract_platform(url),
                    "source": "openstates"
                })
    
    return video_sources

def extract_platform(url: str) -> str:
    """Extract platform from URL."""
    if 'youtube.com' in url or 'youtu.be' in url:
        return 'youtube'
    elif 'vimeo.com' in url:
        return 'vimeo'
    elif 'granicus.com' in url:
        return 'granicus'
    elif 'archive.org' in url:
        return 'archive_org'
    else:
        return 'other'
```

### Expected Results:
- **50+ state YouTube channels** (e.g., @CALegislature, @NYSenate)
- **Local council channels** (expanding)
- **Committee hearing archives**
- **Free API**: 50,000 requests/month (plenty for our needs)

---

## 📊 Combined Impact

### Current Coverage (Without These):
- 85,302 Census jurisdictions
- 76 URLs discovered (15% match rate)
- 20 CDP cities
- 1,366 MeetingBank meetings (but no video URLs extracted)

### After Integration:
| Source | URLs Added | Video Links | Quality |
|--------|-----------|-------------|---------|
| **MeetingBank (videos)** | 1,366 | ✅ YouTube/Vimeo | Excellent |
| **City Scrapers (URLs)** | 100-500 | ✅ Granicus → YouTube | Good |
| **Open States (channels)** | 50-100 | ✅ YouTube channels | Excellent |
| **TOTAL NEW** | **1,500-2,000** | **✅ All have videos** | **High** |

### Why This Matters:
🎯 **Video URLs = Transcription Ready**
- YouTube has auto-captions (free API)
- Vimeo has captions (often)
- Can use Whisper for transcription
- Archive.org has downloadable videos

🎯 **Validated Sources**
- All these URLs are already scraped/validated by other projects
- High success rate (80-100%)
- Active maintenance by civic tech community

---

## 🚀 Implementation Priority

### Week 1: Update MeetingBank Integration (2 hours)
```bash
# Update meetingbank_ingestion.py to extract video URLs
# Load lytang/MeetingBank-transcript dataset
# Extract YouTube IDs, Vimeo IDs, Archive.org links
# Write to bronze/meetingbank_video_urls table
```

**Expected**: 1,366 video URLs (100% success)

### Week 2: City Scrapers URL Extraction (1 day)
```bash
# Clone 5 City Scrapers repos
# Extract start_urls from spider files
# Parse Granicus video pages for YouTube embeds
# Write to bronze/city_scrapers_urls table
```

**Expected**: 100-500 validated meeting URLs

### Week 3: Open States Integration (4 hours)
```bash
# Sign up for Open States API (free)
# Fetch jurisdictions with video sources
# Extract YouTube channels and Vimeo profiles
# Write to bronze/openstates_sources table
```

**Expected**: 50-100 legislative video sources

---

## ✅ Summary

| Integration | Status | Action Needed | Time | Priority |
|-------------|--------|---------------|------|----------|
| **MeetingBank videos** | ⚠️ Partial | Extract video URLs from existing integration | 2 hours | 🔥 **HIGH** |
| **City Scrapers URLs** | ❌ Missing | Clone repos, parse spider files | 1 day | 🔥 **HIGH** |
| **Open States** | ❌ Missing | API integration, extract sources | 4 hours | 🟡 MEDIUM |

**Bottom line**: We have MeetingBank transcripts but NOT the video URLs yet. City Scrapers and Open States are completely missing. All three would add 1,500-2,000 **verified video URLs** - the highest quality sources possible! 🎯
