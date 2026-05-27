"""
Policy Classifier Agent - MLflow version for Databricks Agent Bricks.

Classifies meeting documents for oral health policy topics using:
- Keyword matching and NLP
- LLM-based classification for ambiguous cases
- Unity Catalog for model governance
- MLflow tracing for observability
"""
from typing import Any, Dict, List, Optional
import pandas as pd
from enum import Enum
import mlflow
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from agents.mlflow_base import MLflowChainAgent
from agents.base import AgentRole
from config import settings


class PolicyTopic(str, Enum):
    """Oral health policy topics to classify."""
    WATER_FLUORIDATION = "water_fluoridation"
    SCHOOL_DENTAL_SCREENING = "school_dental_screening"
    MEDICAID_DENTAL = "medicaid_dental_expansion"
    LOW_INCOME_DENTAL_FUNDING = "low_income_dental_funding"
    DENTAL_INSURANCE_MANDATE = "dental_insurance_mandate"
    DENTAL_WORKFORCE = "dental_workforce_development"
    COMMUNITY_HEALTH_CENTER = "community_health_center_dental"
    OTHER_ORAL_HEALTH = "other_oral_health"
    NOT_ORAL_HEALTH = "not_oral_health_related"


class ClassificationResult(BaseModel):
    """Structured classification output."""
    primary_topic: PolicyTopic = Field(description="Primary policy topic")
    secondary_topics: List[PolicyTopic] = Field(default_factory=list, description="Additional relevant topics")
    confidence: float = Field(ge=0.0, le=1.0, description="Classification confidence")
    relevant_excerpts: List[str] = Field(default_factory=list, description="Key text excerpts")
    reasoning: str = Field(description="Brief explanation of classification")


class PolicyClassifierAgent(MLflowChainAgent):
    """
    Agent that classifies documents for oral health policy topics.
    
    Can be deployed to Databricks Model Serving and integrated with
    Unity Catalog for governance.
    """
    
    # Keywords for each topic (fallback classification)
    TOPIC_KEYWORDS = {
        PolicyTopic.WATER_FLUORIDATION: {
            "fluoride", "fluoridation", "water supply", "dental fluorosis",
            "community water", "fluoride levels", "fluoridated water"
        },
        PolicyTopic.SCHOOL_DENTAL_SCREENING: {
            "school dental", "screening program", "student dental", "school health",
            "dental exam", "school nurse", "oral health screening"
        },
        PolicyTopic.MEDICAID_DENTAL: {
            "medicaid dental", "adult dental coverage", "medicaid expansion",
            "dental benefits", "state medicaid", "covered dental services"
        },
        PolicyTopic.LOW_INCOME_DENTAL_FUNDING: {
            "low-income dental", "dental safety net", "free dental clinic",
            "dental voucher", "sliding scale dental", "charity care"
        },
        PolicyTopic.DENTAL_INSURANCE_MANDATE: {
            "dental insurance", "insurance mandate", "coverage requirement",
            "pediatric dental", "essential health benefits"
        },
        PolicyTopic.DENTAL_WORKFORCE: {
            "dental hygienist", "dental therapist", "scope of practice",
            "workforce shortage", "dental provider", "loan repayment"
        },
        PolicyTopic.COMMUNITY_HEALTH_CENTER: {
            "community health center", "FQHC", "health center dental",
            "federally qualified", "CHC dental"
        }
    }
    
    def __init__(self, agent_id: str = "classifier-mlflow-001"):
        """Initialize classifier agent."""
        super().__init__(agent_id, AgentRole.CLASSIFIER)
        self._setup_langchain_tracing()
        
    def _build_chain(self):
        """Build LangChain classification chain."""
        # Initialize LLM (will use AI Gateway if configured)
        llm = ChatOpenAI(
            model=settings.classifier_model,
            temperature=0.1,
            openai_api_key=settings.openai_api_key
        )
        
        # Create output parser
        parser = PydanticOutputParser(pydantic_object=ClassificationResult)
        
        # Create prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert policy analyst specializing in oral health policy.
            
Classify the following government meeting document for oral health policy topics.

Available topics:
- water_fluoridation: Fluoride in public water systems
- school_dental_screening: School-based dental programs
- medicaid_dental_expansion: Medicaid dental coverage
- low_income_dental_funding: Funding for low-income dental care
- dental_insurance_mandate: Insurance coverage requirements
- dental_workforce_development: Training, scope of practice
- community_health_center_dental: CHC/FQHC dental services
- other_oral_health: Other oral health topics
- not_oral_health_related: Not related to oral health

{format_instructions}"""),
            ("user", """Document Title: {title}
            
Document Content:
{content}

Classify this document and provide relevant excerpts.""")
        ])
        
        # Build chain
        chain = prompt | llm | parser
        return chain
    
    def _process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify a document for oral health policy topics.
        
        Args:
            request: Dict with 'document_id', 'title', 'content'
            
        Returns:
            Classification results with topics and confidence
        """
        document_id = request.get("document_id")
        title = request.get("title", "")
        content = request.get("content", "")
        
        with mlflow.start_span(name="classify_document") as span:
            span.set_attribute("document_id", document_id)
            
            # Try keyword-based classification first (faster, cheaper)
            keyword_result = self._classify_by_keywords(title + " " + content)
            
            if keyword_result["confidence"] >= 0.8:
                # High confidence from keywords, no LLM needed
                span.set_attribute("classification_method", "keywords")
                result = keyword_result
            else:
                # Use LLM for ambiguous cases
                span.set_attribute("classification_method", "llm")
                
                try:
                    llm_result = super()._process_request({
                        "title": title,
                        "content": content[:4000],  # Limit context length
                        "format_instructions": self._get_format_instructions()
                    })
                    
                    result = {
                        "document_id": document_id,
                        "primary_topic": llm_result.primary_topic.value,
                        "secondary_topics": [t.value for t in llm_result.secondary_topics],
                        "confidence": llm_result.confidence,
                        "relevant_excerpts": llm_result.relevant_excerpts,
                        "reasoning": llm_result.reasoning,
                        "method": "llm"
                    }
                    
                except Exception as e:
                    # Fallback to keywords if LLM fails
                    span.set_attribute("llm_error", str(e))
                    result = keyword_result
                    result["method"] = "keywords_fallback"
            
            return result
    
    def _classify_by_keywords(self, text: str) -> Dict[str, Any]:
        """
        Fast keyword-based classification.
        
        Args:
            text: Document text
            
        Returns:
            Classification result
        """
        text_lower = text.lower()
        scores = {}
        
        # Score each topic
        for topic, keywords in self.TOPIC_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > 0:
                scores[topic] = score
        
        if not scores:
            return {
                "primary_topic": PolicyTopic.NOT_ORAL_HEALTH.value,
                "secondary_topics": [],
                "confidence": 0.9,
                "relevant_excerpts": [],
                "reasoning": "No oral health keywords found",
                "method": "keywords"
            }
        
        # Get top topics
        sorted_topics = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        primary_topic = sorted_topics[0][0]
        secondary_topics = [t for t, s in sorted_topics[1:3] if s >= 2]
        
        # Calculate confidence based on score gap
        max_score = sorted_topics[0][1]
        confidence = min(0.95, 0.5 + (max_score / 10))
        
        # Extract relevant excerpts
        excerpts = self._extract_excerpts(text, primary_topic)
        
        return {
            "primary_topic": primary_topic.value,
            "secondary_topics": [t.value for t in secondary_topics],
            "confidence": confidence,
            "relevant_excerpts": excerpts,
            "reasoning": f"Found {max_score} keyword matches for {primary_topic.value}",
            "method": "keywords"
        }
    
    def _extract_excerpts(self, text: str, topic: PolicyTopic, max_excerpts: int = 3) -> List[str]:
        """Extract relevant text excerpts for a topic."""
        keywords = self.TOPIC_KEYWORDS.get(topic, set())
        sentences = text.split('. ')
        
        relevant = []
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(keyword in sentence_lower for keyword in keywords):
                relevant.append(sentence.strip())
                if len(relevant) >= max_excerpts:
                    break
        
        return relevant
    
    def _get_format_instructions(self) -> str:
        """Get format instructions for LLM output parsing."""
        parser = PydanticOutputParser(pydantic_object=ClassificationResult)
        return parser.get_format_instructions()
    
    def _get_example_input(self) -> Dict[str, Any]:
        """Get example input for MLflow signature."""
        return {
            "document_id": "doc_12345",
            "title": "City Council Meeting - Water Quality Discussion",
            "content": "The council discussed adding fluoride to the municipal water supply..."
        }


def register_classifier_to_unity_catalog():
    """
    Register the classifier agent to Unity Catalog.
    
    Usage:
        python -c "from agents.mlflow_classifier import register_classifier_to_unity_catalog; register_classifier_to_unity_catalog()"
    """
    agent = PolicyClassifierAgent()
    
    # Log and register to Unity Catalog
    run_id = agent.log_to_mlflow(
        model_name="policy_classifier_agent",
        registered_model_name=f"{settings.catalog_name}.{settings.schema_name}.policy_classifier",
        pip_requirements=[
            "mlflow>=2.10.0",
            "langchain>=0.1.0",
            "openai>=1.6.0",
            "pydantic>=2.5.0"
        ]
    )
    
    print(f"✅ Registered policy classifier agent to Unity Catalog")
    print(f"   Model: {settings.catalog_name}.{settings.schema_name}.policy_classifier")
    print(f"   Run ID: {run_id}")
    
    return run_id


if __name__ == "__main__":
    # Test the agent locally
    agent = PolicyClassifierAgent()
    
    test_input = {
        "document_id": "test_001",
        "title": "School Board Meeting Minutes",
        "content": """
        The school board discussed implementing a new dental screening program
        for elementary students. The program would provide free dental exams
        and referrals to local dentists for students in need.
        """
    }
    
    result = agent.predict(None, test_input)
    print("Classification Result:", result)
