"""
Decision Analysis Agent for extracting structured decision-making context.

Captures:
- How decisions were framed
- Options evaluated
- Tradeoffs discussed
- Rationales provided
- Stakeholder positions
- Evidence cited
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from loguru import logger
import subprocess
import json as json_lib
import os

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from config.settings import settings


@dataclass
class PolicyDecision:
    """
    Structured representation of a policy decision with full context.
    """
    # Basic info
    decision_id: str
    decision_summary: str  # Brief description of what was decided
    outcome: str  # "approved", "rejected", "tabled", "amended"
    
    # Decision framing
    primary_frame: str  # e.g., "public health", "fiscal responsibility", "equity"
    competing_frames: List[str]  # Alternative ways the issue was framed
    framing_language: List[str]  # Key phrases that shaped the discussion
    
    # Options evaluated
    options_considered: List[Dict[str, str]]  # Each option with description
    chosen_option: str
    rejected_options: List[Dict[str, str]]  # With reasons why rejected
    
    # Tradeoffs & deliberation
    tradeoffs_discussed: List[Dict[str, str]]  # e.g., {"tradeoff": "cost vs benefit", "discussion": "..."}
    concerns_raised: List[Dict[str, str]]  # {"stakeholder": "...", "concern": "..."}
    counterarguments: List[str]  # Rebuttals to concerns
    
    # Rationale & justification
    primary_rationale: str  # Main reason for the decision
    supporting_rationales: List[str]  # Additional justifications
    evidence_cited: List[Dict[str, str]]  # {"type": "study/expert/data", "description": "..."}
    
    # Stakeholder analysis
    supporters: List[Dict[str, str]]  # {"name": "...", "role": "...", "argument": "..."}
    opponents: List[Dict[str, str]]
    undecided_or_conflicted: List[Dict[str, str]]
    
    # Vote details
    vote_result: Optional[str]  # "5-2", "unanimous", etc.
    voting_breakdown: List[Dict[str, str]]  # {"member": "...", "vote": "yes/no", "stated_reason": "..."}
    
    # Impact & implementation
    expected_impacts: List[Dict[str, str]]  # {"stakeholder_group": "...", "impact": "..."}
    implementation_timeline: Optional[str]
    cost_estimate: Optional[str]
    
    # Metadata
    meeting_date: datetime
    municipality: str
    state: str
    document_id: str
    confidence_score: float  # 0-1: How confident are we in this analysis?


class DecisionAnalysisAgent:
    """
    Agent for deep analysis of policy decision-making processes.
    
    Uses LLM to extract structured decision context that helps understand:
    - WHY decisions were made (rationales)
    - HOW options were evaluated (deliberation process)
    - WHAT influenced the outcome (frames, evidence, stakeholders)
    
    Example:
        >>> agent = DecisionAnalysisAgent()
        >>> decisions = agent.analyze_document(meeting_doc)
        >>> for decision in decisions:
        >>>     print(f"Decision: {decision.decision_summary}")
        >>>     print(f"Framed as: {decision.primary_frame}")
        >>>     print(f"Rationale: {decision.primary_rationale}")
    """
    
    def __init__(self, use_local: bool = True, model: str = "llama3.3"):
        """
        Initialize the decision analysis agent.
        
        Args:
            use_local: Use local LLM via Ollama (default True for cost-effectiveness)
            model: Model to use (llama3.3, llama3.3:70b, llama3.3:8b, or OpenAI model if use_local=False)
        """
        self.use_local = use_local
        self.model = model
        
        if use_local:
            # Check if Ollama is available
            try:
                result = subprocess.run(['ollama', 'list'], capture_output=True, text=True)
                model_name = self.model.split(':')[0]
                if model_name not in result.stdout:
                    logger.warning(f"Model {self.model} not found. Install with: ollama pull {self.model}")
                    logger.info("Falling back to mock analysis for now")
                logger.info(f"Using local LLM: {self.model}")
            except FileNotFoundError:
                logger.error("Ollama not installed. Install from: https://ollama.ai")
                logger.info("Falling back to mock analysis")
            self.client = None
        else:
            # Use OpenAI API
            if not OPENAI_AVAILABLE:
                raise ImportError("OpenAI package not installed. Run: pip install openai")
            if not settings.openai_api_key:
                raise ValueError("OpenAI API key required. Set OPENAI_API_KEY environment variable.")
            self.client = OpenAI(api_key=settings.openai_api_key)
            if not model.startswith("gpt") and not model.startswith("o1"):
                self.model = "gpt-4o"  # Default to GPT-4o for OpenAI
        
    def analyze_document(
        self,
        document: Dict[str, Any],
        focus_topics: Optional[List[str]] = None
    ) -> List[PolicyDecision]:
        """
        Analyze a meeting document to extract structured decision-making context.
        
        Args:
            document: Meeting document with content
            focus_topics: Optional list of topics to focus on (e.g., ["health", "water"])
            
        Returns:
            List of PolicyDecision objects with full decision context
        """
        content = document.get("content", "")
        if len(content) < 500:
            logger.warning(f"Document {document.get('document_id')} too short for decision analysis")
            return []
        
        logger.info(f"Analyzing decisions in: {document.get('title', 'Unknown')}")
        
        # Build analysis prompt
        prompt = self._build_analysis_prompt(document, focus_topics)
        
        try:
            if self.use_local:
                response_text = self._call_ollama(prompt)
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": self._get_system_prompt()
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.2,  # Low temperature for factual analysis
                    response_format={"type": "json_object"}  # Request JSON output
                )
                response_text = response.choices[0].message.content
            
            import json
            parsed = json.loads(response_text)
            
            # Convert to PolicyDecision objects
            decisions = []
            for decision_data in parsed.get("decisions", []):
                decision = self._create_policy_decision(
                    decision_data,
                    document
                )
                decisions.append(decision)
            
            logger.success(f"Extracted {len(decisions)} policy decisions with full context")
            return decisions
            
        except Exception as e:
            logger.error(f"Error analyzing decisions: {e}")
            return []
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for decision analysis."""
        return """You are an expert policy analyst who extracts structured information about 
government decision-making processes. Your goal is to help citizens understand:

1. **How decisions are framed** - What lens or perspective shapes the discussion?
   (e.g., public health frame, fiscal responsibility frame, equity frame)

2. **What options were evaluated** - What alternatives were considered?
   Not just the final choice, but all options discussed.

3. **What tradeoffs were discussed** - What competing values or priorities were weighed?
   (e.g., short-term costs vs long-term benefits, individual choice vs collective good)

4. **What rationales justified the decision** - Why did decision-makers choose this option?
   Extract stated reasons, not just the outcome.

5. **What evidence influenced the decision** - What facts, studies, or expert testimony 
   were cited?

6. **Who supported/opposed** - What stakeholders took positions and what were their arguments?

You must be:
- **Precise**: Only extract what is explicitly stated in the document
- **Neutral**: Don't add interpretation or bias
- **Comprehensive**: Capture all aspects of the deliberation, not just the final vote
- **Structured**: Return well-organized JSON that can be easily analyzed

If the document doesn't contain decisions or deliberation, return an empty decisions array."""
    
    def _build_analysis_prompt(
        self,
        document: Dict[str, Any],
        focus_topics: Optional[List[str]] = None
    ) -> str:
        """Build the analysis prompt."""
        content = document.get("content", "")[:30000]  # Limit to ~7k tokens
        
        focus_instruction = ""
        if focus_topics:
            focus_instruction = f"\n**Focus especially on decisions related to: {', '.join(focus_topics)}**\n"
        
        prompt = f"""
Analyze this local government meeting document and extract ALL policy decisions with their full context.

**Meeting Information:**
- Municipality: {document.get('municipality', 'Unknown')}
- State: {document.get('state', '')}
- Date: {document.get('meeting_date', 'Unknown')}
- Title: {document.get('title', 'Unknown')}
{focus_instruction}

**Document Content:**
{content}

**Extract for each decision:**

Return a JSON object with this structure:

{{
  "decisions": [
    {{
      "decision_summary": "Brief description of what was decided",
      "outcome": "approved|rejected|tabled|amended",
      
      "framing": {{
        "primary_frame": "Main way the issue was framed (e.g., 'public health', 'fiscal responsibility')",
        "competing_frames": ["Alternative frames used"],
        "framing_language": ["Key phrases that shaped the discussion"]
      }},
      
      "options": {{
        "considered": [
          {{"option": "Description", "pros": ["..."], "cons": ["..."]}},
          ...
        ],
        "chosen": "Which option was selected",
        "rejected": [
          {{"option": "Description", "reason_rejected": "Why it was not chosen"}}
        ]
      }},
      
      "tradeoffs": [
        {{
          "tradeoff": "Cost vs. benefit",
          "discussion": "How this tradeoff was discussed"
        }}
      ],
      
      "concerns": [
        {{
          "stakeholder": "Who raised the concern",
          "concern": "What the concern was",
          "response": "How it was addressed (if mentioned)"
        }}
      ],
      
      "rationale": {{
        "primary": "Main reason for the decision",
        "supporting": ["Additional justifications"],
        "evidence": [
          {{
            "type": "study|expert|data|precedent",
            "description": "What evidence was cited"
          }}
        ]
      }},
      
      "stakeholders": {{
        "supporters": [
          {{
            "name": "Person/org name",
            "role": "Their position/affiliation",
            "argument": "Their main argument"
          }}
        ],
        "opponents": [...],
        "undecided": [...]
      }},
      
      "vote": {{
        "result": "5-2 or unanimous or voice vote",
        "breakdown": [
          {{
            "member": "Council member name",
            "vote": "yes|no|abstain",
            "stated_reason": "Any reason they gave (if mentioned)"
          }}
        ]
      }},
      
      "implementation": {{
        "expected_impacts": [
          {{
            "stakeholder_group": "Who will be affected",
            "impact": "How they'll be affected"
          }}
        ],
        "timeline": "When this will be implemented",
        "cost_estimate": "Estimated cost (if mentioned)"
      }},
      
      "confidence": 0.95
    }}
  ]
}}

**Important:**
- Only include decisions that are actually in the document
- Don't infer or assume - extract only what's explicitly stated
- If a field is not mentioned in the document, use null or empty array
- Multiple decisions should be in separate objects in the decisions array
- For confidence: 1.0 = explicit and clear, 0.5 = mentioned but unclear
"""
        return prompt.strip()
    
    def _call_ollama(self, prompt: str) -> str:
        """Call Ollama for local LLM inference."""
        try:
            # Combine system prompt and user prompt for Ollama
            full_prompt = self._get_system_prompt() + "\n\n" + prompt
            
            # Call Ollama
            result = subprocess.run(
                ['ollama', 'run', self.model, '--format', 'json'],
                input=full_prompt,
                capture_output=True,
                text=True,
                timeout=180  # 3 minute timeout
            )
            
            if result.returncode != 0:
                logger.error(f"Ollama error: {result.stderr}")
                return '{"decisions": []}'
            
            # Return the generated JSON
            output = result.stdout.strip()
            
            # Validate it's JSON
            try:
                json_lib.loads(output)
                return output
            except json_lib.JSONDecodeError:
                logger.error(f"Invalid JSON from Ollama: {output[:200]}")
                return '{"decisions": []}'
                
        except subprocess.TimeoutExpired:
            logger.error("Ollama request timed out")
            return '{"decisions": []}'
        except FileNotFoundError:
            logger.error("Ollama not found. Install from: https://ollama.ai")
            return '{"decisions": []}'
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return '{"decisions": []}'
    
    def _create_policy_decision(
        self,
        decision_data: Dict[str, Any],
        document: Dict[str, Any]
    ) -> PolicyDecision:
        """Convert parsed JSON to PolicyDecision object."""
        from hashlib import md5
        
        # Generate decision ID
        decision_id = md5(
            f"{document.get('document_id', '')}{decision_data.get('decision_summary', '')}".encode()
        ).hexdigest()[:16]
        
        framing = decision_data.get("framing", {})
        options = decision_data.get("options", {})
        rationale = decision_data.get("rationale", {})
        stakeholders = decision_data.get("stakeholders", {})
        vote = decision_data.get("vote", {})
        impl = decision_data.get("implementation", {})
        
        return PolicyDecision(
            decision_id=decision_id,
            decision_summary=decision_data.get("decision_summary", ""),
            outcome=decision_data.get("outcome", "unknown"),
            
            # Framing
            primary_frame=framing.get("primary_frame", ""),
            competing_frames=framing.get("competing_frames", []),
            framing_language=framing.get("framing_language", []),
            
            # Options
            options_considered=options.get("considered", []),
            chosen_option=options.get("chosen", ""),
            rejected_options=options.get("rejected", []),
            
            # Tradeoffs
            tradeoffs_discussed=decision_data.get("tradeoffs", []),
            concerns_raised=decision_data.get("concerns", []),
            counterarguments=[],  # Would need separate extraction
            
            # Rationale
            primary_rationale=rationale.get("primary", ""),
            supporting_rationales=rationale.get("supporting", []),
            evidence_cited=rationale.get("evidence", []),
            
            # Stakeholders
            supporters=stakeholders.get("supporters", []),
            opponents=stakeholders.get("opponents", []),
            undecided_or_conflicted=stakeholders.get("undecided", []),
            
            # Vote
            vote_result=vote.get("result"),
            voting_breakdown=vote.get("breakdown", []),
            
            # Implementation
            expected_impacts=impl.get("expected_impacts", []),
            implementation_timeline=impl.get("timeline"),
            cost_estimate=impl.get("cost_estimate"),
            
            # Metadata
            meeting_date=document.get("meeting_date", datetime.now()),
            municipality=document.get("municipality", ""),
            state=document.get("state", ""),
            document_id=document.get("document_id", ""),
            confidence_score=decision_data.get("confidence", 0.7)
        )
    
    def export_decision_analysis(
        self,
        decisions: List[PolicyDecision],
        output_format: str = "json"
    ) -> str:
        """
        Export decision analysis in various formats.
        
        Args:
            decisions: List of PolicyDecision objects
            output_format: "json", "markdown", or "csv"
            
        Returns:
            Formatted output string
        """
        if output_format == "json":
            import json
            return json.dumps(
                [self._decision_to_dict(d) for d in decisions],
                indent=2,
                default=str
            )
        
        elif output_format == "markdown":
            output = "# Policy Decision Analysis\n\n"
            for i, decision in enumerate(decisions, 1):
                output += f"## Decision {i}: {decision.decision_summary}\n\n"
                output += f"**Outcome:** {decision.outcome}\n\n"
                output += f"**Primary Frame:** {decision.primary_frame}\n\n"
                
                if decision.options_considered:
                    output += "**Options Considered:**\n"
                    for opt in decision.options_considered:
                        output += f"- {opt.get('option', 'Unknown')}\n"
                    output += "\n"
                
                if decision.tradeoffs_discussed:
                    output += "**Tradeoffs Discussed:**\n"
                    for tradeoff in decision.tradeoffs_discussed:
                        output += f"- {tradeoff.get('tradeoff', '')}: {tradeoff.get('discussion', '')}\n"
                    output += "\n"
                
                output += f"**Primary Rationale:** {decision.primary_rationale}\n\n"
                
                if decision.evidence_cited:
                    output += "**Evidence Cited:**\n"
                    for evidence in decision.evidence_cited:
                        output += f"- {evidence.get('type', '')}: {evidence.get('description', '')}\n"
                    output += "\n"
                
                output += "---\n\n"
            
            return output
        
        else:
            raise ValueError(f"Unsupported format: {output_format}")
    
    def _decision_to_dict(self, decision: PolicyDecision) -> Dict[str, Any]:
        """Convert PolicyDecision to dictionary."""
        return {
            "decision_id": decision.decision_id,
            "decision_summary": decision.decision_summary,
            "outcome": decision.outcome,
            "framing": {
                "primary_frame": decision.primary_frame,
                "competing_frames": decision.competing_frames,
                "framing_language": decision.framing_language
            },
            "options": {
                "considered": decision.options_considered,
                "chosen": decision.chosen_option,
                "rejected": decision.rejected_options
            },
            "tradeoffs": decision.tradeoffs_discussed,
            "concerns": decision.concerns_raised,
            "rationale": {
                "primary": decision.primary_rationale,
                "supporting": decision.supporting_rationales,
                "evidence": decision.evidence_cited
            },
            "stakeholders": {
                "supporters": decision.supporters,
                "opponents": decision.opponents,
                "undecided": decision.undecided_or_conflicted
            },
            "vote": {
                "result": decision.vote_result,
                "breakdown": decision.voting_breakdown
            },
            "implementation": {
                "expected_impacts": decision.expected_impacts,
                "timeline": decision.implementation_timeline,
                "cost_estimate": decision.cost_estimate
            },
            "metadata": {
                "meeting_date": decision.meeting_date.isoformat() if decision.meeting_date else None,
                "municipality": decision.municipality,
                "state": decision.state,
                "document_id": decision.document_id,
                "confidence_score": decision.confidence_score
            }
        }
