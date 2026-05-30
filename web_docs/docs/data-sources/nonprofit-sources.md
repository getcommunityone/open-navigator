---
displayed_sidebar: policyMakersSidebar
---

# Nonprofit Data Sources & Reference Sites

This document lists all nonprofit data sources and reference websites used by Open Navigator.

---

## 🏛️ Primary Data Source (Currently Implemented)

### ProPublica Nonprofit Explorer ⭐

**Source:** IRS Business Master File (BMF)  
**URL:** https://www.irs.gov/charities-non-profits/tax-exempt-organization-search-bulk-data-downloads  

**What It Contains:**
- **43,726 nonprofit organizations** (from 5 states with full IRS BMF data)
- **IRS Form 990 data** - Complete financial disclosures
- Revenue, expenses, assets, and liabilities
- Executive compensation
- Mission statements and program descriptions
- NTEE codes for categorization

**Why We Use It:**
> "The IRS Business Master File provides the most authoritative, complete data on tax-exempt organizations directly from the IRS."

**Coverage:**
- ✅ **Volume:** 43,726 organizations from 5 states
- ✅ **Free Access:** Public domain data
- ✅ **Data Quality:** Direct from IRS filings
- ✅ **Monthly Updates:** Refreshed regularly

---

## 📊 Reference Sites (Future Integration)

These sites provide additional nonprofit evaluation and ratings. They are not currently integrated but are listed as important reference resources.

### 1. Charity Navigator - The "Star Rating" Site

**Source:** Charity Navigator  
**URL:** https://www.charitynavigator.org/  
**API:** Available for partners  

**Focus:** Financial Health & Transparency

**What It Provides:**
- **4-star rating system** (easy for citizens to understand)
- Financial accountability scores
- Transparency ratings
- Impact measurements for large nonprofits
- CEO compensation analysis

**Coverage:**
- ~200,000 rated charities
- Focus on larger organizations (>$1M annual revenue)
- Most popular among individual donors

**Use Case for Open Navigator:**
- Add "Charity Navigator Rating" badge to nonprofit profiles
- Filter high-performing nonprofits by star rating
- Show financial health scores alongside Form 990 data

---

### 2. Candid (GuideStar) - The "Volume" Leader

**Source:** Candid (formerly GuideStar)  
**URL:** https://www.guidestar.org/ (now https://candid.org/)  
**API:** Available for partners  

**Focus:** Comprehensive Transparency Data

**What It Provides:**
- **Platinum, Gold, Silver, Bronze Seals of Transparency**
- Self-reported program data (beyond Form 990)
- Board composition and governance information
- Demographic data (staff diversity, equity practices)
- The industry standard for nonprofit verification

**Coverage:**
- 1.8M+ nonprofit profiles
- Most comprehensive volume
- Many nonprofits display "GuideStar Seals" on their websites

**Use Case for Open Navigator:**
- Verify nonprofit legitimacy with transparency seals
- Show governance and demographic data
- Link to detailed GuideStar profiles for more info

---

### 3. GiveWell - The "Impact" Authority

**Source:** GiveWell  
**URL:** https://www.givewell.org/  
**API:** No public API (data available on website)  

**Focus:** Cost-Effectiveness & Evidence-Based Impact

**What It Provides:**
- **Top Charity** recommendations (highly selective)
- Cost-per-life-saved calculations
- Evidence-based impact assessments
- Program effectiveness research
- Most influential for "Effective Altruism" movement

**Coverage:**
- ~10-20 "Top Charities" at any time
- Focus on global health and poverty interventions
- Extremely rigorous evaluation standards

**Use Case for Open Navigator:**
- Highlight GiveWell-recommended charities
- Show cost-effectiveness metrics for top performers
- Filter by "evidence-based impact" certification

---

## 🔗 Additional Reference Resources

### IRS Exempt Organizations Business Master File (BMF)

**Source:** IRS  
**URL:** https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf  

**What It Contains:**
- Complete list of all tax-exempt organizations
- EIN (Employer Identification Number)
- NTEE codes (National Taxonomy of Exempt Entities)
- Subsection code (501(c)(3), 501(c)(4), etc.)
- Raw data (no ratings or analysis)

**Use Case:**
- Cross-reference EINs for data accuracy
- Classify nonprofits by NTEE code (education, health, environment, etc.)

---

### National Center for Charitable Statistics (NCCS)

**Source:** Urban Institute  
**URL:** https://nccs.urban.org/  

**What It Contains:**
- Research on nonprofit sector trends
- Data tools and visualization dashboards
- Policy analysis and reports

**Use Case:**
- Background research on nonprofit sector
- Trend analysis for advocacy strategies

---

## � Grant Research & Fundraising Platforms

These platforms help nonprofits find grant opportunities and manage fundraising. They're built on open-source principles or community-funded models to keep data accessible.

### Grantmakers.io ⭐ - "The Gold Standard for Free Grant Research"

**Source:** Community-supported open-source project  
**URL:** https://www.grantmakers.io/  
**Cost:** 100% FREE, no login required  

**What It Provides:**
- **Lightning-fast search** through IRS 990-PF data (private foundation tax returns)
- **Foundation giving histories** - See who funded what organizations
- **Grantee databases** - Find all grants made to specific nonprofits
- **Geographic targeting** - Search by state, city, or region
- **Year-over-year trends** - Track foundation giving patterns
- **No barriers** - Zero account creation, API keys, or paywalls

**Coverage:**
- ✅ **75,000+ grantmaking foundations** filing Form 990-PF
- ✅ **Millions of grant records** searchable instantly
- ✅ **Full foundation financials** - Assets, officers, giving patterns
- ✅ **Historical data** - Multi-year foundation trends

**Why It's Special:**
> "Grantmakers.io is the gold standard for 'free as in freedom.' It's community-supported to remain accessible forever, with no login walls or premium tiers."

**Use Cases:**
- **Grant Prospecting:** Find foundations that funded similar organizations in your area
- **Relationship Research:** Identify foundations supporting oral health, public health, civic engagement
- **Competitive Analysis:** See which nonprofits are getting grants in your field
- **Foundation Vetting:** Review foundation assets and giving patterns before applying

**Example Searches:**
- Foundations that funded "fluoridation" or "oral health" projects
- Grantmakers in Massachusetts supporting health policy advocacy
- Foundations with >$10M assets funding civic engagement
- All grants made by Robert Wood Johnson Foundation to Alabama nonprofits

---

### Zeffy ⭐ - "100% Free Fundraising with AI Grant Matching"

**Source:** Zeffy, Inc.  
**URL:** https://www.zeffy.com/  
**Cost:** 100% FREE for nonprofits (donor-covered fees model)  

**What It Provides:**
- **100% free fundraising platform** (no platform fees, ever)
- **AI-powered grant matching** - Machine learning matches your mission to opportunities
- **Grant alerts** - Email notifications for new matching grants
- **All-in-one tools** - Donations, events, memberships, grant discovery in one system
- **North America coverage** - U.S. and Canadian grant databases

**Why It's Unique:**
Traditional fundraising platforms charge 3-5% fees on donations. Zeffy's donor-covered model means **100% of donations go to your organization**, making it ideal for grassroots oral health advocacy groups.

**Grant Discovery Features:**
- **Mission-based matching:** Upload your mission, get matched grants
- **Federal grants:** Monitors Grants.gov for opportunities
- **Foundation grants:** Tracks private foundation RFPs
- **Corporate giving:** Alerts for corporate philanthropy programs
- **Local grants:** Community foundation and regional funder opportunities

**Use Cases for Open Navigator:**
- **Nonprofit fundraising:** Zero-cost donation processing for organizations
- **Grant prospecting:** AI helps match oral health nonprofits to relevant grants
- **Event fundraising:** Free ticketing for fundraising galas, community events
- **Membership management:** Track supporters, volunteers, members at no cost

---

### Community Foundations - "Local Grants Often Overlooked"

**Source:** Council on Foundations  
**Locator:** https://www.cof.org/community-foundation-locator  
**Coverage:** 700+ community foundations across the U.S.  

**What They Are:**
Community foundations are public charities that pool donations from individuals, families, and businesses to support local nonprofits through competitive grants, scholarships, and donor-advised funds.

**Why They Matter:**
- 🏘️ **Local focus:** Prioritize organizations in their specific region
- 💵 **Accessible grants:** $500-$50,000 range, ideal for grassroots groups
- 🤝 **Relationship-based:** Know local issues and local leaders
- 📋 **Simpler applications:** Less bureaucratic than federal grants
- ⚡ **Faster decisions:** Quarterly or rolling deadlines
- 🎯 **Mission alignment:** Support community health, civic engagement, education

**Examples:**

| Foundation | Region | Website | Grant Focus |
|------------|--------|---------|-------------|
| Central Alabama Community Foundation | Birmingham, AL | https://www.cacfbirmingham.org/ | Health, education, civic engagement |
| Boston Foundation | Boston, MA | https://www.tbf.org/ | Health, housing, civic participation |
| Community Foundation of Greater Memphis | Memphis, TN | https://www.cfgm.org/ | Health, youth, community engagement |
| Silicon Valley Community Foundation | San Francisco Bay | https://www.siliconvalleycf.org/ | Health, education, environment |
| Seattle Foundation | Seattle, WA | https://www.seattlefoundation.org/ | Racial equity, community health |

**How to Find Your Local Community Foundation:**
1. **Council on Foundations Directory:** https://www.cof.org/community-foundation-locator
2. **Candid Foundation Finder:** https://candid.org/find-us/foundation-finder
3. **Google Search:** "[Your City] Community Foundation"

**Grant Opportunities:**
- **Competitive grants:** Open RFPs for nonprofits in specific focus areas
- **Capacity building:** Support for operations, staffing, strategic planning
- **Donor-advised funds:** Individuals/families make grants through the foundation
- **Fiscal sponsorship:** Some sponsor projects for groups without 501(c)(3) status

**For Oral Health Advocacy:**
Many community foundations have health equity or preventive health focus areas that align perfectly with fluoridation advocacy, dental access programs, and oral health education. They're often the **best first step** for local grassroots campaigns.

---

## �📈 Integration Roadmap

### Phase 1: ✅ **Implemented**
- ProPublica Nonprofit Explorer (3M+ orgs via API)
- Basic search by location and name
- Form 990 financial data display

### Phase 2: 🔄 **In Progress**
- Create nonprofit profile pages with financial summaries
- Add "words vs money" accountability analysis
- Show executive compensation comparisons

### Phase 3: 📋 **Planned**
- Integrate Charity Navigator API for star ratings
- Add transparency seal badges from Candid/GuideStar
- Display GiveWell recommendations for top charities

### Phase 4: 🔮 **Future**
- Real-time API integrations with all reference sites
- Unified nonprofit scoring system
- Automated alerts for rating changes

---

## 🎯 How to Use These Resources

### For Individual Users:
1. **Start with ProPublica** - See the raw financial data (Form 990)
2. **Check Charity Navigator** - Get the 4-star rating for financial health
3. **Verify with Candid** - Confirm transparency seal status
4. **Look for GiveWell** - If seeking highest-impact charities

### For Advocates:
- Use ProPublica data to find inconsistencies ("words vs money")
- Reference Charity Navigator ratings in advocacy materials
- Cite GuideStar seals as proof of transparency
- Highlight GiveWell recommendations for evidence-based giving

### For Researchers:
- Download raw data from IRS BMF
- Use NCCS for sector-wide analysis
- Cross-reference multiple sources for data validation

---

## 📞 Contact & Support

**ProPublica API Support:**  
- Email: data@propublica.org  
- Documentation: https://projects.propublica.org/nonprofits/api

**Charity Navigator:**  
- Partnership inquiries: https://www.charitynavigator.org/about-us/contact/

**Candid (GuideStar):**  
- API access: https://www.guidestar.org/api

**GiveWell:**  
- General inquiries: info@givewell.org

---

## ✅ Data Quality & Updates

- **ProPublica:** Updated annually when new Form 990s are filed with IRS
- **Charity Navigator:** Ratings updated quarterly
- **Candid:** Self-reported data updated by nonprofits continuously
- **GiveWell:** Top Charity list updated annually (November/December)

All data sources listed are **free and publicly accessible**. API access may require partnership agreements for commercial use.
