"""
MLflow-based agent foundation for Databricks Agent Bricks.

Provides:
- MLflow Pyfunc model wrappers for agents
- Unity Catalog integration
- Automatic tracing and observability
- Model serving compatibility
"""
from typing import Any, Dict, List, Optional, Union
from abc import ABC, abstractmethod
import mlflow
from mlflow.pyfunc import PythonModel
from mlflow.models import infer_signature
from mlflow.tracking import MlflowClient
import pandas as pd
from datetime import datetime
from loguru import logger

from agents.base import AgentRole, AgentMessage, AgentStatus
from config import settings


class MLflowAgentBase(PythonModel, ABC):
    """
    Base class for agents that can be deployed via MLflow Model Serving.
    
    Integrates with:
    - Unity Catalog for governance
    - MLflow Tracking for experimentation
    - Databricks Model Serving for deployment
    - Mosaic AI Agent Framework for evaluation
    """
    
    def __init__(self, agent_id: str, role: AgentRole):
        """
        Initialize MLflow agent.
        
        Args:
            agent_id: Unique identifier for this agent
            role: Agent role in the pipeline
        """
        super().__init__()
        self.agent_id = agent_id
        self.role = role
        self.status = AgentStatus.IDLE
        self.client = MlflowClient()
        
    def load_context(self, context):
        """
        Load agent context from MLflow (called during model loading).
        
        Args:
            context: MLflow context with model artifacts
        """
        logger.info(f"Loading {self.role.value} agent from MLflow context")
        # Load any model artifacts, configs, etc.
        pass
    
    @abstractmethod
    def _process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single agent request.
        
        Args:
            request: Input request dictionary
            
        Returns:
            Response dictionary
        """
        pass
    
    def predict(
        self, 
        context, 
        model_input: Union[pd.DataFrame, Dict[str, Any], List[Dict[str, Any]]]
    ) -> Union[pd.DataFrame, List[Dict[str, Any]]]:
        """
        MLflow Pyfunc predict interface.
        
        This is the main entry point when the agent is deployed as a Model Serving endpoint.
        
        Args:
            context: MLflow context
            model_input: Input data (DataFrame, dict, or list of dicts)
            
        Returns:
            Predictions in same format as input
        """
        # Enable MLflow tracing for observability
        with mlflow.start_span(name=f"{self.role.value}_agent") as span:
            span.set_attribute("agent_id", self.agent_id)
            span.set_attribute("agent_role", self.role.value)
            
            try:
                # Convert input to standard format
                if isinstance(model_input, pd.DataFrame):
                    requests = model_input.to_dict('records')
                    return_df = True
                elif isinstance(model_input, dict):
                    requests = [model_input]
                    return_df = False
                else:
                    requests = model_input
                    return_df = False
                
                # Process each request with tracing
                results = []
                for idx, request in enumerate(requests):
                    with mlflow.start_span(name=f"process_request_{idx}") as req_span:
                        req_span.set_attribute("request_id", request.get("request_id", f"req_{idx}"))
                        
                        try:
                            result = self._process_request(request)
                            result["status"] = "success"
                            result["agent_id"] = self.agent_id
                            result["timestamp"] = datetime.utcnow().isoformat()
                            results.append(result)
                            
                            req_span.set_attribute("status", "success")
                            
                        except Exception as e:
                            error_result = {
                                "status": "error",
                                "error": str(e),
                                "agent_id": self.agent_id,
                                "timestamp": datetime.utcnow().isoformat()
                            }
                            results.append(error_result)
                            
                            req_span.set_attribute("status", "error")
                            req_span.set_attribute("error", str(e))
                            logger.error(f"Error processing request {idx}: {e}")
                
                # Return in requested format
                if return_df:
                    return pd.DataFrame(results)
                elif len(results) == 1 and not isinstance(model_input, list):
                    return results[0]
                else:
                    return results
                    
            except Exception as e:
                span.set_attribute("status", "error")
                span.set_attribute("error", str(e))
                logger.error(f"Error in {self.role.value} agent: {e}")
                raise
    
    def log_to_mlflow(
        self, 
        model_name: str,
        artifact_path: str = "agent",
        registered_model_name: Optional[str] = None,
        **kwargs
    ):
        """
        Log this agent to MLflow.
        
        Args:
            model_name: Name for the MLflow run
            artifact_path: Path within the run to store the model
            registered_model_name: Unity Catalog model name (e.g., "main.agents.scraper")
            **kwargs: Additional MLflow logging parameters
        """
        with mlflow.start_run(run_name=model_name) as run:
            # Log agent metadata
            mlflow.log_param("agent_id", self.agent_id)
            mlflow.log_param("agent_role", self.role.value)
            mlflow.log_param("framework", "databricks-agent-bricks")
            
            # Create example input/output for signature
            example_input = self._get_example_input()
            example_output = self.predict(None, example_input)
            signature = infer_signature(example_input, example_output)
            
            # Log the model
            mlflow.pyfunc.log_model(
                artifact_path=artifact_path,
                python_model=self,
                signature=signature,
                registered_model_name=registered_model_name,
                **kwargs
            )
            
            logger.info(f"Logged {self.role.value} agent to MLflow run {run.info.run_id}")
            
            if registered_model_name:
                logger.info(f"Registered model as {registered_model_name}")
                
            return run.info.run_id
    
    @abstractmethod
    def _get_example_input(self) -> Union[pd.DataFrame, Dict[str, Any]]:
        """
        Get example input for MLflow signature inference.
        
        Returns:
            Example input data
        """
        pass
    
    def deploy_to_model_serving(
        self,
        model_name: str,
        endpoint_name: str,
        workload_size: str = "Small",
        scale_to_zero: bool = True
    ) -> str:
        """
        Deploy this agent to Databricks Model Serving.
        
        Args:
            model_name: Registered model name in Unity Catalog
            endpoint_name: Name for the serving endpoint
            workload_size: Endpoint size (Small, Medium, Large)
            scale_to_zero: Whether to scale to zero when idle
            
        Returns:
            Endpoint URL
        """
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.service.serving import ServedEntityInput, EndpointCoreConfigInput
        
        w = WorkspaceClient(
            host=settings.databricks_host,
            token=settings.databricks_token
        )
        
        # Get latest model version
        latest_version = self.client.get_latest_versions(model_name, stages=["None"])[0].version
        
        # Create or update endpoint
        endpoint_config = EndpointCoreConfigInput(
            name=endpoint_name,
            served_entities=[
                ServedEntityInput(
                    entity_name=model_name,
                    entity_version=latest_version,
                    workload_size=workload_size,
                    scale_to_zero_enabled=scale_to_zero
                )
            ]
        )
        
        try:
            endpoint = w.serving_endpoints.create_and_wait(
                name=endpoint_name,
                config=endpoint_config
            )
            logger.info(f"Created endpoint: {endpoint_name}")
        except Exception as e:
            if "already exists" in str(e):
                endpoint = w.serving_endpoints.update_config_and_wait(
                    name=endpoint_name,
                    served_entities=endpoint_config.served_entities
                )
                logger.info(f"Updated endpoint: {endpoint_name}")
            else:
                raise
        
        endpoint_url = f"{settings.databricks_host}/serving-endpoints/{endpoint_name}/invocations"
        return endpoint_url


class MLflowChainAgent(MLflowAgentBase):
    """
    Agent that uses LangChain with MLflow tracing.
    
    Provides integration with:
    - LangChain agents and chains
    - Automatic prompt logging
    - LLM call tracing
    - Tool usage tracking
    """
    
    def __init__(self, agent_id: str, role: AgentRole):
        """Initialize LangChain-based agent."""
        super().__init__(agent_id, role)
        self.chain = None
        
    def _setup_langchain_tracing(self):
        """Enable MLflow tracing for LangChain."""
        mlflow.langchain.autolog()
        
    @abstractmethod
    def _build_chain(self):
        """
        Build the LangChain chain for this agent.
        
        Returns:
            LangChain chain or agent
        """
        pass
    
    def _process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process request through LangChain."""
        if self.chain is None:
            self.chain = self._build_chain()
            
        with mlflow.start_span(name="langchain_invoke") as span:
            result = self.chain.invoke(request)
            
            # Log relevant metrics
            if hasattr(result, "llm_output"):
                span.set_attribute("tokens_used", result.llm_output.get("token_usage", {}).get("total_tokens", 0))
            
            return result
