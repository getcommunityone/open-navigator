---
sidebar_position: 5
---

# AI Model Evaluation & Comparison

## Overview

When extracting structured data from meeting transcripts, knowing the "right answer" is often impossible. This guide shows how to evaluate and compare AI model outputs without ground truth using industry-standard techniques.

## The Challenge

In 2026, AI development has moved away from "Ground Truth" (knowing the right answer) toward **Comparative & Model-Based Evaluation**. For meeting analysis:

- There's no "correct" extraction of a city council decision
- Different models may extract different (but valid) interpretations
- We need systematic ways to evaluate quality and build consensus

## Evaluation Techniques

### 1. LLM-as-a-Judge Pattern

Instead of checking if an answer matches a known truth, use a more powerful model (the "Judge") to evaluate responses based on a rubric.

**Logic:** Evaluation is easier than generation. A model might not perfectly extract all meeting details, but it can spot if an extraction is missing key information.

**Repository:** [DeepEval](https://github.com/confident-ai/deepeval)

#### Local Code Example

```python
from deepeval.metrics import AnswerRelevancyMetric
from deepeval.test_case import LLMTestCase

# Evaluate decision extraction without needing "expected_output"
test_case = LLMTestCase(
    input="What decisions were made about the parks budget?",
    actual_output="The council approved $2.5M for parks renovation with a 7-2 vote..."
)

metric = AnswerRelevancyMetric(threshold=0.7)
metric.measure(test_case)
print(f"Relevancy Score: {metric.score}")  # 0 to 1
print(f"Reasoning: {metric.reason}")       # Why it gave that score
```

#### Using with Bronze Data Model

```python
import psycopg2
from deepeval.metrics import AnswerRelevancyMetric
from deepeval.test_case import LLMTestCase

# Compare decision extractions from bronze_decisions
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

cur.execute("""
    SELECT 
        source_ai_model,
        decision_id,
        headline,
        decision_statement
    FROM bronze_decisions
    WHERE source_event_id = %s
    ORDER BY source_ai_model
""", (event_id,))

results = cur.fetchall()

for model, decision_id, headline, statement in results:
    test_case = LLMTestCase(
        input=f"Extract the decision about {headline}",
        actual_output=statement
    )
    
    metric = AnswerRelevancyMetric(threshold=0.7)
    metric.measure(test_case)
    
    print(f"{model}: Relevancy {metric.score}")
```

### 2. N-Way Consensus (Wisdom of the Crowds)

Run the same prompt on multiple models (e.g., Gemini 1.5, GPT-4, Claude 3). If two agree and one is outlier, the outlier is likely wrong.

**Repository:** [Open WebUI](https://github.com/open-webui/open-webui) (has built-in "Multi-Model Chat")

**Framework:** Self-Consistency

#### Judge Prompt for Consensus

```python
# After getting extractions from 3+ models in bronze_decisions
judge_prompt = """
Here are {n} AI model extractions of the same city council decision:

Model 1 (Gemini 1.5 Flash):
{extraction_1}

Model 2 (GPT-4):
{extraction_2}

Model 3 (Claude 3):
{extraction_3}

Instructions:
1. Identify the common points they all agree on (high confidence)
2. Identify points where they contradict (low confidence)
3. Output a final "Consensus Decision" that synthesizes the most accurate information

Format your response as:
- Consensus Points: [list]
- Contradictions: [list]
- Final Synthesis: [unified decision statement]
"""
```

#### Implementation with Bronze Data

```python
def build_consensus_decision(event_id: int, decision_id: str):
    """Build consensus from multiple model extractions."""
    
    query = """
    SELECT 
        source_ai_model,
        decision_statement,
        headline,
        outcome,
        primary_theme,
        arguments_for,
        arguments_against
    FROM bronze_decisions
    WHERE source_event_id = %s 
      AND decision_id = %s
    ORDER BY source_ai_model
    """
    
    cur.execute(query, (event_id, decision_id))
    extractions = cur.fetchall()
    
    if len(extractions) < 2:
        return extractions[0]  # No consensus needed
    
    # Format extractions for judge
    formatted = []
    for i, (model, statement, headline, outcome, theme, args_for, args_against) in enumerate(extractions, 1):
        formatted.append(f"""
Model {i} ({model}):
- Headline: {headline}
- Statement: {statement}
- Outcome: {outcome}
- Theme: {theme}
- Arguments For: {args_for}
- Arguments Against: {args_against}
        """)
    
    # Use judge model (e.g., Gemini 1.5 Pro or GPT-4)
    judge_response = call_judge_model(
        prompt=judge_prompt.format(
            n=len(extractions),
            **{f'extraction_{i}': ext for i, ext in enumerate(formatted, 1)}
        )
    )
    
    return judge_response
```

### 3. Factual Grounding (RAG Evaluation)

If your extraction is based on source text (meeting transcript), check if the AI's answer is actually contained within the source.

**Metric:** Faithfulness (available in [DeepEval](https://github.com/confident-ai/deepeval) or [RAGAS](https://github.com/explodinggradients/ragas))

**Logic:** If the LLM says "The council voted 9-0" but the transcript says "Vote: 7-2," the Faithfulness score will be low.

```python
from deepeval.metrics import FaithfulnessMetric
from deepeval.test_case import LLMTestCase

# Get original transcript from event
cur.execute("""
    SELECT es.event_description, et.decision_statement
    FROM event es
    JOIN events_text_ai et ON et.event_id = es.event_id
    JOIN bronze_decisions bd ON bd.source_event_id = es.event_id
    WHERE es.event_id = %s
""", (event_id,))

transcript, extracted_decision = cur.fetchone()

test_case = LLMTestCase(
    input="Extract the council's decision",
    actual_output=extracted_decision,
    retrieval_context=[transcript]  # The source document
)

metric = FaithfulnessMetric(threshold=0.7)
metric.measure(test_case)
print(f"Faithfulness: {metric.score}")  # How grounded in source
```

### 4. Deterministic Guardrails

Check the **shape** of the result, even if you don't know the content:

```python
from pydantic import BaseModel, ValidationError
from typing import List, Optional

class DecisionExtraction(BaseModel):
    """Expected structure of a decision extraction."""
    decision_id: str
    headline: str
    decision_statement: str
    outcome: Optional[str]
    primary_theme: Optional[str]
    ntee_code: Optional[str]
    arguments_for: List[dict]
    arguments_against: List[dict]

def validate_extraction(extraction_json: dict) -> tuple[bool, str]:
    """Validate extraction structure."""
    try:
        DecisionExtraction(**extraction_json)
        return True, "Valid structure"
    except ValidationError as e:
        return False, str(e)

# Example: Check all extractions in bronze_decisions
cur.execute("SELECT id, decision_id, structured_data FROM bronze_decisions")
for record_id, decision_id, data in cur.fetchall():
    valid, message = validate_extraction(data)
    if not valid:
        print(f"❌ {decision_id}: {message}")
```

Additional shape checks:

```python
import re

def check_extraction_quality(extraction: dict) -> dict:
    """Run deterministic quality checks."""
    
    checks = {
        'has_decision_id': bool(extraction.get('decision_id')),
        'decision_id_format': bool(re.match(r'^D\d+$', extraction.get('decision_id', ''))),
        'has_headline': bool(extraction.get('headline')),
        'headline_length': 10 <= len(extraction.get('headline', '')) <= 200,
        'has_statement': bool(extraction.get('decision_statement')),
        'statement_length': len(extraction.get('decision_statement', '')) > 20,
        'valid_outcome': extraction.get('outcome') in ['approved', 'rejected', 'tabled', 'amended', None],
        'has_ntee_code': bool(extraction.get('ntee_code')),
        'ntee_code_format': bool(re.match(r'^[A-Z]\d{2}$', extraction.get('ntee_code', ''))),
    }
    
    checks['overall_quality'] = sum(checks.values()) / len(checks)
    return checks
```

## Evaluation Metrics Summary

| Technique | Metric Name | What it Scores | Repository |
|-----------|-------------|----------------|------------|
| LLM-as-a-Judge | AnswerRelevancy | Does answer match the intent? | [DeepEval](https://github.com/confident-ai/deepeval) |
| Source Grounding | Faithfulness | Is answer supported by source docs? | [DeepEval](https://github.com/confident-ai/deepeval), [RAGAS](https://github.com/explodinggradients/ragas) |
| Logic/Reasoning | Coherence | Does answer make logical sense? | [DeepEval](https://github.com/confident-ai/deepeval) |
| Safety | Toxicity/Bias | Does output violate safety rubrics? | [DeepEval](https://github.com/confident-ai/deepeval) |
| Structure | Schema Validation | Does output match expected format? | [Pydantic](https://docs.pydantic.dev/) |

## Next Steps

1. **Implement Evaluation Pipeline**: Add these metrics to `scripts/datasources/gemini/evaluate_extractions.py`
2. **Compare Models**: Use `scripts/datasources/gemini/compare_model_extractions.py` with evaluation scores
3. **Build Consensus**: See [AI Model Merging](./ai-model-merging.md) for techniques to synthesize results
4. **Track Quality**: Store evaluation scores in a new `bronze_evaluation_scores` table

## Example: Full Evaluation Pipeline

```python
#!/usr/bin/env python3
"""
Evaluate bronze decision extractions using multiple metrics.
"""

from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
from deepeval.test_case import LLMTestCase
import psycopg2

def evaluate_decision_extraction(event_id: int, decision_id: str):
    """Evaluate a decision extraction using multiple metrics."""
    
    # Get extraction and source
    cur.execute("""
        SELECT 
            bd.source_ai_model,
            bd.decision_statement,
            bd.headline,
            es.description as transcript
        FROM bronze_decisions bd
        JOIN event es ON es.event_id = bd.source_event_id
        WHERE bd.source_event_id = %s 
          AND bd.decision_id = %s
    """, (event_id, decision_id))
    
    model, statement, headline, transcript = cur.fetchone()
    
    # Test case
    test_case = LLMTestCase(
        input=f"Extract decision about: {headline}",
        actual_output=statement,
        retrieval_context=[transcript]
    )
    
    # Run metrics
    relevancy = AnswerRelevancyMetric(threshold=0.7)
    relevancy.measure(test_case)
    
    faithfulness = FaithfulnessMetric(threshold=0.7)
    faithfulness.measure(test_case)
    
    # Deterministic checks
    quality_checks = check_extraction_quality({
        'decision_id': decision_id,
        'headline': headline,
        'decision_statement': statement
    })
    
    return {
        'model': model,
        'relevancy_score': relevancy.score,
        'faithfulness_score': faithfulness.score,
        'structure_quality': quality_checks['overall_quality'],
        'passed_all': all([
            relevancy.score >= 0.7,
            faithfulness.score >= 0.7,
            quality_checks['overall_quality'] >= 0.8
        ])
    }

# Run evaluation
results = evaluate_decision_extraction(event_id=192614, decision_id='D001')
print(f"Model: {results['model']}")
print(f"Relevancy: {results['relevancy_score']:.2f}")
print(f"Faithfulness: {results['faithfulness_score']:.2f}")
print(f"Structure: {results['structure_quality']:.2f}")
print(f"Overall: {'✅ PASS' if results['passed_all'] else '❌ FAIL'}")
```

## Resources

- [DeepEval Documentation](https://docs.confident-ai.com/)
- [RAGAS Documentation](https://docs.ragas.io/)
- [Prompt Engineering Guide - Evaluation](https://www.promptingguide.ai/introduction/evaluation)
- [OpenAI Evals Framework](https://github.com/openai/evals)
