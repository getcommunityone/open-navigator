#!/usr/bin/env python3
"""
Test the Policy Reasoning Analyzer with a sample bill

This demonstrates:
1. Loading bill data from the database
2. Running AI analysis with local Llama 3
3. Extracting summaries, topics, and reasoning
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.policy_reasoning_analyzer import PolicyReasoningAnalyzer
import duckdb
from loguru import logger

def test_analyzer():
    """Test analyzer with a real bill"""
    
    logger.info("=" * 70)
    logger.info("TESTING POLICY REASONING ANALYZER")
    logger.info("=" * 70)
    
    # Load a sample bill
    logger.info("\n1. Loading sample bill from database...")
    conn = duckdb.connect()
    
    result = conn.execute("""
        SELECT bill_id, bill_number, title, abstract
        FROM read_parquet('data/gold/bills_bills.parquet')
        WHERE state = 'GA' 
        AND LOWER(title) LIKE '%fluorid%'
        LIMIT 1
    """).fetchone()
    
    if not result:
        logger.error("No fluoride bills found in Georgia")
        return
    
    bill_id, bill_number, title, abstract = result
    
    logger.info(f"   Bill: {bill_number}")
    logger.info(f"   Title: {title[:80]}...")
    logger.info(f"   Abstract: {abstract[:150] if abstract else 'N/A'}...")
    
    # Initialize analyzer with Llama 3.3 (8B model - fits in 32GB WSL allocation)
    logger.info("\n2. Initializing AI analyzer (Llama 3.3 8B)...")
    analyzer = PolicyReasoningAnalyzer(
        model="llama3.3",  # 8B model (for 70B, increase WSL memory to 56GB)
        local=True
    )
    
    # Run analysis
    logger.info("\n3. Running AI analysis...")
    logger.info("   This may take 30-60 seconds with local LLM...")
    
    try:
        analysis = analyzer.analyze_bill(
            bill_id=bill_id,
            bill_text=abstract or title,
            bill_abstract=abstract or title
        )
        
        # Display results
        logger.info("\n" + "=" * 70)
        logger.info("ANALYSIS RESULTS")
        logger.info("=" * 70)
        
        logger.info(f"\n📋 SUMMARY:")
        logger.info(f"   {analysis.summary}")
        
        logger.info(f"\n📚 DETAILED SUMMARY:")
        logger.info(f"   {analysis.detailed_summary}")
        
        logger.info(f"\n🏷️  TOPICS:")
        logger.info(f"   Primary: {analysis.primary_topic}")
        logger.info(f"   Specific: {', '.join(analysis.topics)}")
        
        logger.info(f"\n💡 PRIMARY RATIONALE:")
        logger.info(f"   {analysis.primary_rationale}")
        
        logger.info(f"\n⚖️  TRADEOFFS:")
        for i, tradeoff in enumerate(analysis.tradeoffs_identified, 1):
            logger.info(f"   {i}. {tradeoff.get('tradeoff', 'N/A')}")
            logger.info(f"      Resolution: {tradeoff.get('resolution', 'N/A')}")
        
        logger.info(f"\n🎯 KEY DECISION FACTORS:")
        for factor in analysis.key_decision_factors:
            logger.info(f"   • {factor}")
        
        logger.info(f"\n📊 OUTCOME:")
        logger.info(f"   Status: {analysis.final_outcome}")
        logger.info(f"   Explanation: {analysis.outcome_explanation}")
        
        logger.info(f"\n✅ Confidence Score: {analysis.confidence_score:.2%}")
        
        logger.info("\n" + "=" * 70)
        logger.info("✅ TEST COMPLETE")
        logger.info("=" * 70)
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        import traceback
        traceback.print_exc()
    
    conn.close()


if __name__ == "__main__":
    test_analyzer()
