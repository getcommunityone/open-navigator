---
sidebar_position: 1
---

# Databricks Apps Deployment Guide

## Overview

The CommunityOne Open Navigatory application has been refactored as a **React + FastAPI Databricks App**, providing:

- 🎨 **Modern React UI** with TypeScript, Tailwind CSS, and interactive visualizations
- ⚡ **FastAPI Backend** serving both API and static frontend
- ☁️ **Databricks Apps Deployment** with Unity Catalog integration
- 🔒 **Enterprise Security** via Databricks secrets and authentication
- 📊 **Real-time Analytics** powered by Delta Lake and Model Serving

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Databricks Workspace                   │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │         Databricks App (This Application)        │   │
│  │                                                  │   │
│  │  ┌──────────────┐      ┌──────────────────┐    │   │
│  │  │ React        │ ───▶ │ FastAPI Backend   │    │   │
│  │  │ Frontend     │      │                   │    │   │
│  │  │ (TypeScript) │      │ • REST API        │    │   │
│  │  │              │      │ • Static Serving  │    │   │
│  │  └──────────────┘      └──────────────────┘    │   │
│  │                               │                 │   │
│  └───────────────────────────────┼─────────────────┘   │
│                                  │                      │
│  ┌───────────────────────────────▼─────────────────┐   │
│  │          Unity Catalog & Delta Lake             │   │
│  │  • raw_documents                                │   │
│  │  • classified_documents                         │   │
│  │  • advocacy_opportunities                       │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │           Model Serving Endpoints                │   │
│  │  • policy-classifier-prod                       │   │
│  │  • sentiment-analyzer-prod                      │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Prerequisites

### 1. Databricks Workspace
- Databricks Runtime 14.3 LTS ML or higher
- Unity Catalog enabled
- Model Serving enabled

### 2. Local Development Tools
- Python 3.11+
- Node.js 20+
- Databricks CLI

### 3. API Keys
- OpenAI API key (for LLM-based classification)
- Anthropic API key (optional)

---

## Local Development

### Setup

```bash
# Clone and setup
cd open-navigator
./scripts/setup-local.sh
```

### Run Development Server

**Option 1: Separate Frontend + Backend (Hot Reload)**

```bash
# Terminal 1 - Backend
source venv/bin/activate
uvicorn api.app:app --reload

# Terminal 2 - Frontend  
cd frontend
npm run dev
```

Visit: http://localhost:3000

**Option 2: Production Mode (Serves Built Frontend)**

```bash
# Build frontend first
cd frontend
npm run build
cd ..

# Run app
source venv/bin/activate
python scripts/test-app.py
```

Visit: http://localhost:8000

---

## Deploying to Databricks Apps

### Step 1: Configure Environment

```bash
# Set Databricks credentials
export DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
export DATABRICKS_TOKEN=dapi1234567890abcdef

# Set API keys
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
```

### Step 2: Deploy

```bash
# One-command deployment
./scripts/deploy-databricks-app.sh
```

This script will:
1. ✅ Build React frontend (optimized production build)
2. ✅ Create Databricks secrets for credentials
3. ✅ Deploy app to Databricks Apps
4. ✅ Configure Model Serving endpoints
5. ✅ Provide access URL

### Step 3: Access Your App

Once deployed, access at:
```
https://your-workspace.cloud.databricks.com/apps/open-navigator
```

---

## Configuration

### app.yaml

The main configuration file for Databricks Apps:

```yaml
command:
  - "uvicorn"
  - "api.app:app"
  - "--host"
  - "0.0.0.0"
  - "--port"
  - "8000"

env:
  - name: DATABRICKS_HOST
    valueFrom:
      databricksSecret:
        key: host
        scope: oral-health-app
  - name: OPENAI_API_KEY
    valueFrom:
      databricksSecret:
        key: openai_key
        scope: oral-health-app

resources:
  - name: policy-classifier-endpoint
    modelServing:
      endpoint: policy-classifier-prod

port: 8000
```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABRICKS_HOST` | Workspace URL | Yes |
| `DATABRICKS_TOKEN` | Access token | Yes |
| `DATABRICKS_WAREHOUSE_ID` | SQL warehouse ID | Yes |
| `OPENAI_API_KEY` | OpenAI API key | Yes |
| `ANTHROPIC_API_KEY` | Anthropic API key | No |
| `CATALOG_NAME` | Unity Catalog name | Yes |
| `SCHEMA_NAME` | Schema name | Yes |

---

## Frontend Features

### Dashboard
- 📊 Real-time statistics
- 📈 Topic distribution charts
- 📋 Recent opportunities list

### Interactive Heatmap
- 🗺️ Geographic visualization
- 🎯 Filterable by state, topic, urgency
- 💡 Click markers for details

### Documents Browser
- 🔍 Full-text search
- 📄 Paginated results
- 🏷️ Topic tags

### Opportunities Manager
- 🚨 Urgency-based filtering
- ✉️ One-click email generation
- 📅 Meeting calendar integration

### Settings Panel
- ⚙️ Configure target states
- 📝 Select policy topics
- 🔔 Email notifications
- 📊 Agent status monitoring

---

## API Endpoints

### Core Endpoints

```
GET  /api/health                    - Health check
GET  /api/dashboard                 - Dashboard statistics
GET  /api/opportunities             - List opportunities (filterable)
GET  /api/documents                 - List documents (searchable)
POST /api/workflow/start            - Start analysis workflow
GET  /api/workflow/{id}/status      - Check workflow status
POST /api/advocacy/email/{id}       - Generate advocacy email
GET  /api/settings                  - Get settings
PUT  /api/settings                  - Update settings
GET  /api/agents/status             - Agent health status
```

### API Documentation

Once deployed, access interactive API docs at:
- Swagger UI: `https://your-app-url/api/docs`
- ReDoc: `https://your-app-url/api/redoc`

---

## Monitoring

### View App Logs

```bash
databricks apps logs open-navigator
```

### Check App Status

```bash
databricks apps get open-navigator
```

### Monitor Model Serving

```bash
databricks serving-endpoints get policy-classifier-prod
databricks serving-endpoints get sentiment-analyzer-prod
```

---

## Troubleshooting

### Issue: "Frontend not built"

**Solution:**
```bash
cd frontend
npm install
npm run build
```

### Issue: "Databricks CLI not found"

**Solution:**
```bash
pip install databricks-cli
databricks configure --token
```

### Issue: "Secrets not accessible"

**Solution:**
```bash
# Recreate secrets scope
databricks secrets create-scope --scope oral-health-app
databricks secrets put --scope oral-health-app --key host --string-value "$DATABRICKS_HOST"
databricks secrets put --scope oral-health-app --key openai_key --string-value "$OPENAI_API_KEY"
```

### Issue: "App deployment failed"

**Check logs:**
```bash
databricks apps logs open-navigator --follow
```

---

## Cost Optimization

### Databricks Apps Pricing

| Component | Cost Estimate |
|-----------|---------------|
| App hosting | $0.10-0.30/hour |
| Model Serving (Small) | $0.10-0.50/hour |
| Delta Lake storage | $0.023/GB/month |
| SQL Warehouse | Pay per query |

**Total estimated cost:** ~$50-150/month for moderate usage

### Cost Savings Tips

1. **Scale-to-zero**: Model serving endpoints automatically scale down when idle
2. **Batch processing**: Process documents in batches rather than real-time
3. **Hybrid classification**: Use keyword matching before LLM calls (saves ~70% LLM costs)
4. **Delta Lake optimization**: Enable auto-compaction and Z-ordering

---

## Security

### Authentication

Databricks Apps automatically integrate with:
- ✅ Workspace SSO
- ✅ OAuth 2.0
- ✅ SCIM user provisioning

### Data Access

All data access is governed by:
- ✅ Unity Catalog permissions
- ✅ Row-level security
- ✅ Column-level masking

### Secrets Management

Sensitive credentials stored in:
- ✅ Databricks Secrets
- ✅ Never in code or logs
- ✅ Automatic rotation support

---

## Next Steps

1. **Deploy Model Serving Endpoints**
   ```bash
   python -m databricks.deployment
   ```

2. **Initialize Delta Lake Tables**
   ```sql
   -- Run in Databricks SQL
   CREATE SCHEMA IF NOT EXISTS main.agents;
   ```

3. **Start Data Ingestion**
   - Configure target municipalities
   - Run initial scraping workflow
   - Monitor agent status

4. **Customize UI**
   - Edit frontend components in `frontend/src/`
   - Rebuild: `npm run build`
   - Redeploy: `./scripts/deploy-databricks-app.sh`

---

## Support

- 📖 **Documentation**: See README.md and DATABRICKS_MIGRATION.md
- 🐛 **Issues**: Report via GitHub Issues
- 💬 **Community**: Join discussions

---

## License

MIT License - See LICENSE file for details
