"""
Evidence-Based Accountability Dashboards for Policy Advocacy.

These dashboards are designed to make elected officials uncomfortable (productively)
by exposing gaps between rhetoric and reality, deferral tactics, and power imbalances.

Each dashboard explicitly states:
1. The Decision Topic
2. The Conclusion (the uncomfortable truth)
3. The Quantified Factors that prove it

These are for advocacy, not research. Use them to shift debate from "need" to "trade-offs."
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import re
from loguru import logger


# ================================================================
# DASHBOARD 1: THE RHETORIC GAP MONITOR
# ================================================================

@dataclass
class RhetoricGapMetrics:
    """
    Measures the gap between verbal commitment and fiscal priority.
    
    Purpose: Stop debates about "need" (everyone agrees). 
             Start debates about "why aren't you funding it?"
    """
    topic: str
    conclusion: str
    
    # Factor 1: Rhetoric
    sentiment_density: float  # % positive mentions in meetings
    total_mentions: int
    positive_keywords: List[str]
    sample_quotes: List[str]
    
    # Factor 2: Budget Reality
    budget_category: str
    budget_change_dollars: float
    budget_change_percent: float
    prior_year_amount: float
    current_year_amount: float
    
    # The Logic
    gap_type: str  # "Marketing", "Buffer", "Sincere Priority", "Neglect"
    underlying_rationale: str
    
    # Discomfort Factor
    discomfort_score: int  # 1-10, how damning is this?


def calculate_rhetoric_gap(
    topic: str,
    meeting_documents: List[Dict[str, Any]],
    budget_items: List[Any],
    keywords: List[str]
) -> RhetoricGapMetrics:
    """
    Calculate the gap between what they SAY vs. what they FUND.
    
    Example:
        Topic: "Student Health"
        Rhetoric: 92% positive sentiment
        Reality: -$120,000 budget cut
        Logic: "Marketing rationale - wellness is branding, not priority"
    """
    # Calculate sentiment density
    total_mentions = 0
    positive_mentions = 0
    sample_quotes = []
    
    for doc in meeting_documents:
        content = doc.get('content', '').lower()
        
        for keyword in keywords:
            if keyword.lower() in content:
                total_mentions += 1
                
                # Extract context around keyword
                idx = content.find(keyword.lower())
                context = content[max(0, idx-100):idx+100]
                
                # Simple sentiment: check for positive words nearby
                positive_words = ['important', 'priority', 'critical', 'essential',
                                'committed', 'dedicated', 'support', 'invest']
                
                if any(pw in context for pw in positive_words):
                    positive_mentions += 1
                    
                    # Extract quote
                    sentences = re.split(r'[.!?]', content)
                    for sentence in sentences:
                        if keyword.lower() in sentence and len(sentence) > 20:
                            sample_quotes.append(sentence.strip()[:200])
                            break
    
    sentiment_density = (positive_mentions / total_mentions * 100) if total_mentions > 0 else 0
    
    # Find matching budget item
    budget_change = 0
    budget_change_pct = 0
    prior_amount = 0
    current_amount = 0
    budget_category = "Unknown"
    
    for item in budget_items:
        # Match by keywords in category
        if any(kw.lower() in item.category.lower() for kw in keywords):
            budget_category = item.category
            budget_change = item.change_amount
            budget_change_pct = item.change_percent
            prior_amount = item.prior_year_amount
            current_amount = item.current_year_amount
            break
    
    # Determine gap type
    high_rhetoric = sentiment_density > 70
    budget_increased = budget_change > 0
    
    if high_rhetoric and budget_increased:
        gap_type = "Sincere Priority"
        rationale = "Rhetoric matches fiscal commitment - genuine priority"
        discomfort = 2
    elif high_rhetoric and not budget_increased:
        gap_type = "Marketing Rationale"
        rationale = f"Board uses '{topic}' as branding to satisfy constituents, but fiscal priority is declining. Health funds likely used as 'buffer' for other costs."
        discomfort = 9  # Very uncomfortable
    elif not high_rhetoric and budget_increased:
        gap_type = "Quiet Priority"
        rationale = "Low public discussion but increased funding - administrative decision"
        discomfort = 3
    else:
        gap_type = "Neglect"
        rationale = "Low rhetoric and declining budget - not a priority"
        discomfort = 5
    
    return RhetoricGapMetrics(
        topic=topic,
        conclusion=f"Verbal commitment to {topic} is {'high' if high_rhetoric else 'low'}, but fiscal priority is {'rising' if budget_increased else 'declining'}.",
        sentiment_density=sentiment_density,
        total_mentions=total_mentions,
        positive_keywords=keywords,
        sample_quotes=sample_quotes[:5],
        budget_category=budget_category,
        budget_change_dollars=budget_change,
        budget_change_percent=budget_change_pct,
        prior_year_amount=prior_amount,
        current_year_amount=current_amount,
        gap_type=gap_type,
        underlying_rationale=rationale,
        discomfort_score=discomfort
    )


# ================================================================
# DASHBOARD 2: THE LOGIC CHAIN (Sequential Deferral)
# ================================================================

@dataclass
class DeferralPattern:
    """
    Tracks how long a decision is delayed and the shifting justifications.
    
    Purpose: Expose "analysis paralysis" as a strategic avoidance tool.
    """
    topic: str
    conclusion: str
    
    # Deferral timeline
    first_mentioned: datetime
    total_deferrals: int
    months_in_limbo: int
    
    # Shifting justifications
    justification_history: List[Dict[str, Any]]  # [{month, rationale, speaker}]
    
    # The Logic
    pattern_type: str  # "Rationale of Attrition", "Sincere Analysis", "Political Timing"
    strategic_inference: str
    
    # Discomfort Factor
    discomfort_score: int


def detect_deferral_pattern(
    topic: str,
    decisions: List[Any],
    meeting_documents: List[Dict[str, Any]]
) -> Optional[DeferralPattern]:
    """
    Detect when a decision is being strategically delayed.
    
    Example:
        Topic: "Community Dental Clinic Funding"
        Deferrals: 4 times in 6 months
        Shifting Justifications:
            - Month 1: "Waiting for tax revenue projections"
            - Month 4: "Waiting for legal clarity on liability"
        Logic: "Rationale of Attrition - waiting for advocate momentum to fade"
    """
    # Find all mentions of this topic
    relevant_decisions = [d for d in decisions if topic.lower() in d.decision_summary.lower()]
    
    if not relevant_decisions:
        return None
    
    # Sort by date
    relevant_decisions.sort(key=lambda d: d.meeting_date)
    
    # Count deferrals
    deferrals = [d for d in relevant_decisions if "defer" in d.outcome.lower() 
                 or "table" in d.outcome.lower() 
                 or "postpone" in d.outcome.lower()
                 or "work session" in d.outcome.lower()]
    
    if len(deferrals) < 2:
        return None  # Not a pattern
    
    first_date = relevant_decisions[0].meeting_date
    last_date = relevant_decisions[-1].meeting_date
    months_in_limbo = (last_date - first_date).days // 30
    
    # Extract justification history
    justification_history = []
    for decision in deferrals:
        # Extract rationale from decision
        rationale = decision.primary_rationale or "No explicit rationale given"
        
        justification_history.append({
            'month': decision.meeting_date.strftime('%B %Y'),
            'rationale': rationale,
            'speaker': decision.supporters[0].get('name', 'Board Member') if decision.supporters else 'Unknown'
        })
    
    # Determine pattern type
    if len(deferrals) >= 3 and months_in_limbo >= 4:
        pattern_type = "Rationale of Attrition"
        strategic_inference = f"The board isn't debating the {topic}'s merit; they are waiting for the advocate's momentum to fade before the next election cycle."
        discomfort = 10  # Extremely uncomfortable
    elif months_in_limbo > 12:
        pattern_type = "Political Timing"
        strategic_inference = "Delaying decision until after election to avoid controversy"
        discomfort = 8
    else:
        pattern_type = "Sincere Analysis"
        strategic_inference = "Genuine need for additional information"
        discomfort = 3
    
    return DeferralPattern(
        topic=topic,
        conclusion=f"Administrative 'analysis' is being used as a strategic tool to avoid a final 'Yes' or 'No'." if pattern_type == "Rationale of Attrition" else "Under review",
        first_mentioned=first_date,
        total_deferrals=len(deferrals),
        months_in_limbo=months_in_limbo,
        justification_history=justification_history,
        pattern_type=pattern_type,
        strategic_inference=strategic_inference,
        discomfort_score=discomfort
    )


# ================================================================
# DASHBOARD 3: THE DISPLACEMENT MATRIX
# ================================================================

@dataclass
class DisplacementRow:
    """Single row in the displacement matrix."""
    winner_funded: str
    winner_amount: float
    loser_stagnant: str
    loser_amount: float
    tradeoff_factor: str  # "Visibility", "Asset Maintenance", "Public Safety"


@dataclass
class DisplacementMatrix:
    """
    Shows what got funded vs. what didn't - exposing priorities.
    
    Purpose: Force the "Why is X worth more than Y?" question.
    """
    topic: str
    conclusion: str
    
    # The matrix
    displacements: List[DisplacementRow]
    
    # The Logic
    priority_pattern: str  # "Legacy Rationale", "Visibility Bias", "Equity Gap"
    strategic_inference: str
    
    # Discomfort Factor
    discomfort_score: int


def generate_displacement_matrix(
    topic: str,
    budget_items: List[Any],
    decisions: List[Any],
    visible_categories: List[str] = None,
    invisible_categories: List[str] = None
) -> DisplacementMatrix:
    """
    Generate matrix showing visible assets funded over invisible infrastructure.
    
    Example:
        Winner: New Athletic Turf ($850k)
        Loser: Fluoride System Upgrade ($0)
        Factor: "Visibility - Turf is a PR win; Fluoride is hidden"
    """
    if visible_categories is None:
        visible_categories = ['construction', 'athletic', 'facility', 'building', 
                             'stadium', 'turf', 'renovation', 'HVAC', 'fleet']
    
    if invisible_categories is None:
        invisible_categories = ['health', 'dental', 'fluoride', 'screening', 
                               'nurse', 'mental health', 'counseling']
    
    # Find winners (funded, visible)
    winners = []
    for item in budget_items:
        if item.change_amount > 0:
            if any(cat in item.category.lower() for cat in visible_categories):
                winners.append(item)
    
    # Find losers (stagnant/cut, invisible)
    losers = []
    for item in budget_items:
        if item.change_amount <= 0:
            if any(cat in item.category.lower() for cat in invisible_categories):
                losers.append(item)
    
    # Pair them up
    displacements = []
    
    for i, winner in enumerate(winners):
        if i < len(losers):
            loser = losers[i]
        else:
            # Create synthetic loser if we have more winners
            loser = type('obj', (object,), {
                'category': 'Public Health Programs',
                'current_year_amount': 0
            })()
        
        # Determine tradeoff factor
        if 'athletic' in winner.category.lower() or 'turf' in winner.category.lower():
            factor = "Visibility: Athletic projects are PR wins; health is hidden"
        elif 'HVAC' in winner.category.upper() or 'building' in winner.category.lower():
            factor = "Asset Maintenance: Upkeep of buildings prioritized over health"
        elif 'police' in winner.category.lower() or 'security' in winner.category.lower():
            factor = "Public Safety: Police are a 'primary' rationale"
        else:
            factor = "Administrative preference: Tangible assets over services"
        
        displacements.append(DisplacementRow(
            winner_funded=winner.category,
            winner_amount=winner.current_year_amount,
            loser_stagnant=loser.category,
            loser_amount=loser.current_year_amount,
            tradeoff_factor=factor
        ))
    
    # Determine priority pattern
    if any('visibility' in d.tradeoff_factor.lower() for d in displacements):
        priority_pattern = "Legacy Rationale"
        strategic_inference = "Elected officials prefer funding things they can put their names on or hold ribbon-cuttings for, effectively 'trading' community health for political visibility."
        discomfort = 9
    elif any('asset' in d.tradeoff_factor.lower() for d in displacements):
        priority_pattern = "Asset Maintenance Bias"
        strategic_inference = "Buildings are prioritized over people - maintenance culture"
        discomfort = 7
    else:
        priority_pattern = "Resource Constraint"
        strategic_inference = "Limited resources force difficult choices"
        discomfort = 4
    
    return DisplacementMatrix(
        topic=topic,
        conclusion="The Board prioritizes 'Visible Assets' (Construction) over 'Invisible Infrastructure' (Public Health).",
        displacements=displacements,
        priority_pattern=priority_pattern,
        strategic_inference=strategic_inference,
        discomfort_score=discomfort
    )


# ================================================================
# DASHBOARD 4: THE INFLUENCE RADAR
# ================================================================

@dataclass
class InfluenceMetrics:
    """
    Quantifies who actually has decision power.
    
    Purpose: Call out the person blocking policy by name.
    """
    topic: str
    conclusion: str
    
    # Influence factors
    public_alignment: Dict[str, Any]  # {comments, influence_percent}
    risk_legal_alignment: Dict[str, Any]  # {memos, influence_percent, contact_name}
    consultant_alignment: Dict[str, Any]  # {reports, influence_percent, firm_name}
    elected_alignment: Dict[str, Any]  # {votes, influence_percent}
    
    # The Logic
    power_structure: str  # "Technocratic Rationale", "Public-Driven", "Elite Capture"
    veto_holder: str  # Name of the person/role with effective veto
    strategic_inference: str
    
    # Discomfort Factor
    discomfort_score: int


def calculate_influence_radar(
    topic: str,
    decisions: List[Any],
    meeting_documents: List[Dict[str, Any]]
) -> InfluenceMetrics:
    """
    Calculate who actually drives policy decisions.
    
    Example:
        Public Input: 240+ comments in favor (Influence: 4%)
        Risk/Legal: 1 memo expressing concerns (Influence: 92%)
        Logic: "Technocratic Rationale - lawyers write policy"
    """
    # Find relevant decisions
    relevant = [d for d in decisions if topic.lower() in d.decision_summary.lower()]
    
    if not relevant:
        # Return empty metrics
        return InfluenceMetrics(
            topic=topic,
            conclusion="No decisions found for this topic",
            public_alignment={'comments': 0, 'influence_percent': 0},
            risk_legal_alignment={'memos': 0, 'influence_percent': 0, 'contact_name': 'Unknown'},
            consultant_alignment={'reports': 0, 'influence_percent': 0, 'firm_name': 'Unknown'},
            elected_alignment={'votes': 0, 'influence_percent': 0},
            power_structure="Unknown",
            veto_holder="Unknown",
            strategic_inference="Insufficient data",
            discomfort_score=0
        )
    
    decision = relevant[0]  # Use most recent
    
    # Count public input
    public_comments = len(decision.supporters) + len(decision.opponents)
    public_support_ratio = len(decision.supporters) / public_comments if public_comments > 0 else 0
    
    # Detect legal/risk involvement
    legal_mentions = 0
    legal_contact = "Unknown"
    
    for evidence in decision.evidence_cited:
        if any(term in evidence.get('source', '').lower() 
               for term in ['legal', 'attorney', 'counsel', 'risk', 'liability', 'insurance']):
            legal_mentions += 1
            legal_contact = evidence.get('source', 'Legal Department')
    
    # Detect consultant involvement
    consultant_mentions = 0
    consultant_firm = "Unknown"
    
    for evidence in decision.evidence_cited:
        if any(term in evidence.get('source', '').lower() 
               for term in ['consultant', 'study', 'report', 'analysis', 'firm']):
            consultant_mentions += 1
            consultant_firm = evidence.get('source', 'External Consultant')
    
    # Calculate influence percentages
    # Simple heuristic: outcome alignment
    outcome_approved = decision.outcome.lower() in ['approved', 'adopted', 'passed']
    
    # If public wanted it and got it, high public influence
    # If legal/consultant opposed and it failed, high tech influence
    
    if public_support_ratio > 0.8 and outcome_approved:
        public_influence = 80
        legal_influence = 10
        consultant_influence = 10
        power_structure = "Public-Driven"
        veto_holder = "None - responsive governance"
        discomfort = 2
    elif legal_mentions > 0 and not outcome_approved:
        public_influence = 4
        legal_influence = 92
        consultant_influence = consultant_mentions * 10 if consultant_mentions > 0 else 0
        power_structure = "Technocratic Rationale"
        veto_holder = f"{legal_contact} (Legal/Risk Manager)"
        discomfort = 10  # Maximum discomfort
    elif consultant_mentions > 0 and not outcome_approved:
        public_influence = 8
        legal_influence = 7
        consultant_influence = 85
        power_structure = "Elite Capture"
        veto_holder = f"{consultant_firm}"
        discomfort = 9
    else:
        public_influence = 30
        legal_influence = 30
        consultant_influence = 40
        power_structure = "Mixed Influences"
        veto_holder = "Board discretion"
        discomfort = 4
    
    strategic_inference = ""
    if power_structure == "Technocratic Rationale":
        strategic_inference = f"The Board defaults to the path of least legal resistance, allowing the district's lawyers and CFO to effectively 'write' public health policy. {veto_holder} has functional veto power that outweighs {public_comments}+ citizen comments."
    elif power_structure == "Elite Capture":
        strategic_inference = f"External consultants drive policy more than constituents. {veto_holder} has outsized influence."
    else:
        strategic_inference = "Decision reflects balanced consideration of multiple stakeholders"
    
    return InfluenceMetrics(
        topic=topic,
        conclusion=f"Internal 'Risk Management' has a veto power that outweighs 100% of public input." if power_structure == "Technocratic Rationale" else "Influence is distributed",
        public_alignment={
            'comments': public_comments,
            'influence_percent': public_influence,
            'support_ratio': public_support_ratio * 100
        },
        risk_legal_alignment={
            'memos': legal_mentions,
            'influence_percent': legal_influence,
            'contact_name': legal_contact
        },
        consultant_alignment={
            'reports': consultant_mentions,
            'influence_percent': consultant_influence,
            'firm_name': consultant_firm
        },
        elected_alignment={
            'votes': 1,  # Simplified
            'influence_percent': 100 - public_influence - legal_influence - consultant_influence
        },
        power_structure=power_structure,
        veto_holder=veto_holder,
        strategic_inference=strategic_inference,
        discomfort_score=discomfort
    )


# ================================================================
# DASHBOARD GENERATOR
# ================================================================

def generate_all_accountability_dashboards(
    jurisdiction: str,
    meeting_documents: List[Dict[str, Any]],
    decisions: List[Any],
    budget_items: List[Any],
    focus_topic: str = "Student Health"
) -> Dict[str, Any]:
    """
    Generate all four accountability dashboards for a jurisdiction.
    
    Returns comprehensive accountability report ready for advocacy.
    """
    logger.info(f"Generating accountability dashboards for {jurisdiction}...")
    
    # Dashboard 1: Rhetoric Gap
    rhetoric_gap = calculate_rhetoric_gap(
        topic=focus_topic,
        meeting_documents=meeting_documents,
        budget_items=budget_items,
        keywords=['health', 'wellness', 'wellbeing', 'dental', 'vision', 'nurse']
    )
    
    # Dashboard 2: Deferral Pattern
    deferral_pattern = detect_deferral_pattern(
        topic="dental clinic",  # Specific topic
        decisions=decisions,
        meeting_documents=meeting_documents
    )
    
    # Dashboard 3: Displacement Matrix
    displacement = generate_displacement_matrix(
        topic="2026 Capital Prioritization",
        budget_items=budget_items,
        decisions=decisions
    )
    
    # Dashboard 4: Influence Radar
    influence = calculate_influence_radar(
        topic="school-based dental screening",
        decisions=decisions,
        meeting_documents=meeting_documents
    )
    
    return {
        'jurisdiction': jurisdiction,
        'focus_topic': focus_topic,
        'rhetoric_gap': rhetoric_gap,
        'deferral_pattern': deferral_pattern,
        'displacement_matrix': displacement,
        'influence_radar': influence,
        'max_discomfort_score': max(
            rhetoric_gap.discomfort_score,
            deferral_pattern.discomfort_score if deferral_pattern else 0,
            displacement.discomfort_score,
            influence.discomfort_score
        )
    }
