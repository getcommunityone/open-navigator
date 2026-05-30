# Frontend Integration Guide

Complete guide for integrating the React Policy Accountability Dashboards with the Python backend.

## Quick Start

```bash
# 1. Generate data from Python analysis
cd /home/developer/projects/open-navigator
source .venv/bin/activate
python examples/tuscaloosa_accountability_report.py

# 2. Start frontend
cd frontend/policy-dashboards
npm install
npm start
```

## Architecture

```
Python Backend (Data Generation)
    ↓
    ├── Scrape meetings (agents/scraper.py)
    ├── Extract decisions (extraction/decision_analyzer.py)
    ├── Calculate accountability metrics (extraction/accountability_dashboards.py)
    ├── Generate dashboards (examples/tuscaloosa_accountability_report.py)
    ↓
Output Files
    ├── output/tuscaloosa_accountability_dashboards.json (Python format)
    └── frontend/policy-dashboards/src/data/dashboardData.js (React format)
    ↓
React Frontend (Visualization)
    ├── Load dashboardData.js
    ├── Render 4 dashboards + summary
    └── Display at http://localhost:3000
```

## Data Flow

### 1. Python Analysis

```python
# examples/tuscaloosa_accountability_report.py

# Generate all accountability dashboards
dashboards = generate_all_accountability_dashboards(
    jurisdiction="Tuscaloosa, AL",
    meeting_documents=documents,
    decisions=all_decisions,
    budget_items=all_budget_items
)

# Export for frontend (automatically called)
export_for_frontend(dashboards)
```

### 2. JavaScript Data Format

The export function converts Python dataclasses to JavaScript modules:

**Python:**
```python
@dataclass
class RhetoricGapMetrics:
    sentiment_density: float = 92.0
    budget_change_dollars: float = -120000
```

**JavaScript:**
```javascript
export const rhetoricGapData = {
  sentimentScore: 92,
  budgetDelta: -120000,
  // ... more fields
};
```

### 3. React Components

```jsx
// src/components/WordsVsDollars.jsx
import { rhetoricGapData as d } from '../data/dashboardData';

export default function WordsVsDollars() {
  return (
    <MetricCard 
      value={`${d.sentimentScore}%`}
      label="Positive sentiment" 
    />
  );
}
```

## Component Structure

```
frontend/policy-dashboards/src/
├── components/
│   ├── shared/                    # Reusable UI components
│   │   ├── BarMeter.jsx          # Horizontal bar charts
│   │   ├── MetricCard.jsx        # Key metric display
│   │   ├── Compare.jsx           # 4-column benchmark comparison
│   │   └── InsightBox.jsx        # Summary/logic boxes
│   ├── Summary.jsx               # Summary dashboard (tab 0)
│   ├── WordsVsDollars.jsx        # Dashboard 1: Rhetoric Gap
│   ├── EndlessStudyLoop.jsx      # Dashboard 2: Deferral Pattern
│   ├── WhereMoneyWent.jsx        # Dashboard 3: Displacement Matrix
│   └── WhoIsInCharge.jsx         # Dashboard 4: Influence Radar
├── data/
│   └── dashboardData.js          # ⚠️ AUTO-GENERATED FROM PYTHON
├── App.jsx                        # Main app shell with tabs
└── index.js                       # React entry point
```

## Customization

### Change Dashboard Titles

Edit `src/App.jsx`:

```jsx
const tabs = [
  { id: 0, label: 'Summary', component: Summary },
  { id: 1, label: 'Your Custom Title', component: WordsVsDollars },
  // ...
];
```

### Update Benchmark Data

Currently benchmarks use **placeholder values**. To add real data:

**Option 1: Update Python Export**

```python
# In examples/tuscaloosa_accountability_report.py

def calculate_real_benchmarks(jurisdiction):
    """Query NCES data for real benchmarks."""
    # Query NCES Common Core of Data
    republican_districts = nces_api.query(party="R")
    democratic_districts = nces_api.query(party="D")
    
    return {
        "republicanAvg": np.mean([d.per_student for d in republican_districts]),
        "democraticAvg": np.mean([d.per_student for d in democratic_districts]),
        # ...
    }

# In export_for_frontend()
benchmarks = calculate_real_benchmarks(jurisdiction)
```

**Option 2: Update JavaScript Directly**

```javascript
// src/data/dashboardData.js
benchmarks: {
  thisDistrict: { perStudent: 41, label: "This District" },
  republicanAvg: { perStudent: 74, label: "Republican Districts" },
  // Update these values ↑
}
```

### Add New Metrics

**1. Python Analysis**

```python
# extraction/accountability_dashboards.py

@dataclass
class RhetoricGapMetrics:
    new_metric: float  # Add field
```

**2. Python Export**

```python
# examples/tuscaloosa_accountability_report.py

js_content += f"""
  newMetric: {gap.new_metric},
"""
```

**3. React Component**

```jsx
// src/components/WordsVsDollars.jsx

<MetricCard 
  value={d.newMetric} 
  label="New Metric Description" 
/>
```

### Change Colors

```jsx
// In any component
const colors = {
  positive: "#1D9E75",   // Green - change this
  negative: "#D85A30",   // Red/orange - change this
  neutral: "#222"        // Dark gray
};
```

## Deployment

### Option 1: Static Site

```bash
cd frontend/policy-dashboards

# Build for production
npm run build

# Serve the build folder
# Upload build/* to your web server
```

### Option 2: GitHub Pages

```bash
# Install gh-pages
npm install --save-dev gh-pages

# Add to package.json:
{
  "homepage": "https://yourusername.github.io/oral-health-policy-pulse",
  "scripts": {
    "predeploy": "npm run build",
    "deploy": "gh-pages -d build"
  }
}

# Deploy
npm run deploy
```

### Option 3: Netlify/Vercel

1. Connect repository
2. Set build command: `npm run build`
3. Set publish directory: `build`
4. Deploy

### Option 4: Integrate with Python API

```python
# api/app.py (FastAPI example)
from fastapi.staticfiles import StaticFiles

app.mount(
    "/dashboards", 
    StaticFiles(directory="frontend/policy-dashboards/build", html=True),
    name="dashboards"
)
```

Access at: `http://localhost:8000/dashboards`

## Workflow

### Regular Updates

```bash
# 1. Scrape new data
python main.py scrape --state AL --municipality Tuscaloosa \
  --url https://tuscaloosaal.suiteonemedia.com \
  --platform suiteonemedia --max-events 0

# 2. Run accountability analysis (auto-exports to frontend)
python examples/tuscaloosa_accountability_report.py

# 3. Frontend auto-refreshes if dev server is running
# OR rebuild for production:
cd frontend/policy-dashboards && npm run build
```

### Data Update Frequency

- **Monthly**: Run analysis after each board meeting
- **Quarterly**: Full benchmark recalculation
- **Annual**: Major methodology updates

## Advanced Features

### PDF Export

```bash
npm install html2canvas jspdf
```

```jsx
// src/App.jsx
import html2canvas from 'html2canvas';
import jsPDF from 'jspdf';

function downloadPDF() {
  const element = document.getElementById('dashboard-container');
  html2canvas(element).then(canvas => {
    const pdf = new jsPDF();
    pdf.addImage(canvas.toDataURL('image/png'), 'PNG', 0, 0);
    pdf.save('tuscaloosa-accountability.pdf');
  });
}

// Add button:
<button onClick={downloadPDF}>Download PDF</button>
```

### Presentation Mode

Stack all dashboards for scrollable handout:

```jsx
// src/App.jsx
const searchParams = new URLSearchParams(window.location.search);
const presentMode = searchParams.get('mode') === 'present';

// Render differently based on mode
```

Visit: `http://localhost:3000?mode=present`

### Real-Time API Integration

```jsx
// src/App.jsx
import { useState, useEffect } from 'react';

function App() {
  const [data, setData] = useState(null);
  
  useEffect(() => {
    fetch('/api/accountability/latest')
      .then(res => res.json())
      .then(data => setData(data));
  }, []);
  
  // ...
}
```

## Troubleshooting

### Issue: Data Not Updating

**Solution:**
```bash
# Verify Python export ran
ls -la frontend/policy-dashboards/src/data/dashboardData.js

# Check file timestamp
stat frontend/policy-dashboards/src/data/dashboardData.js

# Restart dev server
cd frontend/policy-dashboards
npm start
```

### Issue: Build Errors

**Solution:**
```bash
# Clear cache
rm -rf node_modules package-lock.json

# Reinstall
npm install

# Try again
npm start
```

### Issue: Wrong Data Showing

**Solution:**
```bash
# Check which data file React is loading
grep -r "dashboardData" frontend/policy-dashboards/src/

# Verify export path in Python
grep "export_for_frontend" examples/tuscaloosa_accountability_report.py
```

### Issue: Benchmarks Are Placeholders

**Expected** - Benchmark data currently uses illustrative values.

**To Fix:**
1. Add NCES data query to Python analysis
2. Calculate per-student averages by party affiliation
3. Update `export_for_frontend()` function

See: "Update Benchmark Data" section above

## Testing

### Manual Testing Checklist

- [ ] Python analysis runs without errors
- [ ] `dashboardData.js` file is generated
- [ ] File timestamp is recent
- [ ] React dev server starts
- [ ] All 5 tabs load correctly
- [ ] Data matches Python output
- [ ] Benchmarks display (even if placeholder)
- [ ] "Ask them" boxes show correct questions

### Automated Testing

```bash
cd frontend/policy-dashboards

# Run tests
npm test

# Coverage report
npm test -- --coverage
```

## Resources

- **React Docs**: https://react.dev/
- **Create React App**: https://create-react-app.dev/
- **Python Backend**: `extraction/accountability_dashboards.py`
- **Strategy Guide**: `docs/ACCOUNTABILITY_DASHBOARD_STRATEGY.md`
- **NCES Data**: https://nces.ed.gov/ccd/

## Support

For issues:
1. Check this guide
2. Review `frontend/policy-dashboards/README.md`
3. Check Python logs: `logs/`
4. Open GitHub issue

---

**Integration Complete** ✅ Python analysis → JavaScript export → React visualization
