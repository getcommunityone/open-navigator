---
sidebar_position: 14
---

# Jurisdiction Discovery - Deployment Options

## Option 1: Local CLI ✅ Recommended for Testing

Run discovery from your local machine.

### Setup

```bash
pip install -r requirements.txt
python main.py init
```

### Usage

```bash
# Test with 100 jurisdictions
python main.py discover-jurisdictions --limit 100

# View results
python main.py discovery-stats

# Full discovery (~30k jurisdictions)
python main.py discover-jurisdictions
```

### When to Use

- Testing and development
- Small-scale discovery (single state)
- One-time manual runs

### Performance

- **Speed**: 3-5 min per 100 jurisdictions
- **Cost**: $0 (local compute)
- **Scale**: Single state or limited runs

---

## Option 2: Databricks Notebook ✅ Recommended for Production

Run discovery in a Databricks notebook with Spark parallel processing.

### Setup

1. **Upload Notebook**
   ```bash
   databricks workspace import \
     notebooks/Jurisdiction_Discovery.py \
     /Users/your-email/Jurisdiction_Discovery \
     --language PYTHON
   ```

2. **Create Cluster**
   - Runtime: 14.3 LTS or higher
   - Node type: Standard_DS3_v2
   - Workers: 2-4 (for parallel processing)
   - Libraries: Install from requirements.txt

3. **Run Notebook**
   - Attach to cluster
   - Execute all cells
   - Monitor progress

### Usage

```python
# In notebook
from discovery.discovery_pipeline import DiscoveryPipeline

pipeline = DiscoveryPipeline()

# Full discovery
await pipeline.run_full_pipeline(discovery_limit=None)
```

### When to Use

- Production discovery runs
- Processing 10,000+ jurisdictions
- Scheduled/automated discovery
- Need parallel processing

### Performance

- **Speed**: ~2-4 hours for 30k jurisdictions (with 4 workers)
- **Cost**: ~$8-15 per run (Databricks cluster)
- **Scale**: Full 90k+ jurisdiction coverage

### Scheduling

Create Databricks Workflow for monthly re-discovery:

```json
{
  "name": "Monthly Jurisdiction Discovery",
  "tasks": [{
    "task_key": "discover_jurisdictions",
    "notebook_task": {
      "notebook_path": "/Users/you/Jurisdiction_Discovery"
    },
    "existing_cluster_id": "your-cluster-id"
  }],
  "schedule": {
    "quartz_cron_expression": "0 0 1 * *",
    "timezone_id": "America/Los_Angeles"
  }
}
```

---

## Option 3: AgentBricks Model Serving (Advanced)

Deploy discovery as a Databricks Model Serving endpoint for API access.

### Setup

```python
from discovery.mlflow_discovery_agent import deploy_discovery_agent

endpoint_url = deploy_discovery_agent(
    endpoint_name="jurisdiction-discovery",
    workload_size="Small"
)
```

### API Usage

```python
import requests

response = requests.post(
    endpoint_url,
    headers={"Authorization": f"Bearer {databricks_token}"},
    json={
        "dataframe_records": [{
            "action": "discover",
            "params": {"limit": 100, "state": "CA"}
        }]
    }
)
```

### When to Use

- API-based workflows
- Integration with other services
- Multi-agent orchestration
- Need programmatic access

### Performance

- **Speed**: On-demand (scales automatically)
- **Cost**: $0.50-2/hour with scale-to-zero
- **Scale**: Unlimited via API

---

## Comparison Matrix

| Feature | Local CLI | Databricks Notebook | AgentBricks |
|---------|-----------|---------------------|-------------|
| **Setup Time** | 5 minutes | 15 minutes | 30 minutes |
| **Cost** | $0 | $8-15/run | $0.50-2/hr |
| **Speed** | 3-5 min/100 | 2-4 hrs/30k | On-demand |
| **Scale** | Limited | High | Auto-scale |
| **API Access** | ❌ | ❌ | ✅ |
| **Scheduling** | ❌ | ✅ | ✅ |
| **Best For** | Testing | Production | API Integration |

---

## Recommended Workflow

### Phase 1: Test Locally
```bash
python main.py discover-jurisdictions --limit 100
python main.py discovery-stats
```

### Phase 2: Production Run
Upload notebook to Databricks and run full discovery with parallel processing.

### Phase 3: Ongoing Operations
Schedule monthly re-discovery job in Databricks Workflows.

---

## Cost Analysis

**No External API Costs!** 🎉

Old approach (deprecated):
- ~~Google Search: $150~~
- ~~Bing Search: $90~~
- ~~Total: $240~~

New approach (pattern-based):
- Local: **$0**
- Databricks: **$8-15** (compute only)
- AgentBricks: **$0.50-2/hour**

**Savings: $240 per discovery run** ✅

---

**All options are production-ready and use sustainable, vendor-neutral methods!** 🚀
