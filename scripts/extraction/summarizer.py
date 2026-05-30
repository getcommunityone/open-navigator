"""
AI-powered meeting summarization using OpenTowns patterns.

This module generates human-readable summaries from meeting transcripts,
agendas, and minutes. Based on OpenTowns.org's approach to making local
government accessible.
"""
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import re

from openai import OpenAI
from loguru import logger

from models.meeting_event import MeetingEvent
from config.settings import settings


@dataclass
class MeetingSummary:
    """
    Structured summary of a government meeting.
    """
    executive_summary: str  # 2-3 sentence overview
    key_decisions: List[str]  # Major decisions made
    health_policy_items: List[str]  # Health-related items
    next_actions: List[str]  # Follow-up items
    
    # Quality metrics
    confidence_score: float  # 0-1: How confident are we in this summary?
    source_length: int  # Character count of source material
    summary_length: int  # Character count of summary
    
    # Metadata
    generated_at: datetime
    model_used: str
    tokens_used: int


class MeetingSummarizer:
    """
    Generate summaries from meeting transcripts using OpenTowns patterns.
    
    Example:
        >>> summarizer = MeetingSummarizer()
        >>> summary = summarizer.summarize(event, full_transcript)
        >>> print(summary.executive_summary)
    """
    
    # Oral health keywords for focused extraction
    ORAL_HEALTH_KEYWORDS = {
        'fluoridation': [
            'fluoride', 'fluoridation', 'water fluoridation',
            'community water fluoridation', 'CWF', 'fluoride treatment'
        ],
        'dental_access': [
            'dental', 'dentist', 'dental clinic', 'dental care',
            'oral health', 'teeth', 'tooth decay', 'dental insurance',
            'medicaid dental', 'dental coverage'
        ],
        'public_health': [
            'health department', 'public health', 'CDC', 'ADA',
            'preventive care', 'health equity', 'health outcomes',
            'community health'
        ],
        'water_systems': [
            'water treatment', 'water system', 'water quality',
            'drinking water', 'water utility', 'water infrastructure'
        ]
    }
    
    def __init__(self):
        """Initialize summarizer with OpenAI client."""
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key required for summarization. Set OPENAI_API_KEY environment variable.")
        
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4o-mini"  # Cost-effective for summaries
        
    def summarize(
        self,
        event: MeetingEvent,
        full_text: str,
        focus_on_health: bool = True
    ) -> MeetingSummary:
        """
        Generate comprehensive summary of a meeting.
        
        Args:
            event: Meeting event object
            full_text: Full transcript, agenda, or minutes text
            focus_on_health: Whether to emphasize health policy items
            
        Returns:
            Structured MeetingSummary object
        """
        logger.info(f"Summarizing meeting: {event.title} ({len(full_text)} chars)")
        
        # Truncate to avoid token limits (GPT-4o-mini: 128k context)
        # Keep first 50k chars (roughly 12k tokens)
        text_to_summarize = full_text[:50000]
        if len(full_text) > 50000:
            logger.warning(f"Text truncated from {len(full_text)} to 50000 chars")
        
        # Build prompt
        prompt = self._build_prompt(event, text_to_summarize, focus_on_health)
        
        # Call OpenAI
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt(focus_on_health)
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Lower temperature for factual accuracy
                max_tokens=1500   # Enough for comprehensive summary
            )
            
            summary_text = response.choices[0].message.content
            tokens_used = response.usage.total_tokens
            
            logger.info(f"Summary generated: {tokens_used} tokens used")
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise
        
        # Parse structured response
        parsed = self._parse_summary(summary_text)
        
        # Calculate confidence score
        confidence = self._calculate_confidence(
            full_text=full_text,
            summary_text=summary_text,
            health_items_found=len(parsed['health_policy_items']) > 0
        )
        
        return MeetingSummary(
            executive_summary=parsed['executive_summary'],
            key_decisions=parsed['key_decisions'],
            health_policy_items=parsed['health_policy_items'],
            next_actions=parsed['next_actions'],
            confidence_score=confidence,
            source_length=len(full_text),
            summary_length=len(summary_text),
            generated_at=datetime.utcnow(),
            model_used=self.model,
            tokens_used=tokens_used
        )
    
    def _get_system_prompt(self, focus_on_health: bool) -> str:
        """Get system prompt for summarization."""
        base_prompt = (
            "You are a civic engagement assistant that summarizes local government "
            "meetings for public understanding. Your summaries help residents stay "
            "informed about decisions that affect their community."
        )
        
        if focus_on_health:
            base_prompt += (
                "\n\nPay special attention to public health policy items, especially "
                "those related to oral health, water fluoridation, dental access, "
                "and health equity."
            )
        
        return base_prompt
    
    def _build_prompt(
        self,
        event: MeetingEvent,
        text: str,
        focus_on_health: bool
    ) -> str:
        """Build the user prompt for summarization."""
        prompt = f"""
Summarize this local government meeting:

**Meeting Details:**
- Title: {event.title}
- Jurisdiction: {event.jurisdiction_name}, {event.state_code}
- Date: {event.start.strftime('%B %d, %Y')}
- Classification: {event.classification.value if event.classification else 'meeting'}

**Full Text:**
{text}

**Please provide:**

1. **Executive Summary** (2-3 sentences)
   - What was this meeting about?
   - What was decided?

2. **Key Decisions** (bullet list)
   - Major votes or resolutions passed
   - Important policy changes
   - Budget allocations
   - Appointments or personnel changes

3. **{"Public Health & Oral Health Items" if focus_on_health else "Notable Discussion Items"}** (if any)
   {"- Water fluoridation discussions" if focus_on_health else ""}
   {"- Dental access or oral health programs" if focus_on_health else ""}
   {"- Health equity initiatives" if focus_on_health else ""}
   - Any other health-related topics

4. **Next Actions** (bullet list)
   - Scheduled future meetings
   - Follow-up items
   - Public hearing dates
   - Deadlines or action items

**Format your response exactly as:**

# Executive Summary
[2-3 sentences here]

# Key Decisions
- [Decision 1]
- [Decision 2]
...

# {"Public Health Items" if focus_on_health else "Discussion Items"}
- [Item 1]
- [Item 2]
...

# Next Actions
- [Action 1]
- [Action 2]
...

If a section has nothing to report, write "None identified."
"""
        return prompt.strip()
    
    def _parse_summary(self, summary_text: str) -> Dict[str, any]:
        """
        Parse structured sections from GPT response.
        """
        # Extract sections using markdown headers
        sections = {
            'executive_summary': '',
            'key_decisions': [],
            'health_policy_items': [],
            'next_actions': []
        }
        
        # Split by markdown headers
        lines = summary_text.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            
            # Detect section headers
            if line.startswith('# Executive Summary'):
                current_section = 'executive_summary'
                continue
            elif line.startswith('# Key Decisions'):
                current_section = 'key_decisions'
                continue
            elif 'Health' in line and line.startswith('#'):
                current_section = 'health_policy_items'
                continue
            elif line.startswith('# Next Actions'):
                current_section = 'next_actions'
                continue
            
            # Process content
            if current_section == 'executive_summary':
                if line and not line.startswith('#'):
                    sections['executive_summary'] += line + ' '
            
            elif current_section in ['key_decisions', 'health_policy_items', 'next_actions']:
                if line.startswith('-') or line.startswith('*'):
                    # Extract bullet point
                    item = line.lstrip('- ').lstrip('* ').strip()
                    if item and item.lower() != 'none identified.':
                        sections[current_section].append(item)
        
        # Clean up executive summary
        sections['executive_summary'] = sections['executive_summary'].strip()
        
        # Fallback if parsing failed
        if not sections['executive_summary']:
            sections['executive_summary'] = summary_text[:200] + "..."
        
        return sections
    
    def _calculate_confidence(
        self,
        full_text: str,
        summary_text: str,
        health_items_found: bool
    ) -> float:
        """
        Calculate confidence score for summary quality.
        
        Factors:
        - Text length (longer = more confidence)
        - Summary length (appropriate ratio)
        - Health items found (if that's our focus)
        """
        # Length confidence
        text_length = len(full_text)
        summary_length = len(summary_text)
        
        if text_length < 500:
            length_score = 0.3  # Very short source
        elif text_length < 2000:
            length_score = 0.6  # Short source
        else:
            length_score = 1.0  # Adequate source
        
        # Summary ratio (should be 5-20% of original)
        ratio = summary_length / text_length if text_length > 0 else 0
        if 0.05 <= ratio <= 0.20:
            ratio_score = 1.0
        elif 0.02 <= ratio <= 0.30:
            ratio_score = 0.7
        else:
            ratio_score = 0.4
        
        # Health items bonus
        health_score = 1.0 if health_items_found else 0.8
        
        # Weighted average
        confidence = (
            length_score * 0.4 +
            ratio_score * 0.4 +
            health_score * 0.2
        )
        
        return round(confidence, 2)
    
    def extract_health_keywords(self, text: str) -> Dict[str, List[str]]:
        """
        Extract oral health keywords from text.
        
        Returns:
            {'fluoridation': ['fluoride', 'CWF'], 'dental_access': [...]}
        """
        text_lower = text.lower()
        found_keywords = {}
        
        for category, keywords in self.ORAL_HEALTH_KEYWORDS.items():
            matches = []
            for keyword in keywords:
                # Word boundary matching
                pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
                if re.search(pattern, text_lower):
                    matches.append(keyword)
            
            if matches:
                found_keywords[category] = matches
        
        return found_keywords


def summarize_meeting_simple(event: MeetingEvent, text: str) -> str:
    """
    Convenience function: Generate summary and return as simple string.
    
    Example:
        >>> summary_text = summarize_meeting_simple(event, transcript)
    """
    summarizer = MeetingSummarizer()
    summary = summarizer.summarize(event, text)
    
    return f"""
{summary.executive_summary}

Key Decisions:
{chr(10).join(f"• {d}" for d in summary.key_decisions) or "• None identified"}

Public Health Items:
{chr(10).join(f"• {h}" for h in summary.health_policy_items) or "• None identified"}

Next Actions:
{chr(10).join(f"• {a}" for a in summary.next_actions) or "• None identified"}
    """.strip()


if __name__ == "__main__":
    # Demo
    from models.meeting_event import Classification
    
    # Example meeting
    demo_event = MeetingEvent(
        title="City Council Regular Meeting",
        classification=Classification.COUNCIL,
        start=datetime(2026, 3, 15, 18, 0),
        jurisdiction_name="Birmingham",
        state_code="AL",
        source="https://example.gov"
    )
    
    # Example transcript excerpt
    demo_transcript = """
    The Birmingham City Council met on March 15, 2026 at 6:00 PM.
    
    Mayor stated that the council will consider Resolution 2026-045 regarding
    community water fluoridation. This follows the recommendation from the 
    Alabama Department of Public Health and the CDC guidelines.
    
    Councilor Smith presented the financial analysis showing the program would
    cost $120,000 annually but could prevent an estimated $1.2 million in 
    dental treatment costs over 10 years.
    
    Councilor Johnson raised concerns about public input and suggested a 
    public hearing on April 10th.
    
    The council voted 7-2 to schedule the public hearing and continue review
    in the Health Committee.
    
    Next regular meeting: March 29, 2026 at 6:00 PM.
    """
    
    try:
        summarizer = MeetingSummarizer()
        summary = summarizer.summarize(demo_event, demo_transcript)
        
        print("🦷 MEETING SUMMARY")
        print("=" * 70)
        print(f"\n📋 {demo_event.title}")
        print(f"📍 {demo_event.jurisdiction_name}, {demo_event.state_code}")
        print(f"📅 {demo_event.start.strftime('%B %d, %Y')}")
        print(f"\n{summary.executive_summary}")
        print(f"\n✅ Key Decisions:")
        for decision in summary.key_decisions:
            print(f"   • {decision}")
        print(f"\n🏥 Health Policy Items:")
        for item in summary.health_policy_items:
            print(f"   • {item}")
        print(f"\n⏭️  Next Actions:")
        for action in summary.next_actions:
            print(f"   • {action}")
        print(f"\n📊 Confidence: {summary.confidence_score:.0%}")
        print(f"💰 Tokens used: {summary.tokens_used}")
        
    except ValueError as e:
        print(f"⚠️  {e}")
        print("\nTo use the summarizer, set OPENAI_API_KEY environment variable:")
        print("  export OPENAI_API_KEY='sk-...'")
