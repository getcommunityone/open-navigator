#!/usr/bin/env python3
"""
Repopulate NTEE codes for all topics using LLM to analyze topic content.

This script uses Google Gemini to re-analyze topics and assign NTEE codes based on:
1. Topic content (highest priority)
2. Theme information
3. Headline

Follows the updated hierarchy: substantive cause areas over Public Policy (W).
Uses automatic model fallback when quotas are exceeded.
"""

import psycopg2
import os
import logging
import google.generativeai as genai
from typing import Optional, Dict, List
import json
import time

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Database and API configuration
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'password')
DATABASE_URL = os.getenv('LOCAL_BRONZE_DATABASE_URL', f'postgresql://postgres:{POSTGRES_PASSWORD}@localhost:5433/open_navigator_bronze')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Gemini models to try (in order of preference)
# Free tier quotas per day (as of 2026):
# - gemini-3.1-flash-lite-preview: 1,500/day (newest, recommended)
# - gemini-2.0-flash-lite: 1,500/day
# - gemini-2.5-flash-lite: 1,000/day
DEFAULT_MODELS = [
    'gemini-3.1-flash-lite-preview',  # Newest preview, 1,500/day ⭐
    'gemini-2.0-flash-lite',          # Stable, 1,500/day
    'gemini-2.5-flash-lite',          # Fallback, 1,000/day
]

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# NTEE inference prompt
NTEE_PROMPT = """Analyze this policy topic and assign the most appropriate NTEE (National Taxonomy of Exempt Entities) codes.

CRITICAL RULES:
1. PRIORITIZE substantive cause areas (A-V, X-Y) over Public Policy (W)
2. W (Public Policy) should ONLY be used for purely procedural/administrative topics like:
   - "Approve meeting minutes"
   - "Adopt council rules"
   - "Budget process timeline"
3. For all other topics, analyze the CONTENT to find the substantive cause area

NTEE Codes:
A - Arts, Culture, and Humanities
B - Education  
C - Environment
D - Animal-Related
E - Health Care
F - Mental Health and Crisis Intervention
G - Disease and Disorder Research
H - Medical Research
I - Crime and Legal Services
J - Employment
K - Food, Agriculture, and Nutrition
L - Housing and Shelter
M - Public Safety and Disaster Relief
N - Recreation and Sports
O - Youth Development
P - Human Services
Q - International and Foreign Affairs
R - Civil Rights and Advocacy
S - Community Improvement
T - Philanthropy and Grantmaking
U - Science and Technology
V - Social Science
W - Public Policy (ONLY for purely procedural/administrative)
X - Religion
Y - Mutual Benefit
Z - Unknown

EXAMPLES:
- "Youth program funding" → Primary: O, Secondary: null
- "School lunch program" → Primary: K, Secondary: B
- "Recycling education campaign" → Primary: C, Secondary: B
- "Senior center renovation" → Primary: P, Secondary: null
- "Approve meeting minutes" → Primary: W, Secondary: null
- "Disability awareness proclamation" → Primary: R, Secondary: P
- "Arts festival approval" → Primary: A, Secondary: null

Topic: {topic}
Primary Theme: {primary_theme}
Secondary Theme: {secondary_theme}
Headline: {headline}

Respond ONLY with a JSON object in this exact format (no markdown, no explanation):
{{
  "primary_ntee_code": "X",
  "primary_ntee_major_group": "Category Name",
  "primary_ntee_category_label": "Category Name",
  "secondary_ntee_code": null,
  "secondary_ntee_major_group": null,
  "secondary_ntee_category_label": null,
  "confidence": "high|medium|low",
  "rationale": "Brief explanation of why this code was chosen"
}}

If the topic spans multiple cause areas, populate the secondary fields. Otherwise, set them to null.
"""


def infer_ntee_codes(
    topic: str,
    primary_theme: str,
    secondary_theme: Optional[str],
    headline: Optional[str],
    model
) -> Optional[Dict]:
    """Use Gemini to infer NTEE codes from topic content."""
    
    prompt = NTEE_PROMPT.format(
        topic=topic,
        primary_theme=primary_theme,
        secondary_theme=secondary_theme or "None",
        headline=headline or "None"
    )
    
    try:
        response = model.generate_content(
            prompt,
            generation_config={
                'temperature': 0.2,  # Lower temperature for consistent classification
                'max_output_tokens': 300,
            }
        )
        text = response.text.strip()
        
        # Remove markdown code fences if present
        if '```' in text:
            parts = text.split('```')
            for part in parts:
                if part.strip().startswith('json') or part.strip().startswith('{'):
                    text = part.replace('json', '').strip()
                    break
        
        result = json.loads(text.strip())
        return result
        
    except Exception as e:
        error_msg = str(e)
        
        # Check if quota exceeded - reraise to trigger model switch
        if '429' in error_msg or 'quota' in error_msg.lower() or 'resource_exhausted' in error_msg.lower():
            logger.warning(f"⚠️ Quota exceeded: {error_msg}")
            raise  # Reraise to trigger model switch
        
        # Other errors - log and skip
        logger.error(f"Failed to infer NTEE: {e}")
        if 'text' in locals():
            logger.error(f"Response text: {text}")
        return None


def repopulate_all_topics(models: List[str] = None):
    """Repopulate NTEE codes for all topics using LLM analysis with model fallback."""
    
    if not GEMINI_API_KEY:
        logger.error("❌ GEMINI_API_KEY not found in environment")
        logger.info("Please set GEMINI_API_KEY in your .env file")
        logger.info("Get a free key at: https://aistudio.google.com/apikey")
        return
    
    # Use default models if not specified
    if models is None:
        models = DEFAULT_MODELS
    
    # Configure Gemini
    genai.configure(api_key=GEMINI_API_KEY)
    
    logger.info("="*70)
    logger.info("NTEE REPOPULATION WITH MULTI-MODEL FALLBACK")
    logger.info("="*70)
    logger.info(f"Models to try: {', '.join(models)}")
    logger.info("")
    
    # Try each model in sequence
    for model_idx, model_name in enumerate(models, 1):
        logger.info(f"🤖 Attempting with model {model_idx}/{len(models)}: {model_name}")
        
        try:
            model = genai.GenerativeModel(model_name)
            
            # Run the repopulation with this model
            success = _repopulate_with_model(model, model_name)
            
            if success:
                logger.info(f"✅ Successfully completed with {model_name}")
                break
                
        except Exception as e:
            error_msg = str(e)
            
            # Check if quota exceeded
            if '429' in error_msg or 'quota' in error_msg.lower() or 'resource_exhausted' in error_msg.lower():
                logger.warning(f"⚠️ Quota exceeded for {model_name}")
                
                # If this is the last model, stop
                if model_idx == len(models):
                    logger.error("❌ All models exhausted - no more quotas available today")
                    logger.info("💡 Options:")
                    logger.info("   1. Run again tomorrow (quotas reset daily)")
                    logger.info("   2. Get API key with higher quotas")
                    logger.info("   3. Process completed topics are saved - script is resumable")
                    break
                else:
                    logger.info(f"   Switching to next model: {models[model_idx]}")
                    continue
            else:
                # Some other error
                logger.error(f"❌ Error with {model_name}: {e}")
                raise


def _repopulate_with_model(model, model_name: str) -> bool:
    """Repopulate topics using a specific model. Returns True if completed successfully."""
    
    logger.info("Connecting to database...")
    conn = psycopg2.connect(DATABASE_URL)
    
    try:
        with conn.cursor() as cur:
            # Get all topics
            cur.execute("""
                SELECT id, decision_id, topic, primary_theme, secondary_theme, headline
                FROM bronze_topics
                ORDER BY id
            """)
            
            all_topics = cur.fetchall()
            logger.info(f"Found {len(all_topics)} topics to reprocess with {model_name}")
            
            updated = 0
            errors = 0
            
            for idx, (topic_id, decision_id, topic, primary_theme, secondary_theme, headline) in enumerate(all_topics, 1):
                if idx % 10 == 0:
                    logger.info(f"Progress: {idx}/{len(all_topics)} ({idx/len(all_topics)*100:.1f}%) - Updated: {updated}, Errors: {errors}")
                
                logger.info(f"Processing topic {topic_id}: {topic}")
                
                try:
                    result = infer_ntee_codes(topic, primary_theme, secondary_theme, headline, model)
                    
                    if result:
                        cur.execute("""
                            UPDATE bronze_topics
                            SET 
                                ntee_code = %s,
                                ntee_major_group = %s,
                                ntee_category_label = %s,
                                secondary_ntee_code = %s,
                                secondary_ntee_major_group = %s,
                                secondary_ntee_category_label = %s
                            WHERE id = %s
                        """, (
                            result['primary_ntee_code'],
                            result['primary_ntee_major_group'],
                            result['primary_ntee_category_label'],
                            result.get('secondary_ntee_code'),
                            result.get('secondary_ntee_major_group'),
                            result.get('secondary_ntee_category_label'),
                            topic_id
                        ))
                        
                        logger.info(f"  ✅ Primary: {result['primary_ntee_code']} - {result['primary_ntee_major_group']}")
                        if result.get('secondary_ntee_code'):
                            logger.info(f"  ✅ Secondary: {result['secondary_ntee_code']} - {result['secondary_ntee_major_group']}")
                        logger.info(f"  Confidence: {result.get('confidence', 'unknown')}")
                        updated += 1
                        
                        # Commit every 10 records
                        if updated % 10 == 0:
                            conn.commit()
                            logger.info(f"💾 Committed {updated} updates")
                    else:
                        logger.warning(f"  ⚠️ Could not infer NTEE for topic {topic_id}")
                        errors += 1
                    
                    # Delay to respect free tier rate limits (15 RPM = 4 sec between requests)
                    time.sleep(4.5)
                    
                except Exception as e:
                    # Check if quota error - if so, raise to trigger model switch
                    error_msg = str(e)
                    if '429' in error_msg or 'quota' in error_msg.lower() or 'resource_exhausted' in error_msg.lower():
                        conn.commit()  # Save progress before switching
                        logger.warning(f"  ⚠️ Quota limit reached at topic {topic_id}")
                        logger.info(f"  💾 Saved {updated} updates before quota limit")
                        raise  # Trigger model switch
                    else:
                        logger.error(f"  ❌ Unexpected error: {e}")
                        errors += 1
                        continue
            
            conn.commit()
            logger.info(f"\n✅ Repopulation with {model_name} complete!")
            logger.info(f"  Updated: {updated}")
            logger.info(f"  Errors: {errors}")
            
            # Show final stats
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(ntee_code) as with_primary_ntee,
                    COUNT(secondary_ntee_code) as with_secondary_ntee,
                    ROUND(100.0 * COUNT(ntee_code) / COUNT(*), 1) as pct_primary,
                    ROUND(100.0 * COUNT(secondary_ntee_code) / COUNT(*), 1) as pct_secondary
                FROM bronze_topics
            """)
            total, primary, secondary, pct_primary, pct_secondary = cur.fetchone()
            logger.info(f"\n📊 Final stats:")
            logger.info(f"  Total topics: {total}")
            logger.info(f"  With primary NTEE: {primary} ({pct_primary}%)")
            logger.info(f"  With secondary NTEE: {secondary} ({pct_secondary}%)")
            
            # Show distribution
            cur.execute("""
                SELECT 
                    ntee_code,
                    ntee_major_group,
                    COUNT(*) as count,
                    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM bronze_topics WHERE ntee_code IS NOT NULL), 1) as pct
                FROM bronze_topics
                WHERE ntee_code IS NOT NULL
                GROUP BY ntee_code, ntee_major_group
                ORDER BY count DESC
                LIMIT 15
            """)
            
            logger.info(f"\n📋 Top 15 primary NTEE categories:")
            for code, group, count, pct in cur.fetchall():
                logger.info(f"  {code} - {group}: {count} ({pct}%)")
            
            # Show secondary NTEE distribution
            cur.execute("""
                SELECT 
                    secondary_ntee_code,
                    secondary_ntee_major_group,
                    COUNT(*) as count
                FROM bronze_topics
                WHERE secondary_ntee_code IS NOT NULL
                GROUP BY secondary_ntee_code, secondary_ntee_major_group
                ORDER BY count DESC
                LIMIT 10
            """)
            
            secondary_results = cur.fetchall()
            if secondary_results:
                logger.info(f"\n📋 Top secondary NTEE categories:")
                for code, group, count in secondary_results:
                    logger.info(f"  {code} - {group}: {count}")
            else:
                logger.info(f"\n📋 No secondary NTEE codes assigned")
            
            return True  # Completed successfully
                
    except Exception as e:
        logger.error(f"❌ Repopulation failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()
        logger.info("Database connection closed")


if __name__ == "__main__":
    repopulate_all_topics()
