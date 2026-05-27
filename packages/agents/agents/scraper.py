"""
Scraper agent for the multi-agent pipeline.

The historical scraper implementation is not in this tree; this module provides a
minimal ``ScraperAgent`` so ``api.main`` and ``main.py serve`` can import. Use
``scripts/discovery/`` and datasource loaders for production scraping.
"""
from __future__ import annotations

from typing import Any, Dict, List

from agents.base import (
    AgentMessage,
    AgentRole,
    AgentStatus,
    BaseAgent,
    MessageType,
)


class ScraperAgent(BaseAgent):
    def __init__(self, agent_id: str = "scraper-001"):
        super().__init__(agent_id, AgentRole.SCRAPER)

    async def __aenter__(self) -> ScraperAgent:
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def process(self, message: AgentMessage) -> List[AgentMessage]:
        self.update_status(AgentStatus.ERROR, "ScraperAgent stub — use scripts/discovery")
        return [
            await self.send_message(
                AgentRole.ORCHESTRATOR,
                MessageType.ERROR,
                {"error": "scraper_not_implemented"},
            )
        ]

    async def _scrape_targets(
        self, targets: List[Dict[str, Any]], ctx: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError(
            "ScraperAgent._scrape_targets is not implemented. "
            "Use scripts/discovery/ or platform-specific loaders."
        )

    async def scrape_social_sources(self, **kwargs: Any) -> List[Dict[str, Any]]:
        return []
