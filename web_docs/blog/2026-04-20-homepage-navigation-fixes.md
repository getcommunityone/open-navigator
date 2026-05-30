---
slug: week-3-easier-access-civic-data
title: "Week 3: Your Gateway to 90,000+ Jurisdictions Just Got Easier - New Homepage Launch"
authors: [communityone]
tags: [documentation, deployment]
---

# Week 3: Your Gateway to 90,000+ Jurisdictions Just Got Easier

This week we tackled critical UX issues affecting the documentation site - fixing routing conflicts, restoring the homepage with logo, and updating all navigation links to work correctly.

{/* truncate */}

## 🔧 What We Fixed

### 1. Homepage "Page Not Found" Error

**Problem:**
- `http://localhost:3000/` showed "page not found"
- Custom homepage at `src/pages/index.tsx` couldn't render
- CommunityOne logo missing
- Routing conflict with Docusaurus configuration

**Solution:**
- Changed `routeBasePath` from `/` to `/docs/`
- Docs now served at `/docs/` path
- Custom homepage renders at root `/`
- Logo displays correctly

### 2. Updated All Navigation Links

Fixed **7 files** with 155 insertions:

**Configuration Updates:**
- `docusaurus.config.ts` - Navbar, footer, logo links
- `src/pages/index.tsx` - Homepage pathway cards, CTA buttons

**Documentation Updates:**
- `intro.md` - Updated all internal links to `/docs/` prefix
- `for-advocates.md` - Fixed policy maker navigation
- `for-developers.md` - Corrected developer guide links
- `dashboard.md` - Updated dashboard references
- `citations.md` - Added Open Data Impact section

### 3. New URL Structure

With `routeBasePath: '/docs/'`:

| What You Want | Correct URL |
|---------------|-------------|
| Homepage | `http://localhost:3000/` |
| Introduction | `http://localhost:3000/docs/intro` |
| Citations | `http://localhost:3000/docs/data-sources/citations` |
| Policy Makers Guide | `http://localhost:3000/docs/for-advocates` |
| Developer Guide | `http://localhost:3000/docs/for-developers` |
| Dashboard | `http://localhost:3000/docs/dashboard` |

## ✨ Homepage Features

The new custom homepage includes:

**Header:**
- CommunityOne logo (SVG)
- "Open Navigator" branding
- Tagline: "Find opportunities in local meetings and budgets"

**Audience Pathways:**
Two cards guiding users based on role:
- 📊 **Policy Makers & Advocates** → `/docs/for-advocates`
- 🛠️ **Developers & Technical Users** → `/docs/for-developers`

**Feature Highlights:**
- 📄 Meeting Minutes & Financial Documents (90,000+ jurisdictions)
- 🤖 Automated Analysis (AI-powered document processing)
- 💰 Words vs Money (Budget vs meeting minute correlation)
- 🔍 Free Public Data (Census, school district, nonprofit data)
- 🗺️ Visual Map (Geographic opportunity discovery)
- 📧 Draft Materials (Automated email and campaign content)

**Call-to-Action:**
- Launch main application (React app on port 5173)
- Access documentation sections
- Explore data sources

## 📊 Build Status

Documentation now builds successfully:
- ✅ All routes working
- ✅ No TypeScript errors
- ✅ Logo displays correctly
- ✅ Navigation links functional
- ✅ Warnings for broken links identified (to be fixed next week)

## 🚀 What's Next

**Week of April 27:**
- Add civic tech section to homepage
- Fix broken anchor links
- Update legacy markdown references
- Test deployment to HuggingFace Spaces

**Week of May 4:**
- Launch production deployment
- Set up custom domain (www.communityone.com)
- Configure OAuth providers
- Enable user authentication

**Week of May 11:**
- Start data extraction pipelines
- Ingest first batch of civic tech projects from GitHub
- Test hackathon event calendar
- Deploy brigade chapter directory

## 🎯 Roadmap: Weekly Blog Posts for 2026

Here's what to expect in upcoming weekly updates:

**May 2026: Production Deployment**
- Week 1: HuggingFace Spaces deployment
- Week 2: Custom domain & SSL setup
- Week 3: OAuth integration (GitHub, Google)
- Week 4: First production users

**June 2026: Data Extraction**
- Week 1: GitHub API integration for civic tech projects
- Week 2: Hackathon event calendar (National Day of Civic Hacking)
- Week 3: Brigade chapter directory (Code for America)
- Week 4: First 1,000 civic tech projects indexed

**July 2026: Analytics & Dashboards**
- Week 1: Community solution templates
- Week 2: Metric views for common use cases
- Week 3: Budget-to-minutes correlation analysis
- Week 4: First real-world case study

**August 2026: Community Engagement**
- Week 1: Partner with first local brigade
- Week 2: Data Academy pilot program (Brookings model)
- Week 3: Hackathon participation (CodeAcross prep)
- Week 4: User feedback and iteration

**September-December 2026: Scale & Impact**
- Monthly: New jurisdiction data (target: 100K+ cities/counties)
- Monthly: Nonprofit data expansion (target: 5M+ organizations)
- Monthly: Meeting minute ingestion (target: 1M+ documents)
- Quarterly: Major feature releases

**2027 Goals:**
- Full coverage of U.S. jurisdictions
- International expansion (Canada, UK)
- Real-time meeting monitoring
- AI-powered policy impact predictions

## 📖 Try It Out

Visit the new homepage at `http://localhost:3000/` to see the redesigned landing page with pathway cards, feature highlights, and clear calls-to-action.

All documentation is now accessible with the `/docs/` prefix - no more "page not found" errors!

---

**Next Post:** Production Deployment & HuggingFace Spaces Setup (Week of April 27)
