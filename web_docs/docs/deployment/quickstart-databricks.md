---
sidebar_position: 3
---

# Quick Start Guide - React + FastAPI Databricks App

## 🚀 Deploy to Databricks Apps (5 minutes)

### Prerequisites
- Databricks workspace with Apps enabled
- OpenAI API key

### Steps

```bash
# 1. Set environment variables
export DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
export DATABRICKS_TOKEN=dapi1234567890abcdef
export OPENAI_API_KEY=sk-...

# 2. Deploy!
./scripts/deploy-databricks-app.sh

# 3. Access your app
# https://your-workspace.cloud.databricks.com/apps/open-navigator
```

That's it! 🎉

---

## 💻 Local Development (10 minutes)

### Option A: Hot Reload (Recommended for UI development)

```bash
# Terminal 1 - Backend
source venv/bin/activate
uvicorn api.app:app --reload
# http://localhost:8000

# Terminal 2 - Frontend (hot reload!)
cd frontend
npm install
npm run dev
# http://localhost:3000
```

### Option B: Production Mode (Test full build)

```bash
# Build frontend
cd frontend
npm install
npm run build
cd ..

# Run app
source venv/bin/activate
python scripts/test-app.py
# http://localhost:8000
```

---

## 📁 Project Structure

```
open-navigator/
├── frontend/                 # React app
│   ├── src/
│   │   ├── pages/           # Dashboard, Heatmap, etc.
│   │   └── components/      # Layout, etc.
│   └── package.json
│
├── api/
│   ├── app.py              # NEW: FastAPI for Databricks App
│   └── main.py             # LEGACY: Original CLI API
│
├── scripts/
│   ├── deploy-databricks-app.sh   # Deploy to cloud
│   ├── setup-local.sh             # Setup dev environment
│   └── test-app.py                # Test production build
│
├── app.yaml                # Databricks App config
└── Dockerfile.app          # Container image
```

---

## 🎯 Common Tasks

### Deploy to Databricks
```bash
./scripts/deploy-databricks-app.sh
```

### View App Logs
```bash
databricks apps logs open-navigator --follow
```

### Update Frontend
```bash
cd frontend
# Make changes...
npm run build
cd ..
./scripts/deploy-databricks-app.sh
```

### Run Tests
```bash
source venv/bin/activate
pytest tests/
```

### Check Agent Status
```bash
curl http://localhost:8000/api/agents/status
```

---

## 📊 Frontend Pages

| Page | Route | Description |
|------|-------|-------------|
| Dashboard | `/` | Stats, charts, recent activity |
| Heatmap | `/heatmap` | Interactive map of opportunities |
| Documents | `/documents` | Browse analyzed documents |
| Opportunities | `/opportunities` | Manage advocacy opportunities |
| Settings | `/settings` | Configure system |

---

## 🔧 Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABRICKS_HOST` | Yes | Workspace URL |
| `DATABRICKS_TOKEN` | Yes | Access token |
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `DATABRICKS_WAREHOUSE_ID` | Yes | SQL warehouse |

### Databricks Secrets

```bash
# Create secrets scope
databricks secrets create-scope --scope oral-health-app

# Add secrets
databricks secrets put --scope oral-health-app --key host --string-value "$DATABRICKS_HOST"
databricks secrets put --scope oral-health-app --key token --string-value "$DATABRICKS_TOKEN"
databricks secrets put --scope oral-health-app --key openai_key --string-value "$OPENAI_API_KEY"
```

---

## 🐛 Troubleshooting

### "Frontend not built"
```bash
cd frontend && npm install && npm run build
```

### "Module not found"
```bash
source venv/bin/activate
pip install -r requirements-cpu.txt
```

### "Databricks CLI not found"
```bash
pip install databricks-cli
```

### "Can't connect to backend"
Check that backend is running on :8000 and frontend proxies to it.

---

## 📚 Documentation

- **Full Deployment Guide**: `DATABRICKS_APP_GUIDE.md`
- **Refactoring Details**: `REACT_REFACTORING.md`
- **Agent Bricks Info**: `databricks/README.md`
- **Main README**: `README.md`

---

## 🆘 Need Help?

1. Check logs: `databricks apps logs open-navigator`
2. Review docs in the `/docs` folder
3. Open an issue on GitHub

---

## ⚡ Pro Tips

- Use `npm run dev` for instant hot reload during UI development
- Deploy often - deployment takes ~2 minutes
- Monitor with `databricks apps get open-navigator`
- Scale to zero saves costs when idle
- Use Chrome DevTools to debug React components

---

**Happy Advocating! 🦷✨**
