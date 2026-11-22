---
sidebar_position: 5
---

# OpenStates Integration & Contribution Opportunities

This document outlines our integration with OpenStates/Plural Policy and potential opportunities to contribute code back to the open-source community.

## 📚 References Added to Citations

We have properly cited and referenced the following OpenStates resources:

### In Root Citations (CITATIONS.md)
- ✅ **OpenStates/Plural Policy** main site
- ✅ **Bulk data downloads** (CSV, JSON, PostgreSQL)
- ✅ **Scrapers repository**: https://github.com/openstates/openstates-scrapers
- ✅ **Local database documentation**: https://docs.openstates.org/contributing/local-database/
- ✅ **Code of Conduct**: https://docs.openstates.org/code-of-conduct/
- ✅ **Schema documentation**: https://github.com/openstates/people/blob/master/schema.md

### In Website Documentation (website/docs/data-sources/citations.md)
- ✅ Comprehensive OpenStates/Plural Policy section
- ✅ PostgreSQL dump setup instructions
- ✅ Contribution guidelines
- ✅ BibTeX citation

### In Contributing Guide (CONTRIBUTING.md)
- ✅ Code of Conduct alignment with OpenStates
- ✅ Upstream contribution guidelines
- ✅ Testing requirements for scraper contributions

---

## 🔄 Our Current OpenStates Integration

### Data We Use

1. **PostgreSQL Monthly Dumps** (9.8GB+)
   - Complete legislative database for all 50 states
   - Script: `scripts/bulk_legislative_download.py --postgres --month 2026-04`
   - Setup: `scripts/setup_openstates_db.sh`
   - Use: Local SQL queries, no API rate limits

2. **CSV/JSON Session Data**
   - Per-state legislative sessions
   - Bill text, votes, sponsors
   - Committee assignments

3. **Video Sources**
   - YouTube channel URLs from `sources` field
   - Granicus video portal links
   - Meeting archive locations

### Our Implementation

**File:** `discovery/openstates_sources.py`
- Fetches jurisdiction data via API
- Extracts video sources (YouTube, Vimeo, Granicus)
- Maps to our jurisdiction database

**File:** `scripts/bulk_legislative_download.py`
- Downloads PostgreSQL dumps
- Downloads CSV/JSON session data
- Handles all 50 states + DC + PR

---

## 🤝 Code We Could Contribute to OpenStates Scrapers

The [openstates-scrapers](https://github.com/openstates/openstates-scrapers) repository uses **Scrapy** to collect legislative data. We have complementary code that could enhance their project:

### 1. Video Source Discovery Patterns

**Our Code:** `discovery/youtube_channel_discovery.py`

**What it does:**
- Finds **all** YouTube channels for a jurisdiction (not just first match)
- Scrapes homepages for YouTube links
- Uses YouTube Data API for verification
- Discovers Vimeo and Granicus portals

**Potential Contribution:**
- Add video source extraction to OpenStates scrapers
- Enhance `sources` field with verified YouTube channels
- Automate Granicus portal discovery

**Example Pattern:**
```python
# Our code finds these patterns
patterns = {
    "youtube_channel": r"youtube\.com/(?:c/|channel/|user/|@)([\w-]+)",
    "vimeo_channel": r"vimeo\.com/([\w-]+)",
    "granicus": r"granicus\.com/([^/]+)",
}
```

### 2. Legistar/Granicus Platform Detection

**Our Code:** `discovery/url_discovery_agent.py`

**What it does:**
- Identifies Legistar instances across cities
- Maps Granicus video portals
- Extracts meeting URLs and agendas

**Potential Contribution:**
- Enhance OpenStates scrapers with meeting video links
- Add Legistar meeting agenda extraction
- Contribute URL validation patterns

**Platform Patterns We Use:**
```python
platforms = {
    "granicus": ["granicus.com", "legistar.com"],
    "youtube": ["youtube.com", "youtu.be"],
    "vimeo": ["vimeo.com"],
}
```

### 3. Meeting Archive Scraping

**Our Code:** `agents/scraper.py`

**What it does:**
- Scrapes PDF meeting minutes
- Extracts text from scanned documents (OCR)
- Parses meeting dates and types
- Handles multiple document formats

**Potential Contribution:**
- Add meeting minutes text extraction to OpenStates
- Enhance bill analysis with meeting context
- Link bills to meeting discussions

---

## 📝 How to Contribute to OpenStates Scrapers

Following their [local database documentation](https://docs.openstates.org/contributing/local-database/):

### 1. Setup OpenStates Development Environment

```bash
# Clone the scrapers repository
git clone https://github.com/openstates/openstates-scrapers.git
cd openstates-scrapers

# Install dependencies
pip install -r requirements.txt

# Setup local PostgreSQL database
createdb openstates

# Import schema (if needed)
psql -d openstates -f schema/openstates.sql
```

### 2. Test Your Scraper Locally

```bash
# Run a specific state scraper
os-update al --scrape --rpm 10

# Validate data
os-update al --scrape --validate
```

### 3. Follow Their Code of Conduct

All contributions must follow the [OpenStates Code of Conduct](https://docs.openstates.org/code-of-conduct/):
- Be respectful and professional
- Welcome diverse perspectives
- Focus on what's best for the community
- Show empathy towards other contributors

### 4. Submit Pull Request

```bash
# Create feature branch
git checkout -b feature/video-sources

# Make changes (add video discovery to a state scraper)
# Example: scrapers/al/videos.py

# Test thoroughly
os-update al --scrape --rpm 10

# Commit and push
git commit -m "Add video source discovery for Alabama legislature"
git push origin feature/video-sources

# Open PR on GitHub
```

---

## 🎯 Specific Contribution Ideas

### Priority 1: Add Video Sources to Scrapers

**Goal:** Enhance the `sources` field with verified video links

**States to Start With:**
- **Alabama** - Has YouTube channel, needs verification
- **California** - @CALegislature (well-documented)
- **Texas** - Multiple chambers on YouTube
- **New York** - Both Assembly and Senate channels

**Implementation:**
```python
# In scrapers/al/__init__.py
class AlabamaScraper(BaseScraper):
    def scrape_sources(self):
        """Add video sources for Alabama legislature."""
        return {
            "youtube": "https://www.youtube.com/@AlabamaLegislature",
            "granicus": "https://alabama.granicus.com/ViewPublisher.php?view_id=6",
        }
```

### Priority 2: Meeting Minutes Integration

**Goal:** Link bills to meeting discussions

**Use Case:**
- When bill HB123 is discussed in committee
- Link to YouTube timestamp of discussion
- Extract quotes from meeting minutes
- Connect legislators' comments to votes

**Implementation:**
```python
# Add meeting metadata to bill objects
bill.add_source(
    url="https://www.youtube.com/watch?v=xyz&t=1234s",
    note="Committee discussion at 20:34"
)
```

### Priority 3: Granicus Portal Scraping

**Goal:** Automate discovery of Granicus video portals

**Pattern:**
- Many jurisdictions use Granicus for meeting videos
- URLs follow pattern: `{jurisdiction}.granicus.com/ViewPublisher.php?view_id={id}`
- Could automate discovery and link to OpenStates jurisdictions

---

## 🔒 License Compatibility

### Our License
- **Code:** Open source (check root LICENSE file)
- **Data:** Citations required (see CITATIONS.md)

### OpenStates License
- **Code:** BSD-style license (permissive)
- **Data:** Public domain (bulk downloads)
- **Content:** Varies by state (some restrictions)

✅ **Compatible:** Our code contributions would be compatible with their license.

---

## 📚 Required Reading Before Contributing

Before submitting any code to OpenStates, review:

1. **Local Database Setup**: https://docs.openstates.org/contributing/local-database/
   - How to set up PostgreSQL locally
   - How to run scrapers in development
   - How to test data quality

2. **Scraper Development Guide**: https://docs.openstates.org/contributing/scrapers/
   - Scrapy patterns used
   - Data validation requirements
   - Testing procedures

3. **Code of Conduct**: https://docs.openstates.org/code-of-conduct/
   - Community standards
   - Communication guidelines
   - Enforcement policies

4. **Schema Documentation**: https://github.com/openstates/people/blob/master/schema.md
   - Data model structure
   - Required vs optional fields
   - Relationship patterns

---

## 🚀 Next Steps

### For This Project

1. ✅ **Citations Added** - OpenStates properly credited
2. ✅ **Code of Conduct** - Aligned with their standards
3. ✅ **Local Database** - PostgreSQL dumps integrated
4. ⏳ **Test Contributions** - Validate our code works with their schema

### For Community Contribution

1. **Identify Target State** - Choose state needing video sources
2. **Test Locally** - Set up OpenStates dev environment
3. **Develop Scraper** - Add video discovery code
4. **Submit PR** - Follow their contribution guidelines
5. **Iterate** - Respond to code review feedback

---

## 💡 Benefits of Contributing

**For OpenStates:**
- Enhanced video source coverage
- Better meeting-to-bill linkage
- More comprehensive legislative tracking

**For Our Project:**
- Upstream improvements benefit us
- Community recognition
- Better data quality for all users

**For Civic Tech:**
- Shared infrastructure improvements
- Reduced duplication of effort
- Stronger open-source ecosystem

---

## 📞 Questions?

- **OpenStates Discord**: https://discord.gg/openstates
- **GitHub Discussions**: https://github.com/openstates/openstates-scrapers/discussions
- **Email**: Open States team (check repository for contact info)

---

**Last Updated:** April 29, 2026  
**Maintained By:** Open Navigator team
