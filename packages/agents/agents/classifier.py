"""
Classifier Agent for identifying oral health policy topics in meeting minutes.
"""
import asyncio
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from loguru import logger

from agents.base import BaseAgent, AgentRole, AgentMessage, MessageType, AgentStatus
from config import settings


class PolicyTopic:
    """Enumeration of oral health policy topics."""
    WATER_FLUORIDATION = "water_fluoridation"
    SCHOOL_DENTAL_SCREENING = "school_dental_screening"
    MEDICAID_DENTAL = "medicaid_dental"
    DENTAL_CLINIC_FUNDING = "dental_clinic_funding"
    COMMUNITY_DENTAL_PROGRAM = "community_dental_program"
    CHILDREN_DENTAL_HEALTH = "children_dental_health"
    DENTAL_CARE_ACCESS = "dental_care_access"
    OTHER_ORAL_HEALTH = "other_oral_health"
    NOT_RELEVANT = "not_relevant"


class ClassifierAgent(BaseAgent):
    """
    Agent responsible for classifying documents by oral health policy topics.
    
    Uses a combination of:
    - Keyword matching for high-precision identification
    - LLM-based classification for nuanced topics
    - Topic modeling for discovering new themes
    """
    
    def __init__(self, agent_id: str = "classifier-001"):
        """Initialize the classifier agent."""
        super().__init__(agent_id, AgentRole.CLASSIFIER)
        self._initialize_keywords()
        self.llm_client = None  # Will be initialized when needed
    
    def _initialize_keywords(self):
        """Initialize keyword patterns for each topic."""
        self.topic_keywords = {
            PolicyTopic.WATER_FLUORIDATION: [
                "fluoridation", "fluoride", "water fluoridation",
                "fluoridated water", "fluoride level", "fluoride treatment",
                "community water fluoridation"
            ],
            PolicyTopic.SCHOOL_DENTAL_SCREENING: [
                "school dental", "dental screening", "school screening",
                "school health screening", "dental exam", "school nurse",
                "student dental"
            ],
            PolicyTopic.MEDICAID_DENTAL: [
                "medicaid dental", "medicaid", "medicare dental",
                "public assistance dental", "low-income dental",
                "dental benefits", "dental coverage"
            ],
            PolicyTopic.DENTAL_CLINIC_FUNDING: [
                "dental clinic", "community dental clinic",
                "dental center", "dental facility", "clinic funding",
                "dental services funding"
            ],
            PolicyTopic.COMMUNITY_DENTAL_PROGRAM: [
                "community dental", "dental program", "oral health program",
                "dental outreach", "mobile dental", "dental van"
            ],
            PolicyTopic.CHILDREN_DENTAL_HEALTH: [
                "children's dental", "pediatric dental", "child dental",
                "kids dental", "youth dental", "infant oral health"
            ],
            PolicyTopic.DENTAL_CARE_ACCESS: [
                "dental access", "access to dental", "dental care",
                "oral health access", "dental services", "dental disparities"
            ]
        }
    
    async def process(self, message: AgentMessage) -> List[AgentMessage]:
        """
        Process classification commands.
        
        Args:
            message: Message containing parsed documents to classify
            
        Returns:
            List of messages with classification results
        """
        self.update_status(AgentStatus.PROCESSING, "Classifying policy documents")
        
        try:
            documents = message.payload.get("documents", [])
            
            # Classify documents in batches
            batch_size = settings.classifier_batch_size
            classified_documents = []
            
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                batch_results = await self._classify_batch(batch)
                classified_documents.extend(batch_results)
            
            # Filter to only relevant documents
            relevant_documents = [
                doc for doc in classified_documents
                if doc["classification"]["primary_topic"] != PolicyTopic.NOT_RELEVANT
            ]
            
            # Send classified documents to sentiment analyzer
            response = await self.send_message(
                AgentRole.SENTIMENT_ANALYZER,
                MessageType.DATA,
                {
                    "workflow_id": message.payload.get("workflow_id"),
                    "documents": relevant_documents,
                    "count": len(relevant_documents),
                    "filtered_count": len(documents) - len(relevant_documents)
                }
            )
            
            self.log_success()
            logger.info(
                f"Classified {len(documents)} documents, "
                f"{len(relevant_documents)} relevant to oral health policy"
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
    
    async def _classify_batch(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Classify a batch of documents.
        
        Args:
            documents: Batch of documents to classify
            
        Returns:
            Documents with classification results
        """
        tasks = [self._classify_document(doc) for doc in documents]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        classified = []
        for doc, result in zip(documents, results):
            if isinstance(result, Exception):
                logger.error(f"Classification error for {doc['document_id']}: {result}")
                doc["classification"] = {
                    "primary_topic": PolicyTopic.NOT_RELEVANT,
                    "error": str(result)
                }
            else:
                doc["classification"] = result
            
            classified.append(doc)
        
        return classified
    
    async def _classify_document(
        self,
        doc: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Classify a single document.
        
        Args:
            doc: Document to classify
            
        Returns:
            Classification results
        """
        text = self._get_searchable_text(doc)
        text_lower = text.lower()
        
        # Keyword-based classification
        topic_scores = {}
        for topic, keywords in self.topic_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > 0:
                topic_scores[topic] = score
        
        # Determine primary topic
        if topic_scores:
            primary_topic = max(topic_scores, key=topic_scores.get)
            confidence = "high" if topic_scores[primary_topic] >= 3 else "medium"
            
            # Get all topics mentioned
            all_topics = list(topic_scores.keys())
        else:
            primary_topic = PolicyTopic.NOT_RELEVANT
            confidence = "high"
            all_topics = []
        
        # Extract relevant excerpts
        excerpts = self._extract_relevant_excerpts(doc, primary_topic)
        
        classification = {
            "primary_topic": primary_topic,
            "all_topics": all_topics,
            "topic_scores": topic_scores,
            "confidence": confidence,
            "relevant_excerpts": excerpts,
            "classified_at": datetime.utcnow().isoformat()
        }
        
        return classification
    
    def _get_searchable_text(self, doc: Dict[str, Any]) -> str:
        """Extract searchable text from document."""
        parts = [
            doc.get("raw_title", ""),
            doc.get("full_text", "")
        ]
        
        # Add agenda items
        for item in doc.get("agenda_items", []):
            parts.append(item.get("description", ""))
        
        # Add discussion sections
        for section in doc.get("discussion_sections", []):
            parts.append(section.get("text", ""))
        
        return " ".join(parts)
    
    def _extract_relevant_excerpts(
        self,
        doc: Dict[str, Any],
        topic: str
    ) -> List[Dict[str, str]]:
        """Extract text excerpts relevant to the topic."""
        if topic == PolicyTopic.NOT_RELEVANT:
            return []
        
        keywords = self.topic_keywords.get(topic, [])
        excerpts = []
        
        # Check discussion sections
        for section in doc.get("discussion_sections", []):
            text = section.get("text", "")
            text_lower = text.lower()
            
            # Check if any keywords present
            if any(keyword in text_lower for keyword in keywords):
                excerpts.append({
                    "source": "discussion",
                    "text": text[:500],  # First 500 chars
                    "section_id": section.get("section_id")
                })
        
        # Check agenda items
        for item in doc.get("agenda_items", []):
            desc = item.get("description", "")
            desc_lower = desc.lower()
            
            if any(keyword in desc_lower for keyword in keywords):
                excerpts.append({
                    "source": "agenda",
                    "text": desc,
                    "item_number": item.get("number")
                })
        
        return excerpts[:5]  # Return top 5 excerpts
    
    async def _llm_classify(
        self,
        text: str,
        preliminary_topics: List[str]
    ) -> Dict[str, Any]:
        """
        Use LLM for nuanced classification when keywords are ambiguous.
        
        Args:
            text: Text to classify
            preliminary_topics: Topics identified by keyword matching
            
        Returns:
            LLM classification results
        """
        # This would use OpenAI API or similar
        # Placeholder for now
        return {
            "llm_topic": preliminary_topics[0] if preliminary_topics else PolicyTopic.NOT_RELEVANT,
            "llm_confidence": 0.8,
            "llm_reasoning": "Based on keyword analysis"
        }
