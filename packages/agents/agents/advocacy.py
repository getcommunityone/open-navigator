"""
Advocacy Writer Agent for generating personalized outreach materials.
"""
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from agents.base import BaseAgent, AgentRole, AgentMessage, MessageType, AgentStatus


class AdvocacyWriterAgent(BaseAgent):
    """
    Agent responsible for generating advocacy materials.
    
    Creates:
    - Personalized emails to local officials
    - Talking points for public testimony
    - Social media content
    - Policy briefs
    - Community outreach materials
    """
    
    def __init__(self, agent_id: str = "advocacy-001"):
        """Initialize the advocacy writer agent."""
        super().__init__(agent_id, AgentRole.ADVOCACY_WRITER)
        self._initialize_templates()
    
    def _initialize_templates(self):
        """Initialize email and content templates."""
        self.email_templates = {
            "critical_vote": {
                "subject": "Urgent: Support Oral Health Policy - Vote Upcoming in {municipality}",
                "opening": (
                    "I am writing to urge your support for the upcoming vote on "
                    "{policy_topic} in {municipality}."
                ),
                "urgency": "This matter requires immediate attention as a vote is scheduled for {meeting_date}."
            },
            "introduce_topic": {
                "subject": "Opportunity to Improve Community Oral Health in {municipality}",
                "opening": (
                    "I am writing to bring to your attention an important opportunity "
                    "to enhance oral health services in {municipality}."
                ),
                "urgency": None
            },
            "address_opposition": {
                "subject": "Addressing Concerns About {policy_topic} in {municipality}",
                "opening": (
                    "I understand there are concerns about {policy_topic}. "
                    "I would like to share evidence-based information that may help inform the discussion."
                ),
                "urgency": None
            },
            "support_existing": {
                "subject": "Thank You for Supporting Oral Health in {municipality}",
                "opening": (
                    "Thank you for your support of {policy_topic}. "
                    "I am writing to express my appreciation and offer additional support."
                ),
                "urgency": None
            }
        }
        
        self.policy_benefits = {
            "water_fluoridation": [
                "Reduces tooth decay by 25% in children and adults",
                "Costs approximately $1 per person per year",
                "Recognized by CDC as one of 10 great public health achievements",
                "Reduces dental treatment costs by $38 per $1 invested",
                "Particularly benefits low-income families with limited access to dental care"
            ],
            "school_dental_screening": [
                "Early detection prevents costly emergency dental procedures",
                "Identifies children who need care before problems become severe",
                "Reduces school absences due to dental pain",
                "Connects families to dental resources and services",
                "Supported by American Academy of Pediatrics"
            ],
            "medicaid_dental": [
                "Improves health outcomes for vulnerable populations",
                "Reduces emergency room visits for dental problems",
                "Prevents progression of oral disease to systemic health issues",
                "Supports working families and children",
                "Generates economic returns through improved productivity"
            ],
            "dental_clinic_funding": [
                "Provides essential services to underserved communities",
                "Reduces health disparities",
                "Creates local jobs and economic activity",
                "Prevents costly emergency care",
                "Serves as safety net for uninsured and underinsured residents"
            ]
        }
    
    async def process(self, message: AgentMessage) -> List[AgentMessage]:
        """
        Process advocacy generation commands.
        
        Args:
            message: Message containing analyzed documents and opportunities
            
        Returns:
            List of messages with generated advocacy materials
        """
        self.update_status(AgentStatus.PROCESSING, "Generating advocacy materials")
        
        try:
            documents = message.payload.get("documents", [])
            opportunities = message.payload.get("opportunities", [])
            
            # Generate advocacy materials for each opportunity
            advocacy_materials = []
            
            for opp in opportunities:
                materials = await self._generate_advocacy_materials(opp, documents)
                advocacy_materials.append(materials)
            
            # Send results back to orchestrator
            response = await self.send_message(
                AgentRole.ORCHESTRATOR,
                MessageType.RESPONSE,
                {
                    "workflow_id": message.payload.get("workflow_id"),
                    "advocacy_materials": advocacy_materials,
                    "opportunities_count": len(opportunities),
                    "materials_generated": len(advocacy_materials)
                }
            )
            
            self.log_success()
            logger.info(f"Generated advocacy materials for {len(opportunities)} opportunities")
            
            return [response]
            
        except Exception as e:
            self.log_failure(str(e))
            error_msg = await self.send_message(
                AgentRole.ORCHESTRATOR,
                MessageType.ERROR,
                {"error": str(e), "agent": self.agent_id}
            )
            return [error_msg]
    
    async def _generate_advocacy_materials(
        self,
        opportunity: Dict[str, Any],
        all_documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate complete advocacy materials for an opportunity.
        
        Args:
            opportunity: Advocacy opportunity details
            all_documents: All analyzed documents for context
            
        Returns:
            Dictionary containing all generated materials
        """
        # Find the source document
        doc = next(
            (d for d in all_documents if d["document_id"] == opportunity["document_id"]),
            None
        )
        
        if not doc:
            logger.error(f"Document not found: {opportunity['document_id']}")
            return {}
        
        # Determine template based on situation
        template_type = self._select_template(opportunity)
        
        # Generate email
        email = await self._generate_email(opportunity, doc, template_type)
        
        # Generate talking points
        talking_points = self._generate_talking_points(opportunity, doc)
        
        # Generate social media content
        social_media = self._generate_social_media(opportunity)
        
        # Generate policy brief
        policy_brief = self._generate_policy_brief(opportunity, doc)
        
        materials = {
            "opportunity_id": opportunity["document_id"],
            "municipality": opportunity["municipality"],
            "state": opportunity["state"],
            "topic": opportunity["topic"],
            "urgency": opportunity["urgency"],
            "materials": {
                "email": email,
                "talking_points": talking_points,
                "social_media": social_media,
                "policy_brief": policy_brief
            },
            "generated_at": datetime.utcnow().isoformat(),
            "metadata": {
                "source_url": opportunity["source_url"],
                "meeting_date": opportunity["meeting_date"]
            }
        }
        
        return materials
    
    def _select_template(self, opportunity: Dict[str, Any]) -> str:
        """Select appropriate email template based on situation."""
        urgency = opportunity.get("urgency")
        stance = opportunity.get("stance")
        
        if urgency == "critical":
            return "critical_vote"
        elif stance in ["opposed", "strongly_opposed"]:
            return "address_opposition"
        elif stance in ["supportive", "strongly_supportive"]:
            return "support_existing"
        else:
            return "introduce_topic"
    
    async def _generate_email(
        self,
        opportunity: Dict[str, Any],
        doc: Dict[str, Any],
        template_type: str
    ) -> Dict[str, Any]:
        """Generate personalized email content."""
        template = self.email_templates[template_type]
        
        # Format template variables
        variables = {
            "municipality": opportunity["municipality"],
            "policy_topic": self._format_topic_name(opportunity["topic"]),
            "meeting_date": opportunity["meeting_date"]
        }
        
        subject = template["subject"].format(**variables)
        opening = template["opening"].format(**variables)
        
        # Build email body
        body_parts = [opening]
        
        # Add urgency if applicable
        if template["urgency"]:
            body_parts.append("\n\n" + template["urgency"].format(**variables))
        
        # Add policy benefits
        body_parts.append("\n\n**Key Benefits:**")
        benefits = self.policy_benefits.get(
            opportunity["topic"],
            ["Improves community health outcomes"]
        )
        for benefit in benefits[:3]:  # Top 3 benefits
            body_parts.append(f"• {benefit}")
        
        # Add call to action
        body_parts.append(self._generate_call_to_action(opportunity))
        
        # Add closing
        body_parts.append(
            "\n\nThank you for your time and consideration. "
            "I would welcome the opportunity to discuss this further."
        )
        body_parts.append("\n\nSincerely,")
        body_parts.append("[Your Name]")
        body_parts.append("[Your Organization]")
        
        email = {
            "subject": subject,
            "body": "\n".join(body_parts),
            "template_type": template_type,
            "personalization_variables": variables
        }
        
        return email
    
    def _generate_call_to_action(self, opportunity: Dict[str, Any]) -> str:
        """Generate appropriate call to action based on urgency."""
        urgency = opportunity.get("urgency")
        stance = opportunity.get("stance")
        
        if urgency == "critical":
            return (
                "\n\n**Action Needed:**\n"
                f"Please vote in favor of this important measure at the upcoming meeting. "
                f"Your constituents' oral health depends on this decision."
            )
        elif stance in ["opposed", "strongly_opposed"]:
            return (
                "\n\n**Requested Action:**\n"
                "I respectfully request a meeting to discuss the evidence supporting this policy "
                "and address any concerns you may have."
            )
        else:
            return (
                "\n\n**Requested Action:**\n"
                "I encourage you to support this initiative and would be happy to provide "
                "additional information or connect you with subject matter experts."
            )
    
    def _generate_talking_points(
        self,
        opportunity: Dict[str, Any],
        doc: Dict[str, Any]
    ) -> List[str]:
        """Generate talking points for public testimony or meetings."""
        topic = opportunity["topic"]
        
        talking_points = [
            f"Introduction: Community member concerned about oral health in {opportunity['municipality']}"
        ]
        
        # Add topic-specific points
        benefits = self.policy_benefits.get(topic, [])
        for i, benefit in enumerate(benefits[:5], 1):
            talking_points.append(f"Point {i}: {benefit}")
        
        # Add local context
        talking_points.append(
            f"Local relevance: This policy addresses needs identified in "
            f"recent community discussions"
        )
        
        # Add closing point
        talking_points.append(
            "Closing: Urge decision-makers to prioritize community oral health"
        )
        
        return talking_points
    
    def _generate_social_media(
        self,
        opportunity: Dict[str, Any]
    ) -> Dict[str, str]:
        """Generate social media content."""
        municipality = opportunity["municipality"]
        topic = self._format_topic_name(opportunity["topic"])
        
        twitter = (
            f"🦷 {municipality} is considering {topic}! "
            f"This could improve oral health for thousands. "
            f"Contact your local officials to show support. "
            f"#OralHealth #PublicHealth"
        )
        
        facebook = (
            f"Important news for {municipality} residents!\n\n"
            f"Our local government is discussing {topic}. "
            f"This policy could significantly improve access to dental care "
            f"for families in our community.\n\n"
            f"Learn more and contact your representatives to voice your support: "
            f"{opportunity.get('source_url', '')}"
        )
        
        return {
            "twitter": twitter,
            "facebook": facebook,
            "instagram": twitter,  # Similar to Twitter
            "hashtags": ["OralHealth", "PublicHealth", municipality.replace(" ", "")]
        }
    
    def _generate_policy_brief(
        self,
        opportunity: Dict[str, Any],
        doc: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate a concise policy brief."""
        topic = opportunity["topic"]
        
        brief = {
            "title": f"Policy Brief: {self._format_topic_name(topic)} in {opportunity['municipality']}",
            "summary": (
                f"This brief outlines the benefits and implementation considerations "
                f"for {self._format_topic_name(topic)}."
            ),
            "background": (
                f"Current discussion in {opportunity['municipality']} presents "
                f"an opportunity to improve community oral health."
            ),
            "key_benefits": self.policy_benefits.get(topic, []),
            "recommendations": [
                "Approve the proposed policy",
                "Allocate necessary funding",
                "Establish implementation timeline",
                "Monitor outcomes and adjust as needed"
            ],
            "evidence_sources": [
                "Centers for Disease Control and Prevention",
                "American Dental Association",
                "Community Preventive Services Task Force"
            ]
        }
        
        return brief
    
    def _format_topic_name(self, topic: str) -> str:
        """Format topic identifier into readable name."""
        topic_names = {
            "water_fluoridation": "community water fluoridation",
            "school_dental_screening": "school-based dental screening",
            "medicaid_dental": "Medicaid dental coverage expansion",
            "dental_clinic_funding": "community dental clinic funding",
            "community_dental_program": "community dental programs",
            "children_dental_health": "children's dental health initiatives",
            "dental_care_access": "dental care access improvements"
        }
        
        return topic_names.get(topic, topic.replace("_", " "))
