"""
Multi-Agent Orchestrator for coordinating the policy analysis pipeline.
"""
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from collections import defaultdict
from loguru import logger

from agents.base import (
    BaseAgent,
    AgentRole,
    AgentMessage,
    MessageType,
    AgentStatus
)


class WorkflowStage(str):
    """Workflow stage identifiers."""
    SCRAPE = "scrape"
    PARSE = "parse"
    CLASSIFY = "classify"
    ANALYZE = "analyze"
    GENERATE = "generate"


class OrchestratorAgent(BaseAgent):
    """
    Orchestrator agent that coordinates the multi-agent workflow.
    
    The orchestrator manages the flow of data through the pipeline:
    1. Scraper Agent -> Collects meeting minutes
    2. Parser Agent -> Extracts structured data
    3. Classifier Agent -> Identifies oral health topics
    4. Sentiment Agent -> Analyzes policy positions
    5. Advocacy Agent -> Generates outreach materials
    """
    
    def __init__(self, agent_id: str = "orchestrator-001"):
        """Initialize the orchestrator agent."""
        super().__init__(agent_id, AgentRole.ORCHESTRATOR)
        self.agents: Dict[AgentRole, BaseAgent] = {}
        self.workflow_state: Dict[str, Any] = defaultdict(dict)
        self.active_workflows: Dict[str, Dict[str, Any]] = {}
        
    def register_agent(self, agent: BaseAgent):
        """
        Register an agent with the orchestrator.
        
        Args:
            agent: The agent to register
        """
        self.agents[agent.role] = agent
        logger.info(f"Registered {agent.role.value} agent: {agent.agent_id}")
    
    async def process(self, message: AgentMessage) -> List[AgentMessage]:
        """
        Process orchestrator commands and route messages.
        
        Args:
            message: The incoming message
            
        Returns:
            List of response messages
        """
        self.update_status(AgentStatus.PROCESSING, "Processing orchestrator command")
        
        try:
            if message.message_type == MessageType.COMMAND:
                command = message.payload.get("command")
                
                if command == "start_workflow":
                    return await self._start_workflow(message.payload)
                elif command == "check_status":
                    return await self._check_workflow_status(message.payload)
                elif command == "stop_workflow":
                    return await self._stop_workflow(message.payload)
            
            self.log_success()
            return []
            
        except Exception as e:
            self.log_failure(str(e))
            return [await self.send_message(
                message.sender,
                MessageType.ERROR,
                {"error": str(e)}
            )]
    
    async def _start_workflow(self, payload: Dict[str, Any]) -> List[AgentMessage]:
        """
        Start a new policy analysis workflow.
        
        Args:
            payload: Workflow configuration
            
        Returns:
            List of messages to initiate the workflow
        """
        import uuid
        
        workflow_id = str(uuid.uuid4())
        workflow_config = payload.get("config", {})
        
        # Initialize workflow state
        self.active_workflows[workflow_id] = {
            "id": workflow_id,
            "started_at": datetime.utcnow(),
            "stage": WorkflowStage.SCRAPE,
            "config": workflow_config,
            "status": "running"
        }
        
        logger.info(f"Starting workflow {workflow_id}")
        
        # Create initial scraping task
        scraper_message = await self.send_message(
            AgentRole.SCRAPER,
            MessageType.COMMAND,
            {
                "workflow_id": workflow_id,
                "command": "scrape",
                "targets": workflow_config.get("scrape_targets", []),
                "date_range": workflow_config.get("date_range", {})
            }
        )
        
        return [scraper_message]
    
    async def _check_workflow_status(self, payload: Dict[str, Any]) -> List[AgentMessage]:
        """
        Check the status of active workflows.
        
        Args:
            payload: Status check request
            
        Returns:
            List containing status response
        """
        workflow_id = payload.get("workflow_id")
        
        if workflow_id and workflow_id in self.active_workflows:
            workflow = self.active_workflows[workflow_id]
            status_payload = {
                "workflow_id": workflow_id,
                "status": workflow.get("status"),
                "stage": workflow.get("stage"),
                "started_at": workflow.get("started_at").isoformat()
            }
        else:
            # Return status of all workflows
            status_payload = {
                "active_workflows": len(self.active_workflows),
                "workflows": [
                    {
                        "id": wf_id,
                        "status": wf["status"],
                        "stage": wf["stage"]
                    }
                    for wf_id, wf in self.active_workflows.items()
                ]
            }
        
        response = await self.send_message(
            AgentRole.ORCHESTRATOR,
            MessageType.RESPONSE,
            status_payload
        )
        
        return [response]
    
    async def _stop_workflow(self, payload: Dict[str, Any]) -> List[AgentMessage]:
        """
        Stop a running workflow.
        
        Args:
            payload: Stop request with workflow_id
            
        Returns:
            List containing confirmation message
        """
        workflow_id = payload.get("workflow_id")
        
        if workflow_id in self.active_workflows:
            self.active_workflows[workflow_id]["status"] = "stopped"
            logger.info(f"Stopped workflow {workflow_id}")
            
            response = await self.send_message(
                AgentRole.ORCHESTRATOR,
                MessageType.RESPONSE,
                {"workflow_id": workflow_id, "status": "stopped"}
            )
        else:
            response = await self.send_message(
                AgentRole.ORCHESTRATOR,
                MessageType.ERROR,
                {"error": f"Workflow {workflow_id} not found"}
            )
        
        return [response]
    
    async def route_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """
        Route a message to the appropriate agent.
        
        Args:
            message: The message to route
            
        Returns:
            Response from the target agent
        """
        target_agent = self.agents.get(message.recipient)
        
        if not target_agent:
            logger.error(f"No agent found for role: {message.recipient}")
            return None
        
        try:
            response = await target_agent.process(message)
            return response
        except Exception as e:
            logger.error(f"Error routing message to {message.recipient}: {e}")
            return None
    
    async def execute_pipeline(
        self,
        scrape_targets: List[Dict[str, Any]],
        date_range: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Execute the complete policy analysis pipeline.
        
        Args:
            scrape_targets: List of government entities to scrape
            date_range: Optional date range for historical data
            
        Returns:
            Dictionary containing pipeline results
        """
        workflow_config = {
            "scrape_targets": scrape_targets,
            "date_range": date_range or {}
        }
        
        # Start the workflow
        start_message = await self.send_message(
            AgentRole.ORCHESTRATOR,
            MessageType.COMMAND,
            {
                "command": "start_workflow",
                "config": workflow_config
            }
        )
        
        results = await self.process(start_message)
        
        return {
            "success": True,
            "workflow_initiated": True,
            "messages": [msg.dict() for msg in results]
        }
    
    def get_all_agent_states(self) -> Dict[str, Any]:
        """Get the current state of all registered agents."""
        return {
            role.value: agent.get_state().dict()
            for role, agent in self.agents.items()
        }
