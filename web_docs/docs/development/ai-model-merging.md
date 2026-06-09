---
sidebar_position: 6
---

# AI Model Merging & Ensemble Strategies

## Overview

After extracting meeting decisions with multiple AI models, you can **merge** the results to create a higher-quality consensus output. This guide covers industry-standard techniques for combining model outputs.

## Why Merge Instead of Pick?

Your bronze data model now stores multiple extractions of the same decision:

```sql
SELECT source_ai_model, headline, outcome 
FROM bronze_decisions 
WHERE source_event_id = 192614 AND decision_id = 'D001';
```

Results:
- `gemini-1.5-flash`: "Parks budget approved" | outcome: `approved`
- `gpt-4`: "Council approves $2.5M parks renovation" | outcome: `approved`  
- `claude-3`: "Parks funding passes 7-2" | outcome: `approved`

Instead of picking one, **merging** synthesizes all three into: "Council approved $2.5M parks renovation budget with a 7-2 vote."

## Merging Techniques

### 1. Together MoA (Mixture-of-Agents) ⭐

The **gold standard** for merging AI outputs. Uses a layered architecture where multiple "Proposer" models generate candidates, then an "Aggregator" model synthesizes them.

**Repository:** [Together MoA](https://github.com/togethercomputer/MoA)

**Performance:** Merging 4 open-source models often beats a single GPT-4o instance.

#### How It Works

```
┌──────────────────────────────────────┐
│  Input: Meeting Transcript           │
└──────────┬───────────────────────────┘
           │
    ┌──────┴──────┬──────────┬─────────┐
    │             │          │         │
┌───▼────┐  ┌────▼───┐  ┌───▼────┐  ┌─▼──────┐
│ Gemini │  │  GPT-4 │  │ Claude │  │ Llama3 │
│ Flash  │  │        │  │   3    │  │        │
└───┬────┘  └────┬───┘  └───┬────┘  └─┬──────┘
    │             │          │         │
    │ Extraction 1│ Extract 2│ Extr. 3 │ Extr. 4
    └─────────┬───┴──────┬───┴─────┬───┘
              │          │         │
         ┌────▼──────────▼─────────▼────┐
         │  Aggregator Model (GPT-4o)   │
         │  Prompt: "Analyze all 4      │
         │  responses, correct errors,  │
         │  synthesize best answer"     │
         └────────────┬─────────────────┘
                      │
              ┌───────▼────────┐
              │ Final Synthesis│
              └────────────────┘
```

#### Implementation with Bronze Data

```python
#!/usr/bin/env python3
"""
Mixture-of-Agents implementation for bronze decision merging.
"""

import psycopg2
from openai import OpenAI
import google.generativeai as genai

client = OpenAI()
genai.configure(api_key=GEMINI_API_KEY)

def get_all_extractions(event_id: int, decision_id: str) -> list:
    """Get all model extractions for a decision."""
    
    query = """
    SELECT 
        source_ai_model,
        headline,
        decision_statement,
        outcome,
        primary_theme,
        ntee_code,
        arguments_for,
        arguments_against,
        vote_tally
    FROM bronze_decisions
    WHERE source_event_id = %s 
      AND decision_id = %s
    ORDER BY source_ai_model
    """
    
    cur.execute(query, (event_id, decision_id))
    return cur.fetchall()

def create_aggregator_prompt(extractions: list) -> str:
    """Create MoA aggregator prompt."""
    
    formatted_extractions = []
    for i, extraction in enumerate(extractions, 1):
        (model, headline, statement, outcome, theme, ntee, args_for, args_against, votes) = extraction
        
        formatted_extractions.append(f"""
### Extraction {i} (Model: {model})

**Headline:** {headline}

**Statement:** {statement}

**Outcome:** {outcome}

**Theme:** {theme} (NTEE: {ntee})

**Arguments For:** {args_for}

**Arguments Against:** {args_against}

**Vote Tally:** {votes}
        """)
    
    prompt = f"""
You are an expert aggregator AI tasked with synthesizing multiple AI model extractions of a city council decision.

Below are {len(extractions)} different extractions of the same decision from different AI models. Each model may have different strengths and weaknesses.

{chr(10).join(formatted_extractions)}

## Your Task

Analyze all {len(extractions)} extractions and create a single, comprehensive, and accurate synthesis that:

1. **Identifies Common Ground:** What do all models agree on? (High confidence)
2. **Resolves Contradictions:** Where models disagree, use reasoning to determine the most likely accurate version
3. **Combines Strengths:** Take the best parts from each extraction
4. **Corrects Errors:** If you spot factual inconsistencies or logical errors, correct them

## Output Format

Provide your synthesis in this JSON structure:

{{
  "synthesized_headline": "...",
  "synthesized_statement": "...",
  "consensus_outcome": "...",
  "consensus_theme": "...",
  "consensus_ntee_code": "...",
  "high_confidence_facts": ["fact1", "fact2"],
  "low_confidence_facts": ["uncertain1", "uncertain2"],
  "arguments_for": [...],
  "arguments_against": [...],
  "vote_tally": {{}},
  "reasoning": "Why you made the synthesis decisions you did"
}}
"""
    
    return prompt

def aggregate_with_gpt4(prompt: str) -> dict:
    """Use GPT-4 as aggregator."""
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an expert at synthesizing multiple AI outputs into a single high-quality result."},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )
    
    return json.loads(response.choices[0].message.content)

def aggregate_with_gemini(prompt: str) -> dict:
    """Use Gemini Pro as aggregator."""
    
    model = genai.GenerativeModel('gemini-1.5-pro')
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json"
        )
    )
    
    return json.loads(response.text)

def moa_synthesize_decision(event_id: int, decision_id: str, aggregator: str = 'gpt-4o'):
    """
    Full MoA pipeline to synthesize decision from multiple extractions.
    
    Args:
        event_id: Source event ID
        decision_id: Decision ID to synthesize
        aggregator: Which model to use as aggregator ('gpt-4o' or 'gemini-pro')
    
    Returns:
        Synthesized decision as dict
    """
    
    # Step 1: Get all proposer outputs (from bronze_decisions)
    extractions = get_all_extractions(event_id, decision_id)
    
    if len(extractions) < 2:
        print(f"⚠️  Only {len(extractions)} extraction(s) found. Need 2+ for MoA.")
        return extractions[0] if extractions else None
    
    print(f"🔄 Running MoA with {len(extractions)} proposer models")
    
    # Step 2: Create aggregator prompt
    prompt = create_aggregator_prompt(extractions)
    
    # Step 3: Run aggregator
    if aggregator == 'gpt-4o':
        synthesis = aggregate_with_gpt4(prompt)
    elif aggregator == 'gemini-pro':
        synthesis = aggregate_with_gemini(prompt)
    else:
        raise ValueError(f"Unknown aggregator: {aggregator}")
    
    print(f"✅ MoA synthesis complete using {aggregator}")
    
    # Step 4: Store synthesis back to bronze (with special model name)
    store_synthesis(event_id, decision_id, synthesis, aggregator_model=aggregator)
    
    return synthesis

def store_synthesis(event_id: int, decision_id: str, synthesis: dict, aggregator_model: str):
    """Store MoA synthesis back to bronze_decisions."""
    
    query = """
    INSERT INTO bronze_decisions (
        source_event_id, source_ai_model, decision_id,
        headline, decision_statement, outcome,
        primary_theme, ntee_code,
        arguments_for, arguments_against, vote_tally
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
    )
    ON CONFLICT (source_event_id, decision_id, source_ai_model)
    DO UPDATE SET
        headline = EXCLUDED.headline,
        decision_statement = EXCLUDED.decision_statement,
        outcome = EXCLUDED.outcome,
        primary_theme = EXCLUDED.primary_theme,
        ntee_code = EXCLUDED.ntee_code,
        arguments_for = EXCLUDED.arguments_for,
        arguments_against = EXCLUDED.arguments_against,
        vote_tally = EXCLUDED.vote_tally,
        extracted_at = CURRENT_TIMESTAMP
    """
    
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (
                event_id,
                f'moa-{aggregator_model}',  # Special model name for synthesis
                decision_id,
                synthesis['synthesized_headline'],
                synthesis['synthesized_statement'],
                synthesis['consensus_outcome'],
                synthesis['consensus_theme'],
                synthesis['consensus_ntee_code'],
                json.dumps(synthesis['arguments_for']),
                json.dumps(synthesis['arguments_against']),
                json.dumps(synthesis['vote_tally'])
            ))
        conn.commit()

# Usage
if __name__ == '__main__':
    result = moa_synthesize_decision(
        event_id=192614, 
        decision_id='D001',
        aggregator='gpt-4o'
    )
    
    print("\n📊 Synthesized Result:")
    print(f"Headline: {result['synthesized_headline']}")
    print(f"Outcome: {result['consensus_outcome']}")
    print(f"Reasoning: {result['reasoning']}")
```

### 2. Weighted Voting / Best-of-N

Instead of full synthesis, pick the "best" extraction based on confidence scores or quality metrics.

```python
def weighted_vote_decision(event_id: int, decision_id: str, weights: dict = None):
    """
    Select best decision using weighted voting.
    
    Args:
        weights: Model weights (e.g., {'gpt-4': 1.5, 'gemini-1.5-flash': 1.0, 'claude-3': 1.2})
    """
    
    if weights is None:
        weights = {
            'gpt-4': 1.5,
            'gemini-1.5-pro': 1.4,
            'claude-3-opus': 1.3,
            'gemini-1.5-flash': 1.0,
            'llama-3-70b': 1.0
        }
    
    extractions = get_all_extractions(event_id, decision_id)
    
    scores = []
    for extraction in extractions:
        model = extraction[0]
        
        # Base score from model weight
        base_score = weights.get(model, 1.0)
        
        # Quality adjustments
        quality_score = calculate_quality_score(extraction)
        
        final_score = base_score * quality_score
        scores.append((final_score, extraction))
    
    # Return highest scoring extraction
    best_score, best_extraction = max(scores, key=lambda x: x[0])
    
    print(f"🏆 Best extraction: {best_extraction[0]} (score: {best_score:.2f})")
    return best_extraction

def calculate_quality_score(extraction) -> float:
    """Calculate quality score for an extraction."""
    
    (model, headline, statement, outcome, theme, ntee, args_for, args_against, votes) = extraction
    
    score = 1.0
    
    # Bonus for completeness
    if headline: score += 0.1
    if statement and len(statement) > 50: score += 0.1
    if outcome: score += 0.1
    if theme: score += 0.1
    if ntee: score += 0.1
    
    # Bonus for detail
    if args_for and len(args_for) > 2: score += 0.1
    if args_against and len(args_against) > 2: score += 0.1
    if votes: score += 0.1
    
    return score
```

### 3. SLERP & Weight Merging (Model-Level)

If you want to merge models at the **weight level** (create a hybrid model), use **Mergekit**.

**Repository:** [Mergekit](https://github.com/arcee-ai/mergekit)

**Use Case:** Create a single model that's 50% "Great at Policy Analysis" (Gemini) and 50% "Great at Argument Extraction" (GPT-4).

```yaml
# mergekit-config.yaml
models:
  - model: google/gemini-1.5-flash-finetuned-policy
    parameters:
      weight: 0.5
  - model: openai/gpt-4-finetuned-arguments
    parameters:
      weight: 0.5

merge_method: slerp  # Spherical Linear Interpolation
dtype: float16
```

```bash
mergekit-yaml mergekit-config.yaml merged-model/ --cuda
```

**Result:** A single model that combines strengths at the neural weight level.

### 4. Dify / Langflow (No-Code Merging)

Visual tools for building multi-model pipelines without code.

**Repositories:** [Dify](https://github.com/langgenius/dify) / [Langflow](https://github.com/logspace-ai/langflow)

**Dify Workflow:**
```
[Meeting Transcript]
        |
    [Parallel Node]
    /    |    \
   /     |     \
[Gemini][GPT-4][Claude]
   \     |     /
    \    |    /
   [Code Node: Compare]
        |
   [LLM Node: Synthesize]
        |
   [Final Decision]
```

### 5. Multi-Layer Ensembling

Combine multiple merging strategies in sequence.

```python
def multi_layer_ensemble(event_id: int, decision_id: str):
    """
    Layer 1: MoA synthesis with GPT-4o
    Layer 2: MoA synthesis with Gemini Pro  
    Layer 3: Weighted vote between the two syntheses
    """
    
    # Layer 1: GPT-4o aggregation
    synthesis_gpt = moa_synthesize_decision(event_id, decision_id, aggregator='gpt-4o')
    
    # Layer 2: Gemini Pro aggregation
    synthesis_gemini = moa_synthesize_decision(event_id, decision_id, aggregator='gemini-pro')
    
    # Layer 3: Meta-aggregation (judge which synthesis is better)
    meta_prompt = f"""
    Two different aggregator models synthesized the same decision:
    
    Synthesis A (GPT-4o):
    {json.dumps(synthesis_gpt, indent=2)}
    
    Synthesis B (Gemini Pro):
    {json.dumps(synthesis_gemini, indent=2)}
    
    Which synthesis is more accurate, comprehensive, and well-reasoned?
    Output the letter (A or B) and explain why.
    """
    
    # Use a third model as meta-judge
    meta_judge = client.chat.completions.create(
        model="claude-3-opus",
        messages=[{"role": "user", "content": meta_prompt}]
    )
    
    winner = meta_judge.choices[0].message.content
    
    return synthesis_gpt if 'A' in winner else synthesis_gemini
```

## Merging Strategies Comparison

| Technique | Complexity | Quality | Speed | Cost | Best For |
|-----------|------------|---------|-------|------|----------|
| **MoA** | Medium | ⭐⭐⭐⭐⭐ | Medium | $$ | Highest quality synthesis |
| **Weighted Vote** | Low | ⭐⭐⭐ | Fast | $ | Quick consensus |
| **SLERP/Mergekit** | High | ⭐⭐⭐⭐ | One-time | $ (upfront) | Permanent hybrid model |
| **Dify/Langflow** | Low | ⭐⭐⭐⭐ | Medium | $$ | Non-coders, rapid prototyping |
| **Multi-Layer** | High | ⭐⭐⭐⭐⭐ | Slow | $$$ | Critical decisions, research |

## Implementation Roadmap

### Phase 1: Basic Comparison (✅ Complete)
- [x] Multi-model bronze schema
- [x] `compare_model_extractions.py` script
- [x] Storage of multiple extractions

### Phase 2: Evaluation (In Progress)
- [ ] Implement DeepEval metrics
- [ ] Add quality scoring to bronze
- [ ] Create evaluation dashboard

### Phase 3: Simple Merging
- [ ] Implement weighted voting
- [ ] Add MoA synthesis script
- [ ] Create `bronze_decisions_synthesis` table

### Phase 4: Advanced Merging
- [ ] Multi-layer ensembling
- [ ] Fine-tune aggregator models
- [ ] Build consensus API endpoint

## Example: Full MoA Pipeline

```bash
# 1. Extract with multiple models
python scripts/datasources/gemini/analyze_meeting_transcripts.py --model gemini-1.5-flash
python scripts/datasources/gemini/analyze_meeting_transcripts.py --model gpt-4
python scripts/datasources/gemini/analyze_meeting_transcripts.py --model claude-3

# 2. Load to bronze
python scripts/datasources/gemini/extract_to_bronze.py

# 3. Compare extractions
python scripts/datasources/gemini/compare_model_extractions.py --event-id 192614

# 4. Run MoA synthesis
python scripts/datasources/gemini/moa_synthesize.py --event-id 192614 --aggregator gpt-4o

# 5. Query final synthesis
psql -d open_navigator_bronze -c "
  SELECT headline, decision_statement, outcome 
  FROM bronze_decisions 
  WHERE source_event_id = 192614 
    AND source_ai_model = 'moa-gpt-4o';
"
```

## Resources

- [Together MoA Paper](https://arxiv.org/abs/2406.04692)
- [Mergekit Documentation](https://github.com/arcee-ai/mergekit/blob/main/docs/README.md)
- [Dify Documentation](https://docs.dify.ai/)
- [Langflow Documentation](https://docs.langflow.org/)
- [Ensemble Methods in ML](https://scikit-learn.org/stable/modules/ensemble.html)

## Related

- [AI Model Evaluation](./ai-model-evaluation.md) - How to evaluate individual models
- [Bronze Data Model](../data-sources/meeting-data.md) - Multi-model schema design
