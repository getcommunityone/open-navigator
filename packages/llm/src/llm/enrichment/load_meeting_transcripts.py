#!/usr/bin/env python3
"""
Gemini Meeting Video Analysis - Policy Frame Extraction

This script:
1. Fetches recent meeting videos from event (most recent N per channel)
2. Filters for channels with known channel_type OR in localview
3. Passes YouTube video URLs directly to Gemini (no transcript needed)
4. Analyzes using Gemini AI with policy_analysis.md prompt
5. Stores structured results in bronze_events_analysis_ai table
6. Supports incremental processing (skip already analyzed)

By default: Analyzes the 5 most recent meetings per channel across all states.

Usage:
    # Analyze most recent 5 meetings per channel (all states, known channels)
    python -m llm.enrichment.load_meeting_transcripts
    
    # Analyze only priority states (AL, GA, IN, MA, WA, WI)
    python -m llm.enrichment.load_meeting_transcripts --priority-states
    
    # Analyze specific state(s)
    python -m llm.enrichment.load_meeting_transcripts --states MA
    python -m llm.enrichment.load_meeting_transcripts --states MA,WI,AL
    
    # Analyze more meetings per channel
    python -m llm.enrichment.load_meeting_transcripts --meetings-per-channel 10
    
    # Force re-analysis (skip incremental check)
    python -m llm.enrichment.load_meeting_transcripts --force
    
    # Dry run (show what would be analyzed)
    python -m llm.enrichment.load_meeting_transcripts --dry-run
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any
import argparse
import json
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parents[5]))

import psycopg2
from psycopg2.extras import RealDictCursor, execute_batch
from loguru import logger
from dotenv import load_dotenv
import re

try:
    import google.generativeai as genai
except ImportError:
    logger.error("google-generativeai not installed. Run: pip install google-generativeai")
    sys.exit(1)

# Load environment variables
load_dotenv()

# Database connection
DATABASE_URL = os.getenv('NEON_DATABASE_URL_DEV', 'postgresql://postgres:password@localhost:5433/open_navigator')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Prompt path
PROMPTS_DIR = Path(__file__).parents[5] / 'prompts'
POLICY_ANALYSIS_PROMPT = PROMPTS_DIR / 'policy_analysis.md'

# Priority states
PRIORITY_STATES = ['AL', 'GA', 'IN', 'MA', 'WA', 'WI']


class MeetingTranscriptAnalyzer:
    """Analyze meeting transcripts using Gemini AI."""
    
    def __init__(
        self,
        database_url: str,
        gemini_api_key: str,
        meetings_per_channel: int = 3,
        force_reanalyze: bool = False,
        delay_seconds: float = 2.0,
        model_name: str = 'gemini-3.1-flash-lite-preview'
    ):
        self.database_url = database_url
        self.gemini_api_key = gemini_api_key
        self.meetings_per_channel = meetings_per_channel
        self.force_reanalyze = force_reanalyze
        self.delay_seconds = delay_seconds
        self.model_name = model_name
        
        # Configure Gemini
        genai.configure(api_key=self.gemini_api_key)
        # Initialize the selected model
        self.model = genai.GenerativeModel(self.model_name)
        
        # Load prompt template
        self.prompt_template = self._load_prompt()
        
        logger.info(f"✅ Gemini API configured (using {self.model_name})")
        logger.info(f"✅ Loaded policy analysis prompt from {POLICY_ANALYSIS_PROMPT}")
    
    def _load_prompt(self) -> str:
        """Load the policy analysis prompt from markdown file."""
        if not POLICY_ANALYSIS_PROMPT.exists():
            raise FileNotFoundError(f"Prompt file not found: {POLICY_ANALYSIS_PROMPT}")
        
        with open(POLICY_ANALYSIS_PROMPT, 'r') as f:
            return f.read()
    
    def create_table(self):
        """Create bronze_events_analysis_ai table if it doesn't exist."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS bronze.bronze_events_analysis_ai (
            id SERIAL PRIMARY KEY,
            -- Soft reference to civic_event.legacy_id (the integer PK preserved by migration 048).
            -- No FK constraint declared — bronze.bronze_events_analysis_ai pre-dates the rename
            -- and adding a FK to an existing table risks blocking writes during the rename.
            event_id INTEGER NOT NULL,
            video_id VARCHAR(20) NOT NULL,
            analysis_type VARCHAR(50) DEFAULT 'policy_frame_analysis',
            ai_model VARCHAR(100) DEFAULT 'gemini-1.5-flash',
            prompt_version VARCHAR(50) DEFAULT 'v1.0',
            
            -- Raw AI response
            raw_response TEXT,
            
            -- Structured JSON analysis (from policy_analysis.md)
            structured_analysis JSONB,
            
            -- Human-readable summary
            summary_text TEXT,
            
            -- Mermaid timeline
            timeline_mermaid TEXT,
            
            -- Processing metadata
            processing_time_seconds FLOAT,
            tokens_used INTEGER,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            UNIQUE(event_id, analysis_type, ai_model)
        );
        
        CREATE INDEX IF NOT EXISTS idx_events_ai_event_id ON bronze.bronze_events_analysis_ai(event_id);
        CREATE INDEX IF NOT EXISTS idx_events_ai_video_id ON bronze.bronze_events_analysis_ai(video_id);
        CREATE INDEX IF NOT EXISTS idx_events_ai_created ON bronze.bronze_events_analysis_ai(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_events_ai_analysis_type ON bronze.bronze_events_analysis_ai(analysis_type);
        """
        
        with psycopg2.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(create_table_sql)
            conn.commit()
        
        logger.info("✅ bronze_events_analysis_ai table created/verified")
    
    def cleanup_null_records(self):
        """Delete existing records where raw_response is NULL (failed API calls)."""
        delete_sql = """
        DELETE FROM bronze.bronze_events_analysis_ai
        WHERE raw_response IS NULL
        """
        
        with psycopg2.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(delete_sql)
                deleted_count = cur.rowcount
            conn.commit()
        
        if deleted_count > 0:
            logger.info(f"🧹 Cleaned up {deleted_count} records with null raw_response")
        else:
            logger.info("✅ No null records to clean up")
    
    def get_meetings_to_analyze(
        self,
        states_filter: Optional[List[str]] = None,
        limit_per_channel: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get recent meetings to analyze from event.
        
        Returns the most recent N meetings per channel (no transcripts needed).
        Filters for channels with:
          - Known channel_type (not 'unknown'), OR
          - In localview (curated channels)
        Requires YouTube video URLs only.
        If states_filter is None, searches all states.
        Ordered by event_date DESC within each channel.
        """
        # Build query to get top N meetings per channel
        query = """
        WITH ranked_meetings AS (
            SELECT
                -- OCD-aligned column names after migration 048 (event_* -> name/description/start_date,
                -- meeting_type -> classification). Aliased back to the old names so downstream code that
                -- reads result dicts keyed by 'event_id' / 'event_title' / 'event_date' still works.
                e.legacy_id     AS event_id,
                e.name          AS event_title,
                e.description   AS event_description,
                e.start_date    AS event_date,
                e.event_time,
                e.video_url,
                e.channel_id,
                e.channel_url,
                e.jurisdiction_name,
                e.jurisdiction_type,
                e.state         AS state_code,    -- state column holds 2-letter code post-fold
                e.state,
                e.city,
                e.classification AS meeting_type,
                c.channel_type,
                c.in_localview,
                ROW_NUMBER() OVER (
                    PARTITION BY e.channel_id
                    ORDER BY e.start_date DESC, e.event_time DESC NULLS LAST
                ) as rn
            FROM public.civic_event e
            INNER JOIN intermediate.int_events_channels_enriched c
                ON e.channel_id = c.channel_id
            WHERE e.video_url IS NOT NULL
              AND e.video_url LIKE 'https://www.youtube.com/watch%%'
              AND (
                  (c.channel_type IS NOT NULL AND c.channel_type != 'unknown')
                  OR c.in_localview = true
              )
        """
        
        # Build parameter list
        params = []
        
        # Add state filter if provided (inside the CTE)
        if states_filter:
            # state column post-migration-048 holds either a 2-letter code or full name
            # depending on row provenance; callers pass 2-letter codes. This filter only
            # matches rows where state happens to be stored as the code.
            query += "              AND e.state = ANY(%s)\n"
            params.append(states_filter)
        
        # Close the CTE and add the main query
        query += """        )
        SELECT * FROM ranked_meetings 
        WHERE rn <= %s
        """
        params.append(limit_per_channel)
        
        if not self.force_reanalyze:
            # Add filter to skip already analyzed
            query += """
              AND NOT EXISTS (
                SELECT 1 FROM bronze.bronze_events_analysis_ai ai
                WHERE ai.event_id = ranked_meetings.event_id
                  AND ai.analysis_type = 'policy_frame_analysis'
                  AND ai.error_message IS NULL
            )
            """
        
        query += """
        ORDER BY state_code, channel_id, event_date DESC
        """
        
        conn = psycopg2.connect(self.database_url)
        cursor = conn.cursor()
        
        try:
            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            return results
        finally:
            cursor.close()
            conn.close()
    
    def analyze_meeting(self, meeting: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a single meeting using Gemini AI with video URL.
        
        Returns structured analysis with JSON, summary, and timeline.
        """
        logger.info(f"🤖 Analyzing: {meeting['title'][:70]}...")
        logger.info(f"   📍 {meeting['jurisdiction_name']}, {meeting['state_code'] or 'UNKNOWN'}")
        logger.info(f"   📅 {meeting['event_date']}")
        logger.info(f"   📺 {meeting['video_url']}")
        
        # Build the prompt with video URL
        prompt_parts = self._build_analysis_prompt(meeting)
        
        # Call Gemini API with video URL
        start_time = time.time()
        
        try:
            response = self.model.generate_content(
                prompt_parts,
                generation_config={
                    'temperature': 0.2,  # Lower temperature for more consistent JSON
                    'max_output_tokens': 8192,
                }
            )
            
            processing_time = time.time() - start_time
            
            # Extract response text
            raw_response = response.text
            
            # Parse the three-document response
            parsed = self._parse_response(raw_response)
            
            logger.info(f"   ✅ Analysis complete ({processing_time:.1f}s)")
            
            return {
                'raw_response': raw_response,
                'structured_analysis': parsed['json_analysis'],
                'summary_text': parsed['summary'],
                'timeline_mermaid': parsed['timeline'],
                'processing_time_seconds': processing_time,
                'tokens_used': response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else None,
                'error_message': None
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"   ✗ Analysis failed: {e}")
            
            # Check if this is a quota error (429)
            if '429' in error_msg or 'quota' in error_msg.lower():
                logger.warning("   ⚠️ QUOTA EXCEEDED - This is a daily limit error")
                # Re-raise to stop processing
                raise
            
            return {
                'raw_response': None,
                'structured_analysis': None,
                'summary_text': None,
                'timeline_mermaid': None,
                'processing_time_seconds': time.time() - start_time,
                'tokens_used': None,
                'error_message': error_msg
            }
    
    def _build_analysis_prompt(self, meeting: Dict[str, Any]) -> list:
        """Build the complete prompt for Gemini with video URL."""
        
        # Extract meeting context
        context = f"""
# Meeting Video for Analysis

**Meeting Details:**
- **Body:** {meeting['jurisdiction_name']} {meeting.get('jurisdiction_type', '')}
- **Location:** {meeting.get('city', '')}, {meeting.get('state') or 'Unknown'} ({meeting['state_code'] or 'N/A'})
- **Date:** {meeting['event_date']}
- **Time:** {meeting.get('event_time', 'N/A')}
- **Meeting Type:** {meeting.get('meeting_type', 'Unknown')}
- **Title:** {meeting['title']}

---

"""
        
        # Combine context with policy analysis prompt
        full_prompt = context + self.prompt_template
        
        # Return as list: [video_url, text_prompt] for multimodal input
        return [meeting['video_url'], full_prompt]
    
    def _extract_json_robust(self, text: str) -> str:
        """
        Robustly extract JSON from text that might have markdown fences or other wrappers.
        Returns cleaned JSON string ready for parsing.
        """
        # Remove markdown code fences
        if '```json' in text:
            # Extract content between ```json and ```
            match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
            if match:
                text = match.group(1)
        elif text.startswith('```'):
            # Remove generic code fences
            lines = text.split('\n')
            if len(lines) > 2:
                text = '\n'.join(lines[1:-1])
        
        # Find the first { and last } to extract just the JSON object
        first_brace = text.find('{')
        last_brace = text.rfind('}')
        
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            text = text[first_brace:last_brace + 1]
        
        return text.strip()
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse the three-document response from Gemini.
        
        Expected format:
        1. JSON object
        2. ---DOCUMENT_BREAK---
        3. Human-readable summary
        4. ---DOCUMENT_BREAK---
        5. Mermaid timeline
        """
        parts = response_text.split('---DOCUMENT_BREAK---')
        
        json_analysis = None
        summary = None
        timeline = None
        
        if len(parts) >= 1:
            # Extract JSON (first part)
            try:
                # Use robust JSON extraction
                json_text = self._extract_json_robust(parts[0])
                
                # Try to parse
                json_analysis = json.loads(json_text)
                
            except json.JSONDecodeError as e:
                logger.warning(f"   ⚠️ JSON parsing failed: {e}")
                logger.warning(f"   📄 First 500 chars: {parts[0][:500]}")
                logger.warning(f"   📄 Last 200 chars: {parts[0][-200:]}")
                
                # Save raw text for manual inspection
                json_analysis = {
                    'error': 'Failed to parse JSON',
                    'error_details': str(e),
                    'raw_preview': parts[0][:1000]
                }
        
        if len(parts) >= 2:
            # Human-readable summary (second part)
            summary = parts[1].strip()
        
        if len(parts) >= 3:
            # Mermaid timeline (third part)
            timeline = parts[2].strip()
        
        return {
            'json_analysis': json_analysis,
            'summary': summary,
            'timeline': timeline
        }
    
    def save_analysis(self, meeting: Dict[str, Any], analysis: Dict[str, Any]) -> bool:
        """Save analysis results to bronze_events_analysis_ai table.
        
        Returns:
            True if saved, False if skipped (due to null raw_response)
        """
        
        # Skip saving if API call failed and there's no raw_response
        if analysis['raw_response'] is None:
            logger.warning(f"   ⚠️ Skipping database save - no raw_response (API call failed)")
            return False
        
        # Extract video_id from YouTube URL
        video_id = meeting['video_url'].split('v=')[-1].split('&')[0] if 'v=' in meeting['video_url'] else 'unknown'

        structured = analysis.get('structured_analysis')
        if isinstance(structured, dict) and video_id != 'unknown':
            from llm.gemini.meeting_date_qa import qa_recorded_video_meeting_date

            structured, date_warnings = qa_recorded_video_meeting_date(
                structured,
                video_id=video_id,
                title=str(meeting.get('title') or ''),
                published_at=meeting.get('event_date'),
            )
            analysis['structured_analysis'] = structured
            for w in date_warnings:
                logger.warning(w)
        
        insert_sql = """
        INSERT INTO bronze.bronze_events_analysis_ai (
            event_id, video_id, analysis_type, ai_model, prompt_version,
            raw_response, structured_analysis, summary_text, timeline_mermaid,
            processing_time_seconds, tokens_used, error_message
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s
        )
        ON CONFLICT (event_id, analysis_type, ai_model)
        DO UPDATE SET
            raw_response = EXCLUDED.raw_response,
            structured_analysis = EXCLUDED.structured_analysis,
            summary_text = EXCLUDED.summary_text,
            timeline_mermaid = EXCLUDED.timeline_mermaid,
            processing_time_seconds = EXCLUDED.processing_time_seconds,
            tokens_used = EXCLUDED.tokens_used,
            error_message = EXCLUDED.error_message,
            updated_at = CURRENT_TIMESTAMP
        """
        
        with psycopg2.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(insert_sql, (
                    meeting['event_id'],
                    video_id,
                    'policy_frame_analysis',
                    self.model_name,
                    'v1.0',
                    analysis['raw_response'],
                    json.dumps(analysis['structured_analysis']) if analysis['structured_analysis'] else None,
                    analysis['summary_text'],
                    analysis['timeline_mermaid'],
                    analysis['processing_time_seconds'],
                    analysis['tokens_used'],
                    analysis['error_message']
                ))
            conn.commit()
        
        logger.info(f"   💾 Saved analysis to database")
        return True
    
    def run(self, states_filter: Optional[List[str]] = None, dry_run: bool = False):
        """Main processing loop."""
        
        logger.info("=" * 70)
        logger.info("GEMINI MEETING TRANSCRIPT ANALYSIS")
        logger.info("=" * 70)
        logger.info(f"States: {states_filter if states_filter else 'ALL'}")
        logger.info(f"Channels: Known channel_type OR in_localview")
        logger.info(f"Meetings per channel: {self.meetings_per_channel} (most recent)")
        logger.info(f"Force re-analyze: {self.force_reanalyze}")
        logger.info(f"Dry run: {dry_run}")
        logger.info("")
        
        # Create table
        self.create_table()
        
        # Clean up any existing null records
        self.cleanup_null_records()
        
        # Get meetings to analyze
        logger.info("🔍 Finding meetings to analyze...")
        meetings = self.get_meetings_to_analyze(
            states_filter=states_filter,
            limit_per_channel=self.meetings_per_channel
        )
        
        if not meetings:
            logger.info("✅ No meetings to analyze (all done or no transcripts available)")
            return
        
        logger.info(f"📋 Found {len(meetings)} meetings to analyze")
        logger.info("")
        
        # Group by state for reporting
        by_state = {}
        for m in meetings:
            state = m['state_code']
            by_state.setdefault(state, []).append(m)
        
        for state, state_meetings in sorted(by_state.items(), key=lambda x: (x[0] is None, x[0] or '')):
            logger.info(f"   {state if state else 'UNKNOWN'}: {len(state_meetings)} meetings")
        
        logger.info("")
        
        if dry_run:
            logger.info("🏃 DRY RUN - Showing what would be analyzed:")
            for i, meeting in enumerate(meetings, 1):
                logger.info(f"   [{i}] {meeting['state_code'] or 'UNKNOWN'} - {meeting['jurisdiction_name']}")
                logger.info(f"       {meeting['title'][:70]}")
                logger.info(f"       {meeting['event_date']} - {meeting['video_url']}")
            return
        
        # Process each meeting
        success_count = 0
        error_count = 0
        quota_exceeded = False
        
        for i, meeting in enumerate(meetings, 1):
            logger.info(f"\n[{i}/{len(meetings)}] Processing meeting...")
            
            try:
                # Analyze
                analysis = self.analyze_meeting(meeting)
                
                # Save (only if we have valid data)
                saved = self.save_analysis(meeting, analysis)
                
                # Count results
                if analysis['error_message'] or not saved:
                    error_count += 1
                else:
                    success_count += 1
                
                # Rate limiting delay
                if i < len(meetings):
                    logger.info(f"   ⏳ Waiting {self.delay_seconds}s before next request...")
                    time.sleep(self.delay_seconds)
                
            except Exception as e:
                error_msg = str(e)
                
                # Check for quota errors
                if '429' in error_msg or 'quota' in error_msg.lower():
                    logger.error(f"   ✗ QUOTA EXCEEDED: {e}")
                    quota_exceeded = True
                    error_count += 1
                    break  # Stop processing
                else:
                    logger.error(f"   ✗ Failed to process meeting: {e}")
                    error_count += 1
        
        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("ANALYSIS COMPLETE")
        logger.info("=" * 70)
        logger.info(f"✅ Successful: {success_count}")
        logger.info(f"✗ Errors: {error_count}")
        logger.info(f"📊 Total processed: {success_count + error_count} of {len(meetings)} found")
        
        if quota_exceeded:
            logger.warning("\n" + "⚠️  " * 20)
            logger.warning("QUOTA EXCEEDED - Daily limit reached")
            logger.warning("⚠️  " * 20)
            logger.warning("")
            logger.warning("📊 Gemini Free Tier Limits:")
            logger.warning(f"   • Model: {self.model_name}")
            logger.warning("   • Reset: Daily at midnight Pacific Time")
            logger.warning("")
            logger.warning("🔧 Solutions:")
            logger.warning("   1. Wait until tomorrow (quota resets at midnight PT)")
            logger.warning("   2. Try Flash-Lite model: --model gemini-2.5-flash-lite (1000 req/day)")
            logger.warning("   3. Upgrade to paid tier: https://ai.google.dev/pricing")
            logger.warning("   4. Process fewer meetings: --meetings-per-channel 1")
            logger.warning("")
            logger.warning(f"💡 Remaining to process: {len(meetings) - (success_count + error_count)} meetings")
            logger.warning("   Run the same command tomorrow to continue from where you left off")
        
        logger.info("")
        logger.info("💡 Query results:")
        logger.info("   SELECT * FROM bronze.bronze_events_analysis_ai ORDER BY created_at DESC LIMIT 10;")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Analyze meeting transcripts using Gemini AI with policy frame analysis'
    )
    
    parser.add_argument(
        '--states',
        type=str,
        help='Comma-separated state codes (default: all states with known channel types)'
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
        help='Delay between API requests in seconds (default: 5.0 for free tier 15 req/min limit)'
    )
    
    parser.add_argument(
        '--model',
        type=str,
        default='gemini-3.1-flash-lite-preview',
        choices=[
            'gemini-3.1-flash-lite-preview',
            'gemini-2.0-flash-lite',
            'gemini-2.5-flash-lite',
            'gemini-flash-lite-latest',
            'gemini-2.5-flash',
            'gemini-2.0-flash',
            'gemini-flash-latest',
            'gemini-1.5-flash',
            'gemini-1.5-pro'
        ],
        help='Gemini model to use (default: gemini-3.1-flash-lite-preview - newest preview with high free quota)'
    )
    
    args = parser.parse_args()
    
    # Check API key
    if not GEMINI_API_KEY:
        logger.error("❌ GEMINI_API_KEY not found in environment variables")
        logger.info("\n💡 To fix:")
        logger.info("   1. Get a Gemini API key: https://makersuite.google.com/app/apikey")
        logger.info("   2. Add to .env file: GEMINI_API_KEY=your_key_here")
        return 1
    
    # Parse states filter
    states_filter = None
    if args.states:
        states_filter = [s.strip().upper() for s in args.states.split(',')]
    elif args.priority_states:
        states_filter = PRIORITY_STATES
        logger.info(f"Using priority states: {', '.join(PRIORITY_STATES)}")
    
    # Show model info
    model_quotas = {
        'gemini-3.1-flash-lite-preview': '1,500 requests/day (preview - free tier) ⭐ RECOMMENDED',
        'gemini-2.0-flash-lite': '1,500 requests/day (free tier)',
        'gemini-2.5-flash-lite': '1,000 requests/day (free tier)',
        'gemini-flash-lite-latest': '1,000+ requests/day (free tier)',
        'gemini-2.5-flash': '1,000 requests/day (free tier)',
        'gemini-2.0-flash': '1,000 requests/day (free tier)',
        'gemini-flash-latest': '20 requests/day (free tier)',
        'gemini-1.5-flash': '20 requests/day (free tier)',
        'gemini-1.5-pro': 'Paid tier only'
    }
    logger.info(f"Using model: {args.model}")
    logger.info(f"Quota: {model_quotas.get(args.model, 'Unknown')}")
    logger.info("")
    
    # Initialize analyzer
    analyzer = MeetingTranscriptAnalyzer(
        database_url=DATABASE_URL,
        gemini_api_key=GEMINI_API_KEY,
        meetings_per_channel=args.meetings_per_channel,
        force_reanalyze=args.force,
        delay_seconds=args.delay,
        model_name=args.model
    )
    
    try:
        analyzer.run(states_filter=states_filter, dry_run=args.dry_run)
        return 0
    except Exception as e:
        logger.error(f"✗ Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
