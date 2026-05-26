# Integration Guide: Reusing Open-Source Municipal Scraping Logic

## Overview
This guide shows how to integrate proven patterns from established open-source projects into the CommunityOne Open Navigatory scraping pipeline.

## Current State
✅ **You already have:**
- Census Gazetteer data with 85,302 jurisdictions (names + FIPS codes)
- GSA .gov domain matching
- 76 discovered URLs ready for scraping
- Legistar platform references in codebase
- Base ScraperAgent class in `agents/scraper.py`

---

## 1. Civic Scraper Integration
**Repository:** `biglocalnews/civic-scraper`
**License:** Apache 2.0 (✅ Compatible)

### What to Adopt:
#### A. Platform Detection Logic
```python
# They have excellent platform detection
# Location: civic_scraper/platforms/__init__.py

PLATFORMS = {
    'legistar': LegistarScraper,
    'granicus': GranicusScraper,
    'calagenda': CalAgendaScraper,
    'civicplus': CivicPlusScraper
}

def detect_platform(url: str) -> Optional[str]:
    """Auto-detect which platform a URL uses"""
    if 'legistar.com' in url or '/Legistar/' in url:
        return 'legistar'
    elif 'granicus.com' in url or '/Mediasite/' in url:
        return 'granicus'
    # ... more patterns
```

**Your Action:** Add `discovery/platform_detector.py` using their patterns

#### B. Document Downloader with Retry Logic
```python
# civic_scraper/download.py has robust downloading
# Features:
# - Exponential backoff
# - Content-type validation
# - Duplicate detection via hash
# - Progress tracking

async def download_document(url: str, session: httpx.AsyncClient) -> bytes:
    """Download with retries and validation"""
    for attempt in range(3):
        try:
            response = await session.get(url, timeout=30.0)
            response.raise_for_status()
            
            # Validate it's actually a document
            content_type = response.headers.get('content-type', '')
            if 'pdf' in content_type or 'html' in content_type:
                return response.content
        except Exception as e:
            if attempt == 2:
                raise
            await asyncio.sleep(2 ** attempt)
```

**Your Action:** Enhance `agents/scraper.py` with their retry patterns

---

## 2. City Scrapers Integration
**Repository:** `city-scrapers/city-scrapers`
**License:** MIT (✅ Compatible)

### What to Adopt:
#### A. Standardized Event Schema
```python
# They normalize all meeting data to a common format
# city_scrapers/core/models.py

@dataclass
class Event:
    title: str
    description: str
    classification: str  # "Board", "Commission", "Council"
    start: datetime
    end: Optional[datetime]
    all_day: bool
    location: Dict[str, Any]
    links: List[Dict[str, str]]  # [{"title": "Agenda", "href": "..."}]
    source: str
    
# Classification types they use:
CLASSIFICATIONS = [
    "Board",
    "Commission", 
    "Committee",
    "Council",
    "Town Hall",
    "Public Hearing"
]
```

**Your Action:** Create `models/meeting_event.py` with this schema for your Silver layer

#### B. Scraper Testing Framework
```python
# They have excellent test patterns
# tests/test_scrapers.py

def test_scraper():
    """Test with frozen HTML responses"""
    scraper = CityScraper()
    
    # Use saved HTML files to avoid live requests during testing
    with open('tests/fixtures/sample_calendar.html') as f:
        results = scraper.parse(f.read())
    
    assert len(results) > 0
    assert results[0].title
    assert results[0].source
```

**Your Action:** Add `tests/fixtures/` directory with sample HTML from different platforms

---

## 3. Council Data Project (CDP) Integration
**Repository:** `CouncilDataProject/cdp-scrapers`
**License:** MIT (✅ Compatible)

### What to Adopt:
#### A. Generic Ingestion Pipeline
```python
# CDP has a beautiful generic scraper pipeline
# cdp_scrapers/scraper_utils.py

class IngestionModel:
    """Standard format for ingested data"""
    sessions: List[Session]  # Individual meetings
    
@dataclass
class Session:
    video_uri: Optional[str]
    session_datetime: datetime
    session_index: int
    caption_uri: Optional[str]
    
@dataclass  
class EventMinutesItem:
    name: str
    minutes_item: MinutesItem
    
    
def reduced_list(items: List[Any], key_attr: str) -> List[Any]:
    """Deduplicate items by a key attribute"""
    seen = set()
    result = []
    for item in items:
        key = getattr(item, key_attr)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
```

**Your Action:** Create `models/ingestion.py` based on their schemas

#### B. Video Transcript Integration (Future)
```python
# CDP processes meeting videos into searchable transcripts
# This is advanced but incredibly valuable

# They use:
# - AWS Transcribe / Google Speech-to-Text
# - Sentence indexing with timestamps
# - Speaker diarization (who said what)

# You could add this in Phase 2 after document scraping works
```

**Your Action:** Document in `docs/ROADMAP.md` for future implementation

---

## 4. Engagic Integration
**Repository:** `Engagic/engagic`
**License:** Check repo (likely AGPL)

### What to Adopt:
#### A. "Matter" Tracking Across Meetings
```python
# Engagic tracks individual legislative items across meetings
# This is PERFECT for oral health policy tracking

@dataclass
class Matter:
    matter_id: str
    matter_number: str  # "Bill 2024-001"
    title: str
    type: str  # "Ordinance", "Resolution", "Motion"
    first_introduced: datetime
    status: str  # "Introduced", "Committee", "Passed", "Failed"
    votes: List[Vote]
    related_documents: List[str]
    
# Track how a fluoridation ordinance evolves:
# Meeting 1: Introduced (just mentioned in minutes)
# Meeting 2: Committee review (document link added)
# Meeting 3: Public hearing (comments recorded)
# Meeting 4: Final vote (result captured)
```

**Your Action:** Create `models/matter.py` for tracking policy evolution

#### B. LLM-Powered Document Parsing
```python
# Engagic uses LLMs to extract structure from "blob" PDFs
# You already have OpenAI configured!

async def extract_agenda_items(pdf_text: str) -> List[AgendaItem]:
    """Use GPT to extract structured items from unstructured text"""
    prompt = """
    Extract agenda items from this meeting minutes text.
    For each item, identify:
    - Item number
    - Title
    - Description  
    - Any votes or decisions
    - Keywords related to health, dental, fluoride, water, public health
    
    Return JSON array.
    """
    
    response = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You extract structured data from government documents"},
            {"role": "user", "content": f"{prompt}\n\n{pdf_text}"}
        ],
        response_format={"type": "json_object"}
    )
    
    return json.loads(response.choices[0].message.content)
```

**Your Action:** Add `extraction/llm_parser.py` using your existing OpenAI setup

---

## 5. Councilmatic Integration
**Repository:** `datamade/councilmatic-starter-template`
**License:** MIT (✅ Compatible)

### What to Adopt:
#### A. Person/Organization Tracking
```python
# Councilmatic tracks who voted on what
# Useful for understanding power dynamics around oral health policy

@dataclass
class Person:
    name: str
    role: str  # "Council Member", "Mayor", "Commissioner"
    district: Optional[str]
    party: Optional[str]
    
@dataclass
class Vote:
    motion: str
    option: str  # "yes", "no", "abstain"
    person: Person
    date: datetime
```

**Your Action:** Add to `models/governance.py`

#### B. Search Interface Patterns
```python
# They have excellent search UX
# filters.py shows what users want:

SEARCH_FILTERS = [
    "date_range",
    "topic",  # ["health", "water", "budget"]
    "organization",  # Which board/commission
    "document_type",  # ["agenda", "minutes", "transcript"]
    "status",  # ["pending", "passed", "failed"]
]

# Your FastAPI endpoints could mirror this
@app.get("/api/search")
async def search_documents(
    query: str,
    topics: List[str] = Query(default=["oral_health", "fluoridation"]),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    state: Optional[str] = None
):
    """Search scraped documents with filters"""
    # Query your Delta Lake Gold layer
```

**Your Action:** Add to `api/routes/search.py` (create if doesn't exist)

---

## Implementation Priorities

### Phase 1: Foundation (Week 1)
- [ ] **Platform Detection** - Add `discovery/platform_detector.py` from Civic Scraper patterns
- [ ] **Standardized Schema** - Create `models/meeting_event.py` from City Scrapers
- [ ] **Enhanced Downloader** - Improve `agents/scraper.py` retry logic

### Phase 2: Scraping (Week 2-3)
- [ ] **Legistar Scraper** - Implement full Legistar support using Civic Scraper patterns
- [ ] **Generic HTML Parser** - Use BeautifulSoup patterns from City Scrapers
- [ ] **PDF Extraction** - Add PyPDF2/pdfplumber support

### Phase 3: Intelligence (Week 4)
- [ ] **LLM Parser** - Add `extraction/llm_parser.py` from Engagic patterns
- [ ] **Matter Tracking** - Create `models/matter.py` for policy evolution
- [ ] **Keyword Detection** - Oral health, fluoridation, dental policy detection

### Phase 4: Scale (Week 5+)
- [ ] **Test All 76 URLs** - Run full scraper on discovered targets
- [ ] **Expand to All Municipalities** - Process all 32,333 jurisdictions
- [ ] **Video Transcripts** - CDP-style video processing (future)

---

## Code Snippets to Add Now

### 1. Platform Detector
**File:** `discovery/platform_detector.py`
```python
"""
Platform detection for municipal websites.
Based on patterns from biglocalnews/civic-scraper.
"""
from typing import Optional
from urllib.parse import urlparse

PLATFORM_PATTERNS = {
    'legistar': [
        'legistar.com',
        '/Legistar/',
        '/LegislationDetail.aspx',
        '/Calendar.aspx'
    ],
    'granicus': [
        'granicus.com',
        '/Mediasite/',
        '/ViewPublisher.php'
    ],
    'municode': [
        'municode.com',
        '/meeting_minutes'
    ],
    'civicplus': [
        'civicplus.com',
        '/AgendaCenter/',
        '/DocumentCenter/'
    ]
}

def detect_platform(url: str) -> Optional[str]:
    """
    Detect which platform a municipality website uses.
    
    Args:
        url: Municipality website URL
        
    Returns:
        Platform name or None if unknown
    """
    url_lower = url.lower()
    
    for platform, patterns in PLATFORM_PATTERNS.items():
        if any(pattern.lower() in url_lower for pattern in patterns):
            return platform
    
    return None


def get_scraper_class(platform: str):
    """Get appropriate scraper class for platform"""
    from scrapers.legistar import LegistarScraper
    from scrapers.granicus import GranicusScraper
    from scrapers.generic import GenericScraper
    
    scrapers = {
        'legistar': LegistarScraper,
        'granicus': GranicusScraper
    }
    
    return scrapers.get(platform, GenericScraper)
```

### 2. Meeting Event Model
**File:** `models/meeting_event.py`
```python
"""
Standardized meeting event model.
Based on City Scrapers schema.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any

@dataclass
class Location:
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None

@dataclass
class Link:
    title: str  # "Agenda", "Minutes", "Video"
    href: str
    content_type: Optional[str] = None  # "application/pdf", "text/html"

@dataclass
class MeetingEvent:
    """
    Normalized representation of a government meeting.
    Compatible with City Scrapers format.
    """
    # Core identification
    id: str  # Hash of source_url + start_time
    title: str
    description: str
    classification: str  # "Board", "Commission", "Council", "Committee"
    
    # Temporal
    start: datetime
    end: Optional[datetime] = None
    all_day: bool = False
    
    # Spatial
    location: Location
    
    # Content
    links: List[Link] = field(default_factory=list)
    source: str = ""  # Original URL
    
    # Metadata
    jurisdiction_name: str = ""
    state_code: str = ""
    fips_code: Optional[str] = None
    scraped_at: datetime = field(default_factory=datetime.utcnow)
    
    # Health policy relevance (your special sauce!)
    oral_health_relevant: bool = False
    keywords_found: List[str] = field(default_factory=list)
    confidence_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Delta Lake storage"""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'classification': self.classification,
            'start': self.start.isoformat(),
            'end': self.end.isoformat() if self.end else None,
            'all_day': self.all_day,
            'location_name': self.location.name,
            'location_address': self.location.address,
            'links': [{'title': l.title, 'href': l.href} for l in self.links],
            'source': self.source,
            'jurisdiction_name': self.jurisdiction_name,
            'state_code': self.state_code,
            'fips_code': self.fips_code,
            'scraped_at': self.scraped_at.isoformat(),
            'oral_health_relevant': self.oral_health_relevant,
            'keywords_found': self.keywords_found,
            'confidence_score': self.confidence_score
        }
```

### 3. Enhanced Discovery Pipeline
**Add to:** `discovery/discovery_pipeline.py`
```python
    async def discover_platform_capabilities(self):
        """
        For each discovered URL, detect which platform it uses.
        This prepares optimal scraping strategies.
        """
        from discovery.platform_detector import detect_platform
        
        logger.info("Detecting platforms for discovered URLs...")
        
        silver_path = f"{settings.delta_lake_path}/silver/discovered_urls"
        urls_df = self.spark.read.format("delta").load(silver_path)
        
        enriched_urls = []
        for row in urls_df.take(urls_df.count()):
            row_dict = row.asDict()
            url = row_dict['url']
            
            # Detect platform
            platform = detect_platform(url)
            row_dict['platform'] = platform if platform else 'generic'
            row_dict['scraper_ready'] = platform is not None
            
            enriched_urls.append(row_dict)
        
        # Write back to Silver layer with platform info
        from pyspark.sql import Row
        enriched_df = self.spark.createDataFrame([Row(**u) for u in enriched_urls])
        enriched_df.write.format("delta").mode("overwrite").save(silver_path)
        
        logger.success(f"Platform detection complete - {len(enriched_urls)} URLs analyzed")
        
        return enriched_urls
```

---

## Next Steps

1. **Review Licenses** - All mentioned projects use permissive licenses (MIT/Apache 2.0), but double-check
2. **Clone Repos Locally** - Study their code structure:
   ```bash
   cd /tmp
   git clone https://github.com/biglocalnews/civic-scraper
   git clone https://github.com/city-scrapers/city-scrapers
   ```
3. **Add Attribution** - In your `README.md`, credit these projects
4. **Start with Platform Detector** - Implement `discovery/platform_detector.py` first
5. **Test with Your 76 URLs** - Run platform detection on your discovered URLs

---

## Resources

- **Civic Scraper Docs**: https://github.com/biglocalnews/civic-scraper/wiki
- **City Scrapers Tutorial**: https://cityscrapers.org/docs/development/
- **CDP Architecture**: https://councildataproject.org/
- **Legistar API Docs**: https://webapi.legistar.com/Home/Examples

---

## Questions to Consider

1. **Do you want video transcript support?** (CDP pattern, requires AWS/GCP credits)
2. **How important is real-time tracking?** (vs batch processing)
3. **Will you expose a public API?** (Councilmatic patterns useful here)
4. **Need to track voting records?** (Councilmatic person/vote models)

Let me know which phase you want to implement first!
