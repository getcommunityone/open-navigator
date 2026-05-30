---
title: Open Navigator
sidebar_position: 2
displayed_sidebar: gettingStartedSidebar
---

# Open Navigator

**Open Navigator** is the main application interface providing search, analysis, and visualization tools for advocacy opportunities across the United States.

## 🎯 What's Inside

The platform gives you access to:

- **925 government jurisdictions** - Counties, cities, townships, school districts
- **43,726 nonprofit organizations** - Complete IRS Form 990 financial data (5 states)
- **6,913 meeting transcripts** - Government meeting minutes
- **306 school districts** - Financial and meeting data
- **362 elected officials** - Voting records and decision patterns
- **4,372 churches** - Community-based organizations
- **5 states** - States with complete IRS BMF data

---

## 📱 Interface Overview

The interactive platform provides real-time access to:

- 📊 **Analytics** - Overview of opportunities and trends
- 🗺️ **Interactive Heatmap** - Geographic visualization of policy opportunities  
- 📄 **Document Explorer** - Search and browse meeting minutes
- 🔔 **Opportunities** - Identified advocacy opportunities
- 🏛️ **Nonprofit Solutions** - Search nonprofit organizations by location and service
- ⚙️ **Settings** - Configure alerts and preferences

## Accessing Open Navigator

### Development Mode

```bash
# Terminal 1: Start the API backend
source .venv/bin/activate
python main.py serve

# Terminal 2: Start the React frontend
cd frontend
npm install
npm run dev

# Open http://localhost:3000
```

### Production Deployment

#### Option 1: Databricks Apps (Recommended)

```bash
export DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
export DATABRICKS_TOKEN=dapi...
export OPENAI_API_KEY=sk-...

./scripts/deploy-databricks-app.sh
```

#### Option 2: Docker

```bash
docker-compose up -d
# Open Navigator available at http://localhost:8000
```

## Features

### Analytics Overview

Real-time statistics and trend analysis:
- Active opportunities by state and topic
- Urgency distribution
- Recent discoveries
- Top locations

### Interactive Heatmap

Color-coded map showing:
- 🔴 Critical urgency (vote imminent)
- 🟠 High urgency (active debate)
- 🟡 Medium urgency (moderate discussion)  
- 🟢 Low urgency (early stage)

Click any marker for full details and generated advocacy materials.

### Document Explorer

Search and filter capabilities:
- Full-text search across meeting minutes
- Filter by jurisdiction, date, topic
- View original documents and parsed data
- Export results

### Nonprofit Search

Find local organizations:
- Search by location and keyword
- Filter by NTEE category (health, education, etc.)
- View financial data from Form 990s
- Access mission statements and contact info

## API Integration

Open Navigator communicates with the FastAPI backend:

**Base URL:** `http://localhost:8000/api`

**Key Endpoints:**
- `GET /api/opportunities` - List advocacy opportunities
- `GET /api/documents` - Search meeting minutes
- `GET /api/nonprofits` - Search nonprofit organizations
- `GET /api/data/status` - Check data ingestion status

See the [API Reference](/docs/api) for complete documentation.

## Need Help?

- Browse the [Documentation](/docs/intro)
- [Report an Issue](https://github.com/getcommunityone/open-navigator-for-engagement/issues)
- [Request a Feature](https://github.com/getcommunityone/open-navigator-for-engagement/issues/new)

---

<div class="alert alert--success">
  <strong>Quick Links</strong>
  <ul>
    <li><a href="http://localhost:3000" target="_blank">Open Navigator (Dev)</a></li>
    <li><a href="http://localhost:8000/docs" target="_blank">API Docs (Dev)</a></li>
    <li><a href="/intro">Project Documentation</a></li>
  </ul>
</div>
