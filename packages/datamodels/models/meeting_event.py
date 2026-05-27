"""
Standardized models for government meeting data.

Based on City Scrapers schema (MIT License):
https://github.com/city-scrapers/city-scrapers

These models provide a consistent format regardless of the source platform
(Legistar, Granicus, generic websites, etc.).
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import hashlib
import json


class Classification(str, Enum):
    """Meeting classification types (from City Scrapers)"""
    BOARD = "Board"
    COMMISSION = "Commission"
    COMMITTEE = "Committee"
    COUNCIL = "Council"
    TOWN_HALL = "Town Hall"
    PUBLIC_HEARING = "Public Hearing"
    NOT_CLASSIFIED = "Not classified"


class EventStatus(str, Enum):
    """Meeting status"""
    TENTATIVE = "tentative"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    PASSED = "passed"  # Meeting has already occurred


@dataclass
class Location:
    """Meeting location information"""
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    
    def __str__(self):
        parts = [self.name]
        if self.address:
            parts.append(self.address)
        if self.city and self.state:
            parts.append(f"{self.city}, {self.state}")
        elif self.city:
            parts.append(self.city)
        return ", ".join(parts)


@dataclass
class Link:
    """Document or resource link"""
    title: str  # "Agenda", "Minutes", "Video Recording", "Packet"
    href: str
    content_type: Optional[str] = None  # "application/pdf", "text/html", "video/mp4"
    
    def __post_init__(self):
        """Infer content type from URL if not provided"""
        if not self.content_type:
            if self.href.endswith('.pdf'):
                self.content_type = 'application/pdf'
            elif self.href.endswith('.html') or self.href.endswith('.htm'):
                self.content_type = 'text/html'
            elif self.href.endswith('.doc') or self.href.endswith('.docx'):
                self.content_type = 'application/msword'
            elif 'video' in self.href or 'youtube' in self.href:
                self.content_type = 'video/mp4'


@dataclass
class MeetingEvent:
    """
    Standardized government meeting event.
    
    Compatible with City Scrapers Event schema.
    Extended with oral health policy tracking fields.
    """
    # === Core Identification ===
    title: str
    description: str
    classification: Classification
    
    # === Temporal ===
    start: datetime
    end: Optional[datetime] = None
    all_day: bool = False
    status: EventStatus = EventStatus.CONFIRMED
    
    # === Spatial ===
    location: Location = field(default_factory=lambda: Location(name="TBD"))
    
    # === Content ===
    links: List[Link] = field(default_factory=list)
    source: str = ""  # Original URL where event was found
    
    # === Jurisdiction ===
    jurisdiction_name: str = ""
    state_code: str = ""
    fips_code: Optional[str] = None
    
    # === Metadata ===
    scraped_at: datetime = field(default_factory=datetime.utcnow)
    
    # === Oral Health Policy Tracking (YOUR VALUE-ADD!) ===
    oral_health_relevant: bool = False
    keywords_found: List[str] = field(default_factory=list)
    confidence_score: float = 0.0
    
    # Generated fields
    id: str = field(init=False)
    
    def __post_init__(self):
        """Generate unique ID after initialization"""
        self.id = self._generate_id()
    
    def _generate_id(self) -> str:
        """Generate unique ID from source + start time"""
        unique_string = f"{self.source}_{self.start.isoformat()}_{self.title}"
        return hashlib.sha256(unique_string.encode()).hexdigest()[:16]
    
    def add_link(self, title: str, href: str, content_type: Optional[str] = None):
        """Convenience method to add a document link"""
        self.links.append(Link(title=title, href=href, content_type=content_type))
    
    def has_agenda(self) -> bool:
        """Check if event has an agenda document"""
        return any('agenda' in link.title.lower() for link in self.links)
    
    def has_minutes(self) -> bool:
        """Check if event has meeting minutes"""
        return any('minute' in link.title.lower() for link in self.links)
    
    def has_video(self) -> bool:
        """Check if event has video recording"""
        return any(
            'video' in link.title.lower() or 
            link.content_type == 'video/mp4' 
            for link in self.links
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for Delta Lake storage.
        
        Handles datetime serialization and nested objects.
        """
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'classification': self.classification.value,
            'status': self.status.value,
            
            # Temporal (ISO 8601 format)
            'start': self.start.isoformat(),
            'end': self.end.isoformat() if self.end else None,
            'all_day': self.all_day,
            
            # Spatial (flattened)
            'location_name': self.location.name,
            'location_address': self.location.address,
            'location_city': self.location.city,
            'location_state': self.location.state,
            
            # Links (as JSON array)
            'links': [
                {
                    'title': link.title,
                    'href': link.href,
                    'content_type': link.content_type
                }
                for link in self.links
            ],
            
            # Source tracking
            'source': self.source,
            'jurisdiction_name': self.jurisdiction_name,
            'state_code': self.state_code,
            'fips_code': self.fips_code,
            'scraped_at': self.scraped_at.isoformat(),
            
            # Oral health relevance
            'oral_health_relevant': self.oral_health_relevant,
            'keywords_found': self.keywords_found,
            'confidence_score': self.confidence_score,
            
            # Convenience flags
            'has_agenda': self.has_agenda(),
            'has_minutes': self.has_minutes(),
            'has_video': self.has_video()
        }
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MeetingEvent':
        """
        Create MeetingEvent from dictionary.
        
        Useful for loading from Delta Lake or JSON.
        """
        # Parse datetimes
        start = datetime.fromisoformat(data['start']) if isinstance(data['start'], str) else data['start']
        end = datetime.fromisoformat(data['end']) if data.get('end') and isinstance(data['end'], str) else data.get('end')
        scraped_at = datetime.fromisoformat(data.get('scraped_at', datetime.utcnow().isoformat()))
        
        # Reconstruct location
        location = Location(
            name=data.get('location_name', 'TBD'),
            address=data.get('location_address'),
            city=data.get('location_city'),
            state=data.get('location_state')
        )
        
        # Reconstruct links
        links = [
            Link(
                title=link['title'],
                href=link['href'],
                content_type=link.get('content_type')
            )
            for link in data.get('links', [])
        ]
        
        return cls(
            title=data['title'],
            description=data['description'],
            classification=Classification(data['classification']),
            status=EventStatus(data.get('status', 'confirmed')),
            start=start,
            end=end,
            all_day=data.get('all_day', False),
            location=location,
            links=links,
            source=data['source'],
            jurisdiction_name=data.get('jurisdiction_name', ''),
            state_code=data.get('state_code', ''),
            fips_code=data.get('fips_code'),
            scraped_at=scraped_at,
            oral_health_relevant=data.get('oral_health_relevant', False),
            keywords_found=data.get('keywords_found', []),
            confidence_score=data.get('confidence_score', 0.0)
        )


@dataclass
class Matter:
    """
    Legislative matter/item tracking across meetings.
    
    Based on Engagic's "Matter" model for tracking policy evolution.
    Perfect for tracking fluoridation ordinances, health board decisions, etc.
    """
    matter_id: str
    matter_number: Optional[str] = None  # "Bill 2024-001", "Resolution 45"
    title: str = ""
    type: str = "Unknown"  # "Ordinance", "Resolution", "Motion", "Discussion"
    
    # Lifecycle
    first_introduced: Optional[datetime] = None
    status: str = "Introduced"  # "Introduced", "Committee", "Hearing", "Passed", "Failed"
    
    # Related content
    related_meetings: List[str] = field(default_factory=list)  # Meeting IDs
    related_documents: List[Link] = field(default_factory=list)
    
    # Votes (if applicable)
    votes_for: int = 0
    votes_against: int = 0
    votes_abstain: int = 0
    
    # Oral health specific
    is_health_policy: bool = False
    policy_keywords: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'matter_id': self.matter_id,
            'matter_number': self.matter_number,
            'title': self.title,
            'type': self.type,
            'first_introduced': self.first_introduced.isoformat() if self.first_introduced else None,
            'status': self.status,
            'related_meetings': self.related_meetings,
            'related_documents': [
                {'title': doc.title, 'href': doc.href}
                for doc in self.related_documents
            ],
            'votes_for': self.votes_for,
            'votes_against': self.votes_against,
            'votes_abstain': self.votes_abstain,
            'is_health_policy': self.is_health_policy,
            'policy_keywords': self.policy_keywords
        }


# Example usage
if __name__ == "__main__":
    # Create a sample meeting event
    event = MeetingEvent(
        title="City Council Regular Meeting",
        description="Regular meeting of the Birmingham City Council",
        classification=Classification.COUNCIL,
        start=datetime(2026, 4, 21, 18, 0),
        end=datetime(2026, 4, 21, 20, 0),
        location=Location(
            name="City Hall Council Chambers",
            address="710 N 20th Street",
            city="Birmingham",
            state="AL"
        ),
        source="https://birminghamal.gov/meetings",
        jurisdiction_name="Birmingham",
        state_code="AL"
    )
    
    # Add documents
    event.add_link("Agenda", "https://birminghamal.gov/agenda.pdf", "application/pdf")
    event.add_link("Previous Minutes", "https://birminghamal.gov/minutes.pdf")
    
    # Mark as oral health relevant
    event.oral_health_relevant = True
    event.keywords_found = ["fluoridation", "water", "public health"]
    event.confidence_score = 0.85
    
    # Print as JSON
    print(event.to_json())
    
    # Show what's available
    print(f"\nHas agenda: {event.has_agenda()}")
    print(f"Has minutes: {event.has_minutes()}")
    print(f"Has video: {event.has_video()}")
