# Governance Meeting Transcript Deconstruction Prompt

## Objective
Your objective is to deconstruct a governance meeting transcript to expose the underlying logic of its outcomes. Do not provide a chronological summary; instead, pinpoint the specific drivers behind each decision, identify the key actors who steered the debate, and articulate the specific risks, resources, and **Heat Index** (the distinction between emotional intensity and procedural conflict) at play.

## The Heat Index (Intensity vs. Friction)
To provide a score for comparison across meetings, you must distinguish between two distinct signals:
- **Intensity Score (0–10):** Measures **Passion**. Look for "The Pivot" (switching from data to personal anecdote), first-person singular ("My kids," "My home"), and adverbial intensity (words like "unacceptable," "urgent," "fundamental," "disaster").
- **Friction Score (0–10):** Measures **Conflict**. Look for "Negation Clusters" ("I disagree," "Incorrect"), "Procedural Pushback" ("Point of order," "I wasn't finished"), and rapid-fire exchanges where speakers change every 10–15 words.

**Frame Analysis Requirements:**
For each decision, extract and contrast competing problem frames—the different ways stakeholders diagnose the cause, assign responsibility, propose solutions, and rank moral values. Frame analysis must explicitly capture:
- **Competing causal interpretations** (individual behavior vs system capacity, biology vs policy failure, etc.)
- **Moral value conflicts** (collective safety vs individual liberty, equity vs efficiency, etc.)
- **Normative tradeoffs** (whose interests are advanced, whose are constrained, which harms are accepted)
- **Counter-frame structure** (how opponents diagnose the problem, cause, and remedy)
- **Frame stability** (is this a new frame or extension of prior ones, does it lock in a dominant narrative)

## Writing Style
Apply Smart Brevity discipline to every text field: open with a headline that front-loads the so-what, follow with a colon and the essential detail, cut everything else.

## Scope
This prompt must work across any type of governance meeting regardless of jurisdiction size, body type, formality level, or subject matter — including but not limited to city councils, fire district budget hearings, school boards, county commissions, planning boards, utility authorities, and special district meetings. Adapt gracefully: if a field is not applicable to the meeting type set it to null rather than forcing a value that does not fit.

## Entity Identification and Cross-Query Linking
For every person, organization, legislation, financial item, and decision subject extracted from the transcript, generate stable cross-query identifiers so that entities can be linked across multiple meeting analyses without ambiguity.
- **Person slug rule:** normalize to `person_firstname_lastname_role_jurisdiction` all lowercase underscores no punctuation.
- **Organization slug rule:** normalize to `org_shortname_jurisdiction`.
- **Legislation slug rule:** normalize to `leg_type_number_year_jurisdiction`.
- **Subject slug rule:** normalize to `subject_descriptive_name_jurisdiction`. The subject slug must represent the underlying matter not the meeting action.

## Location and Postal Code Extraction
For each decision, extract the 5-digit ZIP code (postal_code), county FIPS code (county_fips), and county name (county) of the city or location associated with that decision. Determine these based on:
- The meeting location if the decision applies to that specific area
- The subject location if the decision pertains to a specific address, facility, parcel, or geographic area
- The jurisdiction's primary location if the decision is jurisdiction-wide
Priority order: specific subject location > meeting location > jurisdiction primary location.

## Theme Classification & COFOG Mappings
Map each primary theme to its COFOG code:

| Theme | COFOG |
|---|---|
| Fiscal and Budget Management | COFOG-01 |
| Infrastructure and Capital Projects | COFOG-04 |
| Zoning and Land Use | COFOG-06 |
| Public Safety and Emergency Services | COFOG-03 |
| Environmental and Natural Resources | COFOG-05 |
| Housing and Community Development | COFOG-06 |
| Economic Development and Business | COFOG-04 |
| Transportation and Mobility | COFOG-04 |
| Education and Workforce | COFOG-09 |
| Health and Human Services | COFOG-07 |
| Civil Rights and Equity | COFOG-01 |
| Governance and Administrative Policy | COFOG-01 |
| Parks and Recreation | COFOG-08 |
| Utilities and Public Works | COFOG-06 |
| Technology and Innovation | COFOG-04 |
| Legal and Compliance | COFOG-01 |
| Intergovernmental Relations | COFOG-01 |
| Public Engagement and Communications | COFOG-01 |

## NTEE Major Group Codes
Assign the most specific NTEE code determinable from context for organizations (A-Z). Always prioritize substantive cause areas (A-V, X-Y) over Public Policy (W).

## Financial Items
Extract every dollar value mentioned in the transcript into `financial_items` regardless of whether it is tied to a formal vote — include estimates, bids, appropriations, contract values, grants, fees, levy amounts, tax rates, and bond amounts.

## Mermaid Diagram Generation Rules
### Decision Timeline (diagram_timeline)
Generate a Mermaid timeline showing the chronological progression of the specific decision: prior context → this meeting's action → next steps. Quote all timestamps: `"09:00"`.
### Decision Mindmap (diagram_mindmap)
Generate a Mermaid mindmap showing: outcome, key arguments, stakeholders, financial impacts, and Heat Index peaks.

## Output Instructions

### STEP 1 — JSON
Output the JSON object and nothing else until the final curly brace. The JSON must be parseable by `JSON.parse()`. Populate the `heat_index` block for every decision. After the closing curly brace, output:
`---DOCUMENT_BREAK---`

### STEP 2 — Human-Readable Summary
Transform the JSON into a narrative optimized for human comprehension.
- **Meeting Overview:** Body name, type, date, location, attendance.
- **Key Decisions:** Include headline, location, outcome, and **Heat Index Analysis** (Intensity/Friction scores + Climax Quote).
- **Frame Analysis:** Dominant frame, counter-frames, causal contest, and value conflict.
- **Financial Summary:** Table of all financial items with amount, type, and context.
- **People and Organizations:** Bullet list of key actors with party affiliation and lobbyist status marked.

---

## JSON Schema

```json
{
  "meeting": {
    "meeting_id": "string",
    "body_name": "string",
    "body_type": "string",
    "meeting_date": "YYYY-MM-DD",
    "location": "string or null",
    "jurisdiction": "string",
    "session_info": { "is_multi_session": "boolean", "series_id": "string or null" }
  },
  "people": [
    {
      "person_id": "string",
      "full_name": "string",
      "role": "string",
      "party_affiliation": "string",
      "is_lobbyist": "boolean",
      "appeared_as": "string"
    }
  ],
  "organizations": [
    {
      "org_id": "string",
      "org_name": "string",
      "org_type": "string",
      "ntee_code": "string or null",
      "role_in_meeting": "string"
    }
  ],
  "financial_items": [
    {
      "financial_item_id": "string",
      "amount": 0,
      "amount_type": "string",
      "org_id": "string",
      "funding_source": "string or null"
    }
  ],
  "decisions": [
    {
      "decision_id": "string",
      "subject_id": "string",
      "topic": "string",
      "headline": "string",
      "decision_statement": "string",
      "decision_method": "string",
      "outcome": "string",
      "heat_index": {
        "intensity_score": 0,
        "friction_score": 0,
        "peak_signal_type": "string",
        "climax_quote": "string",
        "audience_response": "string or null"
      },
      "postal_code": "string or null",
      "county_fips": "string or null",
      "county": "string or null",
      "primary_theme": "string",
      "primary_theme_cofog": "string",
      "ntee_code": "string or null",
      "frame_analysis": {
        "dominant_frame": { "frame_label": "string", "moral_foundation": "string", "proposed_remedy": "string" },
        "counter_frames": [],
        "moral_frames": [ { "value_tension": "string", "resolution_method": "string" } ],
        "tradeoff_frames": []
      },
      "diagram_timeline": "string",
      "diagram_mindmap": "string"
    }
  ]
}