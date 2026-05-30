#!/usr/bin/env python3
"""
Compare AI model extractions for the same meeting decision.

This script demonstrates how to use the multi-model support in the bronze layer
to compare how different AI models extracted the same decision.

Usage:
    # Compare all models for a specific event
    python -m llm.enrichment.compare_model_extractions --event-id 192614
    
    # Compare specific models for an event  
    python -m llm.enrichment.compare_model_extractions --event-id 192614 --models gemini-1.5-flash gpt-4
    
    # Compare across all events (summary)
    python -m llm.enrichment.compare_model_extractions --summary
"""

import os
import sys
from pathlib import Path
import argparse
from typing import Dict, List, Any
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parents[5]))

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


def compare_decisions_for_event(event_id: int, models: List[str] = None):
    """
    Compare decision extractions across different models for a specific event.
    
    Args:
        event_id: The source event ID
        models: Optional list of specific models to compare. If None, compares all.
    """
    logger.info(f"Comparing decision extractions for event {event_id}")
    
    query = """
    SELECT 
        source_ai_model,
        decision_id,
        headline,
        decision_statement,
        outcome,
        primary_theme,
        ntee_code,
        ntee_category_label,
        json_array_length(arguments_for) as num_arguments_for,
        json_array_length(arguments_against) as num_arguments_against,
        extracted_at
    FROM bronze_decisions
    WHERE source_event_id = %s
    """
    
    params = [event_id]
    
    if models:
        query += " AND source_ai_model = ANY(%s)"
        params.append(models)
    
    query += " ORDER BY source_ai_model, decision_id"
    
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            results = cur.fetchall()
    
    if not results:
        logger.warning(f"No decision extractions found for event {event_id}")
        return
    
    logger.info(f"\nFound {len(results)} decision extractions:")
    logger.info("=" * 100)
    
    # Group by decision_id
    by_decision = {}
    for row in results:
        (ai_model, decision_id, headline, statement, outcome, theme, 
         ntee_code, ntee_label, num_for, num_against, extracted_at) = row
        
        if decision_id not in by_decision:
            by_decision[decision_id] = []
        
        by_decision[decision_id].append({
            'model': ai_model,
            'headline': headline,
            'statement': statement,
            'outcome': outcome,
            'theme': theme,
            'ntee_code': ntee_code,
            'ntee_label': ntee_label,
            'num_arguments_for': num_for,
            'num_arguments_against': num_against,
            'extracted_at': extracted_at
        })
    
    # Display comparison
    for decision_id, extractions in by_decision.items():
        logger.info(f"\nDecision ID: {decision_id}")
        logger.info(f"Extracted by {len(extractions)} model(s):")
        
        for ext in extractions:
            logger.info(f"\n  Model: {ext['model']}")
            logger.info(f"  Headline: {ext['headline']}")
            logger.info(f"  Outcome: {ext['outcome']}")
            logger.info(f"  Theme: {ext['theme']} ({ext['ntee_code']} - {ext['ntee_label']})")
            logger.info(f"  Arguments: {ext['num_arguments_for']} for, {ext['num_arguments_against']} against")
            logger.info(f"  Extracted: {ext['extracted_at']}")
        
        # Compare differences
        if len(extractions) > 1:
            logger.info(f"\n  🔍 Differences:")
            
            # Compare headlines
            headlines = set(e['headline'] for e in extractions if e['headline'])
            if len(headlines) > 1:
                logger.info(f"    ⚠️  Different headlines: {len(headlines)} variations")
            
            # Compare outcomes
            outcomes = set(e['outcome'] for e in extractions if e['outcome'])
            if len(outcomes) > 1:
                logger.info(f"    ⚠️  Different outcomes: {outcomes}")
            
            # Compare NTEE codes
            ntee_codes = set(e['ntee_code'] for e in extractions if e['ntee_code'])
            if len(ntee_codes) > 1:
                logger.info(f"    ⚠️  Different NTEE codes: {ntee_codes}")
            
            # Compare argument counts
            arg_for_counts = set(e['num_arguments_for'] for e in extractions if e['num_arguments_for'])
            if len(arg_for_counts) > 1:
                logger.info(f"    ⚠️  Different argument counts (for): {arg_for_counts}")
        
        logger.info("-" * 100)


def summary_across_all_events():
    """Show summary statistics of model comparisons across all events."""
    
    logger.info("Summary of multi-model extractions:")
    logger.info("=" * 100)
    
    query = """
    WITH model_counts AS (
        SELECT 
            source_event_id,
            decision_id,
            COUNT(DISTINCT source_ai_model) as num_models
        FROM bronze_decisions
        GROUP BY source_event_id, decision_id
    )
    SELECT 
        num_models,
        COUNT(*) as num_decisions
    FROM model_counts
    GROUP BY num_models
    ORDER BY num_models;
    """
    
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            results = cur.fetchall()
    
    logger.info("\nDecisions by number of model extractions:")
    for num_models, num_decisions in results:
        logger.info(f"  {num_models} model(s): {num_decisions} decisions")
    
    # Get model usage stats
    model_query = """
    SELECT 
        source_ai_model,
        COUNT(*) as num_extractions
    FROM bronze_decisions
    GROUP BY source_ai_model
    ORDER BY num_extractions DESC;
    """
    
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(model_query)
            results = cur.fetchall()
    
    logger.info("\nModel usage:")
    for model, count in results:
        logger.info(f"  {model}: {count} extractions")
    
    logger.info("=" * 100)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Compare AI model extractions for meeting decisions"
    )
    parser.add_argument(
        '--event-id',
        type=int,
        help='Event ID to compare'
    )
    parser.add_argument(
        '--models',
        nargs='+',
        help='Specific models to compare (e.g., gemini-1.5-flash gpt-4)'
    )
    parser.add_argument(
        '--summary',
        action='store_true',
        help='Show summary statistics across all events'
    )
    
    args = parser.parse_args()
    
    if args.summary:
        summary_across_all_events()
    elif args.event_id:
        compare_decisions_for_event(args.event_id, args.models)
    else:
        parser.error("Provide either --event-id or --summary")


if __name__ == '__main__':
    main()
