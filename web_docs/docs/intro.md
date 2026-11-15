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

Coverage grows as data is loaded, so this page doesn't list totals. The current counts (jurisdictions, school districts, nonprofits, meetings, decisions, officials) come from the live API: [communityone.com/api/stats](https://www.communityone.com/api/stats), which reads the warehouse directly. Meeting analysis is deep in a few states and thin elsewhere.

All data is **100% free and public** - no subscriptions or API fees required.

---

## 🎯 Top 5 Use Cases

These are the most useful ways to use Open Navigator. Each one says what you would look at and where it is in the app;
the figures come from the record you open, never from this page.

### 📊 1. Hold Governments Accountable

**The Problem:** Cities and school boards name priorities in meetings that their budgets don't fund.

**The Solution:** Put how often a topic is discussed next to how much money it moves. **Money and talk**
(`/money-and-talk`) pairs the decisions on a theme with the spending tied to them, and each decision links to the
meeting and the passage it came from.

### 🗺️ 2. Find Policy Windows for Advocacy

**The Problem:** Advocates miss the moments when a government is about to decide.

**The Solution:** The **Watch Next** lens on the home page lists upcoming votes, and **Policy questions**
(`/policy-questions`) shows where the same question has come up in other places and how it was decided there.

### 🏛️ 3. Understand Nonprofits in Your Area

**The Problem:** It's hard to see what local nonprofits take in and spend, and whether local government ever mentions
them.

**The Solution:** **Nonprofits** (`/nonprofits`) shows organizations with their IRS Form 990 filings, and search
shows any meeting where the organization was named, with the passage.

### 🗣️ 4. Follow Public Debate

**The Problem:** It's hard to know what residents and officials actually said about a policy.

**The Solution:** Each decision page lists the speakers and, where they were extracted, the arguments made, quoted
from the transcript, and the
**Contested** lens finds split votes and heated debate.

### 🎓 5. Compare Spending Across Places

**The Problem:** Residents can't easily tell how their government's spending compares with similar places.

**The Solution:** **Show me my money** (on the home page) breaks down what your layers of government spend per
resident, from Census finance data, and the **Census map** (`/census-map`) compares places on Census figures, so you can
ask why yours differs.

:::info[Explore the Complete Data Model]
These use cases are powered by a comprehensive data model with 40+ entities including jurisdictions, meetings, budgets, nonprofits, officials, videos, and more.

**[View Complete Data Model ERD](/docs/data-sources/data-model-erd)** - Interactive diagram with all entity relationships
:::

---

## 📊 What Data We Integrate

Open Navigator combines multiple free, public data sources:

- **📄 Meeting Minutes**: transcripts and videos from municipal meetings
- **📺 Video Channels**: state legislature and local government YouTube channels
- **💰 Financial Data**: local government finance and IRS Form 990 filings
- **🗺️ Geographic Coverage**: states, counties and cities from the Census
- **🏛️ Nonprofits**: IRS tax-exempt organizations with Form 990 financial data
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
