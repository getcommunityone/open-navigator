"""
Test suite for the Oral Health Policy Pulse system.
"""
import pytest
from agents.base import AgentRole, MessageType, AgentStatus
from agents.orchestrator import OrchestratorAgent
from agents.scraper import ScraperAgent
from agents.classifier import ClassifierAgent, PolicyTopic


class TestAgentBase:
    """Test base agent functionality."""
    
    def test_agent_initialization(self):
        """Test that agents initialize correctly."""
        agent = ScraperAgent()
        assert agent.role == AgentRole.SCRAPER
        assert agent.state.status == AgentStatus.IDLE
    
    def test_agent_status_update(self):
        """Test agent status updates."""
        agent = ScraperAgent()
        agent.update_status(AgentStatus.PROCESSING, "Test task")
        
        assert agent.state.status == AgentStatus.PROCESSING
        assert agent.state.current_task == "Test task"


class TestClassifier:
    """Test classifier agent."""
    
    def test_keyword_classification(self):
        """Test keyword-based classification."""
        classifier = ClassifierAgent()
        
        doc = {
            "document_id": "test-001",
            "raw_title": "Discussion on Water Fluoridation",
            "full_text": "The city council discussed water fluoridation and its benefits.",
            "agenda_items": [],
            "discussion_sections": []
        }
        
        # This would be async in real usage
        # result = await classifier._classify_document(doc)
        
        # For now, just test that the method exists
        assert hasattr(classifier, '_classify_document')
        assert hasattr(classifier, 'topic_keywords')
        assert PolicyTopic.WATER_FLUORIDATION in classifier.topic_keywords


class TestOrchestrator:
    """Test orchestrator agent."""
    
    def test_orchestrator_initialization(self):
        """Test orchestrator initialization."""
        orchestrator = OrchestratorAgent()
        assert orchestrator.role == AgentRole.ORCHESTRATOR
        assert len(orchestrator.agents) == 0
    
    def test_agent_registration(self):
        """Test agent registration."""
        orchestrator = OrchestratorAgent()
        scraper = ScraperAgent()
        
        orchestrator.register_agent(scraper)
        
        assert AgentRole.SCRAPER in orchestrator.agents
        assert orchestrator.agents[AgentRole.SCRAPER] == scraper


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
