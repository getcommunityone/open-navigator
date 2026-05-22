# Official Government Website Scraper

Scrapes official .gov domains from the GSA registry to extract civic engagement data.

## 📊 Data Source

- **Source:** 2,272+ official .gov domains from GSA registry (loaded in `jurisdictions_details_search`)
- **Authority:** U.S. General Services Administration
- **Coverage:** All registered .gov domains

## 🎯 Purpose

Extract civic engagement data from official government websites:
- Meeting schedules and agendas  
- Board/council member directories
- Department contact information
- YouTube channel links
- Social media accounts
- Public records portals

## 📁 Scripts

- `scrape_gov_websites.py` - Main scraper for .gov domains

## 🚀 Usage

```bash
# Scrape first 100 jurisdictions from dev states
python scrape_gov_websites.py --states AL,GA,IN,MA,WA,WI --limit 100

# Scrape specific state
python scrape_gov_websites.py --states MA --limit 50

# Dry run (preview without updating)
python scrape_gov_websites.py --states WA --limit 20 --dry-run
```

## 📋 What We Extract

### YouTube Channels
- Channel IDs from embedded players
- Channel links from nav menus
- Patterns: `/c/`, `/channel/`, `/@username`

### Meeting Pages
- Agenda portals
- Meeting calendars
- Board/council pages
- Committee pages

### Contact Information
- Email addresses (parsed from text and mailto links)
- Department directories
- Staff listings

### Social Media
- Facebook pages
- Twitter/X accounts
- Instagram profiles
- LinkedIn pages

## 🏗️ Common Platforms

The scraper recognizes these government website platforms:

- **CivicPlus** - Meeting agendas at `/AgendaCenter/`
- **Granicus Legistar** - Legislative management at `{city}.legistar.com`
- **WordPress** - Custom municipal sites
- **OpenGov** - Transparency portals

## 🔄 Type of Load

**ENRICHMENT LOAD** - Adds meeting/video data to existing jurisdiction records

## ⚠️ Rate Limiting

- 2-second delay between requests
- Respects robots.txt
- 15-second timeout per request
- Caches results to avoid duplicate scraping

## 📝 Example Output

```json
{
  "domain": "bostonma.gov",
  "title": "City of Boston",
  "youtube_channels": ["CityofBoston", "UC..."],
  "meeting_pages": [
    {
      "url": "https://boston.gov/departments/city-council/meetings",
      "text": "City Council Meetings"
    }
  ],
  "contact_emails": ["info@boston.gov"],
  "social_media": {
    "facebook": ["https://facebook.com/CityofBoston"],
    "twitter": ["https://twitter.com/CityOfBoston"]
  }
}
```

## 🎯 Next Steps

After scraping, the data can be used to:
1. Populate `youtube_channels` in `jurisdictions_details_search`
2. Create events in `event` from meeting calendars
3. Update contact information
4. Validate existing data sources
