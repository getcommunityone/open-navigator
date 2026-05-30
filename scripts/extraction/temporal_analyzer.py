"""
Temporal Analysis Agent for election cycle and timing analysis.

Analyzes:
- Do high-visibility projects get approved before elections?
- Contention scores over time
- Deferral patterns (political sensitivity)
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict
from loguru import logger


@dataclass
class ElectionCyclePattern:
    """Pattern of decision-making relative to elections."""
    jurisdiction: str
    election_date: datetime
    
    # Decision patterns
    decisions_12mo_before: int
    decisions_6mo_before: int
    decisions_3mo_before: int
    decisions_post_election: int
    
    # High-visibility projects
    stadium_or_parks_pre_election: List[str]
    school_renovations_pre_election: List[str]
    
    # Analysis
    pre_election_spike: bool
    avg_project_cost_pre_election: float
    avg_project_cost_post_election: float
    
    inference: str  # "Incumbency protection", "Normal variance", etc.


@dataclass
class ContentionMetrics:
    """Metrics for analyzing decision contention."""
    decision_id: str
    decision_summary: str
    meeting_date: datetime
    
    # Vote analysis
    ayes: int
    nays: int
    abstentions: int
    contention_score: float  # nays / total votes
    unanimous: bool
    
    # Discussion analysis
    public_comments: int
    discussion_length_minutes: Optional[int]
    deferred_count: int  # How many times tabled before decision
    
    # Inference
    contention_level: str  # "High", "Medium", "Low"
    likely_rationale: str


class TemporalAnalyzer:
    """
    Analyze timing patterns in government decision-making.
    
    Implements:
    1. Election cycle correlation
    2. Contention score tracking
    3. Deferral pattern analysis
    4. Temporal trend identification
    """
    
    def __init__(self):
        """Initialize temporal analyzer."""
        pass
    
    def analyze_election_cycle(
        self,
        decisions: List[Any],  # PolicyDecision objects
        jurisdiction: str,
        election_dates: List[datetime]
    ) -> List[ElectionCyclePattern]:
        """
        Analyze decision patterns around election cycles.
        
        Tests hypothesis: Do "legacy" projects get approved before elections?
        """
        patterns = []
        
        for election_date in election_dates:
            # Define time windows
            window_12mo = election_date - timedelta(days=365)
            window_6mo = election_date - timedelta(days=180)
            window_3mo = election_date - timedelta(days=90)
            post_election = election_date + timedelta(days=180)
            
            # Count decisions in each window
            decisions_12mo = []
            decisions_6mo = []
            decisions_3mo = []
            decisions_post = []
            
            for decision in decisions:
                if decision.meeting_date >= window_12mo and decision.meeting_date < election_date:
                    decisions_12mo.append(decision)
                    if decision.meeting_date >= window_6mo:
                        decisions_6mo.append(decision)
                    if decision.meeting_date >= window_3mo:
                        decisions_3mo.append(decision)
                elif decision.meeting_date >= election_date and decision.meeting_date < post_election:
                    decisions_post.append(decision)
            
            # Identify high-visibility projects
            high_vis_keywords = ["stadium", "park", "renovation", "construction", "building"]
            
            stadiums_parks = []
            school_renovations = []
            
            for decision in decisions_6mo:
                summary_lower = decision.decision_summary.lower()
                if any(kw in summary_lower for kw in high_vis_keywords):
                    if "school" in summary_lower or "education" in summary_lower:
                        school_renovations.append(decision.decision_summary)
                    else:
                        stadiums_parks.append(decision.decision_summary)
            
            # Calculate costs if available
            pre_costs = []
            post_costs = []
            
            for decision in decisions_6mo:
                if decision.cost_estimate:
                    try:
                        # Extract numeric value from "$XXX,XXX" format
                        cost_str = decision.cost_estimate.replace('$', '').replace(',', '')
                        cost = float(cost_str.split()[0])
                        pre_costs.append(cost)
                    except:
                        pass
            
            for decision in decisions_post:
                if decision.cost_estimate:
                    try:
                        cost_str = decision.cost_estimate.replace('$', '').replace(',', '')
                        cost = float(cost_str.split()[0])
                        post_costs.append(cost)
                    except:
                        pass
            
            # Detect spike
            baseline = len(decisions_post) if decisions_post else 1
            pre_election_spike = len(decisions_6mo) > baseline * 1.5
            
            # Infer rationale
            if pre_election_spike and (stadiums_parks or school_renovations):
                inference = "Possible incumbency protection or legacy building"
            elif pre_election_spike:
                inference = "Increased activity before election (cause unclear)"
            else:
                inference = "No significant pre-election pattern detected"
            
            pattern = ElectionCyclePattern(
                jurisdiction=jurisdiction,
                election_date=election_date,
                decisions_12mo_before=len(decisions_12mo),
                decisions_6mo_before=len(decisions_6mo),
                decisions_3mo_before=len(decisions_3mo),
                decisions_post_election=len(decisions_post),
                stadium_or_parks_pre_election=stadiums_parks,
                school_renovations_pre_election=school_renovations,
                pre_election_spike=pre_election_spike,
                avg_project_cost_pre_election=sum(pre_costs) / len(pre_costs) if pre_costs else 0,
                avg_project_cost_post_election=sum(post_costs) / len(post_costs) if post_costs else 0,
                inference=inference
            )
            
            patterns.append(pattern)
        
        return patterns
    
    def calculate_contention_scores(
        self,
        decisions: List[Any]
    ) -> List[ContentionMetrics]:
        """
        Calculate contention scores for all decisions.
        
        High contention = conflicting trade-offs or politically sensitive
        """
        contention_metrics = []
        
        for decision in decisions:
            # Parse vote results
            ayes, nays, abstentions = self._parse_vote_result(decision.vote_result)
            
            total_votes = ayes + nays + abstentions
            contention_score = nays / total_votes if total_votes > 0 else 0
            unanimous = (nays == 0 and abstentions == 0)
            
            # Estimate public engagement
            public_comments = len(decision.supporters) + len(decision.opponents)
            
            # Count deferrals (not directly available, would need meeting history)
            deferred_count = 0  # Would need to track across meetings
            
            # Classify contention level
            if contention_score > 0.3 or public_comments > 10:
                contention_level = "High"
                likely_rationale = "Politically sensitive or conflicting stakeholder interests"
            elif contention_score > 0.1 or public_comments > 3:
                contention_level = "Medium"
                likely_rationale = "Some disagreement but manageable"
            else:
                contention_level = "Low"
                likely_rationale = "Consensus or administrative matter"
            
            metrics = ContentionMetrics(
                decision_id=decision.decision_id,
                decision_summary=decision.decision_summary,
                meeting_date=decision.meeting_date,
                ayes=ayes,
                nays=nays,
                abstentions=abstentions,
                contention_score=contention_score,
                unanimous=unanimous,
                public_comments=public_comments,
                discussion_length_minutes=None,  # Would need transcript timing
                deferred_count=deferred_count,
                contention_level=contention_level,
                likely_rationale=likely_rationale
            )
            
            contention_metrics.append(metrics)
        
        return contention_metrics
    
    def _parse_vote_result(self, vote_result: Optional[str]) -> tuple[int, int, int]:
        """Parse vote result string into ayes, nays, abstentions."""
        if not vote_result:
            return (0, 0, 0)
        
        # Pattern: "5-2", "7-0", "Unanimous", etc.
        if "unanimous" in vote_result.lower():
            return (7, 0, 0)  # Assume typical board size
        
        if "-" in vote_result:
            parts = vote_result.split("-")
            try:
                ayes = int(parts[0].strip())
                nays = int(parts[1].strip())
                return (ayes, nays, 0)
            except:
                return (0, 0, 0)
        
        return (0, 0, 0)
    
    def analyze_keyword_density(
        self,
        documents: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Analyze keyword density to understand governance drivers.
        
        "Grant" > "Taxpayer" = Outside funding driven
        "Emergency" frequent = Administrative convenience
        """
        keyword_categories = {
            "funding_source": ["grant", "federal", "state funding", "matching", "taxpayer", "local"],
            "urgency": ["emergency", "immediate", "urgent", "asap", "critical"],
            "process": ["work session", "public hearing", "committee", "postpone", "table"],
            "values": ["equity", "efficiency", "safety", "growth", "innovation"]
        }
        
        total_words = 0
        keyword_counts = defaultdict(int)
        
        for doc in documents:
            content = doc.get("content", "").lower()
            words = content.split()
            total_words += len(words)
            
            for category, keywords in keyword_categories.items():
                for keyword in keywords:
                    count = content.count(keyword.lower())
                    keyword_counts[f"{category}:{keyword}"] += count
        
        # Calculate density (per 1000 words)
        densities = {}
        for keyword, count in keyword_counts.items():
            densities[keyword] = (count / total_words * 1000) if total_words > 0 else 0
        
        return dict(sorted(densities.items(), key=lambda x: x[1], reverse=True))
    
    def infer_governance_logic(
        self,
        keyword_densities: Dict[str, float],
        contention_scores: List[ContentionMetrics],
        election_patterns: List[ElectionCyclePattern]
    ) -> Dict[str, Any]:
        """
        Synthesize all temporal analyses into governance logic inference.
        
        Returns narrative about how this jurisdiction operates.
        """
        # Analyze funding drivers
        grant_density = keyword_densities.get("funding_source:grant", 0)
        taxpayer_density = keyword_densities.get("funding_source:taxpayer", 0)
        
        if grant_density > taxpayer_density * 2:
            funding_driver = "Outside funding (grants/state) drives decisions more than local tax base"
        else:
            funding_driver = "Local taxpayer concerns are prominent in decision-making"
        
        # Analyze urgency patterns
        emergency_density = keyword_densities.get("urgency:emergency", 0)
        if emergency_density > 2.0:  # More than 2 per 1000 words
            urgency_pattern = "Frequent 'emergency' framing - may indicate reactive governance"
        else:
            urgency_pattern = "Standard deliberative process"
        
        # Analyze contention
        avg_contention = sum(c.contention_score for c in contention_scores) / len(contention_scores) if contention_scores else 0
        if avg_contention > 0.2:
            decision_style = "Frequently contentious - diverse stakeholder interests or partisan divide"
        else:
            decision_style = "Consensus-oriented - low conflict or dominant coalition"
        
        # Election influence
        has_election_spike = any(p.pre_election_spike for p in election_patterns)
        if has_election_spike:
            election_influence = "Visible increase in high-profile projects before elections"
        else:
            election_influence = "No clear election cycle pattern"
        
        return {
            "primary_driver": funding_driver,
            "urgency_pattern": urgency_pattern,
            "decision_style": decision_style,
            "election_influence": election_influence,
            "keyword_densities": keyword_densities,
            "avg_contention_score": avg_contention,
            "summary": f"This jurisdiction appears to be driven by {funding_driver.lower()}, with {decision_style.lower()}. {election_influence}."
        }
