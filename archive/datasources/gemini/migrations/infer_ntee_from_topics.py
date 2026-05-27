#!/usr/bin/env python3
"""
Use Google Gemini to infer NTEE codes for topics without organization links.

For topics where we couldn't extract NTEE from organizations, use the LLM
to infer the most appropriate NTEE code based on the topic and theme.
"""

import psycopg2
import os
import logging
import google.generativeai as genai
from typing import Optional, Dict
import json

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Database and API configuration
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'password')
DATABASE_URL = os.getenv('LOCAL_BRONZE_DATABASE_URL', f'postgresql://postgres:{POSTGRES_PASSWORD}@localhost:5433/open_navigator_bronze')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# NTEE code mapping
NTEE_PROMPT = """Given a policy topic and theme, determine the most appropriate NTEE (National Taxonomy of Exempt Entities) code.

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
W - Public Policy
X - Religion
Y - Mutual Benefit
Z - Unknown

Topic: {topic}
Theme: {theme}
Headline: {headline}

Respond ONLY with a JSON object in this exact format (no markdown, no explanation):
{{"ntee_code": "X", "ntee_major_group": "Category Name", "ntee_category_label": "Category Name", "confidence": "high|medium|low"}}

If this is a general governance/administrative topic with no specific cause area, use:
{{"ntee_code": "W", "ntee_major_group": "Public Policy", "ntee_category_label": "Public Policy", "confidence": "high"}}
"""


def infer_ntee(topic: str, theme: str, headline: str, model) -> Optional[Dict]:
    """Use Gemini to infer NTEE code from topic text."""
    
    prompt = NTEE_PROMPT.format(
        topic=topic,
        theme=theme,
        headline=headline
    )
    
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Remove markdown code fences if present
        if text.startswith('```'):
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
            text = '```'.join(text.split('```')[:-1]) if '```' in text else text
        
        result = json.loads(text.strip())
        return result
        
    except Exception as e:
        logger.error(f"Failed to infer NTEE: {e}")
        return None


def infer_missing_ntee():
    """Infer NTEE codes for topics without organization links."""
    
    if not GEMINI_API_KEY:
        logger.error("❌ GEMINI_API_KEY not found in environment")
        logger.info("Get a free key at: https://aistudio.google.com/apikey")
        return
    
    # Configure Gemini
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')  # 1,500/day free tier
    
    logger.info("Connecting to database...")
    conn = psycopg2.connect(DATABASE_URL)
    
    try:
        with conn.cursor() as cur:
            # Find topics without NTEE
            cur.execute("""
                SELECT id, decision_id, topic, primary_theme, headline
                FROM bronze_topics
                WHERE ntee_code IS NULL
                ORDER BY id
            """)
            
            topics_to_process = cur.fetchall()
            logger.info(f"Found {len(topics_to_process)} topics without NTEE codes")
            
            if not topics_to_process:
                logger.info("✅ All topics already have NTEE codes!")
                return
            
            updated = 0
            for topic_id, decision_id, topic, theme, headline in topics_to_process:
                logger.info(f"Processing topic {topic_id}: {topic}")
                
                result = infer_ntee(topic, theme, headline or "", model)
                
                if result:
                    cur.execute("""
                        UPDATE bronze_topics
                        SET 
                            ntee_code = %s,
                            ntee_major_group = %s,
                            ntee_category_label = %s
                        WHERE id = %s
                    """, (
                        result['ntee_code'],
                        result['ntee_major_group'],
                        result['ntee_category_label'],
                        topic_id
                    ))
                    
                    logger.info(f"  ✅ Assigned: {result['ntee_code']} - {result['ntee_major_group']} (confidence: {result.get('confidence', 'unknown')})")
                    updated += 1
                else:
                    logger.warning(f"  ⚠️ Could not infer NTEE for topic {topic_id}")
            
            conn.commit()
            logger.info(f"\n✅ Updated {updated} topics with inferred NTEE codes")
            
            # Show final stats
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(ntee_code) as with_ntee,
                    ROUND(100.0 * COUNT(ntee_code) / COUNT(*), 1) as pct
                FROM bronze_topics
            """)
            total, with_ntee, pct = cur.fetchone()
            logger.info(f"\n📊 Final stats:")
            logger.info(f"  Total topics: {total}")
            logger.info(f"  With NTEE: {with_ntee} ({pct}%)")
            
    except Exception as e:
        logger.error(f"❌ Inference failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()
        logger.info("Database connection closed")


if __name__ == "__main__":
    infer_missing_ntee()
