"""
Parser Agent for extracting and structuring data from raw meeting minutes.
"""
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from agents.base import BaseAgent, AgentRole, AgentMessage, MessageType, AgentStatus


class ParserAgent(BaseAgent):
    """
    Agent responsible for parsing raw meeting documents into structured data.
    
    Extracts:
    - Meeting metadata (date, type, location)
    - Attendees and participants
    - Agenda items
    - Discussion topics
    - Votes and decisions
    - Action items
    """
    
    def __init__(self, agent_id: str = "parser-001"):
        """Initialize the parser agent."""
        super().__init__(agent_id, AgentRole.PARSER)
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile regex patterns for parsing."""
        self.patterns = {
            "date": re.compile(
                r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}",
                re.IGNORECASE
            ),
            "time": re.compile(r"\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?"),
            "attendees": re.compile(r"(?:Present|Attending|Members Present):(.+?)(?:\n\n|\Z)", re.DOTALL | re.IGNORECASE),
            "motion": re.compile(r"(?:MOTION|Motion|MOVED)(.+?)(?:CARRIED|PASSED|FAILED|$)", re.DOTALL | re.IGNORECASE),
            "vote": re.compile(r"(?:Vote|VOTE):\s*(.+)", re.IGNORECASE),
            "agenda_item": re.compile(r"(?:Item|ITEM)\s+#?(\d+|[A-Z])[\.:]\s*(.+?)(?=\n(?:Item|ITEM)|$)", re.DOTALL | re.IGNORECASE)
        }
    
    async def process(self, message: AgentMessage) -> List[AgentMessage]:
        """
        Process parsing commands.
        
        Args:
            message: Message containing raw documents to parse
            
        Returns:
            List of messages with parsed data
        """
        self.update_status(AgentStatus.PROCESSING, "Parsing meeting documents")
        
        try:
            documents = message.payload.get("documents", [])
            
            parsed_documents = []
            
            for doc in documents:
                parsed = await self._parse_document(doc)
                if parsed:
                    parsed_documents.append(parsed)
            
            # Send parsed documents to classifier
            response = await self.send_message(
                AgentRole.CLASSIFIER,
                MessageType.DATA,
                {
                    "workflow_id": message.payload.get("workflow_id"),
                    "documents": parsed_documents,
                    "count": len(parsed_documents)
                }
            )
            
            self.log_success()
            logger.info(f"Parsed {len(parsed_documents)} documents")
            
            return [response]
            
        except Exception as e:
            self.log_failure(str(e))
            error_msg = await self.send_message(
                AgentRole.ORCHESTRATOR,
                MessageType.ERROR,
                {"error": str(e), "agent": self.agent_id}
            )
            return [error_msg]
    
    async def _parse_document(self, doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse a single meeting document.
        
        Args:
            doc: Raw document data
            
        Returns:
            Parsed document with structured fields
        """
        try:
            content = doc.get("content", "")
            
            parsed = {
                "document_id": doc["document_id"],
                "source_url": doc["source_url"],
                "municipality": doc["municipality"],
                "state": doc["state"],
                "raw_title": doc["title"],
                "parsed_at": datetime.utcnow().isoformat(),
                
                # Extracted structured data
                "meeting_date": self._extract_date(content, doc.get("meeting_date")),
                "meeting_time": self._extract_time(content),
                "meeting_type": doc.get("meeting_type", "Unknown"),
                "attendees": self._extract_attendees(content),
                "agenda_items": self._extract_agenda_items(content),
                "motions": self._extract_motions(content),
                "votes": self._extract_votes(content),
                "discussion_sections": self._extract_discussion_sections(content),
                
                # Full text for semantic search
                "full_text": content,
                
                # Metadata
                "metadata": doc.get("metadata", {})
            }
            
            return parsed
            
        except Exception as e:
            logger.error(f"Error parsing document {doc.get('document_id')}: {e}")
            return None
    
    def _extract_date(self, content: str, fallback_date: Optional[str]) -> str:
        """Extract meeting date from content."""
        match = self.patterns["date"].search(content)
        if match:
            return match.group(0)
        return fallback_date or datetime.utcnow().isoformat()
    
    def _extract_time(self, content: str) -> Optional[str]:
        """Extract meeting time from content."""
        match = self.patterns["time"].search(content)
        return match.group(0) if match else None
    
    def _extract_attendees(self, content: str) -> List[str]:
        """Extract list of meeting attendees."""
        match = self.patterns["attendees"].search(content)
        if match:
            attendees_text = match.group(1)
            # Split by comma or newline
            attendees = re.split(r'[,\n]', attendees_text)
            return [a.strip() for a in attendees if a.strip()]
        return []
    
    def _extract_agenda_items(self, content: str) -> List[Dict[str, str]]:
        """Extract agenda items from content."""
        items = []
        for match in self.patterns["agenda_item"].finditer(content):
            items.append({
                "number": match.group(1).strip(),
                "description": match.group(2).strip()
            })
        return items
    
    def _extract_motions(self, content: str) -> List[Dict[str, str]]:
        """Extract motions from content."""
        motions = []
        for match in self.patterns["motion"].finditer(content):
            motions.append({
                "text": match.group(1).strip(),
                "full_match": match.group(0).strip()
            })
        return motions
    
    def _extract_votes(self, content: str) -> List[Dict[str, str]]:
        """Extract voting records from content."""
        votes = []
        for match in self.patterns["vote"].finditer(content):
            votes.append({
                "result": match.group(1).strip()
            })
        return votes
    
    def _extract_discussion_sections(self, content: str) -> List[Dict[str, str]]:
        """Extract discussion sections from content."""
        # Split content into paragraphs
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        
        sections = []
        for i, para in enumerate(paragraphs):
            if len(para) > 100:  # Only substantial paragraphs
                sections.append({
                    "section_id": i,
                    "text": para
                })
        
        return sections
