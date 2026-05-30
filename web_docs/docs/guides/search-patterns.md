# Scale and Search Patterns: End-to-End Civic Tech Projects

This guide analyzes **6 additional civic tech projects** focused on full-stack deployments, large-scale data aggregation, and public search portals. These complement our existing integration (Civic Scraper, City Scrapers, CDP, Engagic, Councilmatic) with new patterns for:

- 🤖 **AI summarization** (OpenTowns, MeetingBank)
- 🔍 **Multi-jurisdiction search** (CivicBand, LocalView)
- 🔔 **Keyword alerting** (OpenTowns)
- 📊 **Research-grade pipelines** (LocalView, MeetingBank)
- 🌍 **International adaptability** (OpenCouncil)

---

## 🎯 What's NEW vs. Our Existing Integration

| Pattern | Already Have | NEW from These Projects |
|---------|--------------|-------------------------|
| Platform detection | ✅ Civic Scraper | - |
| Event schema | ✅ City Scrapers | - |
| Video ingestion | ✅ CDP | ✅ LocalView scale patterns |
| Matter tracking | ✅ Engagic | - |
| Search UX | ✅ Councilmatic | ✅ CivicBand cross-jurisdiction |
| **AI Summarization** | ❌ | ✅ **OpenTowns, MeetingBank** |
| **Keyword Alerts** | ❌ | ✅ **OpenTowns** |
| **Scale (1,000+ jurisdictions)** | ⚠️ Partial | ✅ **CivicBand, LocalView** |
| **International patterns** | ❌ | ✅ **OpenCouncil** |

---

## 📚 Project Analysis

### 1. Council Data Project (CDP) ⭐ Already Integrated

**Status**: Already documented in `INTEGRATION_GUIDE.md`

**Key patterns we already use**:
- Video transcript ingestion
- Searchable transcript storage
- Event indexing pipeline

**See**: `docs/INTEGRATION_GUIDE.md` Section 4

---

### 2. OpenTowns 🆕 AI Summarization Pioneer

**GitHub**: https://opentowns.org  
**License**: Open civic-tech (check specific repo)  
**Focus**: Small towns, AI-generated summaries, keyword alerts

#### 🔥 What to Adopt

**A. AI Summarization Pattern**
```python
# They generate readable summaries from raw transcripts/PDFs
# Pattern: transcript → summary → key decisions

from openai import OpenAI
from models.meeting_event import MeetingEvent

async def generate_meeting_summary(event: MeetingEvent, transcript: str) -> dict:
    """
    OpenTowns pattern: Generate human-readable meeting summaries.
    
    Returns:
        {
            'executive_summary': str,      # 2-3 sentences
            'key_decisions': list[str],     # Bullet points
            'health_policy_items': list[str],  # Filtered for oral health
            'next_actions': list[str]       # Follow-up items
        }
    """
    client = OpenAI()
    
    prompt = f"""
    Summarize this local government meeting for public understanding.
    
    Meeting: {event.title}
    Date: {event.start.strftime('%B %d, %Y')}
    Transcript: {transcript[:10000]}  # First 10k chars
    
    Provide:
    1. Executive summary (2-3 sentences)
    2. Key decisions made (bullet points)
    3. Health policy items (if any)
    4. Next actions/follow-ups
    
    Focus on: What decisions were made? What happens next?
    """
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",  # Cost-effective for summaries
        messages=[
            {"role": "system", "content": "You are a civic engagement assistant helping residents understand local government."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3  # Lower for factual accuracy
    )
    
    # Parse response into structured format
    summary_text = response.choices[0].message.content
    
    return {
        'executive_summary': extract_section(summary_text, 'Executive summary'),
        'key_decisions': extract_bullets(summary_text, 'Key decisions'),
        'health_policy_items': extract_bullets(summary_text, 'Health policy'),
        'next_actions': extract_bullets(summary_text, 'Next actions'),
        'raw_summary': summary_text
    }
```

**B. Keyword Alert System**
```python
# OpenTowns sends alerts when keywords appear in meetings
# Pattern: Watch list → match detection → user notification

from typing import List, Dict
import re

class KeywordAlertSystem:
    """
    OpenTowns pattern: Alert users when keywords appear in meetings.
    """
    
    # Oral health keyword categories
    KEYWORD_CATEGORIES = {
        'fluoridation': [
            'fluoride', 'fluoridation', 'water treatment',
            'community water fluoridation', 'CWF'
        ],
        'dental_access': [
            'dental', 'dentist', 'oral health', 'teeth',
            'medicaid dental', 'dental clinic'
        ],
        'public_health': [
            'health department', 'public health', 'CDC',
            'preventive care', 'health equity'
        ]
    }
    
    def detect_keywords(self, text: str) -> Dict[str, List[str]]:
        """
        Find all matching keywords in text.
        
        Returns: {'fluoridation': ['fluoride', 'CWF'], ...}
        """
        text_lower = text.lower()
        matches = {}
        
        for category, keywords in self.KEYWORD_CATEGORIES.items():
            found = []
            for keyword in keywords:
                # Word boundary matching
                pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
                if re.search(pattern, text_lower):
                    found.append(keyword)
            
            if found:
                matches[category] = found
        
        return matches
    
    def generate_alert(self, event: MeetingEvent, matches: Dict[str, List[str]]) -> dict:
        """
        Create alert notification for users.
        """
        return {
            'alert_type': 'keyword_match',
            'jurisdiction': f"{event.jurisdiction_name}, {event.state_code}",
            'meeting_title': event.title,
            'meeting_date': event.start.isoformat(),
            'categories_matched': list(matches.keys()),
            'keywords_found': [kw for kws in matches.values() for kw in kws],
            'meeting_url': event.source,
            'priority': 'high' if 'fluoridation' in matches else 'medium'
        }
```

**Implementation Priority**: 🔥 **HIGH** - Summaries make data usable for advocates

---

### 3. LocalView 🆕 Research-Grade Scale

**Website**: https://www.localview.net  
**GitHub**: https://mellonurbanism.harvard.edu/localview  
**License**: Open-source data pipeline  
**Scale**: Nationwide coverage, largest public dataset

#### 🔥 What to Adopt

**A. Scale Architecture Patterns**

LocalView handles **thousands of jurisdictions** with:
1. **Batch processing** (not real-time)
2. **Distributed storage** (videos + transcripts)
3. **Quality metrics** (completeness scoring)

```python
# LocalView pattern: Process jurisdictions in batches with quality tracking

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class JurisdictionQuality:
    """
    LocalView pattern: Track data quality per jurisdiction.
    """
    jurisdiction_name: str
    state_code: str
    
    # Completeness metrics
    total_meetings_expected: int  # Based on calendar
    total_meetings_found: int
    meetings_with_agendas: int
    meetings_with_minutes: int
    meetings_with_videos: int
    meetings_with_transcripts: int
    
    # Freshness
    last_scraped: datetime
    last_meeting_found: Optional[datetime]
    scraping_frequency: str  # 'daily', 'weekly', 'monthly'
    
    # Health metrics
    consecutive_failures: int
    last_success: Optional[datetime]
    
    @property
    def completeness_score(self) -> float:
        """
        Overall data quality score (0-100).
        """
        if self.total_meetings_expected == 0:
            return 0.0
        
        found_rate = self.total_meetings_found / self.total_meetings_expected
        agenda_rate = self.meetings_with_agendas / max(self.total_meetings_found, 1)
        minutes_rate = self.meetings_with_minutes / max(self.total_meetings_found, 1)
        
        # Weighted average
        score = (
            found_rate * 40 +      # 40%: Finding meetings
            agenda_rate * 30 +      # 30%: Having agendas
            minutes_rate * 30       # 30%: Having minutes
        )
        
        return min(score * 100, 100.0)
    
    @property
    def health_status(self) -> str:
        """
        Scraper health: healthy, degraded, failed
        """
        if self.consecutive_failures >= 5:
            return 'failed'
        elif self.consecutive_failures >= 2:
            return 'degraded'
        else:
            return 'healthy'
```

**B. Batch Processing Strategy**
```python
# LocalView processes in batches, not all-at-once

from pyspark.sql import SparkSession
from typing import Iterator

def process_jurisdictions_in_batches(
    spark: SparkSession,
    batch_size: int = 100,
    priority_filter: str = 'high'
) -> Iterator[dict]:
    """
    LocalView pattern: Process large numbers of jurisdictions efficiently.
    
    Strategy:
    1. Load high-priority jurisdictions first
    2. Process in batches to manage memory
    3. Track quality metrics per batch
    4. Resume from failures
    """
    # Load targets from Gold layer
    targets_df = spark.read.format("delta").load("data/delta/gold/scraping_targets")
    
    # Filter and sort
    priority_targets = targets_df \
        .filter(f"priority_tier = '{priority_filter}'") \
        .orderBy("priority_score", ascending=False)
    
    total_targets = priority_targets.count()
    
    # Process in batches
    for offset in range(0, total_targets, batch_size):
        batch_df = priority_targets.limit(batch_size).offset(offset)
        
        batch_results = {
            'batch_number': offset // batch_size + 1,
            'batch_size': batch_size,
            'jurisdictions_processed': 0,
            'meetings_found': 0,
            'errors': []
        }
        
        for row in batch_df.collect():
            try:
                # Scrape jurisdiction
                meetings = scrape_jurisdiction(row['url'], row['platform'])
                batch_results['jurisdictions_processed'] += 1
                batch_results['meetings_found'] += len(meetings)
                
            except Exception as e:
                batch_results['errors'].append({
                    'jurisdiction': row['jurisdiction_name'],
                    'error': str(e)
                })
        
        yield batch_results
```

**Implementation Priority**: 🔥 **HIGH** - Essential for scaling to 32,333 municipalities

---

### 4. MeetingBank 🆕 Summarization Research

**Website**: https://meetingbank.github.io  
**GitHub**: Linked from site  
**License**: Open dataset  
**Focus**: 6 cities, high-quality summarization benchmark

#### 🔥 What to Adopt

**A. Summarization Quality Benchmarks**

MeetingBank is used in academic research for summarization. They have:
- **Gold-standard human summaries** (for validation)
- **Multiple summary lengths** (short, medium, long)
- **Evaluation metrics** (ROUGE, BERTScore)

```python
# MeetingBank pattern: Validate AI summaries against quality benchmarks

from typing import Dict
import numpy as np

class SummaryQualityValidator:
    """
    MeetingBank pattern: Ensure AI summaries meet quality standards.
    """
    
    # Quality thresholds from academic research
    MIN_ROUGE_L = 0.25  # ROUGE-L F1 score
    MIN_LENGTH_RATIO = 0.05  # Summary should be 5-20% of original
    MAX_LENGTH_RATIO = 0.20
    
    def validate_summary(self, original: str, summary: str) -> Dict[str, any]:
        """
        Check if summary meets quality standards.
        """
        # Length checks
        orig_words = len(original.split())
        summ_words = len(summary.split())
        length_ratio = summ_words / orig_words if orig_words > 0 else 0
        
        # Basic quality checks
        checks = {
            'length_appropriate': self.MIN_LENGTH_RATIO <= length_ratio <= self.MAX_LENGTH_RATIO,
            'has_key_terms': self._check_key_terms(original, summary),
            'no_repetition': self._check_repetition(summary),
            'proper_structure': self._check_structure(summary),
        }
        
        return {
            'passes_validation': all(checks.values()),
            'checks': checks,
            'length_ratio': length_ratio,
            'word_count': summ_words,
            'quality_score': sum(checks.values()) / len(checks)
        }
    
    def _check_key_terms(self, original: str, summary: str) -> bool:
        """
        Ensure summary includes key terms from original.
        """
        # Extract important terms (simplified - use TF-IDF in production)
        orig_words = set(original.lower().split())
        summ_words = set(summary.lower().split())
        
        # At least 30% overlap of unique terms
        overlap = len(orig_words & summ_words) / len(orig_words)
        return overlap >= 0.30
    
    def _check_repetition(self, summary: str) -> bool:
        """
        Check for excessive repetition (indicates poor quality).
        """
        sentences = summary.split('.')
        unique_ratio = len(set(sentences)) / len(sentences) if sentences else 0
        return unique_ratio >= 0.80  # At least 80% unique sentences
    
    def _check_structure(self, summary: str) -> bool:
        """
        Check for proper summary structure.
        """
        # Should have multiple sentences
        sentences = [s.strip() for s in summary.split('.') if s.strip()]
        return len(sentences) >= 2 and len(sentences) <= 10
```

**Implementation Priority**: 🟡 **MEDIUM** - Important for quality, but MVP can use basic summaries

---

### 5. CivicBand 🆕 Multi-Jurisdiction Search

**Website**: https://civic.band  
**GitHub**: Linked from site (Raft Foundation)  
**Scale**: 1,000+ municipalities  
**Focus**: Google-like search across jurisdictions

#### 🔥 What to Adopt

**A. Cross-Jurisdiction Search Architecture**

CivicBand lets users search "fluoridation" and get results from **all municipalities** at once.

```python
# CivicBand pattern: Federated search across jurisdictions

from elasticsearch import Elasticsearch  # Or Meilisearch for open-source
from typing import List, Dict
from models.meeting_event import MeetingEvent

class CrossJurisdictionSearch:
    """
    CivicBand pattern: Search meetings across all jurisdictions.
    """
    
    def __init__(self):
        # Use Meilisearch (open-source) or Elasticsearch
        self.es = Elasticsearch(['http://localhost:9200'])
        self.index_name = 'meeting_events'
    
    def index_meeting(self, event: MeetingEvent):
        """
        Add meeting to search index.
        """
        doc = {
            'id': event.id,
            'title': event.title,
            'description': event.description,
            'jurisdiction': event.jurisdiction_name,
            'state': event.state_code,
            'date': event.start.isoformat(),
            'full_text': self._build_searchable_text(event),
            'agenda_url': next((link.href for link in event.links if 'agenda' in link.title.lower()), None),
            'oral_health_relevant': event.oral_health_relevant,
            'keywords': event.keywords_found
        }
        
        self.es.index(index=self.index_name, id=event.id, document=doc)
    
    def search(
        self,
        query: str,
        states: List[str] = None,
        date_range: tuple = None,
        oral_health_only: bool = False
    ) -> List[Dict]:
        """
        Search across all jurisdictions.
        
        Example:
            search("fluoridation", states=['AL', 'GA'], oral_health_only=True)
        """
        must_clauses = [
            {"multi_match": {
                "query": query,
                "fields": ["title^3", "description^2", "full_text"],  # Boost title matches
                "type": "best_fields"
            }}
        ]
        
        # Filter by state
        if states:
            must_clauses.append({"terms": {"state": states}})
        
        # Filter by date range
        if date_range:
            must_clauses.append({
                "range": {"date": {"gte": date_range[0], "lte": date_range[1]}}
            })
        
        # Filter oral health only
        if oral_health_only:
            must_clauses.append({"term": {"oral_health_relevant": True}})
        
        search_query = {
            "query": {"bool": {"must": must_clauses}},
            "size": 100,
            "highlight": {
                "fields": {
                    "title": {},
                    "description": {},
                    "full_text": {"fragment_size": 150}
                }
            },
            "sort": [
                {"_score": "desc"},
                {"date": "desc"}
            ]
        }
        
        results = self.es.search(index=self.index_name, body=search_query)
        
        return [{
            'jurisdiction': hit['_source']['jurisdiction'],
            'state': hit['_source']['state'],
            'title': hit['_source']['title'],
            'date': hit['_source']['date'],
            'snippet': hit.get('highlight', {}).get('full_text', [''])[0],
            'url': hit['_source']['agenda_url'],
            'relevance_score': hit['_score']
        } for hit in results['hits']['hits']]
    
    def _build_searchable_text(self, event: MeetingEvent) -> str:
        """
        Combine all text fields for indexing.
        """
        parts = [
            event.title or '',
            event.description or '',
            ' '.join(event.keywords_found),
            ' '.join(link.title for link in event.links)
        ]
        return ' '.join(parts)
```

**B. Jurisdiction Faceting**
```python
# CivicBand shows result counts by jurisdiction

def get_search_facets(query: str) -> Dict[str, int]:
    """
    Show how many results per jurisdiction.
    
    Example output:
        {
            'Birmingham, AL': 12,
            'Atlanta, GA': 8,
            'Montgomery, AL': 5
        }
    """
    search_query = {
        "query": {"multi_match": {"query": query, "fields": ["title", "full_text"]}},
        "size": 0,  # We only want aggregations
        "aggs": {
            "by_jurisdiction": {
                "terms": {
                    "field": "jurisdiction.keyword",
                    "size": 50  # Top 50 jurisdictions
                },
                "aggs": {
                    "by_state": {
                        "terms": {"field": "state.keyword"}
                    }
                }
            }
        }
    }
    
    results = self.es.search(index=self.index_name, body=search_query)
    
    facets = {}
    for bucket in results['aggregations']['by_jurisdiction']['buckets']:
        jurisdiction = bucket['key']
        count = bucket['doc_count']
        state = bucket['by_state']['buckets'][0]['key']
        facets[f"{jurisdiction}, {state}"] = count
    
    return facets
```

**Implementation Priority**: 🟡 **MEDIUM** - Valuable for end-users, but scraping comes first

---

### 6. OpenCouncil 🆕 International Adaptability

**Website**: https://opencouncil.gr  
**GitHub**: https://github.com/schemalabz/opencouncil  
**License**: Open-source  
**Focus**: Greek councils, but adaptable to U.S.

#### 🔥 What to Adopt

**A. Internationalization Patterns**

OpenCouncil works in Greece (different government structure). This teaches us:
- **Flexible schema** (not hardcoded to U.S. structures)
- **Configurable jurisdiction types** (councils, boards, commissions)
- **Multi-language support** (not needed now, but good architecture)

```python
# OpenCouncil pattern: Flexible jurisdiction configuration

from enum import Enum
from dataclasses import dataclass
from typing import List, Optional

class GovernmentLevel(Enum):
    """
    OpenCouncil pattern: Support multiple government structures.
    """
    MUNICIPAL = "municipal"          # City/town councils
    COUNTY = "county"                # County boards
    TOWNSHIP = "township"            # Township boards
    SCHOOL_DISTRICT = "school"       # School boards
    SPECIAL_DISTRICT = "special"     # Water, fire, etc.
    STATE = "state"                  # State agencies (future)

@dataclass
class JurisdictionConfig:
    """
    OpenCouncil pattern: Configure each jurisdiction's unique structure.
    """
    jurisdiction_name: str
    government_level: GovernmentLevel
    
    # Meeting schedule
    typical_meeting_frequency: str  # 'weekly', 'biweekly', 'monthly'
    typical_meeting_days: List[str]  # ['Monday', 'Thursday']
    typical_meeting_time: str  # '18:00'
    
    # Website structure
    calendar_url: Optional[str]
    agenda_url_pattern: Optional[str]  # Template: "https://example.gov/agenda-{date}"
    minutes_url_pattern: Optional[str]
    
    # Legislative bodies
    bodies: List[str]  # ['City Council', 'Planning Commission', 'Board of Health']
    
    # Custom fields
    metadata: dict  # For jurisdiction-specific data

# Example: Configure Birmingham, AL
BIRMINGHAM_CONFIG = JurisdictionConfig(
    jurisdiction_name="Birmingham",
    government_level=GovernmentLevel.MUNICIPAL,
    typical_meeting_frequency='biweekly',
    typical_meeting_days=['Tuesday'],
    typical_meeting_time='18:00',
    calendar_url="https://birminghamal.gov/council/meetings",
    bodies=['City Council', 'Board of Health', 'Planning Commission'],
    metadata={'population': 200733, 'oral_health_priority': 'high'}
)
```

**Implementation Priority**: 🟢 **LOW** - Good architecture, but not urgent

---

## 🎯 Implementation Roadmap

### Phase 1: AI Summarization (OpenTowns pattern) 🔥
**Priority**: HIGH  
**Timeline**: 1-2 weeks  
**Depends on**: Existing OpenAI integration

```python
# TODO: Implement in extraction/summarizer.py
- [ ] Generate executive summaries from meeting transcripts
- [ ] Extract key decisions as bullet points
- [ ] Identify health policy items
- [ ] Add quality validation (MeetingBank patterns)
```

### Phase 2: Keyword Alerts (OpenTowns pattern) 🔥
**Priority**: HIGH  
**Timeline**: 1 week  
**Depends on**: Meeting data ingestion

```python
# TODO: Implement in alerts/keyword_monitor.py
- [ ] Define oral health keyword categories
- [ ] Pattern matching with word boundaries
- [ ] Generate alerts for users
- [ ] Email/webhook notification system
```

### Phase 3: Scale Architecture (LocalView pattern) 🔥
**Priority**: HIGH  
**Timeline**: 2 weeks  
**Depends on**: Platform scrapers

```python
# TODO: Implement in discovery/batch_processor.py
- [ ] Quality metrics per jurisdiction
- [ ] Batch processing (100 at a time)
- [ ] Failure tracking and retry
- [ ] Completeness scoring
```

### Phase 4: Multi-Jurisdiction Search (CivicBand pattern) 🟡
**Priority**: MEDIUM  
**Timeline**: 2-3 weeks  
**Depends on**: Significant meeting data

```python
# TODO: Implement in search/federated_search.py
- [ ] Set up Elasticsearch or Meilisearch
- [ ] Index all meetings
- [ ] Cross-jurisdiction search API
- [ ] Jurisdiction faceting
```

### Phase 5: Quality Validation (MeetingBank pattern) 🟡
**Priority**: MEDIUM  
**Timeline**: 1 week  
**Depends on**: AI summarization

```python
# TODO: Implement in extraction/quality_validator.py
- [ ] Summary length validation
- [ ] Key term extraction
- [ ] Repetition detection
- [ ] Structure checking
```

### Phase 6: Flexible Config (OpenCouncil pattern) 🟢
**Priority**: LOW  
**Timeline**: 1 week  
**Depends on**: None

```python
# TODO: Implement in config/jurisdiction_configs.py
- [ ] Per-jurisdiction configuration
- [ ] Meeting schedule patterns
- [ ] Legislative body tracking
```

---

## 📊 Comparison with Existing Integration

| Capability | Original 5 Projects | New 6 Projects | Status |
|------------|-------------------|---------------|--------|
| Platform detection | ✅ Civic Scraper | - | **Complete** |
| Event schema | ✅ City Scrapers | - | **Complete** |
| Video ingestion | ✅ CDP | ✅ LocalView (scale) | **Need scale patterns** |
| Matter tracking | ✅ Engagic | - | **Complete** |
| Person/vote tracking | ✅ Councilmatic | - | Roadmapped |
| **AI Summarization** | ❌ | ✅ OpenTowns, MeetingBank | **TODO: High priority** |
| **Keyword Alerts** | ❌ | ✅ OpenTowns | **TODO: High priority** |
| **Cross-jurisdiction search** | ⚠️ Basic | ✅ CivicBand | **TODO: Medium priority** |
| **Quality metrics** | ❌ | ✅ LocalView, MeetingBank | **TODO: Medium priority** |
| **Batch processing** | ⚠️ Basic | ✅ LocalView | **TODO: High priority** |

---

## 💻 Quick Start: Integrate Summarization

Here's how to add OpenTowns-style summarization **right now**:

```python
# File: extraction/summarizer.py

from openai import OpenAI
from models.meeting_event import MeetingEvent
from config.settings import settings

client = OpenAI(api_key=settings.openai_api_key)

def summarize_meeting(event: MeetingEvent, full_text: str) -> dict:
    """
    Generate OpenTowns-style summary with oral health focus.
    """
    prompt = f"""
    You are summarizing a local government meeting for public health advocates.
    
    Meeting: {event.title}
    Jurisdiction: {event.jurisdiction_name}, {event.state_code}
    Date: {event.start.strftime('%B %d, %Y')}
    
    Full text (first 8000 chars):
    {full_text[:8000]}
    
    Provide:
    1. Executive Summary (2-3 sentences)
    2. Key Decisions (bullet list)
    3. Oral Health Items (if any - fluoridation, dental access, etc.)
    4. Next Actions (follow-ups, future meetings)
    
    Focus on: What was decided? What's happening next?
    """
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You summarize local government meetings for public understanding."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    
    return {
        'summary': response.choices[0].message.content,
        'model': 'gpt-4o-mini',
        'tokens_used': response.usage.total_tokens
    }

# Usage:
# summary = summarize_meeting(event, full_transcript)
# event.description = summary['summary']
```

---

## 🎬 Next Steps

1. **Implement AI summarization** (OpenTowns pattern) → Makes data usable
2. **Add keyword alerts** (OpenTowns pattern) → Engage advocates
3. **Add batch processing** (LocalView pattern) → Scale to 1,000+ jurisdictions
4. **Build search interface** (CivicBand pattern) → User discovery
5. **Add quality metrics** (LocalView + MeetingBank) → Monitor data health

---

## 📖 References

- **OpenTowns**: https://opentowns.org
- **LocalView**: https://www.localview.net
- **MeetingBank**: https://meetingbank.github.io
- **CivicBand**: https://civic.band
- **OpenCouncil**: https://github.com/schemalabz/opencouncil
- **Council Data Project**: https://councildataproject.org (see INTEGRATION_GUIDE.md)

---

## 📝 License & Attribution

All patterns documented here are derived from open-source projects:
- OpenTowns: Open civic-tech project
- LocalView: Open-source (Harvard Mellon Urbanism)
- MeetingBank: Open dataset
- CivicBand: Open-source (Raft Foundation)
- OpenCouncil: Open-source (MIT)
- CDP: MIT License

When using code patterns, maintain attribution per each project's license.
