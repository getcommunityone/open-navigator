# Policy Accountability Dashboards

**Evidence-based accountability dashboards for local government policy advocacy**

Interactive web dashboards that expose gaps between rhetoric and reality, deferral tactics, and power imbalances in local government decision-making.

## Quick Start

```bash
# Install dependencies
cd frontend/policy-dashboards
npm install

# Start development server
npm start
```

The app will open at `http://localhost:3000`

## Overview

This React application visualizes accountability data from local government meetings and budgets. It presents four key dashboards:

1. **They cut health spending while praising wellness** - Rhetoric vs. reality gap
2. **Delayed 6 months and counting** - Sequential deferral patterns  
3. **What got funded instead** - Budget displacement analysis
4. **One memo beat 240 residents** - Influence power mapping

Plus a **Summary** page that provides an overview and strategic guidance.

## Data Integration

### Automatic Data Export from Python

The Python accountability analysis automatically exports data for the frontend:

```bash
# Run the full analysis (includes frontend export)
python examples/tuscaloosa_accountability_report.py
```

This generates: `frontend/policy-dashboards/src/data/dashboardData.js`

### Manual Data Updates

To update dashboard data manually, edit `src/data/dashboardData.js`:

```javascript
export const rhetoricGapData = {
  sentimentScore: 92,     // Update this
  budgetDelta: -120000,   // And this
  // ... more fields
};
```

## Project Structure

```
frontend/policy-dashboards/
├── public/
│   └── index.html
├── src/
│   ├── components/
│   │   ├── shared/           # Reusable components
│   │   │   ├── BarMeter.jsx
│   │   │   ├── MetricCard.jsx
│   │   │   ├── Compare.jsx
│   │   │   └── InsightBox.jsx
│   │   ├── Summary.jsx       # Summary dashboard
│   │   ├── WordsVsDollars.jsx    # Dashboard 1
│   │   ├── EndlessStudyLoop.jsx  # Dashboard 2
│   │   ├── WhereMoneyWent.jsx    # Dashboard 3
│   │   └── WhoIsInCharge.jsx     # Dashboard 4
│   ├── data/
│   │   └── dashboardData.js  # All dashboard data (UPDATE THIS)
│   ├── App.jsx
│   └── index.js
├── package.json
└── README.md
```

## Features

### Per-Capita Benchmarks

Each dashboard includes comparisons to:
- This District
- Republican Districts Average
- Democratic Districts Average  
- National Average

This framing shows the issue transcends partisan politics.

### Interactive Navigation

- Click dashboard titles in tabs to switch views
- Click summary findings to jump to detailed dashboards
- Clean, print-friendly design

### Export to PDF

Add PDF export capability:

```bash
npm install html2canvas jspdf
```

Then add a download button (see component code for implementation).

## Customization

### Change Colors

Edit the color variables in each component:

```javascript
const colors = { 
  positive: "#1D9E75",   // Green
  negative: "#D85A30",   // Red/orange
  neutral: "#222"        // Dark gray
};
```

### Add New Benchmarks

Update the `benchmarks` object in `dashboardData.js`:

```javascript
benchmarks: {
  thisDistrict: { perStudent: 41, label: "This District" },
  // Add more comparison groups here
}
```

### Customize Dashboard Names

Edit the `tabs` array in `src/App.jsx`:

```javascript
const tabs = [
  { id: 1, label: 'Your Custom Title Here', component: WordsVsDollars },
  // ...
];
```

## Deployment

### Build for Production

```bash
npm run build
```

This creates an optimized build in `build/` folder.

### Deploy to GitHub Pages

```bash
# Install GitHub Pages package
npm install --save-dev gh-pages

# Add to package.json scripts:
"predeploy": "npm run build",
"deploy": "gh-pages -d build"

# Deploy
npm run deploy
```

### Deploy to Netlify/Vercel

1. Connect your repository to Netlify or Vercel
2. Set build command: `npm run build`
3. Set publish directory: `build`
4. Deploy!

## Presentation Mode

Add URL parameter support for presentation mode (stacks all dashboards vertically):

```javascript
// In App.jsx
const urlParams = new URLSearchParams(window.location.search);
const presentMode = urlParams.get('mode') === 'present';
```

Then visit: `http://localhost:3000?mode=present`

## Data Sources

The accountability dashboards use data from:

- **NCES Common Core of Data (CCD)** - School district financials
- **ASTDD State Oral Health Programs** - Program tracking
- **NCES F-33 Survey** - Capital outlay by function
- **National Association of School Nurses** - Liability data
- **ADA Health Policy Institute** - Dental health metrics

All sources are cited in dashboard components.

## Strategic Usage

### For Board Meetings

1. Start with **Summary** to set context
2. Move to **specific dashboard** based on board response
3. Use the "Ask them" boxes for direct questions

### For Media

Lead with **Dashboard 4** (Influence Radar) - it's the headline:
> "Risk Manager's One Memo Outweighed 240 Citizen Testimonies"

### For Advocacy Training

Show all four to demonstrate:
- Data-driven approach
- Understanding of political dynamics  
- Ability to counter deflection tactics

## Development

### Available Scripts

- `npm start` - Development server
- `npm run build` - Production build
- `npm test` - Run tests
- `npm run eject` - Eject from Create React App

### Adding New Dashboards

1. Create component in `src/components/`
2. Add data to `src/data/dashboardData.js`
3. Import and add to tabs in `src/App.jsx`
4. Update Python export function

## Support

For questions or issues:

- **Documentation**: See `docs/ACCOUNTABILITY_DASHBOARD_STRATEGY.md`
- **Python Backend**: See `extraction/accountability_dashboards.py`
- **Examples**: See `examples/tuscaloosa_accountability_report.py`

## License

Part of the Open Navigator project.

---

**Built with React** | **Designed for Policy Advocacy** | **Evidence-Based Accountability**
