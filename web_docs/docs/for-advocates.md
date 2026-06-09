---
sidebar_position: 1
displayed_sidebar: policyMakersSidebar
---

# For Policy Makers & Advocates

Welcome! This section is designed for **policy makers, advocates, researchers, and community organizers** who want to use Open Navigator to drive change.

## Data at Your Fingertips

Open Navigator gives you access to comprehensive accountability data across the entire United States:

<div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '15px', margin: '20px 0'}}>

<div style={{padding: '15px', background: '#e3f2fd', borderLeft: '4px solid #2196F3', borderRadius: '4px'}}>
  <div style={{fontSize: '2em', fontWeight: 'bold', color: '#1976D2'}}>925</div>
  <div style={{color: '#555'}}>Government jurisdictions tracked</div>
  <div style={{fontSize: '0.9em', color: '#777', marginTop: '5px'}}>Counties, cities, townships, school districts</div>
</div>

<div style={{padding: '15px', background: '#f1f8e9', borderLeft: '4px solid #8BC34A', borderRadius: '4px'}}>
  <div style={{fontSize: '2em', fontWeight: 'bold', color: '#689F38'}}>43,726</div>
  <div style={{color: '#555'}}>Nonprofit organizations</div>
  <div style={{fontSize: '0.9em', color: '#777', marginTop: '5px'}}>Complete IRS Form 990 data from 5 states</div>
</div>

<div style={{padding: '15px', background: '#fff3e0', borderLeft: '4px solid #FF9800', borderRadius: '4px'}}>
  <div style={{fontSize: '2em', fontWeight: 'bold', color: '#F57C00'}}>6,913</div>
  <div style={{color: '#555'}}>Meeting minutes analyzed</div>
  <div style={{fontSize: '0.9em', color: '#777', marginTop: '5px'}}>AI-extracted decisions and budget items</div>
</div>

<div style={{padding: '15px', background: '#fce4ec', borderLeft: '4px solid #E91E63', borderRadius: '4px'}}>
  <div style={{fontSize: '2em', fontWeight: 'bold', color: '#C2185B'}}>362</div>
  <div style={{color: '#555'}}>Elected officials</div>
  <div style={{fontSize: '0.9em', color: '#777', marginTop: '5px'}}>Voting records and decision patterns</div>
</div>

</div>

### Coverage Breakdown

- **🏛️ Jurisdictions**: 925 tracked across 5 states
- **🏙️ School Districts**: 306 districts with financial data
- **🏫 Churches**: 4,372 congregations mapped
- **🗺️ States**: 5 states with complete IRS BMF data

**All data is free and public** - sourced from official government registries and IRS filings.

:::tip[Complete Data Source Citations]
All data sources are properly cited with licenses, BibTeX references, and attribution.

**[Citations & Data Sources](/docs/data-sources/citations)**

Includes:
- **Academic Research**: MeetingBank, LocalView (Harvard), Council Data Project, City Scrapers
- **Government Data**: U.S. Census Bureau, NCES, IRS Tax-Exempt Organization Search
- **Civic Tech Standards**: OCD-ID, Popolo, Schema.org, CEDS
- **Fact-Checking**: N/A (not currently integrated)
- **Nonprofit Data**: IRS BMF (43,726 orgs from 5 states)
- **Churches & Congregations**: 4,372 congregations from IRS data
- **Enterprise Partnerships**: Microsoft, Google, AWS, Databricks for data infrastructure
:::

---

## What You'll Find Here

Use the **left sidebar** as a simple path from mission to outcomes. The same flow is summarized here:

### 1. Define your cause / mission

- **[Nonprofit resources](/docs/resources/nonprofit-resources)** — Sector context and mission-aligned organizations

### 2. Identify who to engage

Learn who and what the data covers so you can target the right officials, organizations, and forums:

- **[Data overview](/docs/data-sources/overview)** — What data is available and where it comes from
- **[Citations & Data Sources](/docs/data-sources/citations)** — Licenses, methods, and full source list
- **[Nonprofit data](/docs/data-sources/nonprofit-sources)** — Financial and program signals for organizations
- **[Video sources](/docs/data-sources/video-sources)** — Meeting channels and video discovery

### 3. Choose a strategy

Frameworks for accountability and advocacy:

- **[Budget-to-minutes analysis](/docs/guides/political-economy)** — Correlate rhetoric with spending
- **[Accountability strategy](/docs/guides/accountability-strategy)** — Track gaps between talk and action
- **[Impact navigation](/docs/guides/impact-navigation)** — Find opportunities for policy change

### 4. Define what success looks like

See end-to-end examples and implementation patterns:

- **[Tuscaloosa complete analysis](/docs/case-studies/tuscaloosa-complete)** — Full data sources and statistics
- **[Tuscaloosa discovery process](/docs/case-studies/tuscaloosa-discovery)** — How we found the data
- **[Tuscaloosa pipeline guide](/docs/case-studies/tuscaloosa-pipeline)** — Step-by-step implementation

## Common Use Cases

### 1. Government Accountability

**Challenge:** Elected officials say one thing, fund another.

**Solution:** Compare meeting rhetoric with budget allocations to expose gaps.

```
City Council: "School dental programs are our top priority"
Budget Reality: Dental funding decreased 20%

→ Advocacy Angle: "City cut screenings 20% despite calling it a priority"
```

### 2. Nonprofit Verification

**Challenge:** Verify that nonprofits allocate resources according to their mission.

**Solution:** Compare board meeting minutes with Form 990 spending patterns.

```
Board Minutes: "Expanding access to underserved communities"
Form 990: Only 12% of budget on direct services

→ Donor Alert: "Organization claims to serve underserved but allocates <15% to programs"
```

### 3. Finding Existing Solutions

**Challenge:** Officials claim "we can't do X - it's too risky/expensive/complex."

**Solution:** Find nonprofits or nearby jurisdictions already doing it successfully.

```
Official: "We can't do dental screenings - legal liability"
Reality: 3 local nonprofits already providing screenings

→ Response: "Here are 3 organizations doing it safely. Can we support their expansion?"
```

### 4. Opportunity Cost Analysis

**Challenge:** Show what wasn't funded when money went elsewhere.

**Solution:** Highlight spending on non-essentials vs. cuts to critical services.

```
City spent $200K on new city hall landscaping
While cutting $150K from children's dental programs
→ Impact: 800 kids now without dental screenings
```

## Getting Started

### Step 1: Explore the Data

Visit **http://localhost:5173** (Open Navigator application) to:
- Search meetings by location, topic, and date
- View the heatmap of advocacy opportunities
- Look up nonprofit organizations in your area
- Filter by urgency and policy topic

### Step 2: Understand the Analysis

Read the [Budget-to-Minutes Analysis](/docs/guides/political-economy) guide to understand how the platform correlates rhetoric with spending.

### Step 3: See It In Action

Review the [Tuscaloosa case study](/docs/case-studies/tuscaloosa-complete) to see a complete analysis of one city.

### Step 4: Apply to Your Area

Use the search and filter tools in Open Navigator to find:
- Upcoming votes and hearings
- Budget discussions
- Gaps between priorities and funding
- Local nonprofits providing services

## Key Concepts

### Budget-to-Minutes Analysis

The platform compares what organizations **say** in meetings with what they **fund** in budgets:

| Meeting Rhetoric | Budget Reality | Analysis |
|------------------|----------------|----------|
| "Critical priority" | +5% increase | ✅ Aligned |
| "Essential program" | Flat funding | ⚠️ Lip Service |
| Rarely discussed | +25% increase | 🔍 Hidden Priority |
| Heavy debate | -15% cut | ❌ Performative Talk |

### Urgency Levels

Opportunities are classified by action urgency:

- 🔴 **Critical** - Vote imminent, immediate action required
- 🟠 **High** - Active debate, high engagement needed
- 🟡 **Medium** - Moderate discussion, monitoring recommended
- 🟢 **Low** - Early stage, awareness building

### Data Quality

All data comes from **100% free, public sources**:
- Government meeting minutes (required by law to be public)
- IRS Form 990 filings (public records for tax-exempt organizations)
- Government budgets (published on official .gov sites)
- YouTube videos (publicly accessible government channels)

## Need Help?

### Non-Technical Questions

- **What data is available?** → [Data Sources Overview](/docs/data-sources/overview)
- **How does the analysis work?** → [Political Economy Guide](/docs/guides/political-economy)
- **Can I see an example?** → [Case Studies](/docs/case-studies/tuscaloosa-complete)

### Technical Support

If you need help setting up or accessing data:
- Visit the [Developer Documentation](/docs/quickstart)
- File an issue on [GitHub](https://github.com/getcommunityone/open-navigator-for-engagement/issues)
- Contact: johnbowyer@communityone.com

## Next Steps

1. **Explore the Application** - Visit http://localhost:5173
2. **Learn the Framework** - Read [Budget-to-Minutes Analysis](/docs/guides/political-economy)
3. **See Examples** - Review [case studies](/docs/case-studies/tuscaloosa-complete)
4. **Start Your Research** - Search for your jurisdiction in Open Navigator
