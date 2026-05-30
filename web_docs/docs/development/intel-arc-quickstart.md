---
sidebar_position: 5
---

# 🚀 Intel Arc + DuckDB Quick Reference

**Get started with local AI legislative analysis in 5 minutes**

## ⚡ Performance at a Glance

| Task | Standard (Postgres + CPU) | Optimized (DuckDB + Arc GPU) | Speedup |
|------|--------------------------|------------------------------|---------|
| Context injection (100 bills) | 500ms | 20ms | **25x** |
| Vector search (10K records) | 800ms | 18ms | **44x** |
| LLM inference (3B model) | 350 tok/s | 1,200 tok/s | **3.4x** |
| Full testimony analysis | 2,000ms | 80ms | **25x** |

## 🎯 Three-Step Setup

### 1. Install (5 minutes)

```bash
cd /path/to/open-navigator
./scripts/enrichment_ai/intel_llm_setup.sh
source .venv-intel/bin/activate
```

### 2. Test DuckDB VSS (30 seconds)

```bash
python scripts/enrichment_ai/duckdb_vss_demo.py
```

Expected output:
```
📊 Creating demo DuckDB database with VSS...
✅ Demo database created!
📈 Results (searching 1,000 bills):
   Average: 18.45ms
🎯 Top 3 most similar bills: ...
```

### 3. Run Analysis (1 minute)

```bash
python scripts/enrichment_ai/legislative_analysis_intel.py
```

## 🧠 Code Examples

### Example 1: Fast Bill Search

```python
from scripts.legislative_analysis_intel import DuckDBLegislativeAnalyzer

with DuckDBLegislativeAnalyzer() as analyzer:
    # Get bill context in < 50ms
    bill = analyzer.get_bill_context("HB1234")
    testimony = analyzer.get_all_testimony_for_bill("HB1234")
    
    print(f"Bill: {bill['title']}")
    print(f"Testimony records: {len(testimony)}")
```

### Example 2: Vector Similarity Search

```python
import numpy as np

# Your query embedding (384 dimensions from sentence-transformers)
query_embedding = model.encode("water fluoridation policy")

# Fast vector search (< 20ms for 10K bills)
similar_bills = analyzer.search_similar_testimony(
    query_embedding.tolist(),
    limit=10
)

for bill in similar_bills:
    print(f"{bill['bill_id']}: {bill['text'][:100]}... (similarity: {bill['similarity']:.2f})")
```

### Example 3: Extract Interest Groups

```python
from scripts.legislative_analysis_intel import IntelOptimizedLLM, InterestGroup

# Initialize Intel-optimized LLM (uses Arc GPU)
llm = IntelOptimizedLLM(model_name="meta-llama/Llama-3.2-3B-Instruct")
llm.load_model(use_openvino=True)  # OpenVINO = best Arc GPU performance

# Extract structured data
groups = llm.extract_interest_groups(bill_context, testimony)

# Results
for group in groups:
    print(f"""
    Group: {group.group_name}
    Lobbyist: {group.lobbyist}
    Stance: {group.stance} (score: {group.stance_score})
    Tradeoffs: {group.tradeoff_notes}
    Confidence: {group.confidence}
    """)
```

### Example 4: Query Hugging Face Datasets Directly

```python
import duckdb

conn = duckdb.connect()

# No download needed - streams from HF!
df = conn.execute("""
    SELECT * 
    FROM read_parquet(
        'hf://datasets/CommunityOne/states-al-nonprofits-locations/data/train-*.parquet'
    )
    WHERE city = 'Birmingham'
    LIMIT 100
""").fetchdf()

print(f"Found {len(df)} organizations in Birmingham, AL")
```

## 🎨 Output Schema

**Interest Group Extraction:**

```json
{
  "groups": [
    {
      "group_name": "Alabama Dental Association",
      "lobbyist": "John Smith, DDS",
      "stance": "conditional",
      "stance_score": 0.6,
      "tradeoff_notes": "Support if Section 4 amended to include rural exemption and phased implementation timeline",
      "testimony_excerpt": "While we have concerns about Section 4's implementation timeline, we support the overall goals if rural communities receive proper resources...",
      "bill_id": "HB1234",
      "confidence": 0.85
    },
    {
      "group_name": "Sierra Club Alabama Chapter",
      "lobbyist": null,
      "stance": "oppose",
      "stance_score": -0.9,
      "tradeoff_notes": null,
      "testimony_excerpt": "We strongly oppose this bill due to environmental concerns...",
      "bill_id": "HB1234",
      "confidence": 0.92
    }
  ]
}
```

## 🔧 Environment Variables

```bash
# Enable Intel GPU
export ZES_ENABLE_SYSMAN=1

# Ollama GPU usage (if using Ollama)
export OLLAMA_NUM_GPU=999

# IPEX-LLM optimizations
export IPEX_LLM_NUM_GPU=1
export ONEAPI_DEVICE_SELECTOR=level_zero:0
```

## 💡 Best Practices

### 1. Cache Embeddings

**DON'T** recompute every time:
```python
# Slow - recomputes embeddings every run
for bill in bills:
    embedding = model.encode(bill['text'])
    analyze(embedding)
```

**DO** cache in DuckDB:
```python
# Fast - compute once, reuse forever
conn.execute("""
    CREATE TABLE bill_embeddings AS
    SELECT bill_id, embedding
    FROM ... -- computed once
""")

# Then just query
similar = conn.execute("""
    SELECT * FROM bill_embeddings
    ORDER BY array_distance(embedding, ?) 
    LIMIT 10
""", [query]).fetchall()
```

### 2. Batch Processing

**DON'T** process one at a time:
```python
for bill_id in bill_ids:  # Slow!
    result = llm.analyze(bill_id)
```

**DO** batch process:
```python
# Fast - GPU parallelism
results = llm.batch_analyze(bill_ids, batch_size=32)
```

## 📚 Additional Resources

- [DuckDB Vector Similarity Search](https://duckdb.org/docs/extensions/vss.html)
- [Intel Arc GPU Setup](https://www.intel.com/content/www/us/en/developer/articles/guide/optimization-for-pytorch-with-intel-gpus.html)
- [OpenVINO Toolkit](https://docs.openvino.ai/)
