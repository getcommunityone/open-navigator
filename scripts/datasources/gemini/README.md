# Gemini AI Meeting Analysis

Scripts for analyzing government meeting transcripts using Google Gemini AI with policy frame analysis.

**✅ 100% FREE** - Uses Gemini 1.5 Flash free tier (15 requests/min, 1,500/day, 1M tokens/day)

## Overview

This directory contains scripts that use Google's Gemini AI (FREE TIER) to perform deep policy analysis on government meeting transcripts. The analysis extracts:

- **Competing problem frames** - How stakeholders diagnose causes and assign responsibility
- **Moral value conflicts** - Tensions between collective safety vs individual liberty, equity vs efficiency
- **Power dynamics** - Who influenced decisions, whose interests advanced/constrained
- **Financial impacts** - Dollar amounts and budget implications
- **Decision timelines** - Chronological flow of events

## Scripts

### Core Analysis

#### `analyze_meeting_transcripts.py`

Main script for analyzing meeting transcripts with Gemini AI.

**What it does:**
1. Fetches recent meetings from `event` (priority states: AL, GA, IN, MA, WA, WI)
2. Filters for known channel types (municipal, county, school) OR channels in localview
3. Gets transcripts from `events_text_search`
4. Analyzes using Gemini 1.5 Flash (FREE tier) with policy_analysis.md prompt
5. Stores structured JSON, human-readable summary, and Mermaid timeline in `events_text_ai`
6. Supports incremental processing (skips already analyzed)

**Usage:**

```bash
# Setup (first time)
pip install google-generativeai

# Get FREE API key from https://makersuite.google.com/app/apikey
# Add to .env file:
echo "GEMINI_API_KEY=your_key_here" >> .env

# ✅ All analysis is FREE (within generous daily limits)

# Analyze most recent 5 meetings per channel (default)
python scripts/datasources/gemini/analyze_meeting_transcripts.py

# Analyze specific state
python scripts/datasources/gemini/analyze_meeting_transcripts.py --states MA

# Analyze more meetings per channel
python scripts/datasources/gemini/analyze_meeting_transcripts.py --meetings-per-channel 10

# Force re-analysis (ignore previously analyzed)
python scripts/datasources/gemini/analyze_meeting_transcripts.py --force

# Dry run (see what would be analyzed)
python scripts/datasources/gemini/analyze_meeting_transcripts.py --dry-run

# Multiple states
python scripts/datasources/gemini/analyze_meeting_transcripts.py --states "MA,WI,GA"
```

#### `extract_to_bronze.py`

Extract structured AI analysis to Bronze tables for multi-model comparison.

**What it does:**
1. Reads `events_text_ai.structured_analysis` JSON column
2. Extracts entities: people, organizations, decisions, bills, topics, causes
3. Loads into normalized Bronze tables in separate database
4. Supports multiple AI models extracting the same decision

**Usage:**

```bash
# Create bronze database and tables, load all data
python scripts/datasources/gemini/extract_to_bronze.py

# Just create tables (no data load)
python scripts/datasources/gemini/extract_to_bronze.py --create-tables-only

# Load data without recreating tables
python scripts/datasources/gemini/extract_to_bronze.py --skip-create-tables
```

#### `compare_model_extractions.py`

Compare how different AI models extracted the same meeting decision.

**Usage:**

```bash
# Summary of all multi-model extractions
python scripts/datasources/gemini/compare_model_extractions.py --summary

# Compare specific event
python scripts/datasources/gemini/compare_model_extractions.py --event-id 192614

# Compare specific models
python scripts/datasources/gemini/compare_model_extractions.py --event-id 192614 --models gemini-1.5-flash gpt-4
```

#### `moa_synthesize.py` ⭐

**NEW** - Mixture-of-Agents synthesis to merge multiple model extractions into consensus.

**What it does:**
1. Gets all model extractions of the same decision from bronze
2. Uses powerful "aggregator" model (GPT-4o or Gemini Pro) to synthesize
3. Identifies consensus facts, contradictions, and best parts from each model
4. Stores synthesis back to bronze with model name `moa-{aggregator}`

**Usage:**

```bash
# Synthesize specific decision with GPT-4o
python scripts/datasources/gemini/moa_synthesize.py --event-id 192614 --decision-id D001

# Use Gemini Pro as aggregator
python scripts/datasources/gemini/moa_synthesize.py --event-id 192614 --decision-id D001 --aggregator gemini-pro

# Synthesize all decisions for an event
python scripts/datasources/gemini/moa_synthesize.py --event-id 192614 --all

# Dry run (see prompt without calling API)
python scripts/datasources/gemini/moa_synthesize.py --event-id 192614 --decision-id D001 --dry-run
```

**Why use MoA?**
- Combines strengths of multiple models (better than any single model)
- Identifies high vs low confidence facts
- Resolves contradictions systematically
- Industry best practice for AI evaluation in 2026

### Supporting Scripts

### One-Time & Migration Scripts

Migration scripts and one-time utilities are located in the `migrations/` subfolder. These include:

- Database schema migrations (multi-model support, NTEE fields)
- Data backfill scripts (NTEE codes, organization IDs)
- Cleanup utilities

**See [migrations/README.md](migrations/README.md) for details.**

These scripts are **not part of the regular workflow** and should only be run when:
- Setting up a fresh database
- Applying schema changes
- Backfilling historical data

```bash
# Example: Apply multi-model support migration
python scripts/datasources/gemini/migrations/migrate_multimodel_support.py

# Example: Backfill NTEE codes
python scripts/datasources/gemini/migrations/repopulate_ntee_codes.py
```

## Database Schema

### `events_text_ai` Table

Stores AI analysis results:

```sql
CREATE TABLE events_text_ai (
    id SERIAL PRIMARY KEY,
    event_id INTEGER REFERENCES event(event_id),
    video_id VARCHAR(20),
    analysis_type VARCHAR(50) DEFAULT 'policy_frame_analysis',
    ai_model VARCHAR(100) DEFAULT 'gemini-1.5-flash',
    
    -- Analysis outputs
    structured_analysis JSONB,   -- JSON from policy_analysis.md
    summary_text TEXT,            -- Human-readable summary
    timeline_mermaid TEXT,        -- Mermaid timeline diagram
    
    -- Metadata
    processing_time_seconds FLOAT,
    tokens_used INTEGER,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Bronze Tables (Multi-Model Extraction)

Bronze layer stores normalized extractions for comparison across AI models:

```sql
-- Bronze Decisions (multi-model support)
CREATE TABLE bronze_decisions (
    id SERIAL PRIMARY KEY,
    source_event_id INTEGER,
    source_ai_model VARCHAR(100),  -- e.g., 'gemini-1.5-flash', 'gpt-4', 'moa-gpt-4o'
    decision_id VARCHAR(255),
    headline TEXT,
    decision_statement TEXT,
    outcome VARCHAR(50),
    primary_theme VARCHAR(100),
    ntee_code VARCHAR(10),
    arguments_for JSONB,
    arguments_against JSONB,
    vote_tally JSONB,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Multi-model support: same decision can be extracted by multiple models
    UNIQUE(source_event_id, decision_id, source_ai_model)
);

-- Bronze Contacts, Organizations, Bills, Topics, Causes (similar pattern)
-- All support multiple model extractions with source_ai_model column
```

**Key feature:** The `source_ai_model` column + UNIQUE constraint allows storing:
- Same decision extracted by Gemini 1.5 Flash
- Same decision extracted by GPT-4
- Same decision extracted by Claude 3
- Synthesized version from MoA (`moa-gpt-4o`)

## Query Results

```sql
-- View recent analyses
SELECT 
    e.event_title,
    e.jurisdiction_name,
    e.state_code,
    e.event_date,
    ai.ai_model,
    ai.processing_time_seconds,
    ai.created_at
FROM events_text_ai ai
JOIN event e ON ai.event_id = e.event_id
ORDER BY ai.created_at DESC
LIMIT 10;

-- Get structured JSON analysis
SELECT 
    e.event_title,
    ai.structured_analysis->'meeting'->'body_name' as body,
    jsonb_array_length(ai.structured_analysis->'decisions') as decision_count,
    ai.summary_text
FROM events_text_ai ai
JOIN event e ON ai.event_id = e.event_id
WHERE ai.error_message IS NULL;

-- Extract frame analysis from JSON
SELECT 
    e.event_title,
    decision->>'topic' as topic,
    decision->'frame_analysis'->'dominant_frame'->>'frame_label' as dominant_frame,
    decision->'frame_analysis'->'counter_frames'->0->>'frame_label' as counter_frame
FROM events_text_ai ai
JOIN event e ON ai.event_id = e.event_id,
LATERAL jsonb_array_elements(ai.structured_analysis->'decisions') as decision
WHERE ai.error_message IS NULL;
```

### Multi-Model Comparison Queries

```sql
-- Find decisions extracted by multiple models
SELECT 
    source_event_id,
    decision_id,
    COUNT(DISTINCT source_ai_model) as num_models,
    array_agg(DISTINCT source_ai_model) as models
FROM bronze_decisions
GROUP BY source_event_id, decision_id
HAVING COUNT(DISTINCT source_ai_model) > 1
ORDER BY num_models DESC;

-- Compare specific decision across models
SELECT 
    source_ai_model,
    headline,
    outcome,
    primary_theme,
    ntee_code,
    json_array_length(arguments_for) as num_args_for,
    json_array_length(arguments_against) as num_args_against
FROM bronze_decisions
WHERE source_event_id = 192614 
  AND decision_id = 'D001'
ORDER BY source_ai_model;

-- Get MoA synthesis for comparison
SELECT 
    headline,
    decision_statement,
    outcome,
    primary_theme
FROM bronze_decisions
WHERE source_event_id = 192614 
  AND decision_id = 'D001'
  AND source_ai_model = 'moa-gpt-4o';

-- Model performance stats
SELECT 
    source_ai_model,
    COUNT(*) as total_decisions,
    COUNT(DISTINCT source_event_id) as total_events,
    AVG(json_array_length(arguments_for)) as avg_arguments_for,
    AVG(json_array_length(arguments_against)) as avg_arguments_against,
    COUNT(*) FILTER (WHERE outcome IS NOT NULL) as decisions_with_outcome
FROM bronze_decisions
GROUP BY source_ai_model
ORDER BY total_decisions DESC;
```

## Prompt Template

The analysis uses `/prompts/policy_analysis.md` which defines:

- **Entity linking** - Person slugs, organization types, legislation IDs
- **Theme classification** - COFOG codes, NTEE categories
- **Frame analysis** - Causal interpretations, value conflicts, power maps
- **Smart Brevity** - Concise, headline-first writing style
- **Three outputs** - JSON, human summary, Mermaid timeline

## Cost Estimates

**Gemini 1.5 Flash (FREE TIER):**
- ✅ **FREE up to 15 requests/minute**
- ✅ **FREE up to 1 million tokens/day**
- ✅ **FREE up to 1,500 requests/day**

**Typical meeting analysis:**
- Input: 10K-50K tokens (transcript + prompt)
- Output: 5K-10K tokens (JSON + summary + timeline)
- **Cost: $0.00** (within free tier limits)

**For 5 meetings × 10 channels = 50 meetings:**
- **Estimated cost: FREE** ✅
- Processing time: ~4 minutes (with 5s delays)
- Well within free tier daily limits

**Free tier limits:**
- 15 requests/minute = 900 requests/hour
- 1,500 requests/day max
- Script processes ~12 meetings/min = 720 meetings/hour (with 5s delays)
- Can analyze all 1,500 daily meetings in ~2 hours

## Rate Limits

**Gemini 1.5 Flash FREE tier limits:**
- ✅ **15 requests/minute**
- ✅ **1,500 requests/day**
- ✅ **1 million tokens/day**

**Current settings:**
- 5 second delay between requests (default)
- Processes ~12 meetings/minute (720/hour)
- Safely within 15 req/min free tier limit

**No rate limiting needed** for typical usage (under 1,500 meetings/day)

If you somehow hit limits:
```bash
# Slow down to 10s between requests
python scripts/datasources/gemini/analyze_meeting_transcripts.py --delay 10.0
```

## Workflow

### Standard Analysis Pipeline

#### 1. Load Meeting Videos
```bash
# First, get meeting videos with transcripts
python scripts/datasources/youtube/load_youtube_events_to_postgres.py \
  --states AL,GA,IN,MA,WA,WI \
  --skip-transcripts \
  --max-videos 100
```

#### 2. Get Transcripts (later, when needed)
```bash
# Fetch transcripts for stored videos
python scripts/datasources/youtube/load_youtube_events_to_postgres.py \
  --states AL,GA,IN,MA,WA,WI \
  --max-videos 10  # Just most recent ones
```

#### 3. Analyze with Gemini
```bash
# Run AI analysis on meetings with transcripts
python scripts/datasources/gemini/analyze_meeting_transcripts.py
```

#### 4. Extract to Bronze
```bash
# Extract structured data to bronze tables
python scripts/datasources/gemini/extract_to_bronze.py
```

#### 5. Query Results
```bash
# Check results
PGPASSWORD=password psql -h localhost -p 5433 -U postgres -d open_navigator -c \
  "SELECT COUNT(*) FROM events_text_ai WHERE error_message IS NULL;"
```

### Multi-Model Comparison Pipeline (Advanced) ⭐

For highest quality extractions, analyze the same meeting with multiple models and synthesize results:

#### 1. Analyze with Multiple Models
```bash
# Model 1: Gemini 1.5 Flash (free, fast)
python scripts/datasources/gemini/analyze_meeting_transcripts.py --states MA

# TODO: Add support for additional models (GPT-4, Claude 3, etc.)
```

#### 2. Extract All Models to Bronze
```bash
python scripts/datasources/gemini/extract_to_bronze.py
```

#### 3. Compare Extractions
```bash
# See summary of multi-model coverage
python scripts/datasources/gemini/compare_model_extractions.py --summary

# Compare specific event
python scripts/datasources/gemini/compare_model_extractions.py --event-id 192614
```

#### 4. Run MoA Synthesis (Mixture-of-Agents)
```bash
# Synthesize all decisions using GPT-4o as aggregator
python scripts/datasources/gemini/moa_synthesize.py --event-id 192614 --all

# Or use Gemini Pro as aggregator (cheaper)
python scripts/datasources/gemini/moa_synthesize.py --event-id 192614 --all --aggregator gemini-pro
```

#### 5. Query Synthesis Results
```bash
psql -d open_navigator_bronze -c "
  SELECT decision_id, headline, outcome FROM bronze_decisions
  WHERE source_event_id = 192614 AND source_ai_model = 'moa-gpt-4o'
  ORDER BY decision_id;
"
```

**Benefits:** Higher accuracy, identifies biases, builds confidence through consensus

## Troubleshooting

**Issue: "GEMINI_API_KEY not found"**
```bash
# Get key from https://makersuite.google.com/app/apikey
echo "GEMINI_API_KEY=AIza..." >> .env
```

**Issue: "google.generativeai not installed"**
```bash
pip install google-generativeai
```

**Issue: Rate limiting**
```bash
# Increase delay between requests
python scripts/datasources/gemini/analyze_meeting_transcripts.py --delay 5.0
```

**Issue: JSON parsing errors**
- Check `events_text_ai.error_message` column
- Review `raw_response` for debugging
- Gemini may occasionally return malformed JSON

**Issue: No meetings found**
- Check that meetings have transcripts: `SELECT COUNT(*) FROM events_text_search;`
- Verify state codes: `SELECT DISTINCT state_code FROM event;`
- Try `--force` to re-analyze existing meetings

## Next Steps

### Analysis Improvements
1. **Multi-model analysis** - Implement GPT-4 and Claude 3 support in `analyze_meeting_transcripts.py`
2. **Aggregate insights** - Build summary views of frame analysis across meetings
3. **Trend detection** - Track how frames evolve over time
4. **Fine-tune prompts** - Adjust policy_analysis.md based on results
5. **Batch processing** - Analyze historical meetings en masse

### AI Evaluation & Merging 🆕
6. **Implement DeepEval** - Add automated quality metrics (Faithfulness, Relevancy, Coherence)
7. **Build consensus dashboard** - Visualize model agreements and contradictions
8. **Optimize MoA** - Fine-tune aggregator prompts for better synthesis
9. **Track model performance** - Store evaluation scores in bronze tables
10. **Export to frontend** - Display MoA synthesized decisions in UI

## Resources

- **[AI Model Evaluation Guide](../../website/docs/development/ai-model-evaluation.md)** - LLM-as-a-Judge, N-Way Consensus, metrics
- **[AI Model Merging Guide](../../website/docs/development/ai-model-merging.md)** - MoA, ensemble strategies, SLERP
- **[Gemini AI Documentation](https://ai.google.dev/docs)** - Official API docs
- **[DeepEval Framework](https://github.com/confident-ai/deepeval)** - Evaluation metrics library
- **[Together MoA](https://github.com/togethercomputer/MoA)** - Mixture-of-Agents reference implementation
