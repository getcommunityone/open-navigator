#!/usr/bin/env python3
"""
Intelligent Multi-Model Gemini Analysis

This script tries multiple Gemini models in order of best quota,
falling back to the next model when quota is exceeded.

This maximizes throughput by using multiple models' daily quotas:
- gemini-3.1-flash-lite-preview: 1,500/day
- gemini-2.0-flash-lite: 1,500/day  
- gemini-2.5-flash-lite: 1,000/day
- gemini-2.5-flash: 1,000/day
= Total potential: 5,000+ requests/day

Usage:
    # Try all high-quota models for priority states
    python scripts/datasources/gemini/analyze_with_multi_models.py --priority-states
    
    # Try specific models
    python scripts/datasources/gemini/analyze_with_multi_models.py \
      --priority-states \
      --models gemini-3.1-flash-lite-preview,gemini-2.0-flash-lite
    
    # Dry run
    python scripts/datasources/gemini/analyze_with_multi_models.py --priority-states --dry-run
"""

import os
import sys
from pathlib import Path
import argparse

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from loguru import logger
from dotenv import load_dotenv

# Import the analyzer
from scripts.datasources.gemini.analyze_meeting_transcripts import (
    MeetingTranscriptAnalyzer,
    DATABASE_URL,
    GEMINI_API_KEY,
    PRIORITY_STATES
)

# Load environment variables
load_dotenv()

# Models in order of preference (best quota first)
DEFAULT_MODELS = [
    'gemini-3.1-flash-lite-preview',  # 1,500/day
    'gemini-2.0-flash-lite',           # 1,500/day
    'gemini-2.5-flash-lite',           # 1,000/day
    'gemini-2.5-flash',                # 1,000/day
]

MODEL_QUOTAS = {
    'gemini-3.1-flash-lite-preview': 1500,
    'gemini-2.0-flash-lite': 1500,
    'gemini-2.5-flash-lite': 1000,
    'gemini-flash-lite-latest': 1000,
    'gemini-2.5-flash': 1000,
    'gemini-2.0-flash': 1000,
}


def run_with_model_fallback(
    models: list,
    states_filter: list = None,
    meetings_per_channel: int = 5,
    force_reanalyze: bool = False,
    delay_seconds: float = 5.0,
    dry_run: bool = False
):
    """
    Run analysis with automatic model fallback.
    
    Tries models in order, switching to next when quota is exceeded.
    """
    
    logger.info("=" * 70)
    logger.info("INTELLIGENT MULTI-MODEL GEMINI ANALYSIS")
    logger.info("=" * 70)
    logger.info(f"Models to try (in order): {', '.join(models)}")
    logger.info(f"Total potential quota: {sum(MODEL_QUOTAS.get(m, 0) for m in models):,} requests/day")
    logger.info("")
    
    total_success = 0
    total_errors = 0
    
    for i, model in enumerate(models, 1):
        logger.info("")
        logger.info("🔄 " * 30)
        logger.info(f"Trying Model {i}/{len(models)}: {model}")
        logger.info(f"Quota: {MODEL_QUOTAS.get(model, 'Unknown')} requests/day")
        logger.info("🔄 " * 30)
        logger.info("")
        
        # Initialize analyzer with this model
        analyzer = MeetingTranscriptAnalyzer(
            database_url=DATABASE_URL,
            gemini_api_key=GEMINI_API_KEY,
            meetings_per_channel=meetings_per_channel,
            force_reanalyze=force_reanalyze,
            delay_seconds=delay_seconds,
            model_name=model
        )
        
        try:
            # Run analysis
            result = analyzer.run(states_filter=states_filter, dry_run=dry_run)
            
            # If we get here without quota error, we're done
            logger.info(f"✅ Completed with {model}")
            break
            
        except Exception as e:
            error_msg = str(e)
            
            # Check if quota exceeded
            if '429' in error_msg or 'quota' in error_msg.lower():
                logger.warning(f"⚠️ Quota exceeded for {model}")
                logger.warning(f"   Processed some meetings, moving to next model...")
                
                # If this is the last model, stop
                if i == len(models):
                    logger.error("❌ All models exhausted - no more quotas available today")
                    logger.info("💡 Run again tomorrow or upgrade to paid tier")
                    break
                else:
                    logger.info(f"   Switching to next model: {models[i]}")
                    continue
            else:
                # Some other error
                logger.error(f"❌ Error with {model}: {e}")
                raise
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("MULTI-MODEL ANALYSIS COMPLETE")
    logger.info("=" * 70)
    logger.info("")
    logger.info("💡 Check results:")
    logger.info("   SELECT ai_model, COUNT(*) FROM events_text_ai")
    logger.info("   WHERE created_at::date = CURRENT_DATE")
    logger.info("   GROUP BY ai_model;")


def main():
    parser = argparse.ArgumentParser(
        description='Intelligent multi-model Gemini analysis with automatic fallback'
    )
    
    parser.add_argument(
        '--states',
        type=str,
        help='Comma-separated state codes'
    )
    
    parser.add_argument(
        '--priority-states',
        action='store_true',
        help=f'Use priority states only ({", ".join(PRIORITY_STATES)})'
    )
    
    parser.add_argument(
        '--meetings-per-channel',
        type=int,
        default=5,
        help='Number of most recent meetings to analyze per channel (default: 5)'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force re-analysis (skip incremental check)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be analyzed without actually running'
    )
    
    parser.add_argument(
        '--delay',
        type=float,
        default=5.0,
        help='Delay between API requests in seconds (default: 5.0)'
    )
    
    parser.add_argument(
        '--models',
        type=str,
        help=f'Comma-separated models to try (default: {",".join(DEFAULT_MODELS)})'
    )
    
    args = parser.parse_args()
    
    # Check API key
    if not GEMINI_API_KEY:
        logger.error("❌ GEMINI_API_KEY not found in environment variables")
        return 1
    
    # Parse states filter
    states_filter = None
    if args.states:
        states_filter = [s.strip().upper() for s in args.states.split(',')]
    elif args.priority_states:
        states_filter = PRIORITY_STATES
    
    # Parse models
    models = DEFAULT_MODELS
    if args.models:
        models = [m.strip() for m in args.models.split(',')]
    
    try:
        run_with_model_fallback(
            models=models,
            states_filter=states_filter,
            meetings_per_channel=args.meetings_per_channel,
            force_reanalyze=args.force,
            delay_seconds=args.delay,
            dry_run=args.dry_run
        )
        return 0
    except Exception as e:
        logger.error(f"✗ Multi-model analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
