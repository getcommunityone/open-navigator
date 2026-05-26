"""
Core agent base classes and protocols for the multi-agent system.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from datetime import UTC, datetime
from enum import Enum
from pydantic import BaseModel, Field
from loguru import logger


class AgentRole(str, Enum):
    """Enumeration of agent roles in the system."""
    SCRAPER = "scraper"
    PARSER = "parser"
    CLASSIFIER = "classifier"
    SENTIMENT_ANALYZER = "sentiment_analyzer"
    DEBATE_GRADER = "debate_grader"
    ADVOCACY_WRITER = "advocacy_writer"
    ORCHESTRATOR = "orchestrator"


class MessageType(str, Enum):
    """Types of messages exchanged between agents."""
    DATA = "data"
    COMMAND = "command"
    QUERY = "query"
    RESPONSE = "response"
    ERROR = "error"
    STATUS = "status"


class AgentMessage(BaseModel):
    """Message structure for inter-agent communication."""
    message_id: str = Field(..., description="Unique message identifier")
    sender: AgentRole = Field(..., description="Sending agent role")
    recipient: AgentRole = Field(..., description="Receiving agent role")
    message_type: MessageType = Field(..., description="Type of message")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: Dict[str, Any] = Field(default_factory=dict, description="Message payload")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class AgentStatus(str, Enum):
    """Agent operational status."""
    IDLE = "idle"
    PROCESSING = "processing"
    WAITING = "waiting"
    ERROR = "error"
    COMPLETED = "completed"


class AgentState(BaseModel):
    """Current state of an agent."""
    agent_id: str
    role: AgentRole
    status: AgentStatus = AgentStatus.IDLE
    current_task: Optional[str] = None
    tasks_completed: int = 0
    tasks_failed: int = 0
    last_activity: datetime = Field(default_factory=lambda: datetime.now(UTC))
    error_message: Optional[str] = None


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the system.
    
    Each agent must implement the process method to handle incoming messages
    and perform its specific role in the pipeline.
    """
    
    def __init__(self, agent_id: str, role: AgentRole):
        """
        Initialize the base agent.
        
        Args:
            agent_id: Unique identifier for this agent instance
            role: The role this agent plays in the system
        """
        self.agent_id = agent_id
        self.role = role
        self.state = AgentState(agent_id=agent_id, role=role)
        self.message_queue: List[AgentMessage] = []
        logger.info(f"Initialized {role.value} agent: {agent_id}")
    
    @abstractmethod
    async def process(self, message: AgentMessage) -> Union[AgentMessage, List[AgentMessage]]:
        """
        Process an incoming message and return response(s).
        
        Args:
            message: The message to process
            
        Returns:
            One or more response messages
        """
        pass
    
    def update_status(self, status: AgentStatus, task: Optional[str] = None):
        """Update the agent's current status."""
        self.state.status = status
        self.state.current_task = task
        self.state.last_activity = datetime.now(UTC)
        logger.debug(f"{self.role.value} agent {self.agent_id} status: {status.value}")
    
    def log_success(self):
        """Log a successful task completion."""
        self.state.tasks_completed += 1
        self.update_status(AgentStatus.IDLE)
    
    def log_failure(self, error: str):
        """Log a task failure."""
        self.state.tasks_failed += 1
        self.state.error_message = error
        self.update_status(AgentStatus.ERROR)
        logger.error(f"{self.role.value} agent {self.agent_id} error: {error}")
    
    async def send_message(
        self,
        recipient: AgentRole,
        message_type: MessageType,
        payload: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> AgentMessage:
        """
        Create and send a message to another agent.
        
        Args:
            recipient: The receiving agent's role
            message_type: Type of message to send
            payload: Message content
            metadata: Optional metadata
            
        Returns:
            The created message
        """
        import uuid
        
        message = AgentMessage(
            message_id=str(uuid.uuid4()),
            sender=self.role,
            recipient=recipient,
            message_type=message_type,
            payload=payload,
            metadata=metadata or {}
        )
        
        return message
    
    def get_state(self) -> AgentState:
        """Get the current state of the agent."""
        return self.state


class AgentMetrics(BaseModel):
    """Metrics for monitoring agent performance."""
    agent_id: str
    role: AgentRole
    total_messages_processed: int = 0
    total_processing_time_seconds: float = 0.0
    average_processing_time_seconds: float = 0.0
    success_rate: float = 0.0
    error_count: int = 0
    last_error: Optional[str] = None
    uptime_seconds: float = 0.0
