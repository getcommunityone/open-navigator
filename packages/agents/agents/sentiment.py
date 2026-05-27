"""
Sentiment Analyzer Agent for determining policy stance and debate intensity.
"""
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from agents.base import BaseAgent, AgentRole, AgentMessage, MessageType, AgentStatus


class PolicyStance:
    """Enumeration of policy stances."""
    STRONGLY_SUPPORTIVE = "strongly_supportive"
    SUPPORTIVE = "supportive"
    NEUTRAL = "neutral"
    OPPOSED = "opposed"
    STRONGLY_OPPOSED = "strongly_opposed"
    DEBATED = "debated"  # When there's active debate


class DebateIntensity:
    """Enumeration of debate intensity levels."""
    NONE = "none"  # Passing mention
    LOW = "low"  # Brief discussion
    MODERATE = "moderate"  # Extended discussion
    HIGH = "high"  # Heated debate with multiple viewpoints
    CRITICAL = "critical"  # Vote imminent or major decision pending


class SentimentAnalyzerAgent(BaseAgent):
    """
    Agent responsible for analyzing sentiment and policy stance.
    
    Determines:
    - Overall stance toward oral health policies
    - Intensity of debate/discussion
    - Key arguments for and against
    - Likelihood of policy action
    - Advocacy opportunities
    """
    
    def __init__(self, agent_id: str = "sentiment-001"):
        """Initialize the sentiment analyzer agent."""
        super().__init__(agent_id, AgentRole.SENTIMENT_ANALYZER)
        self._initialize_indicators()
    
    def _initialize_indicators(self):
        """Initialize sentiment and debate indicators."""
        self.supportive_indicators = [
            "approve", "support", "favor", "endorse", "recommend",
            "beneficial", "important", "necessary", "implement",
            "move forward", "proceed with"
        ]
        
        self.opposition_indicators = [
            "oppose", "against", "reject", "deny", "concerns about",
            "problems with", "issues with", "delay", "postpone",
            "table the motion", "reconsider"
        ]
        
        self.debate_indicators = [
            "discussion", "debate", "motion", "vote", "amendment",
            "public comment", "testimony", "hearing", "concerns",
            "questions about", "divided"
        ]
        
        self.urgency_indicators = [
            "urgent", "immediate", "deadline", "vote", "decision",
            "approval needed", "time-sensitive", "pressing",
            "second reading", "final vote"
        ]
    
    async def process(self, message: AgentMessage) -> List[AgentMessage]:
        """
        Process sentiment analysis commands.
        
        Args:
            message: Message containing classified documents
            
        Returns:
            List of messages with sentiment analysis results
        """
        self.update_status(AgentStatus.PROCESSING, "Analyzing policy sentiment and debate")
        
        try:
            documents = message.payload.get("documents", [])
            
            analyzed_documents = []
            
            for doc in documents:
                analysis = await self._analyze_document(doc)
                doc["sentiment_analysis"] = analysis
                analyzed_documents.append(doc)
            
            # Identify advocacy opportunities
            opportunities = self._identify_advocacy_opportunities(analyzed_documents)
            
            # Send to advocacy writer agent
            response = await self.send_message(
                AgentRole.ADVOCACY_WRITER,
                MessageType.DATA,
                {
                    "workflow_id": message.payload.get("workflow_id"),
                    "documents": analyzed_documents,
                    "opportunities": opportunities,
                    "count": len(analyzed_documents)
                }
            )
            
            self.log_success()
            logger.info(
                f"Analyzed sentiment for {len(analyzed_documents)} documents, "
                f"found {len(opportunities)} advocacy opportunities"
            )
            
            return [response]
            
        except Exception as e:
            self.log_failure(str(e))
            error_msg = await self.send_message(
                AgentRole.ORCHESTRATOR,
                MessageType.ERROR,
                {"error": str(e), "agent": self.agent_id}
            )
            return [error_msg]
    
    async def _analyze_document(
        self,
        doc: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze sentiment and policy stance for a document.
        
        Args:
            doc: Document to analyze
            
        Returns:
            Sentiment analysis results
        """
        text = self._get_analyzable_text(doc)
        text_lower = text.lower()
        
        # Count sentiment indicators
        support_score = sum(
            1 for indicator in self.supportive_indicators
            if indicator in text_lower
        )
        
        opposition_score = sum(
            1 for indicator in self.opposition_indicators
            if indicator in text_lower
        )
        
        debate_score = sum(
            1 for indicator in self.debate_indicators
            if indicator in text_lower
        )
        
        urgency_score = sum(
            1 for indicator in self.urgency_indicators
            if indicator in text_lower
        )
        
        # Determine policy stance
        stance = self._determine_stance(support_score, opposition_score, debate_score)
        
        # Determine debate intensity
        intensity = self._determine_intensity(debate_score, urgency_score, doc)
        
        # Extract key arguments
        arguments = self._extract_arguments(doc, text_lower)
        
        # Calculate advocacy urgency
        advocacy_urgency = self._calculate_advocacy_urgency(
            stance, intensity, urgency_score
        )
        
        analysis = {
            "stance": stance,
            "debate_intensity": intensity,
            "support_score": support_score,
            "opposition_score": opposition_score,
            "debate_score": debate_score,
            "urgency_score": urgency_score,
            "advocacy_urgency": advocacy_urgency,
            "key_arguments": arguments,
            "analyzed_at": datetime.utcnow().isoformat()
        }
        
        return analysis
    
    def _get_analyzable_text(self, doc: Dict[str, Any]) -> str:
        """Extract text for sentiment analysis."""
        parts = []
        
        # Prioritize excerpts from classification
        for excerpt in doc.get("classification", {}).get("relevant_excerpts", []):
            parts.append(excerpt.get("text", ""))
        
        # Add motions (highly relevant)
        for motion in doc.get("motions", []):
            parts.append(motion.get("text", ""))
        
        # Add votes
        for vote in doc.get("votes", []):
            parts.append(vote.get("result", ""))
        
        # Fallback to full text if needed
        if not parts:
            parts.append(doc.get("full_text", ""))
        
        return " ".join(parts)
    
    def _determine_stance(
        self,
        support_score: int,
        opposition_score: int,
        debate_score: int
    ) -> str:
        """Determine overall policy stance."""
        if debate_score >= 3 and abs(support_score - opposition_score) <= 1:
            return PolicyStance.DEBATED
        
        if support_score > opposition_score:
            if support_score >= 3:
                return PolicyStance.STRONGLY_SUPPORTIVE
            else:
                return PolicyStance.SUPPORTIVE
        elif opposition_score > support_score:
            if opposition_score >= 3:
                return PolicyStance.STRONGLY_OPPOSED
            else:
                return PolicyStance.OPPOSED
        else:
            return PolicyStance.NEUTRAL
    
    def _determine_intensity(
        self,
        debate_score: int,
        urgency_score: int,
        doc: Dict[str, Any]
    ) -> str:
        """Determine debate intensity."""
        # Check for votes or motions (indicates high intensity)
        has_vote = len(doc.get("votes", [])) > 0
        has_motion = len(doc.get("motions", [])) > 0
        
        if urgency_score >= 2 or (has_vote and has_motion):
            return DebateIntensity.CRITICAL
        elif debate_score >= 5 or has_vote or has_motion:
            return DebateIntensity.HIGH
        elif debate_score >= 3:
            return DebateIntensity.MODERATE
        elif debate_score >= 1:
            return DebateIntensity.LOW
        else:
            return DebateIntensity.NONE
    
    def _extract_arguments(
        self,
        doc: Dict[str, Any],
        text_lower: str
    ) -> Dict[str, List[str]]:
        """Extract key arguments for and against."""
        arguments = {
            "supporting": [],
            "opposing": []
        }
        
        # Extract from motions and discussion
        for motion in doc.get("motions", []):
            motion_text = motion.get("text", "").lower()
            
            if any(ind in motion_text for ind in self.supportive_indicators):
                arguments["supporting"].append(motion.get("text", ""))
            elif any(ind in motion_text for ind in self.opposition_indicators):
                arguments["opposing"].append(motion.get("text", ""))
        
        return arguments
    
    def _calculate_advocacy_urgency(
        self,
        stance: str,
        intensity: str,
        urgency_score: int
    ) -> str:
        """
        Calculate how urgent advocacy action is needed.
        
        Returns: "critical", "high", "medium", "low", or "none"
        """
        # Critical: Vote imminent and debated/opposed
        if intensity == DebateIntensity.CRITICAL:
            if stance in [PolicyStance.DEBATED, PolicyStance.OPPOSED, PolicyStance.STRONGLY_OPPOSED]:
                return "critical"
            return "high"
        
        # High: Active debate with opposition
        if intensity == DebateIntensity.HIGH:
            if stance in [PolicyStance.OPPOSED, PolicyStance.STRONGLY_OPPOSED]:
                return "high"
            elif stance == PolicyStance.DEBATED:
                return "high"
            return "medium"
        
        # Medium: Moderate discussion or emerging issue
        if intensity == DebateIntensity.MODERATE:
            return "medium"
        
        # Low: Early stage or general mention
        if intensity == DebateIntensity.LOW:
            return "low"
        
        return "none"
    
    def _identify_advocacy_opportunities(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Identify advocacy opportunities across all analyzed documents.
        
        Args:
            documents: All analyzed documents
            
        Returns:
            List of advocacy opportunities
        """
        opportunities = []
        
        for doc in documents:
            sentiment = doc.get("sentiment_analysis", {})
            urgency = sentiment.get("advocacy_urgency")
            
            # Only flag high and critical urgency items
            if urgency in ["critical", "high"]:
                opportunity = {
                    "document_id": doc["document_id"],
                    "municipality": doc["municipality"],
                    "state": doc["state"],
                    "meeting_date": doc["meeting_date"],
                    "source_url": doc["source_url"],
                    "topic": doc["classification"]["primary_topic"],
                    "stance": sentiment["stance"],
                    "intensity": sentiment["debate_intensity"],
                    "urgency": urgency,
                    "key_excerpts": doc["classification"].get("relevant_excerpts", []),
                    "recommended_action": self._recommend_action(sentiment, doc)
                }
                opportunities.append(opportunity)
        
        # Sort by urgency
        urgency_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        opportunities.sort(key=lambda x: urgency_order.get(x["urgency"], 4))
        
        return opportunities
    
    def _recommend_action(
        self,
        sentiment: Dict[str, Any],
        doc: Dict[str, Any]
    ) -> str:
        """Recommend advocacy action based on analysis."""
        stance = sentiment.get("stance")
        intensity = sentiment.get("debate_intensity")
        
        if intensity == DebateIntensity.CRITICAL:
            if stance in [PolicyStance.OPPOSED, PolicyStance.STRONGLY_OPPOSED]:
                return "URGENT: Contact officials immediately. Vote imminent."
            elif stance == PolicyStance.DEBATED:
                return "URGENT: Provide supporting testimony. Decision pending."
        
        if stance == PolicyStance.DEBATED:
            return "Engage with stakeholders. Provide educational materials."
        elif stance in [PolicyStance.OPPOSED, PolicyStance.STRONGLY_OPPOSED]:
            return "Initiate dialogue with decision-makers. Address concerns."
        elif stance == PolicyStance.NEUTRAL:
            return "Introduce topic to agenda. Build awareness."
        
        return "Monitor situation. Prepare support materials."
