---
sidebar_position: 1
---

# Unified Search Feature

LinkedIn-style search across contacts, meetings, organizations, and causes.

## Features

### Unified Search
- **Single search box** searches across all content types
- **Real-time autocomplete** suggestions as you type
- **Grouped results** by type (People, Meetings, Organizations, Causes)
- **Advanced filters** for state, NTEE codes, and content types
- **Relevance scoring** - most relevant results first

### Search Experience

The search works like LinkedIn:
1. **Type in the search box** - Get instant suggestions
2. **See all results** - Grouped by People, Meetings, Organizations, Causes
3. **Filter by type** - Click badges to show only specific content
4. **Filter by location** - Narrow results to specific states

## Using the Search

### From the Header
Every page (except home) has a search bar in the header:
- Type your query
- Press Enter
- Get comprehensive results

### Direct Access
Visit `/search` to access the full search experience.

### Example Searches

**Find People:**
```
Search: "mayor" or "city council member"
Results: Local officials, their titles, and jurisdictions
```

**Find Meetings:**
```
Search: "dental health" or "affordable housing"
Results: Meeting transcripts discussing these topics
```

**Find Organizations:**
```
Search: "food bank" + Filter: "Health"
Results: Nonprofits providing food assistance
```

**Find Causes:**
```
Search: "education"
Results: NTEE categories related to education
```

## API Endpoints

### Unified Search
```bash
GET /api/search?q=dental&types=meetings,organizations&state=AL
```

**Parameters:**
- `q` (optional): Search query; omit to browse by filters
- `types` (optional): Comma-separated types: `leaders`, `meetings`, `documents` (meeting videos), `meeting_documents`, `decisions`, `bills`, `topics`, `questions`, `causes`, `organizations`, `jurisdictions` (places), `grants`, `grant_opportunities`
- `state` (optional): 2-letter state code; `city` / `county_fips` / `jurisdiction_id` narrow further
- `ntee_code` (optional): Filter organizations by NTEE code prefix
- `org_type` (optional): Comma-separated organization sub-types, OR'd together; applies to `organizations` (see below). An unknown value returns 400.
- `facets` (optional): `org_type` adds `org_type_totals` to the response
- `limit` (optional): Max results per type (default: 20)

### Organization sub-types (`org_type`)

Organization search reads the golden org master `mdm_organization`, left-joined to the
`mdm_organization_nonprofit` satellite for 990 and NTEE detail, so it returns every
searchable organization type, not only nonprofits (#1221).

| `org_type` | What it matches | Rows (2026-11-26, local warehouse) |
|---|---|---:|
| `nonprofit` | `org_type = 'nonprofit'` | 3,731,149 |
| `foundation` | private foundations: nonprofit `foundation_code` 02, 03 or 04 (IRS BMF) | 134,259 |
| `church` | places of worship | 251,285 |
| `government` | townships, municipalities, police, school districts, counties, agencies | 110,102 |
| `company` | `org_type` `business` + `company` (includes the curated data-center companies) | 5,864 |
| `healthcare` | mostly hospitals | 7,783 |
| `education` | schools and education organizations | 1,227 |
| `political` | parties and political committees | 101 |

`org_type = 'other'` (39,787 rows) is **never** searchable: sampled rows are private family
and living trusts from property records, so they name private persons (see AGENTS.md,
"Privacy and data ethics").

`facets=org_type` returns `org_type_totals` (one real count per sub-type for the same
query and place scope, ignoring the `org_type` narrowing itself) and sets
`type_totals.organizations` to the exact total for the selected sub-types. The facet is
cached for an hour and time-boxed (`SEARCH_ORG_TYPE_FACET_TIMEOUT_S`, default 6s). When it
times out it is omitted, and the UI shows no count rather than a guess.

### Search categories in the UI

The home search box's **Search in** picker and the `/search` Filters share one list,
`web_app/src/lib/searchCategories.ts`: All, Meetings, Videos, Meeting Documents, Decisions,
Bills, Topics, Questions, Causes, Leaders, **Organizations** (all types) with the sub-types
Nonprofits, Foundations, Places of worship, Government bodies, Companies & businesses,
Healthcare, Schools & education and Political groups, then **Places**, Grants and Grant
Opportunities. A sub-type is carried in the URL as `?types=organizations&org_type=<id>`.
`/search` reads it, shows an "Organization type" chip, names the Organizations tab after
it, and offers the sub-types as checkboxes under Filters. Add a category here only when the
API returns real rows for it.

**Response:**
```json
{
 "query": "dental",
 "total_results": 45,
 "results": {
 "contacts": [...],
 "meetings": [...],
 "organizations": [...],
 "causes": [...]
 },
 "filters": {
 "state": "AL",
 "ntee_code": null,
 "types": ["meetings", "organizations"]
 }
}
```

### Autocomplete Suggestions
```bash
GET /api/search/suggest?q=dent&limit=5
```

**Response:**
```json
{
 "query": "dent",
 "suggestions": [
 "dental health",
 "dental services"
 ]
}
```

## Data Sources

Search queries across:

**Contacts** (Local Officials):
- ~1,500 officials across 5 states
- Names, titles, jurisdictions
- Files: `data/gold/states/{STATE}/contacts_local_officials.parquet`

**Meetings** (Transcripts):
- ~153,000 meeting records
- Titles, bodies, dates, jurisdictions
- Files: `data/gold/states/{STATE}/meetings.parquet`

**Organizations** (all searchable types, see "Organization sub-types" above):
- `public.mdm_organization` (golden org master, ~4.1M rows) left-joined to `public.mdm_organization_nonprofit`
- Names, cities, states, org type and subtype, NTEE codes and 990 figures for nonprofits

**Causes** (NTEE Categories):
- 196 nonprofit categories
- Codes, descriptions, categories
- File: `data/gold/reference/causes_ntee_codes`

## UI Components

### Search Result Card
Each result shows:
- **Icon** - Visual indicator of type (person, calendar, building, heart)
- **Title** - Name, meeting title, organization name
- **Subtitle** - Context (location, date, category)
- **Description** - Preview snippet
- **Badge** - Type indicator with color coding

### Color Coding
- **People** (Contacts): Blue
- **Meetings**: Green
- **Organizations**: Purple
- **Causes**: Pink

### Filter Chips
Quick-toggle filters for:
- All content types (default)
- Individual types (People, Meetings, Organizations, Causes)
- State filter
- Advanced filters panel

## Example Use Cases

### 1. Find Local Health Officials
```
Query: "health"
Types: Contacts
State: AL
→ Shows health department officials in Alabama
```

### 2. Research Affordable Housing Meetings
```
Query: "affordable housing"
Types: Meetings
State: MA
→ Shows all meetings discussing affordable housing in Massachusetts
```

### 3. Discover Food Assistance Organizations
```
Query: "food"
Types: Organizations
→ Shows food banks, pantries, and meal programs
```

### 4. Explore Education Causes
```
Query: "education"
Types: Causes
→ Shows NTEE categories for schools, scholarships, tutoring
```

## Performance

- **Relevance scoring**: Text matching with position boosting
- **Limited file scanning**: Max 5 states for contacts/meetings
- **National file optimization**: 1000-row sample for orgs
- **Autocomplete**: Common terms pre-indexed
- **Real-time filtering**: Client-side type filtering

## Technical Details

### Backend (FastAPI)
- **Router**: `/api/routes/search.py`
- **Functions**:
 - `unified_search()` - Main search endpoint
 - `search_suggestions()` - Autocomplete
 - `search_contacts()` - People search
 - `search_meetings()` - Meeting search
 - `search_organizations()` - Org search
 - `search_causes()` - Cause search
 - `calculate_relevance_score()` - Scoring algorithm

### Frontend (React + TypeScript)
- **Component**: `/frontend/src/pages/UnifiedSearch.tsx`
- **Features**:
 - React Query for data fetching
 - Autocomplete with debouncing
 - URL parameter sync
 - Responsive design
 - Keyboard navigation

### Routing
- **URL**: `/search?q={query}&state={state}`
- **Header Integration**: Global search redirects to `/search`
- **Deep Linking**: Share search results via URL

## Quick Start

### Start the API
```bash
cd /home/developer/projects/open-navigator
source .venv/bin/activate
uvicorn api.main:app --reload --port 8001
```

### Start the Frontend
```bash
cd frontend
npm run dev
```

### Test the Search
1. Navigate to http://localhost:5173
2. Click the search bar in the header (any page except home)
3. Type "dental health"
4. Press Enter
5. See results grouped by type!

## Future Enhancements

Potential improvements:
- Full-text search with Elasticsearch
- Fuzzy matching for typos
- Geographic proximity scoring
- Date range filters for meetings
- Revenue/budget filters for orgs
- Search history/recent searches
- Save searches
- Email alerts for new results
- Export results to CSV

## Troubleshooting

**No results found:**
- Check data files exist in `data/gold/`
- Try broader search terms
- Remove filters
- Check state filter matches available data

**Slow searches:**
- Reduce limit parameter
- Filter by specific types
- Specify state to limit file scanning

**Autocomplete not working:**
- Check API is running on port 8001
- Verify `/api/search/suggest` endpoint
- Check browser console for errors
