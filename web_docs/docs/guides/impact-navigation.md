---
displayed_sidebar: policyMakersSidebar
---

# Impact-Driven Navigation Guide

The frontend has been transformed from a technical data audit to a **citizen mobilization tool** with persona-based navigation.

## Quick Start

```bash
cd /home/developer/projects/open-navigator/frontend/policy-dashboards
npm start
```

Opens at `http://localhost:3000` with the new impact-focused interface.

---

## Navigation Structure

### 1. Home Page: "Tuscaloosa Decision Pulse"

**Purpose:** Big picture context that mobilizes citizens

**Components:**
- **City Pulse** - Visual comparison: $28M capital vs $2.4M health
- **Accountability Alert** - Scrolling ticker of deferrals (e.g., "152 days in limbo")
- **Persona Cards** - Find your impact by audience
- **Topic Cards** - Browse by domain

**Key Feature:** Moves from "agendas" to "impact stories"

### 2. Persona-Based Navigation (Impact Stories)

Click a persona card to see targeted impact:

#### 🏠 Parent → Student Dental Health
**Shows:** "The Learning Barrier Map"
- Left: School map with dental pain absence rates (red = high)
- Right: Veto chain flowchart (1,200 petitions → blocked by 1 memo)
- Bottom: Key fact (0 liability suits in 35 states with programs)

#### 📢 Advocate → Transparency & Vetoes
**Shows:** "The Influence Radar"
- Who has veto power
- Public input vs bureaucratic influence
- Name the blocker directly

#### 🚰 Resident → Water & Infrastructure
**Shows:** "The Lifetime Health Tax"
- Coming soon (template provided)

### 3. Browse by Topic (Filterable View)

**Primary Navigation (Topic/Domain):**
- ✅ Public Health (Dental, Water, Mental Health)
- 📚 Education & Youth (School Board, Pre-K)
- 🏗️ Infrastructure (Roads, Utilities, Construction)
- 🚨 Public Safety (Police, Fire, EMS)

**Secondary Filters (Pattern):**
- [ ] Technocratic Veto (legal/risk managers blocking)
- [ ] Sequential Deferral (repeated "tabling for study")
- [ ] Performance Rationale (rhetoric not matching funding)

**Tertiary Filters (Resource Type):**
- [ ] Video Recap
- [ ] Budget PDF
- [ ] Impact Dashboard
- [ ] Summary Notes

### 4. Analysis Dashboards (Original Technical View)

The original accountability dashboards are still available:
- Summary
- They cut health spending while praising wellness
- Delayed 6 months and counting
- What got funded instead
- One memo beat 240 residents

### 5. All Decisions (Searchable List)

Complete searchable list of decisions with:
- Policy domain badges
- Speakers and rationales
- Vote results
- Tradeoffs discussed
- Evidence cited

---

## How Citizens Use This

### Parent Journey:
1. **Lands on Home** → Sees "$28M capital vs $2.4M health"
2. **Clicks "Parent" card** → Views dental screening veto story
3. **Sees map** → Their kid's school is in red zone
4. **Sees veto chain** → Patricia Johnson blocked it with 1 memo
5. **Key fact** → 0 lawsuits in 35 states = memo has no basis
6. **Action** → Knows exactly who to call and what to ask

### Advocate Journey:
1. **Lands on Home** → Sees "152 days in limbo" alert
2. **Clicks "Advocate" card** → Views influence radar
3. **Sees data** → 92% influence from 1 memo vs 4% from 240 citizens
4. **Action** → Names veto holder in public meeting

### Journalist Journey:
1. **Browses by Topic** → Filters for "Public Health"
2. **Filters by Pattern** → Selects "Sequential Deferral"
3. **Finds story** → Dental clinic tabled 4 times with shifting excuses
4. **Clicks dashboard** → Gets full analysis with benchmarks
5. **Action** → Headline: "One Risk Manager Blocked 240 Residents"

---

## Data Flow

### Current (Example Data)
The app currently shows **example/placeholder data**. All numbers (e.g., $28M, 152 days, 1,200 petitions) are illustrative.

### Real Data Integration

To populate with actual Tuscaloosa data:

```bash
# Run Python analysis (auto-exports to frontend)
cd /home/developer/projects/open-navigator
source .venv/bin/activate
python examples/tuscaloosa_accountability_report.py
```

This updates: `frontend/policy-dashboards/src/data/dashboardData.js`

### Adding New Impact Stories

1. **Create component** in `src/components/ImpactDashboard.jsx`
2. **Add persona mapping** in the component logic
3. **Update HomePage** persona cards with new option

Example:
```javascript
// In ImpactDashboard.jsx
if (persona === 'business-owner' && topic === 'economic-development') {
  return <EconomicImpactStory />;
}
```

---

## Customization

### Change Metrics on Home Page

Edit `src/components/HomePage.jsx`:

```javascript
// Update "City Pulse" numbers
Capital Projects: $28M  // Change this
Health: $2.4M           // And this

// Update accountability alert
West Alabama Dental Clinic... 152 consecutive days  // Update days
```

### Add New Topics

Edit `src/components/TopicNavigation.jsx`:

```javascript
const topics = [
  { id: 'environment', label: 'Environment', sublabel: 'Parks, Recycling', color: '#2C7A7B' },
  // Add more...
];
```

### Add New Patterns

```javascript
const patterns = [
  { id: 'grant-chasing', label: 'Grant Chasing', description: 'Decisions driven by available grants' },
  // Add more...
];
```

---

## Visual Design Philosophy

### Before (Technical Audit)
- Tab navigation with abstract names ("Rhetoric Gap Monitor")
- Focus on methodology and metrics
- Audience: Data analysts

### After (Citizen Mobilization)
- Persona-first navigation ("I am a Parent")
- Focus on impact stories and actionable insights
- Audience: Parents, advocates, residents

### Key Changes

1. **Language:** "Bricks over Biological Needs" not "Capital vs Health Allocation"
2. **Visuals:** Maps and flowcharts not just bar charts
3. **Framing:** "The Veto" not "Decision Pattern Analysis"
4. **Action:** "Call Patricia Johnson" not "Observe governance trend"

---

## Technical Architecture

### Components

```
src/components/
├── HomePage.jsx              # Landing page with personas
├── ImpactDashboard.jsx       # Impact stories by persona
├── TopicNavigation.jsx       # Topic/pattern/resource filters
├── WordsVsDollars.jsx        # Original dashboards (still available)
├── EndlessStudyLoop.jsx      
├── WhereMoneyWent.jsx        
├── WhoIsInCharge.jsx         
└── shared/
    ├── FilterPanel.jsx       # Legacy search/filter
    ├── DecisionCard.jsx      # Individual decision cards
    └── DashboardTile.jsx     # Tile-based navigation
```

### State Management

```javascript
viewMode: 'home' | 'impact' | 'browse' | 'dashboards' | 'decisions'
selectedPersona: 'parent' | 'advocate' | 'resident' | null
selectedTopic: string | null
selectedTopics: string[]      // Filter by domain
selectedPatterns: string[]    // Filter by pattern
selectedResources: string[]   // Filter by resource type
```

---

## Next Steps

### 1. Add Real Maps

Replace placeholder with actual Leaflet maps:

```bash
npm install leaflet react-leaflet
```

```javascript
// In DentalHealthImpact component
import { MapContainer, TileLayer, CircleMarker } from 'react-leaflet';

<MapContainer center={[33.2098, -87.5692]} zoom={12}>
  <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
  {schools.map(school => (
    <CircleMarker
      center={[school.lat, school.lng]}
      radius={school.dentalPainRate * 10}
      color={school.dentalPainRate > 0.4 ? 'red' : 'blue'}
    />
  ))}
</MapContainer>
```

### 2. Add Video Recaps

```bash
npm install react-player
```

```javascript
import ReactPlayer from 'react-player';

<ReactPlayer url="meeting-video.mp4" controls />
```

### 3. Add Budget PDFs

Link to actual budget documents:

```javascript
<a href="/budgets/fy2026-tuscaloosa.pdf" download>
  Download FY2026 Budget
</a>
```

### 4. Add Scrolling Ticker

For the "Accountability Alert":

```javascript
// Auto-scroll through multiple alerts
const alerts = [
  "Dental clinic: 152 days",
  "Water quality study: 89 days",
  // ...
];

// Rotate every 5 seconds
```

---

## Deployment

Same as before:

```bash
npm run build
# Deploy build/ folder
```

Or use GitHub Pages, Netlify, Vercel (see main README).

---

## FAQ

### Why persona-based navigation?

**Technical dashboards** appeal to researchers. **Impact stories** mobilize citizens. A parent doesn't care about "rhetoric gap metrics" - they care that their kid can't get dental care.

### What happened to the original dashboards?

Still available! Click "Analysis Dashboards" in the top menu. Power users and researchers can still access all the technical analysis.

### Can I add more personas?

Yes! Edit `HomePage.jsx` and `ImpactDashboard.jsx`. Examples:
- Business Owner → Economic Development
- Teacher → Classroom Resources
- Senior → Healthcare Access

### How do I update the numbers?

Run the Python analysis pipeline - it auto-exports to `dashboardData.js`. Or edit that file directly for quick updates.

---

## Support

Questions? See:
- `frontend/policy-dashboards/README.md` - Technical setup
- `docs/FRONTEND_INTEGRATION_GUIDE.md` - Python integration
- `docs/ACCOUNTABILITY_DASHBOARD_STRATEGY.md` - Strategy guide

---

**The goal:** Move people from *awareness* to *action* by showing them exactly how decisions affect their lives and who's making those decisions.
