# Split-Screen System: Government Decisions ↔ Community Response

## The Big Idea

**Show the accountability gap AND the community filling it**

This isn't just about criticizing government - it's about showing citizens **exactly what's not being done** and **who's already doing it** so they can support, join, or replicate those solutions.

---

## The "Big Picture" Flow

### 1. Identify the Neglect
Show what government said no to or deferred.

**Example:**
- **Decision**: "Tabled decision on dental screening partnership"
- **Gap**: "100% of parents want screenings; Board said no"
- **Visual**: Red warning box showing the gap

### 2. Highlight the Logic  
Show the official rationale used to defer/deny.

**Example:**
- **Rationale**: "Legal Risk concerns require additional legal review"
- **Reality Check**: 35 states have school dental programs with zero liability suits
- **Visual**: Quote box with the official excuse

### 3. Bridge the Gap
Show nonprofits already doing this work.

**Example:**
- **Nonprofit**: "West Alabama Dental Initiative"
- **Impact**: 2,400 students served annually
- **Actions**: 
  - ✓ Volunteer opportunities available
  - ⭐ Board seats open
  - 🔗 Direct contact info
- **Visual**: Green success box with nonprofit cards

---

## The Split-Screen Structure

```
┌─────────────────────────────────┬─────────────────────────────────┐
│  🏛️ PUBLIC SECTOR                │  🤝 COMMUNITY SECTOR             │
│                                  │                                  │
│  The Decision:                   │  Nonprofits Filling the Gap:     │
│  • What was decided              │  • Organization name & mission   │
│  • Official rationale            │  • Services provided             │
│  • Outcome & vote                │  • Impact metrics                │
│                                  │  • Contact & volunteer info      │
│  The Gap:                        │  • Board opportunities           │
│  • What was requested            │                                  │
│  • Why it was denied             │  NTEE Code Match:                │
│  • Community impact              │  E32: School-Based Health Care   │
└─────────────────────────────────┴─────────────────────────────────┘
```

---

## NTEE Code Integration

### What are NTEE Codes?

**National Taxonomy of Exempt Entities** - IRS classification system for nonprofits.

### Why Use Them?

1. **Standardization**: Everyone uses the same categories
2. **Interoperability**: Can pull data from Charity Navigator, GiveWell, GuideStar APIs automatically
3. **Precision**: Matches government policy domains to nonprofit service areas
4. **Scalability**: Lightweight site, "Big Data" depth

### Key NTEE Codes for Oral Health Policy

| NTEE Code | Category | Example Nonprofits |
|-----------|----------|-------------------|
| **E32** | School-Based Health Care | Mobile dental clinics |
| **E40** | Health - General | Community health centers |
| **E80** | Health - Mental Health | School counseling orgs |
| **F30** | Mental Health Treatment | Crisis intervention |
| **O50** | Youth Development | After-school programs |
| **P30** | Children & Youth Services | Family support services |
| **W40** | Water Quality | Clean water advocacy |

### Mapping Policy Domains to NTEE Codes

```javascript
const nteeMapping = {
  // Health decisions
  'dental-health': ['E32', 'E40'],
  'mental-health': ['E80', 'F30'],
  'water-quality': ['W40', 'K31'],
  
  // Education decisions
  'school-nutrition': ['K30', 'K34'],
  'after-school': ['O50', 'P30'],
  
  // Safety decisions
  'youth-violence': ['I20', 'O50'],
  'traffic-safety': ['S20']
};
```

---

## Data Model

### Government Decision
```javascript
{
  decision_summary: "Tabled decision on dental screening partnership",
  outcome: "Tabled for further study",
  primary_rationale: "Legal risk concerns...",
  policy_domain: "health",
  ntee_code: "E32", // School-Based Health Care
  community_gap: {
    description: "100% of parents want dental screenings",
    nonprofit_filling_gap: true
  }
}
```

### Nonprofit Organization
```javascript
{
  name: "West Alabama Dental Initiative",
  ein: "63-1234567", // Tax ID for IRS lookup
  ntee_code: "E32",
  ntee_description: "School-Based Health Care",
  mission: "Free dental screenings for underserved students",
  services: [
    "Mobile dental unit visits",
    "Free toothbrush kits",
    "Parent education workshops"
  ],
  annual_budget: 125000,
  students_served: 2400,
  contact: {
    website: "https://wadaldentalinitiative.org",
    email: "info@wadaldentalinitiative.org",
    phone: "(205) 555-0123"
  },
  volunteer_opportunities: true,
  accepting_board_members: true
}
```

---

## User Journey

### 1. Browse Decisions (Left Rail)
User filters by topic: "Public Health"
- Sees decision: "Dental screening partnership tabled"
- Sees badge: "🤝 Community filling gap"
- Clicks to view details

### 2. View Split-Screen
**Left Side** - Government:
- Decision summary
- Official rationale: "Legal risk concerns"
- The accountability gap: "100% of parents want this"

**Right Side** - Community:
- 2 nonprofits doing this work
- West Alabama Dental Initiative: 2,400 students served
- Tuscaloosa Family Health Network: 850 families served

### 3. Take Action
User sees action buttons:
- 📧 Email nonprofit
- 🌐 Visit website
- ✓ Volunteer
- ⭐ Join board

User can now:
- Support existing solutions
- Join boards to change policy from inside
- Cite these orgs in public meetings to prove solutions exist

---

## Future: API Integration

### Phase 1: Static Data (Current)
- Manually curated nonprofit list
- NTEE codes assigned by hand
- Updated quarterly

### Phase 2: IRS Pub 78 API
```python
import requests

def get_nonprofits_by_ntee(ntee_code, city="Tuscaloosa", state="AL"):
    """Fetch nonprofits from IRS tax-exempt organization database"""
    url = f"https://apps.irs.gov/pub/epostcard/data-download-pub78.zip"
    # Parse CSV, filter by NTEE code and location
    return nonprofits
```

### Phase 3: Charity Navigator API
```python
def enrich_nonprofit_data(ein):
    """Get ratings, financials, and impact metrics"""
    url = f"https://api.charitynavigator.org/v1/organizations/{ein}"
    return {
        'overall_rating': 4.2,
        'financial_rating': 4.5,
        'accountability_rating': 4.0,
        'program_expense_ratio': 0.87
    }
```

### Phase 4: GiveWell/GuideStar Integration
- Effectiveness ratings
- Cost per beneficiary
- Transparency scores

---

## Visual Design Principles

### Color Coding

**Government Side (Left):**
- Neutral whites and grays
- Orange/red for "accountability gaps"
- Blue for official actions

**Community Side (Right):**
- Green for "filling the gap"
- Warm colors for impact metrics
- Call-to-action buttons in bright colors

### Typography Hierarchy

1. **Section Headers**: 12px uppercase, 600 weight
2. **Titles**: 18-24px, 600 weight
3. **Body**: 14-16px, 400 weight
4. **Labels**: 11-13px, 500 weight

### Card Layouts

**Decision Card (Left):**
```
┌─────────────────────────────────┐
│ Decision Summary                │
│ ───────────────────────────────│
│ 📝 Official Rationale           │
│ "Legal risk concerns..."        │
│ ───────────────────────────────│
│ ⚠️ The Accountability Gap       │
│ "100% of parents want this"     │
└─────────────────────────────────┘
```

**Nonprofit Card (Right):**
```
┌─────────────────────────────────┐
│ Organization Name               │
│ NTEE E32: School Health Care    │
│ ───────────────────────────────│
│ Mission statement...            │
│ ───────────────────────────────│
│ Services:                       │
│ • Mobile dental unit            │
│ • Free kits                     │
│ ───────────────────────────────│
│ 👥 2,400 students | 💰 $125K    │
│ ───────────────────────────────│
│ [Website] [Email] [Volunteer]   │
│ ✓ Board seats available         │
└─────────────────────────────────┘
```

---

## Messaging Framework

### The Problem (Left Side)
> "The government said **NO** to dental screenings because of 'legal concerns'"

### The Reality Check
> "35 states have school dental programs with **ZERO** liability lawsuits"

### The Solution (Right Side)
> "Here are **2 local nonprofits** already providing this service to **3,250 students**"

### The Call to Action
> "Support them, volunteer with them, or join their boards to **change the system from the inside**"

---

## Implementation Checklist

### Backend
- [x] Add NTEE codes to decision data model
- [x] Add `community_gap` field to decisions
- [ ] Create nonprofit data scraper (IRS Pub 78)
- [ ] Build NTEE code matcher
- [ ] API endpoint for nonprofit lookup by NTEE code

### Frontend
- [x] Create SplitScreenView component
- [x] Add nonprofit cards with contact info
- [x] Show "community filling gap" badges on decision cards
- [x] Add NTEE code display
- [ ] Add nonprofit search/filter
- [ ] Add "Bridge the Gap" action buttons

### Data
- [x] Example nonprofits with NTEE codes
- [ ] Real Tuscaloosa nonprofits database
- [ ] IRS EIN verification
- [ ] Contact info validation
- [ ] Board opportunity verification

### Design
- [x] Split-screen layout
- [x] Color-coded sectors (government vs community)
- [x] Impact metrics display
- [ ] Mobile-responsive breakpoints
- [ ] Print-friendly view

---

## Success Metrics

### Awareness
- % of users who view split-screen view
- Time spent on community sector side
- Click-through rate to nonprofit websites

### Engagement
- Volunteer inquiry form submissions
- Email clicks to nonprofits
- Board opportunity interest

### Impact
- Nonprofits report increased inquiries
- Citizens citing these orgs in public meetings
- Board members recruited through the site

---

## Next Steps

1. **Build IRS Data Pipeline**: Automatically pull nonprofit data by NTEE code
2. **Add Geolocation**: Match nonprofits serving specific zip codes
3. **Create "Take Action" Workflows**: Guided forms for volunteering, joining boards
4. **Add Effectiveness Ratings**: Show which nonprofits have highest impact
5. **Enable Nonprofit Profiles**: Let nonprofits claim and update their listings

---

## The Bigger Vision

**This isn't just a government accountability site - it's a community empowerment platform.**

When citizens see:
1. What government refuses to do
2. Who's already doing it
3. How to support or join them

They have **three pathways to change**:
- Support nonprofits filling the gap NOW
- Join nonprofit boards to scale proven solutions
- Cite these orgs in public meetings to pressure government

**The split-screen design makes this obvious, actionable, and immediate.**
