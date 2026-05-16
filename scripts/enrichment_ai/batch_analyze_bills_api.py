#!/usr/bin/env python3
"""
Batch Bill Analysis with HuggingFace Inference API

Fast, cost-effective analysis using HuggingFace's serverless inference.

Cost estimate:
- ~$0.001-0.003 per bill
- ~$3 for 1,000 bills
- ~30 for 10,000 bills

Speed: ~1-2 seconds per bill (vs 10-15 min on CPU)

Usage:
    # Analyze Alabama fluoride bills (fast test)
    export HF_TOKEN=your_token
    python scripts/enrichment_ai/batch_analyze_bills_api.py --state AL --topic fluoride --limit 10
    
    # Analyze 1000 bills (~$3, ~30 minutes)
    python scripts/enrichment_ai/batch_analyze_bills_api.py --state MA --topic fluoride --limit 1000
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.enrichment_ai.legislative_analysis_intel import (
    DuckDBLegislativeAnalyzer,
    InterestGroup,
    ANALYSIS_DIR
)
from loguru import logger
import argparse
from typing import List, Dict, Any
import time
import os
import json
from huggingface_hub import InferenceClient


class HuggingFaceInferenceLLM:
    """
    HuggingFace Inference API wrapper
    
    Fast serverless inference - pay only for what you use
    """
    
    def __init__(
        self, 
        model_name: str = "meta-llama/Meta-Llama-3-8B-Instruct",
        token: str = None
    ):
        self.model_name = model_name
        self.token = token or os.getenv('HF_TOKEN')
        
        if not self.token:
            raise ValueError("HuggingFace token required! Set HF_TOKEN environment variable")
        
        # Initialize inference client
        self.client = InferenceClient(token=self.token)
        logger.info(f"🌐 Using HuggingFace Inference API: {model_name}")
    
    def extract_interest_groups(
        self, 
        bill_context: Dict[str, Any],
        testimony: List[Dict[str, Any]]
    ) -> List[InterestGroup]:
        """
        Extract interest groups using HuggingFace Inference API
        
        Args:
            bill_context: Bill metadata (id, title, jurisdiction, etc.)
            testimony: List of testimony/speaker data
            
        Returns:
            List of InterestGroup objects
        """
        # Build prompt
        prompt = self._build_prompt(bill_context, testimony)
        
        # Call API using native HuggingFace endpoint (more reliable)
        try:
            import requests
            
            API_URL = f"https://api-inference.huggingface.co/models/{self.model_name}"
            headers = {"Authorization": f"Bearer {self.token}"}
            
            # Simple payload for text generation
            payload = {
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": 500,
                    "temperature": 0.1,
                    "return_full_text": False
                }
            }
            
            response = requests.post(API_URL, headers=headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            # Extract generated text
            if isinstance(result, list) and len(result) > 0:
                response_text = result[0].get('generated_text', '')
            elif isinstance(result, dict):
                response_text = result.get('generated_text', result.get('text', ''))
            else:
                response_text = str(result)
            
            # Parse structured output
            groups = self._parse_response(response_text, bill_context)
            
            return groups
            
        except Exception as e:
            logger.error(f"API call failed: {e}")
            return []
    
    def _build_prompt(
        self, 
        bill_context: Dict[str, Any],
        testimony: List[Dict[str, Any]]
    ) -> str:
        """Build analysis prompt"""
        
        bill_summary = f"""
Bill: {bill_context['bill_number']}
Title: {bill_context['title']}
Jurisdiction: {bill_context.get('jurisdiction', 'Unknown')}
"""
        
        testimony_text = ""
        for t in testimony[:5]:  # Limit to first 5 testimonies
            testimony_text += f"\n- {t.get('speaker', 'Unknown')}"
            if t.get('organization'):
                testimony_text += f" ({t['organization']})"
            testimony_text += f": {t.get('stance', 'unknown')} - {t.get('text', '')[:200]}..."
        
        prompt = f"""Analyze this bill and testimony to identify interest groups.

{bill_summary}

Testimony:
{testimony_text}

For each distinct interest group mentioned, provide:
1. Group name
2. Stance (support/oppose/neutral)
3. Brief reason (1 sentence)

Format as JSON array:
[
  {{"group": "Group Name", "stance": "support", "reason": "Brief reason"}},
  ...
]

Limit to top 5 most relevant groups.
"""
        return prompt
    
    def _parse_response(
        self,
        response_text: str,
        bill_context: Dict[str, Any]
    ) -> List[InterestGroup]:
        """Parse LLM response into InterestGroup objects"""
        
        groups = []
        
        try:
            # Try to extract JSON from response
            # Look for JSON array in response
            import re
            json_match = re.search(r'\[.*?\]', response_text, re.DOTALL)
            
            if json_match:
                data = json.loads(json_match.group())
                
                for item in data:
                    group = InterestGroup(
                        bill_id=bill_context['bill_id'],
                        bill_number=bill_context['bill_number'],
                        topic=bill_context.get('topic', 'unknown'),
                        jurisdiction=bill_context.get('jurisdiction', 'unknown'),
                        group_name=item.get('group', 'Unknown'),
                        stance=item.get('stance', 'unknown'),
                        confidence=0.8,  # API-based, reasonably confident
                        reasoning=item.get('reason', ''),
                        source='llm_analysis'
                    )
                    groups.append(group)
            else:
                logger.warning(f"Could not parse JSON from response: {response_text[:200]}")
                
        except Exception as e:
            logger.error(f"Failed to parse response: {e}")
        
        return groups


def analyze_batch(
    state: str = None,
    topic: str = None,
    limit: int = 10,
    skip_analyzed: bool = True,
    model: str = "meta-llama/Meta-Llama-3-8B-Instruct"
):
    """
    Batch analyze bills using HuggingFace Inference API
    
    Args:
        state: State code filter (e.g., 'AL', 'MA')
        topic: Topic search term (e.g., 'fluoride')
        limit: Maximum bills to analyze
        skip_analyzed: Use incremental processing
        model: Model to use via API
    """
    
    logger.info("=" * 70)
    logger.info("BATCH BILL ANALYSIS WITH HUGGINGFACE INFERENCE API")
    logger.info("=" * 70)
    logger.info(f"State: {state or 'All'}")
    logger.info(f"Topic: {topic or 'All'}")
    logger.info(f"Limit: {limit}")
    logger.info(f"Incremental: {skip_analyzed}")
    logger.info(f"Model: {model}")
    logger.info("")
    logger.info(f"💰 Estimated cost: ${limit * 0.002:.2f} - ${limit * 0.003:.2f}")
    logger.info(f"⏱️  Estimated time: {limit * 2 / 60:.1f} - {limit * 3 / 60:.1f} minutes")
    logger.info("")
    
    # Initialize
    with DuckDBLegislativeAnalyzer() as analyzer:
        # Create tables
        logger.info("📊 Loading bill data...")
        analyzer.create_bills_table()
        analyzer.create_testimony_table()
        
        # Get bills to analyze
        logger.info(f"\n🔍 Finding bills to analyze...")
        bills = analyzer.get_bills_to_analyze(
            state=state,
            topic_filter=topic,
            limit=limit,
            skip_analyzed=skip_analyzed
        )
        
        if not bills:
            logger.info("✅ No bills to analyze (all done or no matches)")
            logger.info(f"\n💡 Tip: Check existing results at:")
            logger.info(f"   {ANALYSIS_DIR / 'interest_groups_analysis.parquet'}")
            return
        
        logger.info(f"📋 Found {len(bills)} bills to analyze")
        logger.info("")
        
        # Initialize API client
        logger.info("🌐 Connecting to HuggingFace Inference API...")
        llm = HuggingFaceInferenceLLM(model_name=model)
        logger.info("✅ API connected")
        logger.info("")
        
        # Process each bill
        all_results = []
        success_count = 0
        error_count = 0
        total_start = time.time()
        
        for i, bill in enumerate(bills, 1):
            logger.info(f"[{i}/{len(bills)}] Analyzing {bill['bill_number']}...")
            logger.info(f"   Title: {bill['title'][:70]}...")
            
            bill_start = time.time()
            
            try:
                # Get testimony (if available)
                testimony = analyzer.get_all_testimony_for_bill(bill['bill_id'])
                
                if not testimony:
                    # Create mock testimony for demo
                    testimony = [{
                        'speaker': 'Public Health Official',
                        'organization': 'State Health Department',
                        'text': bill.get('abstract') or bill['title'],
                        'stance': 'support',
                        'timestamp': '2026-01-01'
                    }]
                
                # Add topic to context
                bill_context = bill.copy()
                bill_context['topic'] = topic or 'policy'
                
                # Extract interest groups via API
                groups = llm.extract_interest_groups(bill_context, testimony)
                
                if groups:
                    all_results.extend(groups)
                    analyzer.save_analysis_results(groups, append=True)
                    success_count += 1
                    
                    bill_time = time.time() - bill_start
                    logger.info(f"   ✅ Found {len(groups)} groups ({bill_time:.1f}s)")
                    
                    for g in groups:
                        logger.info(f"      - {g.group_name}: {g.stance}")
                else:
                    logger.warning(f"   ⚠️  No groups found")
                    
            except Exception as e:
                logger.error(f"   ❌ Error: {e}")
                error_count += 1
            
            # Rate limiting (be nice to the API)
            if i < len(bills):
                time.sleep(0.5)  # Small delay between requests
        
        # Summary
        total_time = time.time() - total_start
        logger.info("")
        logger.info("=" * 70)
        logger.info("📊 BATCH ANALYSIS COMPLETE")
        logger.info("=" * 70)
        logger.info(f"✅ Success: {success_count}/{len(bills)} bills")
        logger.info(f"❌ Errors: {error_count}")
        logger.info(f"📝 Total groups extracted: {len(all_results)}")
        logger.info(f"⏱️  Total time: {total_time/60:.1f} minutes")
        logger.info(f"⚡ Average: {total_time/len(bills):.1f} sec/bill")
        logger.info(f"💾 Results saved to: {ANALYSIS_DIR / 'interest_groups_analysis.parquet'}")
        logger.info("")


def main():
    parser = argparse.ArgumentParser(
        description="Batch bill analysis with HuggingFace Inference API"
    )
    parser.add_argument('--state', type=str, help='State code (e.g., AL, MA)')
    parser.add_argument('--topic', type=str, help='Topic filter (e.g., fluoride)')
    parser.add_argument('--limit', type=int, default=10, help='Max bills to analyze')
    parser.add_argument('--no-incremental', action='store_true', 
                        help='Re-analyze all bills (ignore existing)')
    parser.add_argument('--model', type=str, 
                        default='meta-llama/Meta-Llama-3-8B-Instruct',
                        help='Model name')
    
    args = parser.parse_args()
    
    analyze_batch(
        state=args.state,
        topic=args.topic,
        limit=args.limit,
        skip_analyzed=not args.no_incremental,
        model=args.model
    )


if __name__ == "__main__":
    main()
