#!/usr/bin/env python3
"""
Mixture-of-Agents (MoA) synthesis for bronze decision extractions.

This script implements the MoA pattern to synthesize multiple AI model extractions
of the same meeting decision into a single, high-quality consensus output.

Architecture:
1. Proposers: Multiple models (Gemini, GPT-4, Claude) extract decisions independently
2. Aggregator: A powerful model (GPT-4o or Gemini Pro) synthesizes all extractions

Usage:
    # Synthesize specific decision
    python scripts/datasources/gemini/moa_synthesize.py --event-id 192614 --decision-id D001
    
    # Synthesize all decisions for an event
    python scripts/datasources/gemini/moa_synthesize.py --event-id 192614 --all
    
    # Use Gemini Pro as aggregator instead of GPT-4o
    python scripts/datasources/gemini/moa_synthesize.py --event-id 192614 --aggregator gemini-pro
    
    # Dry run (show prompt without calling API)
    python scripts/datasources/gemini/moa_synthesize.py --event-id 192614 --decision-id D001 --dry-run
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
import argparse
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import psycopg2
from loguru import logger

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Database URL
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'password')
DATABASE_URL = os.getenv('LOCAL_BRONZE_DATABASE_URL', 
                         f'postgresql://postgres:{POSTGRES_PASSWORD}@localhost:5433/open_navigator_bronze')

# API Keys
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')


class MoASynthesizer:
    """Mixture-of-Agents synthesizer for decision extractions."""
    
    def __init__(self, aggregator: str = 'gpt-4o'):
        self.aggregator = aggregator
        
        # Initialize API clients
        if 'gpt' in aggregator.lower() and OPENAI_API_KEY:
            from openai import OpenAI
            self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
        
        if 'gemini' in aggregator.lower() and GEMINI_API_KEY:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            self.genai = genai
        
        if 'claude' in aggregator.lower() and ANTHROPIC_API_KEY:
            from anthropic import Anthropic
            self.anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
    
    def get_all_extractions(self, event_id: int, decision_id: str) -> List[tuple]:
        """Get all model extractions for a decision from bronze."""
        
        query = """
        SELECT 
            source_ai_model,
            headline,
            decision_statement,
            outcome,
            primary_theme,
            primary_theme_cofog,
            ntee_code,
            ntee_category_label,
            arguments_for,
            arguments_against,
            vote_tally,
            tradeoffs,
            power_map
        FROM bronze_decisions
        WHERE source_event_id = %s 
          AND decision_id = %s
          AND source_ai_model NOT LIKE 'moa-%'  -- Exclude previous MoA syntheses
        ORDER BY source_ai_model
        """
        
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(query, (event_id, decision_id))
                return cur.fetchall()
    
    def create_aggregator_prompt(self, extractions: List[tuple]) -> str:
        """Create MoA aggregator prompt."""
        
        formatted_extractions = []
        for i, extraction in enumerate(extractions, 1):
            (model, headline, statement, outcome, theme, theme_cofog, ntee, 
             ntee_label, args_for, args_against, votes, tradeoffs, power_map) = extraction
            
            formatted_extractions.append(f"""
### Extraction {i} (Model: {model})

**Headline:** {headline or 'N/A'}

**Decision Statement:** {statement or 'N/A'}

**Outcome:** {outcome or 'N/A'}

**Primary Theme:** {theme or 'N/A'} (COFOG: {theme_cofog or 'N/A'})

**NTEE Code:** {ntee or 'N/A'} - {ntee_label or 'N/A'}

**Arguments For:** {json.dumps(args_for, indent=2) if args_for else 'N/A'}

**Arguments Against:** {json.dumps(args_against, indent=2) if args_against else 'N/A'}

**Vote Tally:** {json.dumps(votes, indent=2) if votes else 'N/A'}

**Tradeoffs:** {json.dumps(tradeoffs, indent=2) if tradeoffs else 'N/A'}

**Power Map:** {json.dumps(power_map, indent=2) if power_map else 'N/A'}
            """)
        
        prompt = f"""
You are an expert AI aggregator tasked with synthesizing multiple AI model extractions of a city council meeting decision.

Below are {len(extractions)} different extractions of the same decision from different AI models. Each model analyzed the same meeting transcript independently.

{chr(10).join(formatted_extractions)}

## Your Task

Analyze all {len(extractions)} extractions and create a single, comprehensive, and accurate synthesis that:

1. **Identifies Common Ground:** What do all/most models agree on? These are high-confidence facts.
2. **Resolves Contradictions:** Where models disagree, use your reasoning to determine the most likely accurate version.
3. **Combines Strengths:** Take the best parts from each extraction (e.g., one model may have better arguments, another better vote details).
4. **Corrects Errors:** If you spot factual inconsistencies, logical errors, or missing context, correct/add them.
5. **Maintains Accuracy:** Do NOT hallucinate or add information not supported by at least one extraction.

## Critical Synthesis Rules

- If all models agree on a fact → High confidence, use it
- If 2+ models agree on a fact → Medium confidence, likely correct
- If only 1 model mentions a fact → Low confidence, verify against others
- If models contradict → Explain the contradiction in your reasoning

## Output Format

Provide your synthesis as valid JSON:

{{
  "synthesized_headline": "Clear, informative headline",
  "synthesized_statement": "Comprehensive decision statement",
  "consensus_outcome": "approved|rejected|tabled|amended",
  "consensus_theme": "Primary theme all models agree on",
  "consensus_theme_cofog": "COFOG code",
  "consensus_ntee_code": "NTEE code (e.g., 'P20')",
  "consensus_ntee_category": "NTEE category label",
  "high_confidence_facts": ["Fact all models agree on", "Another consensus fact"],
  "low_confidence_facts": ["Fact only 1 model mentioned", "Uncertain detail"],
  "contradictions": [
    {{
      "topic": "What they disagree about",
      "model_a_says": "Model A's version",
      "model_b_says": "Model B's version",
      "likely_truth": "Your best judgment"
    }}
  ],
  "synthesized_arguments_for": [
    {{
      "claim": "...",
      "speaker": "...",
      "evidence": "..."
    }}
  ],
  "synthesized_arguments_against": [
    {{
      "claim": "...",
      "speaker": "...",
      "evidence": "..."
    }}
  ],
  "synthesized_vote_tally": {{
    "yes": 7,
    "no": 2,
    "abstain": 0,
    "absent": 0
  }},
  "synthesized_tradeoffs": [
    {{
      "tradeoff": "...",
      "option_a": "...",
      "option_b": "..."
    }}
  ],
  "synthesis_reasoning": "Detailed explanation of how you made synthesis decisions, which models you trusted for which aspects, and why"
}}

IMPORTANT: Output ONLY valid JSON, no markdown formatting or code blocks.
"""
        
        return prompt
    
    def aggregate_with_gpt4(self, prompt: str) -> Dict[str, Any]:
        """Use GPT-4 as aggregator."""
        
        logger.info("🔄 Calling GPT-4o aggregator...")
        
        response = self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert at synthesizing multiple AI outputs into a single high-quality result. You output valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        return json.loads(response.choices[0].message.content)
    
    def aggregate_with_gemini(self, prompt: str) -> Dict[str, Any]:
        """Use Gemini Pro as aggregator."""
        
        logger.info("🔄 Calling Gemini Pro aggregator...")
        
        model = self.genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content(
            prompt,
            generation_config=self.genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.3
            )
        )
        
        return json.loads(response.text)
    
    def aggregate_with_claude(self, prompt: str) -> Dict[str, Any]:
        """Use Claude as aggregator."""
        
        logger.info("🔄 Calling Claude aggregator...")
        
        response = self.anthropic_client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=4096,
            temperature=0.3,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        return json.loads(response.content[0].text)
    
    def store_synthesis(self, event_id: int, decision_id: str, synthesis: Dict[str, Any]):
        """Store MoA synthesis back to bronze_decisions."""
        
        query = """
        INSERT INTO bronze_decisions (
            source_event_id, source_ai_model, decision_id,
            headline, decision_statement, outcome,
            primary_theme, primary_theme_cofog,
            ntee_code, ntee_category_label,
            arguments_for, arguments_against, vote_tally, tradeoffs
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (source_event_id, decision_id, source_ai_model)
        DO UPDATE SET
            headline = EXCLUDED.headline,
            decision_statement = EXCLUDED.decision_statement,
            outcome = EXCLUDED.outcome,
            primary_theme = EXCLUDED.primary_theme,
            primary_theme_cofog = EXCLUDED.primary_theme_cofog,
            ntee_code = EXCLUDED.ntee_code,
            ntee_category_label = EXCLUDED.ntee_category_label,
            arguments_for = EXCLUDED.arguments_for,
            arguments_against = EXCLUDED.arguments_against,
            vote_tally = EXCLUDED.vote_tally,
            tradeoffs = EXCLUDED.tradeoffs,
            extracted_at = CURRENT_TIMESTAMP
        """
        
        with psycopg2.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(query, (
                    event_id,
                    f'moa-{self.aggregator}',  # Special model name
                    decision_id,
                    synthesis.get('synthesized_headline'),
                    synthesis.get('synthesized_statement'),
                    synthesis.get('consensus_outcome'),
                    synthesis.get('consensus_theme'),
                    synthesis.get('consensus_theme_cofog'),
                    synthesis.get('consensus_ntee_code'),
                    synthesis.get('consensus_ntee_category'),
                    json.dumps(synthesis.get('synthesized_arguments_for', [])),
                    json.dumps(synthesis.get('synthesized_arguments_against', [])),
                    json.dumps(synthesis.get('synthesized_vote_tally', {})),
                    json.dumps(synthesis.get('synthesized_tradeoffs', []))
                ))
            conn.commit()
        
        logger.info(f"💾 Stored synthesis as model: moa-{self.aggregator}")
    
    def synthesize_decision(self, event_id: int, decision_id: str, dry_run: bool = False) -> Optional[Dict[str, Any]]:
        """
        Full MoA pipeline to synthesize decision from multiple extractions.
        
        Args:
            event_id: Source event ID
            decision_id: Decision ID to synthesize
            dry_run: If True, only show prompt without calling API
        
        Returns:
            Synthesized decision as dict, or None if insufficient extractions
        """
        
        logger.info(f"🚀 MoA Synthesis for event={event_id}, decision={decision_id}")
        
        # Get all proposer outputs
        extractions = self.get_all_extractions(event_id, decision_id)
        
        if len(extractions) < 2:
            logger.warning(f"⚠️  Only {len(extractions)} extraction(s) found. Need 2+ for MoA.")
            return None
        
        logger.info(f"📊 Found {len(extractions)} proposer extractions:")
        for model, *_ in extractions:
            logger.info(f"  - {model}")
        
        # Create aggregator prompt
        prompt = self.create_aggregator_prompt(extractions)
        
        if dry_run:
            logger.info("\n" + "="*80)
            logger.info("DRY RUN - Aggregator Prompt:")
            logger.info("="*80)
            print(prompt)
            logger.info("="*80)
            logger.info("✅ Dry run complete (no API call made)")
            return None
        
        # Run aggregator
        if 'gpt' in self.aggregator.lower():
            synthesis = self.aggregate_with_gpt4(prompt)
        elif 'gemini' in self.aggregator.lower():
            synthesis = self.aggregate_with_gemini(prompt)
        elif 'claude' in self.aggregator.lower():
            synthesis = self.aggregate_with_claude(prompt)
        else:
            raise ValueError(f"Unknown aggregator: {self.aggregator}")
        
        logger.info(f"✅ MoA synthesis complete using {self.aggregator}")
        
        # Store synthesis
        self.store_synthesis(event_id, decision_id, synthesis)
        
        # Display summary
        logger.info("\n📊 Synthesis Summary:")
        logger.info(f"  Headline: {synthesis.get('synthesized_headline')}")
        logger.info(f"  Outcome: {synthesis.get('consensus_outcome')}")
        logger.info(f"  High Confidence Facts: {len(synthesis.get('high_confidence_facts', []))}")
        logger.info(f"  Low Confidence Facts: {len(synthesis.get('low_confidence_facts', []))}")
        logger.info(f"  Contradictions: {len(synthesis.get('contradictions', []))}")
        
        if synthesis.get('contradictions'):
            logger.info("\n⚠️  Contradictions Found:")
            for contra in synthesis['contradictions']:
                logger.info(f"  - {contra.get('topic')}: {contra.get('likely_truth')}")
        
        return synthesis


def synthesize_all_decisions(event_id: int, aggregator: str = 'gpt-4o'):
    """Synthesize all decisions for an event."""
    
    # Get all unique decision IDs
    query = """
    SELECT DISTINCT decision_id
    FROM bronze_decisions
    WHERE source_event_id = %s
      AND source_ai_model NOT LIKE 'moa-%'
    ORDER BY decision_id
    """
    
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (event_id,))
            decision_ids = [row[0] for row in cur.fetchall()]
    
    logger.info(f"Found {len(decision_ids)} decisions to synthesize")
    
    synthesizer = MoASynthesizer(aggregator=aggregator)
    
    for i, decision_id in enumerate(decision_ids, 1):
        logger.info(f"\n{'='*80}")
        logger.info(f"Synthesizing {i}/{len(decision_ids)}: {decision_id}")
        logger.info(f"{'='*80}")
        
        try:
            synthesizer.synthesize_decision(event_id, decision_id)
        except Exception as e:
            logger.error(f"❌ Failed to synthesize {decision_id}: {e}")
            continue
    
    logger.info(f"\n✅ Synthesized {len(decision_ids)} decisions for event {event_id}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="MoA synthesis for bronze decision extractions"
    )
    parser.add_argument(
        '--event-id',
        type=int,
        required=True,
        help='Event ID to synthesize'
    )
    parser.add_argument(
        '--decision-id',
        type=str,
        help='Specific decision ID to synthesize (omit to synthesize all)'
    )
    parser.add_argument(
        '--aggregator',
        type=str,
        default='gpt-4o',
        choices=['gpt-4o', 'gemini-pro', 'claude-opus'],
        help='Which model to use as aggregator'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Synthesize all decisions for the event'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show prompt without calling API'
    )
    
    args = parser.parse_args()
    
    if args.all or not args.decision_id:
        synthesize_all_decisions(args.event_id, args.aggregator)
    else:
        synthesizer = MoASynthesizer(aggregator=args.aggregator)
        synthesizer.synthesize_decision(args.event_id, args.decision_id, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
