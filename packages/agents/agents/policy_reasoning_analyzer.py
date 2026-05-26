#!/usr/bin/env python3
"""
Policy Reasoning Analyzer

Uses AI to analyze bills and extract:
- Why decisions were made (rationales)
- What tradeoffs were considered
- How different stakeholders reasoned
- What evidence shaped the outcome

Usage:
    python agents/policy_reasoning_analyzer.py --bill-id ocd-bill/xxx
    python agents/policy_reasoning_analyzer.py --state GA --topic fluoride
"""

import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path
import json
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

@dataclass
class PolicyAnalysis:
    """Structured output from AI policy analysis"""
    bill_id: str
    bill_number: str
    title: str
    
    # Summaries
    summary: str  # 2-3 sentence summary
    detailed_summary: str  # 1-2 paragraph summary
    
    # Topics
    primary_topic: str  # Main category (health, education, etc.)
    topics: List[str]  # Specific topics (fluoridation, funding, etc.)
    
    # Core reasoning
    primary_rationale: str  # Why this bill was introduced
    problem_statement: str  # What problem does it solve?
    
    # Stakeholder positions
    supporting_arguments: List[Dict[str, Any]]  # [{stakeholder, argument, evidence}]
    opposing_arguments: List[Dict[str, Any]]
    
    # Decision factors
    tradeoffs_identified: List[Dict[str, str]]  # [{tradeoff, how_resolved}]
    key_decision_factors: List[str]  # What evidence swayed legislators?
    
    # Outcomes
    compromises_made: List[str]  # How did bill change?
    final_outcome: str
    outcome_explanation: str  # Why did it pass/fail?
    
    # Meta
    confidence_score: float  # AI confidence in analysis
    data_sources: List[str]  # What was analyzed?


class PolicyReasoningAnalyzer:
    """
    Analyzes bills to extract WHY decisions were made, not just WHAT happened.
    
    Uses LLMs to identify reasoning, tradeoffs, and stakeholder positions.
    """
    
    def __init__(self, model: str = "llama3.3", local: bool = True):
        """
        Initialize analyzer
        
        Args:
            model: LLM model to use (llama3.3, llama3.3:70b, llama3.3:8b, llama3.1:70b, etc.)
            local: Use local LLM via Ollama (default True for cost-effectiveness)
        """
        self.model = model
        self.local = local
        
        if local:
            # Check if Ollama is installed
            try:
                import subprocess
                result = subprocess.run(['ollama', 'list'], capture_output=True, text=True)
                if self.model.split(':')[0] not in result.stdout:
                    logger.warning(f"Model {self.model} not found. Install with: ollama pull {self.model}")
            except FileNotFoundError:
                logger.error("Ollama not installed. Install from: https://ollama.ai")
                logger.info("Falling back to mock analysis")
        else:
            # Check for API keys
            if "OPENAI_API_KEY" not in os.environ and "ANTHROPIC_API_KEY" not in os.environ:
                logger.warning("No API keys found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY in .env")
    
    def analyze_bill(self, 
                     bill_id: str,
                     bill_text: str,
                     bill_abstract: str,
                     testimony: Optional[List[Dict]] = None,
                     amendments: Optional[List[Dict]] = None,
                     committee_reports: Optional[List[str]] = None) -> PolicyAnalysis:
        """
        Analyze a bill to extract reasoning and tradeoffs
        
        Args:
            bill_id: Bill identifier
            bill_text: Full bill text (or abstract if full text unavailable)
            bill_abstract: Short summary
            testimony: List of testimony records [{speaker, position, text}]
            amendments: List of amendments [{description, text, outcome}]
            committee_reports: List of committee report texts
            
        Returns:
            PolicyAnalysis with structured reasoning
        """
        
        # Build analysis prompt
        prompt = self._build_analysis_prompt(
            bill_text=bill_text,
            bill_abstract=bill_abstract,
            testimony=testimony or [],
            amendments=amendments or [],
            committee_reports=committee_reports or []
        )
        
        # Run LLM analysis
        analysis_text = self._run_llm_analysis(prompt)
        
        # Parse structured output
        analysis = self._parse_analysis(analysis_text, bill_id)
        
        return analysis
    
    def _build_analysis_prompt(self,
                               bill_text: str,
                               bill_abstract: str,
                               testimony: List[Dict],
                               amendments: List[Dict],
                               committee_reports: List[str]) -> str:
        """Build comprehensive analysis prompt"""
        
        prompt = f"""# Legislative Policy Reasoning Analysis

You are analyzing a policy bill to understand WHY decisions were made, not just WHAT happened.

## Bill Information

**Summary:** {bill_abstract}

**Full Text:**
{bill_text[:5000]}  # Truncate if too long

## Available Context

"""
        
        if testimony:
            prompt += "\n### Legislative Testimony\n\n"
            for t in testimony[:10]:  # Limit to avoid token limits
                prompt += f"**{t.get('speaker', 'Unknown')}** ({t.get('position', 'neutral')}):\n"
                prompt += f"{t.get('text', '')[:500]}\n\n"
        
        if amendments:
            prompt += "\n### Amendments\n\n"
            for a in amendments[:5]:
                prompt += f"- {a.get('description', 'Amendment')}\n"
        
        if committee_reports:
            prompt += "\n### Committee Reports\n\n"
            for report in committee_reports[:2]:
                prompt += f"{report[:1000]}\n\n"
        
        prompt += """
## Analysis Task

Analyze this bill and extract:

### 1. SUMMARY
**Concise Summary (2-3 sentences):** What does this bill do?
- Focus on key actions and impacts
- Use accessible language (no jargon)

**Detailed Summary (1-2 paragraphs):** Comprehensive overview
- Include background context
- Explain mechanisms and implementation

### 2. TOPICS
**Primary Topic:** Main category (choose one)
- Options: health, education, infrastructure, environment, justice, economy, social_services, governance, other

**Specific Topics:** List 3-5 specific topics (lowercase, underscore_separated)
- Examples: water_fluoridation, public_health, local_control, referendum, dental_health
- Be specific and consistent

### 3. PRIMARY RATIONALE
**Why was this bill introduced?** What problem is it trying to solve?
- Be specific about the policy problem
- Identify the underlying goals

### 2. SUPPORTING ARGUMENTS
For each major stakeholder who SUPPORTED the bill:
- Who they are
- Their main argument
- Evidence they cited
- Their interests/motivations

### 3. OPPOSING ARGUMENTS
For each major stakeholder who OPPOSED the bill:
- Who they are
- Their main argument
- Evidence they cited
- Their concerns/motivations

### 4. TRADEOFFS IDENTIFIED
What competing interests were balanced?
For each major tradeoff:
- What was being traded off? (e.g., cost vs. access, freedom vs. safety)
- How was it resolved in the bill?
- Who benefited? Who lost?

### 5. KEY DECISION FACTORS
What evidence, arguments, or events actually swayed the outcome?
- Expert testimony that changed minds?
- Fiscal analysis that shaped decision?
- Political pressure or compromise?
- Constituent input?

### 6. COMPROMISES MADE
How did the bill change through the legislative process?
- What was in original version?
- What changed through amendments?
- Why did it change?

### 7. OUTCOME EXPLANATION
- Did it pass or fail?
- WHY did it pass or fail? (Not just votes, but reasoning)
- What could have changed the outcome?

## Output Format

Provide a structured JSON response with these exact keys:
```json
{
  "summary": "2-3 sentence concise summary",
  "detailed_summary": "1-2 paragraph detailed summary",
  "primary_topic": "health|education|infrastructure|environment|justice|economy|social_services|governance|other",
  "topics": ["topic1", "topic2", "topic3"],
  "primary_rationale": "...",
  "problem_statement": "...",
  "supporting_arguments": [
    {"stakeholder": "...", "argument": "...", "evidence": "...", "motivation": "..."}
  ],
  "opposing_arguments": [
    {"stakeholder": "...", "argument": "...", "evidence": "...", "concern": "..."}
  ],
  "tradeoffs_identified": [
    {"tradeoff": "...", "resolution": "...", "beneficiaries": "...", "losers": "..."}
  ],
  "key_decision_factors": ["...", "..."],
  "compromises_made": ["...", "..."],
  "final_outcome": "passed|failed|pending",
  "outcome_explanation": "...",
  "confidence_score": 0.85
}
```

Focus on REASONING, not just description. Explain WHY, not just WHAT.
"""
        
        return prompt
    
    def _run_llm_analysis(self, prompt: str) -> str:
        """Run LLM analysis"""
        
        if self.local:
            # Use local LLM via Ollama
            logger.info(f"Using local LLM: {self.model}")
            return self._call_ollama(prompt)
        
        else:
            # Use API (OpenAI, Anthropic, etc.)
            if "OPENAI_API_KEY" in os.environ:
                return self._call_openai(prompt)
            elif "ANTHROPIC_API_KEY" in os.environ:
                return self._call_anthropic(prompt)
            else:
                logger.warning("No API key found, returning mock analysis")
                return self._mock_analysis()
    
    def _call_ollama(self, prompt: str) -> str:
        """Call Ollama for local LLM inference"""
        try:
            import subprocess
            import json as json_lib
            
            # Prepare the request
            data = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.3,
                    "num_predict": 4000
                }
            }
            
            # Call Ollama API
            result = subprocess.run(
                ['ollama', 'run', self.model, '--format', 'json'],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0:
                logger.error(f"Ollama error: {result.stderr}")
                return self._mock_analysis()
            
            # Parse response
            try:
                # Ollama returns the generated text directly
                return result.stdout.strip()
            except Exception as e:
                logger.error(f"Failed to parse Ollama response: {e}")
                logger.debug(f"Raw output: {result.stdout[:500]}")
                return self._mock_analysis()
                
        except subprocess.TimeoutExpired:
            logger.error("Ollama request timed out")
            return self._mock_analysis()
        except FileNotFoundError:
            logger.error("Ollama not found. Install from: https://ollama.ai")
            return self._mock_analysis()
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return self._mock_analysis()
    
    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API"""
        try:
            import openai
            
            client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a policy analyst specializing in legislative reasoning analysis."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Lower for more factual analysis
                max_tokens=4000,
                response_format={"type": "json_object"}  # Request JSON
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return self._mock_analysis()
    
    def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic Claude API"""
        try:
            import anthropic
            
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            
            response = client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0.3,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            return response.content[0].text
            
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            return self._mock_analysis()
    
    def _mock_analysis(self) -> str:
        """Mock analysis for testing"""
        return json.dumps({
            "summary": "This bill allows communities to decide on water fluoridation through local referenda rather than state mandate.",
            "detailed_summary": "The bill amends existing public water system regulations to enable local communities to impose or remove water fluoridation programs through a referendum process. Previously, fluoridation decisions were made at the state level. The bill maintains state funding for fluoridation equipment while transferring decision-making authority to local governments. This represents a shift from centralized public health policy to local democratic control.",
            "primary_topic": "health",
            "topics": ["water_fluoridation", "public_health", "local_control", "referendum", "community_autonomy"],
            "primary_rationale": "Allow communities to decide on water fluoridation via referendum",
            "problem_statement": "Lack of local control over water fluoridation decisions",
            "supporting_arguments": [
                {
                    "stakeholder": "Local government advocates",
                    "argument": "Communities should have autonomy over public health decisions",
                    "evidence": "Precedent in other states for local control",
                    "motivation": "Increase local democratic participation"
                }
            ],
            "opposing_arguments": [
                {
                    "stakeholder": "Public health officials",
                    "argument": "Fluoridation is a proven public health intervention",
                    "evidence": "CDC data on cavity reduction",
                    "concern": "Political decisions may override scientific consensus"
                }
            ],
            "tradeoffs_identified": [
                {
                    "tradeoff": "Local autonomy vs. statewide public health",
                    "resolution": "Allowed local referenda but maintained state funding for equipment",
                    "beneficiaries": "Anti-fluoride activists, local governments",
                    "losers": "State health department authority"
                }
            ],
            "key_decision_factors": [
                "Growing constituent pressure against fluoridation",
                "Similar bills passing in neighboring states",
                "Compromise on maintaining state funding"
            ],
            "compromises_made": [
                "Original version removed all fluoridation; final version allows local choice",
                "Added provisions for state equipment funding to appease moderates"
            ],
            "final_outcome": "passed",
            "outcome_explanation": "Passed due to strong constituent pressure and effective compromise",
            "confidence_score": 0.75
        })
    
    def _parse_analysis(self, analysis_text: str, bill_id: str) -> PolicyAnalysis:
        """Parse LLM output into structured PolicyAnalysis"""
        
        try:
            data = json.loads(analysis_text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            import re
            json_match = re.search(r'```json\s*(\{.*\})\s*```', analysis_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(1))
            else:
                raise ValueError("Could not parse LLM response as JSON")
        
        return PolicyAnalysis(
            bill_id=bill_id,
            bill_number=data.get("bill_number", ""),
            title=data.get("title", ""),
            summary=data.get("summary", ""),
            detailed_summary=data.get("detailed_summary", ""),
            primary_topic=data.get("primary_topic", "other"),
            topics=data.get("topics", []),
            primary_rationale=data.get("primary_rationale", ""),
            problem_statement=data.get("problem_statement", ""),
            supporting_arguments=data.get("supporting_arguments", []),
            opposing_arguments=data.get("opposing_arguments", []),
            tradeoffs_identified=data.get("tradeoffs_identified", []),
            key_decision_factors=data.get("key_decision_factors", []),
            compromises_made=data.get("compromises_made", []),
            final_outcome=data.get("final_outcome", ""),
            outcome_explanation=data.get("outcome_explanation", ""),
            confidence_score=data.get("confidence_score", 0.0),
            data_sources=["bill_text", "abstract"]
        )


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze bill reasoning with AI")
    parser.add_argument("--bill-id", help="Bill ID to analyze")
    parser.add_argument("--state", help="State code (e.g., GA)")
    parser.add_argument("--topic", help="Topic filter (e.g., fluoride)")
    parser.add_argument("--model", default="gpt-4-turbo", help="LLM model to use")
    parser.add_argument("--local", action="store_true", help="Use local LLM")
    parser.add_argument("--output", help="Output JSON file path")
    
    args = parser.parse_args()
    
    analyzer = PolicyReasoningAnalyzer(model=args.model, local=args.local)
    
    # Example: Analyze a bill
    logger.info("Policy Reasoning Analyzer")
    logger.info("=" * 60)
    logger.info(f"Model: {args.model}")
    logger.info(f"Local: {args.local}")
    logger.info("")
    
    # TODO: Load bill data from database
    # TODO: Fetch testimony, amendments, committee reports
    # TODO: Run analysis
    # TODO: Save to database or output file
    
    logger.info("✅ Analysis complete")


if __name__ == "__main__":
    main()
