---
sidebar_position: 1
displayed_sidebar: gettingStartedSidebar
---

# Introduction

## CommunityOne: One Map for Every Community

> Every person deserves to find the help they need and have a voice in the decisions that shape their lives. But public resources are scattered, gaps go unseen, and communities are left navigating alone.
>
> CommunityOne changes that. One platform connects residents, leaders, and funders to what's really happening on the ground — so no community has to fight just to be seen.

**Open Navigator** is the open-source engine powering CommunityOne — an AI platform that analyzes municipal meeting minutes, budgets, and nonprofit data to surface opportunities for advocacy and community impact.

:::note[👩‍💻 Developers — start here]
Want to run the platform locally? Head straight to the **[Developer Quick Start Guide](/docs/quickstart)**. It walks you through cloning the repo, installing the three services (app, docs, API), configuring `.env`, and restoring a warehouse snapshot so the app shows real data.
:::

:::tip[All Data is Cited & Properly Attributed]
Every dataset, standard, and research source used in this platform is properly cited with complete attribution, licenses, and BibTeX references.

**[View Complete Citations & Data Sources](/docs/data-sources/citations)** - Academic research (MeetingBank, LocalView, Council Data Project, City Scrapers), Government data (U.S. Census, NCES, IRS), Civic tech standards (OCD-ID, Popolo, Schema.org, CEDS, OMOP CDM), Nonprofit data (ProPublica, Every.org, Findhelp), Church & congregation data (ARDA, HIFLD, National Congregations Study), Enterprise tech partnerships (Microsoft, Google, AWS, Databricks, Snowflake, Salesforce), and more.

**Data Model Alignment:** Our event and meeting data model is compatible with [Council Data Project (CDP)](https://councildataproject.org/) backend schema, enabling interoperability with CDP instances nationwide.
:::

## 👋 Choose Your Path

This documentation is organized by audience. Click the section that best describes you:

<div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px', margin: '30px 0'}}>

<div style={{border: '2px solid #4CAF50', borderRadius: '8px', padding: '20px', background: '#f1f8f4'}}>
  <h3>📊 Policy Makers & Advocates</h3>
  <p><strong>I want to:</strong></p>
  <ul>
    <li>Hold governments accountable</li>
    <li>Analyze meeting minutes and budgets</li>
    <li>Track nonprofit spending</li>
    <li>Find advocacy opportunities</li>
  </ul>
  <p><strong><a href="/docs/for-advocates">→ Go to Advocacy Documentation</a></strong></p>
</div>

<div style={{border: '2px solid #2196F3', borderRadius: '8px', padding: '20px', background: '#e3f2fd'}}>
  <h3>🛠️ Developers & Technical Users</h3>
  <p><strong>I want to:</strong></p>
  <ul>
    <li>Install and configure the platform</li>
    <li>Scrape meeting data</li>
    <li>Deploy to production</li>
    <li>Contribute to development</li>
  </ul>
  <p><strong><a href="/docs/quickstart">→ Start with the Developer Quick Start</a></strong></p>
  <p><a href="/docs/for-developers">Or browse all developer documentation →</a></p>
</div>

</div>

---

## Platform Scale

Open Navigator provides access to comprehensive data from 5 states:

<div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '20px', margin: '30px 0', textAlign: 'center'}}>

<div style={{padding: '20px', background: '#f5f5f5', borderRadius: '8px'}}>
  <div style={{fontSize: '2.5em', fontWeight: 'bold', color: '#2196F3'}}>925</div>
  <div style={{marginTop: '10px', color: '#666'}}>Government Jurisdictions</div>
</div>

<div style={{padding: '20px', background: '#f5f5f5', borderRadius: '8px'}}>
  <div style={{fontSize: '2.5em', fontWeight: 'bold', color: '#4CAF50'}}>43,726</div>
  <div style={{marginTop: '10px', color: '#666'}}>Nonprofit Organizations</div>
</div>

<div style={{padding: '20px', background: '#f5f5f5', borderRadius: '8px'}}>
  <div style={{fontSize: '2.5em', fontWeight: 'bold', color: '#FF9800'}}>6,913</div>
  <div style={{marginTop: '10px', color: '#666'}}>Meeting Minutes Analyzed</div>
</div>

<div style={{padding: '20px', background: '#f5f5f5', borderRadius: '8px'}}>
  <div style={{fontSize: '2.5em', fontWeight: 'bold', color: '#9C27B0'}}>362</div>
  <div style={{marginTop: '10px', color: '#666'}}>Elected Officials</div>
</div>

<div style={{padding: '20px', background: '#f5f5f5', borderRadius: '8px'}}>
  <div style={{fontSize: '2.5em', fontWeight: 'bold', color: '#F44336'}}>306</div>
  <div style={{marginTop: '10px', color: '#666'}}>School Districts</div>
</div>

<div style={{padding: '20px', background: '#f5f5f5', borderRadius: '8px'}}>
  <div style={{fontSize: '2.5em', fontWeight: 'bold', color: '#00BCD4'}}>5</div>
  <div style={{marginTop: '10px', color: '#666'}}>States with Full IRS Data</div>
</div>

</div>

All data is **100% free and public** - no subscriptions or API fees required.

---

## 🎯 Top 5 Use Cases

These are the most powerful ways to use Open Navigator:

### 📊 1. Hold Governments Accountable

**The Problem:** Cities and school boards claim priorities in meetings but don't fund them.

**The Solution:** Compare meeting transcripts with budget line items to expose gaps between rhetoric and reality.

<div style={{background: '#fff', padding: '20px', borderRadius: '8px', border: '2px solid #4CAF50', margin: '20px 0'}}>
  <div style={{fontFamily: 'monospace', fontSize: '0.95em'}}>
    <div><strong>Meeting:</strong> "Mental health is our top priority" (mentioned 47 times)</div>
    <div><strong>Budget:</strong> Mental health funding: +2% (below inflation)</div>
    <div style={{color: '#F44336', fontWeight: 'bold', marginTop: '15px'}}>⚠️ Gap Detected: Performative Talk</div>
  </div>
  <p style={{marginTop: '20px', fontSize: '0.9em', color: '#666'}}><strong>Data Used:</strong> <code>MEETING</code>, <code>BUDGET</code>, <code>JURISDICTION</code>, <code>TOPIC</code></p>
</div>

### 🗺️ 2. Find Policy Windows for Advocacy

**The Problem:** Advocates miss critical moments when governments are receptive to change.

**The Solution:** Track meeting sentiment, budget cycles, and legislation timing to identify when to act.

<div style={{background: '#fff', padding: '20px', borderRadius: '8px', border: '2px solid #2196F3', margin: '20px 0'}}>
  <div>🟢 <strong>Urgent Opportunity:</strong> Tuscaloosa City Council</div>
  <ul style={{marginTop: '10px', lineHeight: '1.8'}}>
    <li>Budget discussion: April 15 (2 weeks away)</li>
    <li>Sentiment: +0.65 (favorable toward policy)</li>
    <li>Similar cities: 3 passed related ordinances</li>
  </ul>
  <div style={{color: '#4CAF50', fontWeight: 'bold', marginTop: '15px'}}>✅ Action: Submit testimony by April 10</div>
  <p style={{marginTop: '20px', fontSize: '0.9em', color: '#666'}}><strong>Data Used:</strong> <code>OPPORTUNITY</code>, <code>SENTIMENT</code>, <code>DATE_DIMENSION</code>, <code>METRIC_VIEW</code></p>
</div>

### 🏛️ 3. Track Nonprofit Effectiveness

**The Problem:** Donors can't verify if nonprofits deliver on their mission.

**The Solution:** Combine Form 990 financial data with service delivery data and meeting citations.

<div style={{background: '#fff', padding: '20px', borderRadius: '8px', border: '2px solid #FF9800', margin: '20px 0'}}>
  <div><strong>Health Nonprofit A:</strong></div>
  <ul style={{marginTop: '10px', lineHeight: '1.8'}}>
    <li>Revenue: $2.5M (Form 990)</li>
    <li>CEO Salary: $450K (18% of revenue)</li>
    <li>Program spending: 42% (below 65% standard)</li>
    <li>Meeting citations: 0 (not mentioned in city meetings)</li>
  </ul>
  <div style={{color: '#F44336', fontWeight: 'bold', marginTop: '15px'}}>⚠️ Red Flag: High overhead, low community presence</div>
  <p style={{marginTop: '20px', fontSize: '0.9em', color: '#666'}}><strong>Data Used:</strong> <code>NONPROFIT</code>, <code>DONATION</code>, <code>CONSTITUENT</code>, <code>PROGRAM_DELIVERY</code></p>
</div>

### 🗣️ 4. Analyze Public Sentiment & Debate

**The Problem:** It's hard to know how communities really feel about policies.

**The Solution:** Extract sentiment from meeting transcripts, public comments, and video debates.

<div style={{background: '#fff', padding: '20px', borderRadius: '8px', border: '2px solid #9C27B0', margin: '20px 0'}}>
  <div><strong>Topic:</strong> School mask policy</div>
  <ul style={{marginTop: '10px', lineHeight: '1.8'}}>
    <li>Public comments: 127 speakers</li>
    <li>Sentiment breakdown: 58% against, 35% for, 7% neutral</li>
    <li>Board vote: 6-1 to require masks</li>
  </ul>
  <div style={{color: '#FF9800', fontWeight: 'bold', marginTop: '15px'}}>📈 Insight: Board voted against majority sentiment</div>
  <p style={{marginTop: '20px', fontSize: '0.9em', color: '#666'}}><strong>Data Used:</strong> <code>MEETING</code>, <code>VIDEO</code>, <code>OFFICIAL</code>, <code>SENTIMENT</code>, <code>VOTE_EVENT</code></p>
</div>

### 🎓 5. Compare Education Spending Across Districts

**The Problem:** Parents don't know if their school district spends money efficiently.

**The Solution:** Benchmark per-pupil spending, administrative costs, and outcomes across similar districts.

<div style={{background: '#fff', padding: '20px', borderRadius: '8px', border: '2px solid #00BCD4', margin: '20px 0'}}>
  <table style={{width: '100%', fontSize: '0.9em', borderCollapse: 'collapse'}}>
    <thead>
      <tr style={{borderBottom: '2px solid #ddd'}}>
        <th style={{textAlign: 'left', padding: '10px'}}>District</th>
        <th style={{textAlign: 'right', padding: '10px'}}>Per-Pupil</th>
        <th style={{textAlign: 'right', padding: '10px'}}>Admin %</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td style={{padding: '10px'}}>Your District</td>
        <td style={{textAlign: 'right', padding: '10px', fontWeight: 'bold', color: '#F44336'}}>$18,500</td>
        <td style={{textAlign: 'right', padding: '10px', fontWeight: 'bold', color: '#F44336'}}>24%</td>
      </tr>
      <tr style={{background: '#f5f5f5'}}>
        <td style={{padding: '10px'}}>Similar District A</td>
        <td style={{textAlign: 'right', padding: '10px'}}>$14,200</td>
        <td style={{textAlign: 'right', padding: '10px'}}>12%</td>
      </tr>
      <tr>
        <td style={{padding: '10px'}}>Similar District B</td>
        <td style={{textAlign: 'right', padding: '10px'}}>$13,800</td>
        <td style={{textAlign: 'right', padding: '10px'}}>11%</td>
      </tr>
    </tbody>
  </table>
  <div style={{color: '#00BCD4', fontWeight: 'bold', marginTop: '15px'}}>📊 Question: Why are admin costs double the average?</div>
  <p style={{marginTop: '20px', fontSize: '0.9em', color: '#666'}}><strong>Data Used:</strong> <code>JURISDICTION</code>, <code>BUDGET</code>, <code>DEMOGRAPHICS</code>, <code>METRIC_VIEW</code></p>
</div>

:::info[Explore the Complete Data Model]
These use cases are powered by a comprehensive data model with 40+ entities including jurisdictions, meetings, budgets, nonprofits, officials, videos, and more.

**[View Complete Data Model ERD](/docs/data-sources/data-model-erd)** - Interactive diagram with all entity relationships
:::

---

## 📊 What Data We Integrate

Open Navigator combines multiple free, public data sources:

- **📄 Meeting Minutes**: 1,000+ municipalities with full transcripts and videos
- **📺 Video Channels**: 50+ state legislature YouTube channels
- **💰 Financial Data**: Complete budget and Form 990 coverage
- **🗺️ Geographic Coverage**: All 50 states, 3,000+ counties and cities
- **🏛️ Nonprofits**: 3M+ organizations with Form 990 financial data
- **🗳️ Elections**: Ballots, candidates, results, polling data
- **✅ Fact-Checking**: Claims verification from trusted sources

See [Data Sources Overview](/docs/data-sources/overview) for complete details.

---

## Quick Start

Follow the **[Developer Quick Start Guide](/docs/quickstart)** for step-by-step installation and setup instructions — clone, install the three services, configure `.env`, and restore a warehouse snapshot.

For production deployment options, see:
- [Databricks Apps Deployment](/docs/deployment/databricks-apps)
- [Docker Deployment](/docs/deployment/docker)
- [HuggingFace Spaces Deployment](/docs/deployment/huggingface-spaces)

---

## Next Steps

<div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '20px', margin: '30px 0'}}>

<div className="card" style={{padding: '20px'}}>
  <h3>For Policy Makers</h3>
  <p>Learn how to find advocacy opportunities and track government accountability.</p>
  <p><strong><a href="/docs/for-advocates">Go to Advocacy Guide →</a></strong></p>
</div>

<div className="card" style={{padding: '20px'}}>
  <h3>🛠️ For Developers</h3>
  <p>Install the platform, configure scrapers, and deploy to production.</p>
  <p><strong><a href="/docs/quickstart">Go to Quick Start →</a></strong></p>
</div>

<div className="card" style={{padding: '20px'}}>
  <h3>Data Model</h3>
  <p>Explore the complete ERD with 40+ entities and data relationships.</p>
  <p><strong><a href="/data-sources/data-model-erd">View ERD →</a></strong></p>
</div>

<div className="card" style={{padding: '20px'}}>
  <h3>Citations</h3>
  <p>View complete citations, licenses, and data source attribution.</p>
  <p><strong><a href="/docs/data-sources/citations">View Citations →</a></strong></p>
</div>

</div>
