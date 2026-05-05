#!/usr/bin/env python3
"""
Check which models have been used in events_text_ai table.

Usage:
    python scripts/datasources/gemini/check_models_used.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import psycopg2
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('NEON_DATABASE_URL_DEV', 'postgresql://postgres:password@localhost:5433/open_navigator')


def check_models_used():
    """Show statistics about which models have been used."""
    
    query = """
    SELECT 
        ai_model,
        COUNT(*) as total_analyses,
        COUNT(CASE WHEN error_message IS NULL THEN 1 END) as successful,
        COUNT(CASE WHEN error_message IS NOT NULL THEN 1 END) as errors,
        MIN(created_at) as first_used,
        MAX(created_at) as last_used
    FROM events_text_ai
    GROUP BY ai_model
    ORDER BY total_analyses DESC
    """
    
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            results = cur.fetchall()
    
    if not results:
        logger.info("No analyses found in database yet")
        return
    
    logger.info("=" * 120)
    logger.info("MODELS USED IN events_text_ai")
    logger.info("=" * 120)
    logger.info("")
    logger.info(f"{'Model':<40} {'Total':<10} {'Success':<10} {'Errors':<10} {'First Used':<20} {'Last Used'}")
    logger.info("-" * 120)
    
    for row in results:
        model, total, success, errors, first, last = row
        logger.info(f"{model:<40} {total:<10} {success:<10} {errors:<10} {str(first)[:19]:<20} {str(last)[:19]}")
    
    logger.info("")
    logger.info(f"Total analyses: {sum(r[1] for r in results):,}")
    logger.info("")
    
    # Show today's activity
    today_query = """
    SELECT 
        ai_model,
        COUNT(*) as count
    FROM events_text_ai
    WHERE created_at::date = CURRENT_DATE
    GROUP BY ai_model
    ORDER BY count DESC
    """
    
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(today_query)
            today_results = cur.fetchall()
    
    if today_results:
        logger.info("📅 Today's Activity:")
        for model, count in today_results:
            logger.info(f"   {model}: {count} analyses")
    else:
        logger.info("📅 No analyses today yet")


if __name__ == '__main__':
    check_models_used()
