"""
Debate Grader Agent for evaluating government decisions using debate framework.

Evaluates decisions across three dimensions:
- Harms: The problem/crisis identified
- Solvency: How the proposed solution addresses the problem
- Topicality: Whether the solution fits within jurisdiction's authority
"""
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from agents.base import BaseAgent, AgentRole, AgentMessage, MessageType, AgentStatus


class DebateDimension:
    """Enumeration of debate evaluation dimensions."""
    HARMS = "harms"  # The problem
    SOLVENCY = "solvency"  # The fix
    TOPICALITY = "topicality"  # The scope


class DebateScore:
    """Score levels for each debate dimension."""
    EXCELLENT = "excellent"  # 4-5/5
    GOOD = "good"  # 3-4/5
    FAIR = "fair"  # 2-3/5
    WEAK = "weak"  # 1-2/5
    MISSING = "missing"  # 0-1/5


class DebateGraderAgent(BaseAgent):
    """
    Agent responsible for grading government decisions using debate framework.
    
    Translates debate concepts for laypeople:
    - Harms → "The Problem": Why is this a crisis in our community?
    - Solvency → "The Fix": How does this solution actually work?
    - Topicality → "The Scope": Does the government have authority to do this?
    """
    
    def __init__(self, agent_id: str = "debate-grader-001"):
        """Initialize the debate grader agent."""
        super().__init__(agent_id, AgentRole.SENTIMENT_ANALYZER)
        self._initialize_criteria()
    
    def _initialize_criteria(self):
        """Initialize evaluation criteria for each dimension."""
        
        # Harms evaluation keywords
        self.harms_indicators = {
            "problem_identification": [
                "crisis", "emergency", "critical", "urgent need",
                "widespread problem", "affecting", "impacting",
                "suffering", "lack of", "shortage", "gap in services"
            ],
            "data_evidence": [
                "statistics", "data shows", "research indicates",
                "study found", "percent", "%", "number of people",
                "cases", "instances", "reports"
            ],
            "affected_population": [
                "children", "families", "residents", "citizens",
                "low-income", "vulnerable", "underserved",
                "community members", "students", "seniors"
            ]
        }
        
        # Solvency evaluation keywords
        self.solvency_indicators = {
            "solution_clarity": [
                "will", "would", "proposes to", "plans to",
                "implement", "establish", "create", "provide",
                "offer", "deliver", "fund", "allocate"
            ],
            "mechanism": [
                "through", "by", "using", "via", "process",
                "program", "initiative", "partnership",
                "collaboration", "service", "system"
            ],
            "evidence_of_effectiveness": [
                "proven", "successful in", "works in",
                "demonstrated", "track record", "best practice",
                "evidence-based", "research-backed"
            ],
            "implementation_plan": [
                "timeline", "budget", "staff", "resources",
                "phase", "rollout", "launch", "start date",
                "completion", "milestones"
            ]
        }
        
        # Topicality evaluation keywords
        self.topicality_indicators = {
            "legal_authority": [
                "authority", "jurisdiction", "mandate",
                "chartered to", "empowered to", "authorized",
                "within our purview", "responsibility"
            ],
            "precedent": [
                "previously", "historically", "past practice",
                "similar actions", "other cities", "state law",
                "federal law", "code", "ordinance"
            ],
            "scope_appropriateness": [
                "city council", "county commission", "board",
                "department", "local government", "municipal",
                "within scope", "appropriate for"
            ]
        }
    
    async def process(self, message: AgentMessage) -> List[AgentMessage]:
        """
        Process debate grading commands.
        
        Args:
            message: Message containing decisions/documents to grade
            
        Returns:
            List of messages with debate grades
        """
        self.update_status(AgentStatus.PROCESSING, "Grading decisions with debate framework")
        
        try:
            documents = message.payload.get("documents", [])
            
            graded_documents = []
            
            for doc in documents:
                grade = await self._grade_document(doc)
                doc["debate_grade"] = grade
                graded_documents.append(doc)
            
            # Calculate aggregate insights
            insights = self._generate_insights(graded_documents)
            
            # Send results
            response = await self.send_message(
                recipient=AgentRole.ORCHESTRATOR,
                message_type=MessageType.RESPONSE,
                payload={
                    "documents": graded_documents,
                    "insights": insights,
                    "graded_count": len(graded_documents)
                }
            )
            
            self.update_status(AgentStatus.COMPLETED, f"Graded {len(graded_documents)} decisions")
            return [response]
            
        except Exception as e:
            logger.error(f"Debate grading failed: {e}")
            self.update_status(AgentStatus.ERROR, str(e))
            raise
    
    async def _grade_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Grade a single document across all debate dimensions.
        
        Args:
            document: Document to grade
            
        Returns:
            Dictionary with grades for each dimension
        """
        text = document.get("content", "").lower()
        title = document.get("title", "").lower()
        combined_text = f"{title} {text}"
        
        # Grade each dimension
        harms_score = self._grade_harms(combined_text)
        solvency_score = self._grade_solvency(combined_text)
        topicality_score = self._grade_topicality(combined_text)
        
        # Calculate overall score
        overall_score = self._calculate_overall_score(
            harms_score, solvency_score, topicality_score
        )
        
        return {
            "dimensions": {
                "harms": {
                    "score": harms_score["score"],
                    "grade": harms_score["grade"],
                    "explanation": harms_score["explanation"],
                    "layperson_label": "The Problem",
                    "layperson_question": "Why is this a crisis in our community?"
                },
                "solvency": {
                    "score": solvency_score["score"],
                    "grade": solvency_score["grade"],
                    "explanation": solvency_score["explanation"],
                    "layperson_label": "The Fix",
                    "layperson_question": "How does this solution actually work?"
                },
                "topicality": {
                    "score": topicality_score["score"],
                    "grade": topicality_score["grade"],
                    "explanation": topicality_score["explanation"],
                    "layperson_label": "The Scope",
                    "layperson_question": "Does the government have authority to do this?"
                }
            },
            "overall": {
                "score": overall_score,
                "grade": self._score_to_grade(overall_score),
                "summary": self._generate_summary(harms_score, solvency_score, topicality_score)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _grade_harms(self, text: str) -> Dict[str, Any]:
        """Grade the 'harms' dimension - problem identification."""
        score = 0
        max_score = 5
        details = []
        
        # Check for problem identification (0-2 points)
        problem_count = sum(1 for keyword in self.harms_indicators["problem_identification"] if keyword in text)
        if problem_count >= 3:
            score += 2
            details.append("Strong problem identification")
        elif problem_count >= 1:
            score += 1
            details.append("Problem mentioned but not detailed")
        
        # Check for data/evidence (0-2 points)
        data_count = sum(1 for keyword in self.harms_indicators["data_evidence"] if keyword in text)
        if data_count >= 2:
            score += 2
            details.append("Data-driven evidence provided")
        elif data_count >= 1:
            score += 1
            details.append("Some evidence mentioned")
        
        # Check for affected population (0-1 point)
        population_count = sum(1 for keyword in self.harms_indicators["affected_population"] if keyword in text)
        if population_count >= 1:
            score += 1
            details.append("Affected population identified")
        
        return {
            "score": score,
            "max_score": max_score,
            "grade": self._score_to_grade(score / max_score * 5),
            "explanation": "; ".join(details) if details else "No clear problem statement"
        }
    
    def _grade_solvency(self, text: str) -> Dict[str, Any]:
        """Grade the 'solvency' dimension - solution effectiveness."""
        score = 0
        max_score = 5
        details = []
        
        # Check for solution clarity (0-1 point)
        solution_count = sum(1 for keyword in self.solvency_indicators["solution_clarity"] if keyword in text)
        if solution_count >= 2:
            score += 1
            details.append("Clear solution proposed")
        
        # Check for mechanism (0-2 points)
        mechanism_count = sum(1 for keyword in self.solvency_indicators["mechanism"] if keyword in text)
        if mechanism_count >= 3:
            score += 2
            details.append("Implementation mechanism described")
        elif mechanism_count >= 1:
            score += 1
            details.append("Basic approach outlined")
        
        # Check for evidence of effectiveness (0-1 point)
        evidence_count = sum(1 for keyword in self.solvency_indicators["evidence_of_effectiveness"] if keyword in text)
        if evidence_count >= 1:
            score += 1
            details.append("Evidence-based approach")
        
        # Check for implementation plan (0-1 point)
        plan_count = sum(1 for keyword in self.solvency_indicators["implementation_plan"] if keyword in text)
        if plan_count >= 2:
            score += 1
            details.append("Implementation plan included")
        
        return {
            "score": score,
            "max_score": max_score,
            "grade": self._score_to_grade(score / max_score * 5),
            "explanation": "; ".join(details) if details else "No clear solution mechanism"
        }
    
    def _grade_topicality(self, text: str) -> Dict[str, Any]:
        """Grade the 'topicality' dimension - scope appropriateness."""
        score = 0
        max_score = 5
        details = []
        
        # Check for legal authority (0-2 points)
        authority_count = sum(1 for keyword in self.topicality_indicators["legal_authority"] if keyword in text)
        if authority_count >= 2:
            score += 2
            details.append("Legal authority cited")
        elif authority_count >= 1:
            score += 1
            details.append("Authority mentioned")
        
        # Check for precedent (0-2 points)
        precedent_count = sum(1 for keyword in self.topicality_indicators["precedent"] if keyword in text)
        if precedent_count >= 2:
            score += 2
            details.append("Precedent established")
        elif precedent_count >= 1:
            score += 1
            details.append("Some precedent referenced")
        
        # Check for scope appropriateness (0-1 point)
        scope_count = sum(1 for keyword in self.topicality_indicators["scope_appropriateness"] if keyword in text)
        if scope_count >= 1:
            score += 1
            details.append("Within appropriate scope")
        
        return {
            "score": score,
            "max_score": max_score,
            "grade": self._score_to_grade(score / max_score * 5),
            "explanation": "; ".join(details) if details else "Unclear jurisdictional authority"
        }
    
    def _score_to_grade(self, normalized_score: float) -> str:
        """Convert numerical score to grade."""
        if normalized_score >= 4.0:
            return DebateScore.EXCELLENT
        elif normalized_score >= 3.0:
            return DebateScore.GOOD
        elif normalized_score >= 2.0:
            return DebateScore.FAIR
        elif normalized_score >= 1.0:
            return DebateScore.WEAK
        else:
            return DebateScore.MISSING
    
    def _calculate_overall_score(
        self,
        harms: Dict[str, Any],
        solvency: Dict[str, Any],
        topicality: Dict[str, Any]
    ) -> float:
        """Calculate weighted overall score."""
        # Weight: Harms 40%, Solvency 40%, Topicality 20%
        harms_normalized = (harms["score"] / harms["max_score"]) * 5
        solvency_normalized = (solvency["score"] / solvency["max_score"]) * 5
        topicality_normalized = (topicality["score"] / topicality["max_score"]) * 5
        
        overall = (harms_normalized * 0.4) + (solvency_normalized * 0.4) + (topicality_normalized * 0.2)
        return round(overall, 2)
    
    def _generate_summary(
        self,
        harms: Dict[str, Any],
        solvency: Dict[str, Any],
        topicality: Dict[str, Any]
    ) -> str:
        """Generate human-readable summary."""
        parts = []
        
        if harms["grade"] in [DebateScore.EXCELLENT, DebateScore.GOOD]:
            parts.append("Strong problem identification")
        else:
            parts.append("Weak problem statement")
        
        if solvency["grade"] in [DebateScore.EXCELLENT, DebateScore.GOOD]:
            parts.append("clear solution")
        else:
            parts.append("unclear fix")
        
        if topicality["grade"] in [DebateScore.EXCELLENT, DebateScore.GOOD]:
            parts.append("within authority")
        else:
            parts.append("questionable scope")
        
        return "; ".join(parts).capitalize()
    
    def _generate_insights(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate aggregate insights from all graded documents."""
        if not documents:
            return {}
        
        total = len(documents)
        dimension_scores = {
            "harms": [],
            "solvency": [],
            "topicality": []
        }
        overall_scores = []
        
        for doc in documents:
            grade = doc.get("debate_grade", {})
            dimensions = grade.get("dimensions", {})
            
            for dim in ["harms", "solvency", "topicality"]:
                if dim in dimensions:
                    dimension_scores[dim].append(dimensions[dim]["score"])
            
            if "overall" in grade:
                overall_scores.append(grade["overall"]["score"])
        
        # Calculate averages
        insights = {
            "total_documents": total,
            "average_scores": {
                "harms": round(sum(dimension_scores["harms"]) / len(dimension_scores["harms"]), 2) if dimension_scores["harms"] else 0,
                "solvency": round(sum(dimension_scores["solvency"]) / len(dimension_scores["solvency"]), 2) if dimension_scores["solvency"] else 0,
                "topicality": round(sum(dimension_scores["topicality"]) / len(dimension_scores["topicality"]), 2) if dimension_scores["topicality"] else 0,
                "overall": round(sum(overall_scores) / len(overall_scores), 2) if overall_scores else 0
            },
            "strongest_dimension": max(
                dimension_scores.items(),
                key=lambda x: sum(x[1]) / len(x[1]) if x[1] else 0
            )[0] if any(dimension_scores.values()) else None,
            "weakest_dimension": min(
                dimension_scores.items(),
                key=lambda x: sum(x[1]) / len(x[1]) if x[1] else 0
            )[0] if any(dimension_scores.values()) else None
        }
        
        return insights
