---
title: URL Dataset Investigation
---

# URL Dataset Investigation: What Already Exists

## 🔍 Current Situation

**What we're doing now**:
- Matching Census jurisdiction names to CISA .gov domains
- Result: 76 URLs from 500 jurisdictions tested (15% match rate)

**What we should check**:
- Do these civic tech projects already have URL datasets?
- Are there HuggingFace datasets with government URLs?
- Can we download their jurisdiction lists instead of discovering ourselves?

---

## 📊 Known URL Datasets to Investigate

### 1. LocalView (Harvard)
**Website**: https://www.localview.net  
**Claim**: "Largest known public dataset of local government meetings"  

**To Check**:
- [ ] Do they publish their jurisdiction URL list?
- [ ] Is their dataset on HuggingFace?
- [ ] Can we download their meeting database?
- [ ] What's their coverage? (They claim nationwide)

**Expected**: URL list for hundreds/thousands of jurisdictions with videos

---

### 2. CivicBand
**Website**: https://civic.band  
**Claim**: "1,000+ municipalities & counties"

**To Check**:
- [ ] Do they publish their URL list?
- [ ] Can we access their database?
- [ ] What jurisdictions do they cover?

**Expected**: 1,000+ verified government website URLs

---

### 3. Council Data Project (CDP)
**Website**: https://councildataproject.org  
**GitHub**: https://github.com/CouncilDataProject

**To Check**:
- [ ] List of deployed instances (each = 1 jurisdiction URL)
- [ ] cdp-data repository (may have jurisdiction lists)
- [ ] Individual deployment configs (contain URLs)

**Expected**: 10-20 cities with full deployment

**Known CDP Cities** (from their website):
- Seattle, WA
- King County, WA
- Portland, OR
- Denver, CO
- Boston, MA
- Oakland, CA
- Alameda County, CA
- Charlotte, NC
- Louisville, KY

---

### 4. City Scrapers
**Website**: https://cityscrapers.org  
**GitHub**: https://github.com/city-scrapers

**To Check**:
- [ ] City Scrapers Chicago (has ~100 agencies)
- [ ] Other City Scrapers deployments (Pittsburgh, Detroit, etc.)
- [ ] Scraper list = jurisdiction URLs

**Expected**: 5-10 cities, each with dozens of agencies/boards

**Known City Scrapers Cities**:
- Chicago (100+ agencies)
- Pittsburgh
- Detroit
- Cleveland
- Los Angeles

---

### 5. Civic Scraper (Big Local News)
**GitHub**: https://github.com/biglocalnews/civic-scraper

**To Check**:
- [ ] Example jurisdiction list in repo
- [ ] Big Local News datasets
- [ ] Stanford Journalism data releases

**Expected**: Curated list of news-worthy jurisdictions

---

### 6. Councilmatic (DataMade)
**Website**: Various (councilmatic.org redirects)  
**GitHub**: https://github.com/datamade

**To Check**:
- [ ] List of Councilmatic deployments
- [ ] Each deployment = 1 city URL

**Known Councilmatic Cities**:
- Chicago, IL (chicagocouncilmatic.org)
- New York, NY (nyc.councilmatic.org)
- Philadelphia, PA (philly.councilmatic.org)
- Los Angeles, CA
- Miami, FL
- Denver, CO

---

### 7. MeetingBank Dataset
**Website**: https://meetingbank.github.io

**To Check**:
- [ ] Download their dataset
- [ ] Extract jurisdiction URLs
- [ ] See what 6 cities they cover

**Known Cities**: 6 large cities (need to check which)

---

### 8. OpenTowns
**Website**: https://opentowns.org

**To Check**:
- [ ] List of covered towns
- [ ] URL database
- [ ] Focus: small towns/cities

**Expected**: Dozens of small municipalities

---

### 9. OpenCouncil (Greece)
**GitHub**: https://github.com/schemalabz/opencouncil

**To Check**:
- [ ] Greek municipality URLs (international example)
- [ ] May have patterns for finding URLs

**Expected**: Greek councils (not directly useful, but patterns may be)

---

## 🗂️ HuggingFace Datasets to Check

### Search Terms:
- "local government"
- "city council"
- "municipal meetings"
- "government websites"
- "civic data"
- "legistar"
- "granicus"

### Potential Datasets:
- [ ] Search: huggingface.co/datasets?search=government
- [ ] Search: huggingface.co/datasets?search=municipal
- [ ] Search: huggingface.co/datasets?search=council
- [ ] Check if LocalView uploaded their data
- [ ] Check if City Scrapers uploaded data
- [ ] Check Big Local News org

---

## 📋 Other Data Sources

### 1. Legistar Client List
**Why**: Legistar is the most popular council management system

**To Check**:
- [ ] Granicus website (they own Legistar)
- [ ] Public list of Legistar clients
- [ ] Scrape legistar.com subdomain list

**Expected**: 1,000+ city council URLs

### 2. Granicus Client List
**Why**: Major civic engagement platform

**To Check**:
- [ ] Granicus website client showcase
- [ ] govdelivery.com (owned by Granicus)

**Expected**: Hundreds of jurisdictions

### 3. CivicPlus Client List
**Why**: Popular municipal website platform

**To Check**:
- [ ] CivicPlus website
- [ ] Public client list

### 4. Municode Client List
**Why**: Online code/ordinance hosting

**To Check**:
- [ ] municode.com directory
- [ ] List of hosted municipalities

---

## 🎯 OPTIMAL STRATEGY

Instead of trying to match jurisdiction names to domains, we should:

### Phase 1: Download Existing Datasets (1-2 days)
1. **LocalView dataset** → Likely has 100s-1000s of URLs with videos
2. **CivicBand database** → 1,000+ municipalities
3. **CDP deployments** → 10-20 cities (high quality)
4. **City Scrapers instances** → 5+ cities, 100s of agencies
5. **Councilmatic deployments** → 6+ major cities
6. **MeetingBank** → 6 cities with transcripts

**Expected total**: 2,000-5,000 high-quality URLs

### Phase 2: Platform Client Lists (1 week)
1. **Legistar subdomain enumeration** → city.legistar.com
2. **Granicus client list** → From their website
3. **CivicPlus client list**
4. **Municode directory**

**Expected total**: 5,000-10,000 URLs

### Phase 3: Census + CISA Matching (current approach)
Keep our current system as fallback for uncovered jurisdictions

**Expected additional**: 1,000-2,000 URLs

---

## 🔥 IMMEDIATE ACTIONS

### 1. Check LocalView Dataset
```bash
# Visit: https://www.localview.net
# Look for: "Download" or "Data" link
# Check: GitHub repo for dataset links
```

### 2. Check HuggingFace
```bash
# Search: https://huggingface.co/datasets?search=local+government
# Search: https://huggingface.co/datasets?search=council+meetings
```

### 3. Scrape Legistar Subdomains
```python
# Try common patterns:
# {city}.legistar.com
# {city}-{state}.legistar.com
# {county}.legistar.com
```

### 4. CDP Deployment List
```bash
# Check: https://councildataproject.org
# Each deployment has a URL in the config
```

### 5. City Scrapers Jurisdiction List
```bash
# Check: https://github.com/city-scrapers/city-scrapers
# Each scraper file = 1 or more agencies
```

---

## 💡 WHY THIS MATTERS

**Current approach**: 76 URLs from 500 jurisdictions = 15% match rate

**Using existing datasets**: Could get 5,000-10,000 URLs immediately

**ROI**: 
- LocalView alone might have 1,000+ URLs ready to use
- Legistar enumeration could yield 3,000+ URLs
- Combined: 10x more coverage with less work

---

## 📝 RECOMMENDATION

**DO THIS FIRST**:
1. ✅ Investigate LocalView dataset (highest potential)
2. ✅ Check HuggingFace for government data
3. ✅ Enumerate Legistar subdomains (legistar.com/*.legistar.com)
4. ✅ Get CDP deployment URLs
5. ✅ Extract City Scrapers jurisdiction lists

**THEN**:
Keep our Census + CISA matching as a fallback for smaller jurisdictions not covered by above.

---

## ⚠️ KEY INSIGHT

We've been trying to **discover** URLs when we should be **downloading** existing URL lists from projects that already did this work!

The civic tech community has likely already mapped thousands of URLs. We should:
1. Download their datasets
2. Extract their URL lists
3. Add our discoveries to fill gaps

This is the "don't reinvent the wheel" principle applied to URL discovery.
