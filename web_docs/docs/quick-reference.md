---
sidebar_position: 4
displayed_sidebar: developersSidebar
---

# 🚀 Quick Reference Card - Databricks App

## Development Commands

```bash
# Backend only (hot reload)
make dev

# Frontend only (hot reload)
make dev-frontend

# Both together
make dev-full

# Production build + run
make run

# Deploy to Databricks
make deploy-databricks
```

## URLs

| Environment | Backend | Frontend | Type |
|-------------|---------|----------|------|
| Development | :8000 | :3000 | Separate |
| Production | :8000 | :8000 | Combined |
| Databricks | [your-workspace]/apps/oral-health-policy-pulse | Same | Combined |

## File Structure

```
frontend/src/
  pages/
    Dashboard.tsx      # /
    Heatmap.tsx        # /heatmap
    Documents.tsx      # /documents
    Opportunities.tsx  # /opportunities
    Settings.tsx       # /settings
  components/
    Layout.tsx         # Sidebar + nav

api/
  app.py              # FastAPI (NEW)
  main.py             # Legacy CLI
  static/             # Built React

scripts/
  deploy-databricks-app.sh
  setup-local.sh
  test-app.py
```

## API Endpoints

```
GET  /api/health
GET  /api/dashboard
GET  /api/opportunities?state=CA&topic=fluoride
GET  /api/documents?search=dental&page=1
POST /api/workflow/start
POST /api/advocacy/email/{id}
GET  /api/settings
PUT  /api/settings
GET  /api/agents/status
```

## Common Tasks

### Add New Page
1. Create `frontend/src/pages/NewPage.tsx`
2. Add route in `frontend/src/App.tsx`
3. Add nav item in `frontend/src/components/Layout.tsx`

### Add API Endpoint
1. Add route in `api/app.py`
2. Add query in `pipeline/delta_lake_queries.py`
3. Call from frontend with `axios.get('/api/...')`

### Deploy Changes
```bash
cd frontend && npm run build && cd ..
./scripts/deploy-databricks-app.sh
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Frontend not built" | `cd frontend && npm run build` |
| "Module not found" | `source venv/bin/activate` |
| Backend not responding | Check port 8000 is free |
| Frontend proxy error | Ensure backend running on :8000 |

## Environment Variables

```bash
export DATABRICKS_HOST=https://...
export DATABRICKS_TOKEN=dapi...
export OPENAI_API_KEY=sk-...
```

## Cost Estimate

| Component | Cost/hour | Cost/month |
|-----------|-----------|------------|
| Databricks App | $0.10-0.30 | $75-225 |
| Model Serving | $0.10-0.50 | $75-375 |
| Delta Lake | - | $25-100 |
| **Total** | **$0.20-0.80** | **$150-700** |

*With scale-to-zero, costs drop to near $0 when idle*

---

**Keep this card handy! 📌**
