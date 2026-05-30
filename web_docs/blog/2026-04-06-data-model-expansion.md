---
slug: week-1-civic-tech-tracking
title: "Week 1: Now Tracking 1,000+ Civic Tech Projects, Hackathons, and Community Solutions"
authors: [communityone]
tags: [data-model, civic-tech, community]
---

# Week 1: Now Tracking 1,000+ Civic Tech Projects, Hackathons, and Community Solutions

This week marks a significant milestone for Open Navigator as we've dramatically expanded our data model to cover civic technology projects, hackathons, and community-driven governance frameworks.

{/* truncate */}

## 🎯 What We Accomplished

### 1. Added 8 New Civic Tech Entities

We've integrated civic technology and open source projects as first-class data entities:

- **CIVIC_TECH_PROJECT** - GitHub repositories, civic tech projects
- **PROJECT_CONTRIBUTOR** - Maintainers and core contributors
- **PROJECT_ISSUE** - "Good first issue" labels for new contributors
- **PROJECT_FUNDING** - GitHub Sponsors, OpenCollective, grants
- **HACKATHON** - National Day of Civic Hacking, CodeAcross events
- **HACKATHON_PROJECT** - Projects built at civic hackathons
- **HACKATHON_PARTICIPANT** - Contributors and attendees
- **BRIGADE_CHAPTER** - Code for America brigade locations (80+ chapters)

### 2. Community Solutions Framework

Added 3 entities to track real-world community engagement:

- **COMMUNITY_SOLUTION** - Implementation of engagement spectrum (Inform → Defer to)
- **SOLUTION_STAKEHOLDER** - CBOs, government, funders, facilitators
- **SOLUTION_METRIC** - Track KPIs, outputs, outcomes, and impact

This framework maps to research from:
- **Spectrum of Community Engagement to Ownership** (Facilitating Power)
- **Harvard Data-Smart City Solutions** (use case templates)
- **Brookings Institution** (Data Academy model)

### 3. Church & Congregation Data

Integrated faith-based organizations into our nonprofit tracking:

- **CONGREGATION** entity with 20 fields
- Data sources: ARDA, HIFLD, National Congregations Study
- Coverage: Churches, mosques, synagogues, temples

## 📊 By the Numbers

- **40+ entities** in our comprehensive ERD
- **2,827 lines** of data model documentation
- **90K+ jurisdictions** tracked
- **3M+ nonprofits** monitored
- **500K+ meeting pages** indexed

## 🔮 What's Next

**Week of April 13:**
- Migrate all citations to Docusaurus documentation
- Add comprehensive BibTeX references
- Expand enterprise tech partnerships section

**Week of April 20:**
- Fix homepage routing issues
- Update navigation structure
- Deploy civic tech section to documentation

**Looking Ahead:**
- Extract GitHub data for civic tech projects
- Build hackathon event calendar
- Create community solution templates

## 🚀 Try It Out

Our data model is fully documented in the [Data Model ERD](/docs/data-sources/data-model-erd) with interactive Mermaid diagrams showing all entity relationships.

Want to contribute? Check out our [GitHub repository](https://github.com/getcommunityone/open-navigator-for-engagement) or join a local Code for America brigade to see the data model in action!

---

**Next Post:** Citations Migration and Documentation Improvements (Week of April 13)
