---
sidebar_position: 2
displayed_sidebar: developersSidebar
---

# 🏗️ Architecture Overview

## Three Separate Services

Open Navigator consists of **three distinct services** that work together:

```
┌─────────────────────────────────────────────────────────┐
│                 Open Navigator Platform                  │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  📚 Documentation Site (Docusaurus)                      │
│  └─> http://localhost:3000                              │
│      • Project overview and marketing                    │
│      • API documentation and guides                      │
│      • Installation instructions                         │
│      • Links to dashboard                                │
│                                                           │
│  ⚛️  Interactive Dashboard (React + Vite)               │
│  └─> http://localhost:5173                              │
│      • Real-time data visualization                      │
│      • Search and filter capabilities                    │
│      • Interactive heatmap                               │
│      • Document explorer                                 │
│      • Nonprofit search                                  │
│      • Opportunity tracker                               │
│                                                           │
│  🔥 API Backend (FastAPI + Python)                       │
│  └─> http://localhost:8000                              │
│      • Data ingestion and processing                     │
│      • Multi-agent AI system                             │
│      • Database connections                              │
│      • API endpoints for dashboard                       │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

## Why Three Services?

### 📚 Documentation Site (`website/`)
- **Purpose**: Documentation, guides, and project information
- **Technology**: Docusaurus (static site generator)
- **Port**: 3000
- **Use Case**: First-time visitors, documentation, API reference

### ⚛️ Dashboard (`frontend/`)
- **Purpose**: Interactive data exploration and analysis
- **Technology**: React 18 + TypeScript + Vite
- **Port**: 5173
- **Use Case**: Daily users exploring data, creating reports, searching

### 🔥 API Backend (`api/`)
- **Purpose**: Data processing and AI agents
- **Technology**: FastAPI + Python
- **Port**: 8000
- **Use Case**: Powers the dashboard, runs background jobs

## Integration Points

### Documentation → Dashboard
- Navbar has "🚀 Dashboard" link pointing to `http://localhost:5173`
- Homepage has "Launch Dashboard" button
- `/dashboard` page auto-redirects to React app

### Dashboard → API
- All data requests go to `http://localhost:8000/api/*`
- Real-time updates via API polling
- Authentication handled via API

### API → Dashboard
- Serves static built dashboard in production
- Provides REST endpoints for all data

## Development Workflow

### Option 1: Start All Services (Recommended)
```bash
./start-all.sh
```

This launches all three services in tmux:
- Window 0: API Backend
- Window 1: React Dashboard  
- Window 2: Documentation Site
- Window 3: Shell

### Option 2: Start Individually
```bash
# Terminal 1: API
source .venv/bin/activate
python main.py serve

# Terminal 2: Dashboard
cd frontend
npm run dev

# Terminal 3: Documentation
cd website
npm start
```

## Access Points

| Service       | Development URL          | Purpose                          |
|---------------|-------------------------|----------------------------------|
| Documentation | http://localhost:3000   | Read guides and API docs         |
| Dashboard     | http://localhost:5173   | **Main application interface**   |
| API           | http://localhost:8000   | Backend services                 |
| API Docs      | http://localhost:8000/docs | Interactive API reference     |

## User Journey

1. **Discovery**: User visits documentation site (port 3000)
2. **Getting Started**: Reads installation guides
3. **Launch**: Clicks "Dashboard" → Opens React app (port 5173)
4. **Usage**: Interacts with dashboard, which calls API (port 8000)

## Production Deployment

In production, the architecture changes:

```
┌─────────────────────────────────────────────────────────┐
│              Production Deployment                        │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  🌐 Reverse Proxy (nginx/Databricks Apps)               │
│  └─> https://opennavigator.org                          │
│                                                           │
│      ├─ /              → Docusaurus static build         │
│      ├─ /docs          → Docusaurus static build         │
│      ├─ /dashboard     → React static build              │
│      └─ /api/*         → FastAPI backend                 │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

### Build Commands
```bash
# Build documentation
cd website && npm run build
# Output: website/build/

# Build dashboard
cd frontend && npm run build
# Output: frontend/dist/

# Deploy backend
# FastAPI serves both static builds
```

## Key Files

### Documentation Site
- `website/docusaurus.config.ts` - Configuration
- `website/src/pages/index.tsx` - Homepage
- `website/docs/` - Documentation markdown files

### Dashboard
- `frontend/src/App.tsx` - Main routes
- `frontend/src/pages/Dashboard.tsx` - **Homepage with stats**
- `frontend/src/pages/Heatmap.tsx` - Interactive map
- `frontend/src/pages/Documents.tsx` - Search interface
- `frontend/src/pages/Nonprofits.tsx` - Nonprofit search
- `frontend/src/pages/Opportunities.tsx` - Opportunity tracker

### API
- `api/app.py` - Databricks Apps entry point
- `api/main.py` - Standalone mode
- `agents/` - Multi-agent system
- `discovery/` - Data ingestion

## Common Confusion

❌ **Wrong**: "The documentation site IS the application"
✅ **Correct**: "The documentation site LINKS TO the application"

❌ **Wrong**: "Port 3000 has search and filters"
✅ **Correct**: "Port 5173 (React dashboard) has search and filters"

❌ **Wrong**: "Docusaurus replaced the dashboard"
✅ **Correct**: "Docusaurus was added FOR documentation, dashboard is unchanged"

## Troubleshooting

### "I can't find the search feature"
→ You're on the documentation site. Click "🚀 Dashboard" in the navbar to access the React app.

### "Dashboard link goes to wrong place"
→ Make sure React dev server is running (`cd frontend && npm run dev`)

### "No data showing in dashboard"
→ Make sure API backend is running (`python main.py serve`)

### "Everything looks different"
→ Documentation site (port 3000) is new. Dashboard (port 5173) is unchanged.

## Next Steps

- [Start all services](../README.md#quick-start)
- [Dashboard documentation](../website/docs/dashboard.md)
- [API documentation](../website/docs/api.md)
