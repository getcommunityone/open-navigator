---
sidebar_position: 13
---

# React + FastAPI Databricks App Refactoring

## Executive Summary

The CommunityOne Open Navigatory has been **completely refactored** from a CLI-based multi-agent system into a **modern full-stack web application** that deploys as a **Databricks App**.

### What Changed

| Before (v1.0) | After (v2.0) |
|---------------|--------------|
| ❌ CLI-only interface | ✅ Modern React web UI |
| ❌ Manual command execution | ✅ Interactive dashboard |
| ❌ Text-based outputs | ✅ Visual charts & maps |
| ❌ Local deployment only | ✅ Cloud-native Databricks Apps |
| ❌ Static HTML heatmap | ✅ Interactive Leaflet map |
| ❌ No user settings | ✅ Configurable UI settings |

---

## New Architecture

### Frontend (React + TypeScript)

**Technology Stack:**
- React 18.2 with TypeScript
- Vite for build tooling
- Tailwind CSS for styling
- React Router for navigation
- TanStack Query for data fetching
- Recharts for data visualization
- Leaflet for interactive maps

**Pages Created:**
1. **Dashboard** (`frontend/src/pages/Dashboard.tsx`)
   - Real-time statistics cards
   - Topic distribution bar/pie charts
   - Recent opportunities table
   
2. **Interactive Heatmap** (`frontend/src/pages/Heatmap.tsx`)
   - Geographic visualization using Leaflet
   - State and topic filters
   - Color-coded urgency markers
   - Popup details for each opportunity
   
3. **Documents Browser** (`frontend/src/pages/Documents.tsx`)
   - Full-text search
   - Pagination
   - Topic tags
   - Direct links to source documents
   
4. **Opportunities Manager** (`frontend/src/pages/Opportunities.tsx`)
   - Filterable list view
   - Urgency-based sorting
   - One-click email generation
   - Talking points display
   - Confidence score visualization
   
5. **Settings Panel** (`frontend/src/pages/Settings.tsx`)
   - Target state configuration
   - Policy topic selection
   - Confidence threshold slider
   - Email notification preferences
   - Agent status monitoring

**Components:**
- **Layout** (`frontend/src/components/Layout.tsx`)
  - Sidebar navigation
  - Header with breadcrumbs
  - Responsive design

### Backend (FastAPI Refactored)

**New File: `api/app.py`**

Completely rewritten FastAPI application optimized for:
- ✅ Serving React static files (SPA routing)
- ✅ REST API endpoints for all frontend interactions
- ✅ Databricks Apps compatibility
- ✅ Delta Lake integration
- ✅ Background task processing
- ✅ CORS support for local development

**Key Endpoints:**
```
GET  /api/health                    # Health check
GET  /api/dashboard                 # Dashboard stats
GET  /api/opportunities             # List opportunities
GET  /api/documents                 # Browse documents
POST /api/workflow/start            # Start analysis
POST /api/advocacy/email/{id}       # Generate email
GET  /api/settings                  # Get settings
PUT  /api/settings                  # Update settings
GET  /api/agents/status             # Agent status
```

**Static File Serving:**
- React build output served from `api/static/`
- SPA routing with catchall route
- Automatic index.html fallback

### Database Layer

**New File: `pipeline/delta_lake_queries.py`**

Added async query methods to support web app:
```python
async def get_dashboard_stats()       # Dashboard statistics
async def query_opportunities()       # Filtered opportunity queries
async def query_documents()           # Document search/pagination
async def count_documents()           # Total count for pagination
async def get_opportunity()           # Single opportunity details
```

---

## Databricks Apps Integration

### Configuration Files

**1. app.yaml** (Databricks Apps manifest)
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

**2. Dockerfile.app** (Container image for Databricks Apps)
- Multi-stage build
- Node.js for frontend build
- Python 3.11 for backend
- Optimized for CPU-only deployment

### Deployment Scripts

**1. scripts/deploy-databricks-app.sh**
```bash
# Automated deployment script:
# 1. Build React frontend
# 2. Create Databricks secrets
# 3. Deploy to Databricks Apps
# 4. Provide access URL
```

**2. scripts/setup-local.sh**
```bash
# Local development setup:
# - Install Python deps
# - Install npm packages
# - Create .env file
```

**3. scripts/test-app.py**
```python
# Test production build locally
# Simulates Databricks Apps environment
```

---

## Project Structure

```
oral-health-policy-pulse/
├── frontend/                      # NEW: React application
│   ├── src/
│   │   ├── components/
│   │   │   └── Layout.tsx        # Main layout component
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx     # Dashboard page
│   │   │   ├── Heatmap.tsx       # Interactive map
│   │   │   ├── Documents.tsx     # Document browser
│   │   │   ├── Opportunities.tsx # Opportunity manager
│   │   │   └── Settings.tsx      # Settings panel
│   │   ├── App.tsx               # Root component
│   │   ├── main.tsx              # Entry point
│   │   └── index.css             # Tailwind styles
│   ├── package.json              # npm dependencies
│   ├── vite.config.ts            # Vite configuration
│   ├── tsconfig.json             # TypeScript config
│   ├── tailwind.config.js        # Tailwind config
│   └── index.html                # HTML template
│
├── api/
│   ├── app.py                    # NEW: Refactored FastAPI app
│   ├── main.py                   # LEGACY: Original API
│   └── static/                   # Built React files (generated)
│
├── pipeline/
│   ├── delta_lake.py             # Original Delta Lake pipeline
│   └── delta_lake_queries.py     # NEW: Query methods for web app
│
├── scripts/                       # NEW: Deployment scripts
│   ├── deploy-databricks-app.sh  # Deploy to Databricks
│   ├── setup-local.sh            # Local development setup
│   └── test-app.py               # Test production build
│
├── app.yaml                       # NEW: Databricks Apps config
├── Dockerfile.app                 # NEW: Production Docker image
├── DATABRICKS_APP_GUIDE.md        # NEW: Deployment documentation
└── README.md                      # UPDATED: Added React info
```

---

## Features by Page

### 1. Dashboard

**Statistics Cards:**
- Total documents analyzed
- Advocacy opportunities found
- States monitored

**Charts:**
- Topic distribution (bar chart)
- Topic distribution (pie chart)

**Recent Activity:**
- Latest opportunities table
- Sortable and filterable

### 2. Interactive Heatmap

**Map Features:**
- OpenStreetMap tiles
- Circle markers for opportunities
- Color-coded by urgency:
  - 🔴 Critical
  - 🟠 High
  - 🟡 Medium
  - 🟢 Low

**Interactivity:**
- Click markers for details
- Filter by state dropdown
- Filter by topic dropdown
- Real-time updates

### 3. Document Browser

**Features:**
- Full-text search across all documents
- Pagination (20 per page)
- Topic tags for each document
- Direct links to source
- Meeting date display
- State/municipality info

### 4. Opportunities Manager

**Display:**
- Card-based layout
- Urgency badge
- Key talking points
- Confidence score bar

**Actions:**
- Generate advocacy email
- Contact via email
- Add to calendar
- Copy talking points

**Filters:**
- Critical only
- High priority
- Medium priority
- Low priority

### 5. Settings Panel

**Configuration Options:**
- Target states (multi-select)
- Policy topics (checkboxes)
- Confidence threshold (slider)
- Email notifications (toggle)

**System Status:**
- Agent health indicators
- Uptime display
- Real-time status

---

## Development Workflow

### Local Development

**1. Backend (Hot Reload)**
```bash
source venv/bin/activate
uvicorn api.app:app --reload
# Runs on http://localhost:8000
```

**2. Frontend (Hot Reload)**
```bash
cd frontend
npm run dev
# Runs on http://localhost:3000
# Proxies API calls to :8000
```

### Production Build

**1. Build Frontend**
```bash
cd frontend
npm run build
# Outputs to api/static/
```

**2. Test Locally**
```bash
python scripts/test-app.py
# Serves at http://localhost:8000
```

**3. Deploy to Databricks**
```bash
./scripts/deploy-databricks-app.sh
# One-command deployment
```

---

## Benefits of Refactoring

### User Experience

| Before | After |
|--------|-------|
| Command-line only | Beautiful web interface |
| Manual file management | Automatic workflows |
| Static visualizations | Interactive maps & charts |
| No configuration UI | Full settings panel |
| Email via CLI | One-click generation |

### Developer Experience

| Before | After |
|--------|-------|
| Python-only | Full-stack (Python + TypeScript) |
| Local deployment | Cloud-native (Databricks Apps) |
| Manual setup | One-command deployment |
| Limited monitoring | Built-in observability |
| No UI testing | Component testing with Vitest |

### Operations

| Before | After |
|--------|-------|
| Single-user CLI | Multi-user web app |
| Local storage | Cloud Delta Lake |
| Manual scaling | Auto-scaling |
| No authentication | Databricks SSO |
| Basic logging | Enterprise monitoring |

---

## Technology Choices

### Why React?
- ✅ Industry-standard UI framework
- ✅ Rich ecosystem of libraries
- ✅ TypeScript support for type safety
- ✅ Excellent developer experience
- ✅ Easy to maintain and extend

### Why Vite?
- ✅ Lightning-fast dev server
- ✅ Instant hot module replacement
- ✅ Optimized production builds
- ✅ Native ES modules support
- ✅ Built-in TypeScript support

### Why Tailwind CSS?
- ✅ Utility-first approach
- ✅ Rapid prototyping
- ✅ Consistent design system
- ✅ Small production bundle
- ✅ Highly customizable

### Why Databricks Apps?
- ✅ Integrated with workspace
- ✅ Automatic authentication
- ✅ Unity Catalog integration
- ✅ Seamless data access
- ✅ Enterprise-ready

---

## Migration Path

### For Existing Users

**v1.0 (CLI) → v2.0 (Web App)**

1. **Keep using CLI** - Original functionality preserved in `api/main.py`
2. **Gradually adopt web UI** - Run both simultaneously
3. **Full migration** - Switch to web-only when ready

**Backward Compatibility:**
- All CLI commands still work
- Original API endpoints unchanged
- Can run standalone or web mode

### For New Users

**Start with Web UI:**
1. Deploy to Databricks Apps
2. Access via browser
3. No CLI needed!

---

## Performance Optimizations

### Frontend
- ✅ Code splitting with React lazy loading
- ✅ Query caching with TanStack Query
- ✅ Optimized bundle size (~300KB gzipped)
- ✅ Lazy-loaded charts and maps
- ✅ Debounced search inputs

### Backend
- ✅ Async endpoints with FastAPI
- ✅ Background task processing
- ✅ Delta Lake query optimization
- ✅ Static file caching
- ✅ CORS preflight caching

### Deployment
- ✅ Scale-to-zero when idle
- ✅ Auto-scaling under load
- ✅ CDN for static assets
- ✅ Connection pooling
- ✅ Gzip compression

---

## Next Steps

### Planned Features

**Phase 1: Enhanced Analytics**
- [ ] Historical trend charts
- [ ] Predictive analytics
- [ ] Custom report builder

**Phase 2: Collaboration**
- [ ] User comments/notes
- [ ] Shared dashboards
- [ ] Team workspaces

**Phase 3: Automation**
- [ ] Scheduled reports
- [ ] Email alerts
- [ ] Slack integration

**Phase 4: Advanced AI**
- [ ] Document Q&A chatbot
- [ ] Meeting video analysis
- [ ] Speech-to-text integration

---

## Deployment Examples

### Example 1: Local Testing

```bash
# Setup
./scripts/setup-local.sh
source venv/bin/activate

# Run backend
uvicorn api.app:app --reload &

# Run frontend
cd frontend && npm run dev
```

### Example 2: Production Deployment

```bash
# Configure
export DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
export DATABRICKS_TOKEN=dapi...
export OPENAI_API_KEY=sk-...

# Deploy
./scripts/deploy-databricks-app.sh

# Monitor
databricks apps logs oral-health-policy-pulse --follow
```

### Example 3: Docker Deployment

```bash
# Build
docker build -f Dockerfile.app -t oral-health-app .

# Run
docker run -p 8000:8000 \
  -e DATABRICKS_HOST=$DATABRICKS_HOST \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  oral-health-app
```

---

## Conclusion

The **React + FastAPI refactoring** transforms CommunityOne Open Navigatory from a developer-focused CLI tool into an **enterprise-ready web application** that can be:

✅ **Deployed instantly** to Databricks Apps  
✅ **Used by non-technical users** via web browser  
✅ **Scaled automatically** for any load  
✅ **Monitored comprehensively** with built-in observability  
✅ **Secured enterprise-grade** with Databricks SSO  

**The future of oral health advocacy is here! 🦷✨**
