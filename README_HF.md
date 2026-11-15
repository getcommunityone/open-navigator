---
title: CommunityOne - Open Navigator
emoji: 🏛️
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
tags:
  - civic-engagement
  - policy-tracking
  - government-transparency
  - nonprofit-discovery
  - open-data
---

# 🏛️ CommunityOne - Open Navigator

**See what your local government decided, with the record to prove it.**

CommunityOne is a civic engagement platform that helps you discover advocacy opportunities, track policy changes, and connect with organizations working on the causes you care about.

## ✨ Features

- **🔍 Unified Search**: Find contacts, meetings, organizations, and causes across the entire United States
- **📊 Real-time Stats**: Live counts for the nation, a state, a county or a city ([/api/stats](https://www.communityone.com/api/stats))
- **🏢 Nonprofit Discovery**: Explore tax-exempt organizations from IRS data, enriched with Every.org
- **📅 Meeting Minutes**: Search government meeting transcripts and agendas
- **🎯 Geographic Filtering**: Browse by state, county, or city to find local opportunities
- **🔐 OAuth Login**: Sign in with HuggingFace, GitHub, or Google to save your preferences

## 🚀 Three Services Architecture

This deployment runs three integrated services:

1. **📚 Documentation** (Docusaurus) - `/docs/`
2. **🖥️ Main Application** (React + Vite) - `/`
3. **⚡ API Backend** (FastAPI) - `/api/`

All services are reverse-proxied through nginx on port 7860.

## 📖 Quick Start

### Browse Without Login
- Click "Browse All" to explore data by state
- Use the search bar to find organizations, contacts, or causes
- Filter by location using the state/county/city selectors

### Sign In for Personalization
- Click "Login" in the top right
- Choose your OAuth provider (HuggingFace, GitHub, or Google)
- Follow organizations, leaders, and causes you care about
- Get personalized recommendations

### Explore the API
- Visit `/redoc` for interactive API documentation
- Try the search endpoints with state filters
- Export data in JSON format for your own projects

## 🛠️ Technology Stack

- **Frontend**: React 18 + TypeScript + Vite + TailwindCSS + shadcn/ui
- **Backend**: Python 3.11 + FastAPI + Pydantic
- **Data**: PostgreSQL (Neon), built by dbt
- **Docs**: Docusaurus v3
- **Infrastructure**: nginx + supervisor + Docker

## 📊 Data Sources

- **IRS BMF**: tax-exempt organizations
- **Every.org**: Nonprofit enrichment (logos, causes, revenue)
- **Open States**: state legislators and bills
- **Census**: jurisdictions and boundaries
- **CityScrapers**: Local government meetings
- **OpenCivicData**: Standardized government data

## 🔗 Links

- **Repository**: [github.com/getcommunityone/open-navigator](https://github.com/getcommunityone/open-navigator)
- **Documentation**: Click "📚 Browse Documentation" on the homepage
- **API Docs**: `/redoc` endpoint
- **Website**: [www.communityone.com](https://www.communityone.com)

## 📝 License

Apache License 2.0 - Free for commercial and non-commercial use

## 🤝 Contributing

We welcome contributions! See CONTRIBUTING.md in the repository for guidelines.

## 💬 Support

- **Issues**: [GitHub Issues](https://github.com/getcommunityone/open-navigator/issues)
- **Discussions**: [GitHub Discussions](https://github.com/getcommunityone/open-navigator/discussions)
- **Email**: johnbowyer@communityone.com

---

Built with ❤️ for civic engagement and government transparency.
