"""
Keyword alert system for oral health policy monitoring.

Based on OpenTowns.org patterns: Monitor meetings for specific keywords
and generate alerts when matches are found.
"""
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
import re
from enum import Enum

from loguru import logger

from models.meeting_event import MeetingEvent


class AlertPriority(Enum):
    """Alert priority levels."""
    CRITICAL = "critical"  # Direct fluoridation mentions
    HIGH = "high"          # Dental access, water systems
    MEDIUM = "medium"      # General public health
    LOW = "low"            # Related but not primary focus


@dataclass
class KeywordMatch:
    """A single keyword match in a document."""
    keyword: str
    category: str
    context: str  # Surrounding text (50 chars before/after)
    position: int  # Character position in text


@dataclass
class KeywordAlert:
    """
    Alert generated when keywords are found in a meeting.
    """
    # Meeting details
    jurisdiction_name: str
    state_code: str
    meeting_title: str
    meeting_date: datetime
    meeting_url: Optional[str]
    
    # Match details
    priority: AlertPriority
    categories_matched: List[str]
    keywords_found: List[str]
    total_matches: int
    matches: List[KeywordMatch] = field(default_factory=list)
    
    # Context
    snippet: str  # Most relevant excerpt
    confidence_score: float  # 0-1: How confident are we this is relevant?
    
    # Metadata
    generated_at: datetime = field(default_factory=datetime.utcnow)
    alert_id: str = ""
    
    def __post_init__(self):
        """Generate unique alert ID."""
        if not self.alert_id:
            date_str = self.meeting_date.strftime('%Y%m%d')
            self.alert_id = f"ALERT-{self.state_code}-{date_str}-{hash(self.meeting_title) % 10000:04d}"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'alert_id': self.alert_id,
            'priority': self.priority.value,
            'jurisdiction': f"{self.jurisdiction_name}, {self.state_code}",
            'meeting_title': self.meeting_title,
            'meeting_date': self.meeting_date.isoformat(),
            'meeting_url': self.meeting_url,
            'categories': self.categories_matched,
            'keywords': self.keywords_found,
            'total_matches': self.total_matches,
            'snippet': self.snippet,
            'confidence': self.confidence_score,
            'generated_at': self.generated_at.isoformat()
        }


class KeywordAlertSystem:
    """
    Monitor meetings for oral health keywords and generate alerts.
    
    Based on OpenTowns.org patterns for keyword-based notifications.
    
    Example:
        >>> alert_system = KeywordAlertSystem()
        >>> alerts = alert_system.scan_meeting(event, full_text)
        >>> for alert in alerts:
        ...     print(f"🔔 {alert.meeting_title}: {alert.keywords_found}")
    """
    
    # Keyword categories with priority weights
    KEYWORD_CATEGORIES = {
        'fluoridation': {
            'priority': AlertPriority.CRITICAL,
            'keywords': [
                'fluoride', 'fluoridation', 'water fluoridation',
                'community water fluoridation', 'CWF',
                'fluoride treatment', 'fluoride program',
                'fluoride levels', 'fluoride concentration',
                'fluoride varnish', 'fluoride supplement'
            ]
        },
        'dental_access': {
            'priority': AlertPriority.HIGH,
            'keywords': [
                'dental', 'dentist', 'dental clinic', 'dental care',
                'oral health', 'teeth', 'tooth decay', 'cavities',
                'dental insurance', 'medicaid dental', 'dental coverage',
                'dental hygienist', 'dental health', 'dental program',
                'dental services', 'dental screening', 'dental sealants'
            ]
        },
        'water_systems': {
            'priority': AlertPriority.HIGH,
            'keywords': [
                'water treatment', 'water system', 'water quality',
                'drinking water', 'water utility', 'water infrastructure',
                'water plant', 'water facility', 'water additive'
            ]
        },
        'public_health': {
            'priority': AlertPriority.MEDIUM,
            'keywords': [
                'health department', 'public health', 'CDC',
                'preventive care', 'health equity', 'health outcomes',
                'community health', 'health services', 'health program',
                'health screening', 'health education'
            ]
        },
        'health_policy': {
            'priority': AlertPriority.MEDIUM,
            'keywords': [
                'health policy', 'health ordinance', 'health regulation',
                'health code', 'health board', 'health commission',
                'ADA', 'American Dental Association',
                'state health department', 'health initiative'
            ]
        },
        'children_health': {
            'priority': AlertPriority.HIGH,
            'keywords': [
                'children health', 'child health', 'pediatric',
                'school health', 'student health', 'WIC program',
                'head start', 'early childhood', 'youth health'
            ]
        }
    }
    
    def scan_meeting(
        self,
        event: MeetingEvent,
        full_text: str,
        min_matches: int = 2,
        include_context: bool = True
    ) -> List[KeywordAlert]:
        """
        Scan a meeting for keyword matches and generate alerts.
        
        Args:
            event: Meeting event to scan
            full_text: Full text of agenda, minutes, or transcript
            min_matches: Minimum keyword matches to generate alert
            include_context: Whether to include surrounding text
            
        Returns:
            List of alerts (may be empty if no significant matches)
        """
        logger.info(f"Scanning meeting: {event.title} ({len(full_text)} chars)")
        
        # Find all keyword matches
        all_matches: List[KeywordMatch] = []
        categories_found: Set[str] = set()
        
        for category, config in self.KEYWORD_CATEGORIES.items():
            matches = self._find_keywords_in_text(
                text=full_text,
                keywords=config['keywords'],
                category=category,
                include_context=include_context
            )
            
            if matches:
                all_matches.extend(matches)
                categories_found.add(category)
                logger.debug(f"Found {len(matches)} matches in category '{category}'")
        
        # Check if we have enough matches
        if len(all_matches) < min_matches:
            logger.info(f"Only {len(all_matches)} matches found, below threshold of {min_matches}")
            return []
        
        # Determine priority
        priority = self._calculate_priority(categories_found)
        
        # Get unique keywords
        unique_keywords = sorted(set(m.keyword for m in all_matches))
        
        # Extract most relevant snippet
        snippet = self._extract_best_snippet(full_text, all_matches)
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            text_length=len(full_text),
            match_count=len(all_matches),
            categories_count=len(categories_found)
        )
        
        # Create alert
        alert = KeywordAlert(
            jurisdiction_name=event.jurisdiction_name,
            state_code=event.state_code,
            meeting_title=event.title,
            meeting_date=event.start,
            meeting_url=event.source,
            priority=priority,
            categories_matched=sorted(categories_found),
            keywords_found=unique_keywords,
            total_matches=len(all_matches),
            matches=all_matches,
            snippet=snippet,
            confidence_score=confidence
        )
        
        logger.info(
            f"Generated {priority.value} priority alert: "
            f"{len(all_matches)} matches in {len(categories_found)} categories"
        )
        
        return [alert]
    
    def _find_keywords_in_text(
        self,
        text: str,
        keywords: List[str],
        category: str,
        include_context: bool
    ) -> List[KeywordMatch]:
        """
        Find all occurrences of keywords in text.
        """
        text_lower = text.lower()
        matches = []
        
        for keyword in keywords:
            # Word boundary matching to avoid false positives
            pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
            
            for match in re.finditer(pattern, text_lower):
                position = match.start()
                
                # Extract context (50 chars before/after)
                if include_context:
                    context_start = max(0, position - 50)
                    context_end = min(len(text), position + len(keyword) + 50)
                    context = text[context_start:context_end]
                    
                    # Clean up context
                    context = context.replace('\n', ' ').strip()
                    if context_start > 0:
                        context = "..." + context
                    if context_end < len(text):
                        context = context + "..."
                else:
                    context = ""
                
                matches.append(KeywordMatch(
                    keyword=keyword,
                    category=category,
                    context=context,
                    position=position
                ))
        
        return matches
    
    def _calculate_priority(self, categories: Set[str]) -> AlertPriority:
        """
        Determine alert priority based on matched categories.
        """
        # Check highest priority category
        if 'fluoridation' in categories:
            return AlertPriority.CRITICAL
        
        high_priority_cats = {'dental_access', 'water_systems', 'children_health'}
        if categories & high_priority_cats:
            return AlertPriority.HIGH
        
        medium_priority_cats = {'public_health', 'health_policy'}
        if categories & medium_priority_cats:
            return AlertPriority.MEDIUM
        
        return AlertPriority.LOW
    
    def _extract_best_snippet(
        self,
        text: str,
        matches: List[KeywordMatch],
        snippet_length: int = 300
    ) -> str:
        """
        Extract the most relevant snippet containing keywords.
        
        Strategy: Find the region with highest density of matches.
        """
        if not matches:
            return text[:snippet_length]
        
        # Sort matches by position
        sorted_matches = sorted(matches, key=lambda m: m.position)
        
        # Find densest region (most matches within snippet_length)
        best_start = 0
        best_count = 0
        
        for i, match in enumerate(sorted_matches):
            start_pos = match.position
            end_pos = start_pos + snippet_length
            
            # Count matches in this window
            count = sum(
                1 for m in sorted_matches
                if start_pos <= m.position <= end_pos
            )
            
            if count > best_count:
                best_count = count
                best_start = start_pos
        
        # Extract snippet
        snippet_start = max(0, best_start - 50)  # Add a bit of lead-in
        snippet_end = min(len(text), best_start + snippet_length + 50)
        snippet = text[snippet_start:snippet_end]
        
        # Clean up
        snippet = snippet.replace('\n', ' ').strip()
        if snippet_start > 0:
            snippet = "..." + snippet
        if snippet_end < len(text):
            snippet = snippet + "..."
        
        return snippet
    
    def _calculate_confidence(
        self,
        text_length: int,
        match_count: int,
        categories_count: int
    ) -> float:
        """
        Calculate confidence score for the alert.
        
        Factors:
        - Match density (matches per 1000 chars)
        - Category diversity (more categories = higher confidence)
        - Text length (longer text = more confident)
        """
        # Match density
        density = (match_count / text_length) * 1000 if text_length > 0 else 0
        if density > 5.0:
            density_score = 1.0
        elif density > 2.0:
            density_score = 0.8
        elif density > 1.0:
            density_score = 0.6
        else:
            density_score = 0.4
        
        # Category diversity
        if categories_count >= 3:
            category_score = 1.0
        elif categories_count == 2:
            category_score = 0.8
        else:
            category_score = 0.6
        
        # Text length
        if text_length > 5000:
            length_score = 1.0
        elif text_length > 1000:
            length_score = 0.8
        else:
            length_score = 0.6
        
        # Weighted average
        confidence = (
            density_score * 0.4 +
            category_score * 0.4 +
            length_score * 0.2
        )
        
        return round(confidence, 2)
    
    def batch_scan_meetings(
        self,
        meetings: List[tuple[MeetingEvent, str]]
    ) -> List[KeywordAlert]:
        """
        Scan multiple meetings and return all alerts.
        
        Args:
            meetings: List of (event, full_text) tuples
            
        Returns:
            All alerts sorted by priority and date
        """
        all_alerts = []
        
        for event, text in meetings:
            try:
                alerts = self.scan_meeting(event, text)
                all_alerts.extend(alerts)
            except Exception as e:
                logger.error(f"Error scanning {event.title}: {e}")
        
        # Sort by priority (critical first) then by date (newest first)
        priority_order = {
            AlertPriority.CRITICAL: 0,
            AlertPriority.HIGH: 1,
            AlertPriority.MEDIUM: 2,
            AlertPriority.LOW: 3
        }
        
        all_alerts.sort(
            key=lambda a: (priority_order[a.priority], -a.meeting_date.timestamp())
        )
        
        return all_alerts


def generate_alert_email(alert: KeywordAlert) -> str:
    """
    Generate email content for an alert.
    
    Returns: HTML email body
    """
    priority_colors = {
        AlertPriority.CRITICAL: "#dc2626",  # Red
        AlertPriority.HIGH: "#ea580c",      # Orange
        AlertPriority.MEDIUM: "#ca8a04",    # Yellow
        AlertPriority.LOW: "#65a30d"        # Green
    }
    
    color = priority_colors[alert.priority]
    
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background-color: {color}; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0;">🔔 {alert.priority.value.upper()} Priority Alert</h2>
        </div>
        
        <div style="padding: 20px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 8px 8px;">
            <h3>{alert.meeting_title}</h3>
            <p><strong>📍 Jurisdiction:</strong> {alert.jurisdiction_name}, {alert.state_code}</p>
            <p><strong>📅 Meeting Date:</strong> {alert.meeting_date.strftime('%B %d, %Y at %I:%M %p')}</p>
            
            <div style="background-color: #f3f4f6; padding: 15px; border-radius: 6px; margin: 20px 0;">
                <h4 style="margin-top: 0;">Keywords Found ({alert.total_matches} matches):</h4>
                <p><strong>Categories:</strong> {', '.join(alert.categories_matched)}</p>
                <p><strong>Keywords:</strong> {', '.join(alert.keywords_found[:10])}{"..." if len(alert.keywords_found) > 10 else ""}</p>
            </div>
            
            <div style="margin: 20px 0;">
                <h4>Relevant Excerpt:</h4>
                <p style="font-style: italic; color: #4b5563;">{alert.snippet}</p>
            </div>
            
            {f'<p><a href="{alert.meeting_url}" style="background-color: {color}; color: white; padding: 10px 20px; text-decoration: none; border-radius: 6px; display: inline-block;">View Full Meeting →</a></p>' if alert.meeting_url else ''}
            
            <hr style="margin: 30px 0; border: none; border-top: 1px solid #e5e7eb;">
            
            <p style="font-size: 12px; color: #6b7280;">
                Alert ID: {alert.alert_id}<br>
                Confidence: {alert.confidence_score:.0%}<br>
                Generated: {alert.generated_at.strftime('%Y-%m-%d %H:%M UTC')}
            </p>
        </div>
    </body>
    </html>
    """
    
    return html


if __name__ == "__main__":
    # Demo
    from models.meeting_event import Classification
    
    # Example meeting with oral health content
    demo_event = MeetingEvent(
        title="City Council Public Health Committee Meeting",
        classification=Classification.COMMITTEE,
        start=datetime(2026, 4, 15, 14, 0),
        jurisdiction_name="Birmingham",
        state_code="AL",
        source="https://birminghamal.gov/meetings/2026-04-15"
    )
    
    # Example meeting text
    demo_text = """
    PUBLIC HEALTH COMMITTEE MEETING
    April 15, 2026 - 2:00 PM
    
    AGENDA
    
    1. Call to Order
    
    2. Discussion: Community Water Fluoridation Program Implementation
       
       Dr. Sarah Johnson from the Alabama Department of Public Health will
       present on the benefits of water fluoridation for oral health. The
       CDC recommends community water fluoridation as one of the ten great
       public health achievements. 
       
       Studies show that fluoridation reduces tooth decay by 25% in children
       and adults. The proposed program would adjust fluoride levels in the
       Birmingham water system to 0.7 mg/L, consistent with CDC guidelines.
       
       Cost-benefit analysis indicates the program would cost $120,000 annually
       but could prevent an estimated $1.2 million in dental treatment costs.
       
    3. Update: Medicaid Dental Coverage Expansion
       
       The state has approved expanded Medicaid dental coverage for adults.
       The Health Department will coordinate with local dental clinics to
       ensure capacity for new patients. Dr. Martinez will discuss the
       dental screening program for Head Start children.
       
    4. Public Comment Period
    
    5. Next Meeting: May 6, 2026
    """
    
    # Scan for keywords
    alert_system = KeywordAlertSystem()
    alerts = alert_system.scan_meeting(demo_event, demo_text)
    
    if alerts:
        alert = alerts[0]
        print("🔔 KEYWORD ALERT GENERATED")
        print("=" * 70)
        print(f"Alert ID: {alert.alert_id}")
        print(f"Priority: {alert.priority.value.upper()}")
        print(f"Meeting: {alert.meeting_title}")
        print(f"Jurisdiction: {alert.jurisdiction_name}, {alert.state_code}")
        print(f"Date: {alert.meeting_date.strftime('%B %d, %Y')}")
        print(f"\nCategories matched ({len(alert.categories_matched)}):")
        for cat in alert.categories_matched:
            print(f"  • {cat}")
        print(f"\nKeywords found ({len(alert.keywords_found)}):")
        for kw in alert.keywords_found[:10]:
            print(f"  • {kw}")
        if len(alert.keywords_found) > 10:
            print(f"  ... and {len(alert.keywords_found) - 10} more")
        print(f"\nTotal matches: {alert.total_matches}")
        print(f"Confidence: {alert.confidence_score:.0%}")
        print(f"\nRelevant snippet:")
        print(f"  {alert.snippet[:200]}...")
    else:
        print("No alerts generated (insufficient keyword matches)")
