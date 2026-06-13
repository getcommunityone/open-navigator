## Objective
Extract the **decisions** made in a governance meeting transcript and **classify** each one. This is a lightweight pass for an open-source civic platform: identify what the body decided, the outcome, and the controlled-vocabulary topic + cause. Do NOT write narratives, diagrams, human-element detail, evidence metrics, or speaking-time data. Output ONLY the JSON object below and nothing else.

## Decisions vs uncontested items
Capture **every distinct council action**, split into two buckets:

- **`decisions[]`** (`D001`, `D002`, …): **contested / debated / opposed** items — anyone (resident, applicant, or a member) spoke against it, *even if it passed unanimously*. A unanimous vote is NOT automatically uncontested; route by whether anyone pushed back.
- **`uncontested_items[]`** (`U001`, `U002`, …): no debate AND no opposition — consent-agenda blocks, routine approvals.

An item appears in **exactly one** bucket, never both. Omit pure housekeeping (approve minutes, roll call). A full session usually has **many** uncontested items and **few** (1–3) decisions.

## Classification (required on every decisions[] AND uncontested_items[] row)
1. **`primary_theme`** — exactly ONE label from this fixed list (do not invent or abbreviate). Use `Governance and Administrative Policy` only for purely procedural items when nothing else fits. If the transcript gives no signal, set `null`.
   - Fiscal and Budget Management
   - Infrastructure and Capital Projects
   - Zoning and Land Use
   - Public Safety and Emergency Services
   - Environmental and Natural Resources
   - Housing and Community Development
   - Economic Development and Business
   - Transportation and Mobility
   - Education and Workforce
   - Health and Human Services
   - Civil Rights and Equity
   - Governance and Administrative Policy
   - Parks and Recreation
   - Utilities and Public Works
   - Technology and Innovation
   - Legal and Compliance
   - Intergovernmental Relations
   - Public Engagement and Communications
2. **`primary_cause_ntee`** — the single best-fit NTEE major-group letter for the substantive cause area (e.g. `E` Health Care, `O` Youth Development, `L` Housing, `S` Community Improvement, `C` Environment, `B` Education, `W` Public/Societal Benefit). Prefer a substantive area over `W` unless the item is strictly administrative. `null` if unclear.
3. **`primary_cause_label`** — a short (≤4 word) plain-language cause area (e.g. "Affordable housing", "Road safety"). `null` if unclear.

## Rules
- Never invent. Use only what the transcript states. Leave fields `null` rather than guessing.
- `place_raw`: the single most relevant verbatim location cue for the item (street/site/neighborhood), or `null`. Do not geocode or normalize.
- `vote_tally`: fill `yes`/`no` only when an explicit count or "unanimous" is stated; otherwise `null`.
- Output the JSON object matching the schema below and NOTHING ELSE.

## JSON Schema
{
  "meeting": {
    "meeting_id": "string",
    "body_name": "string",
    "meeting_date": "YYYY-MM-DD or null",
    "jurisdiction": "string",
    "meeting_summary": "string — 1 sentence, overall meeting outcome"
  },
  "decisions": [
    {
      "decision_id": "string — D001, D002, …",
      "headline": "string — short lead, max ~12 words",
      "decision_statement": "string — one sentence: what was decided",
      "outcome": "string — e.g. Approved, Denied, Deferred, Tabled",
      "vote_tally": { "yes": "number or null", "no": "number or null" },
      "primary_theme": "string or null — one exact label from the list above",
      "primary_cause_ntee": "string or null — single NTEE major-group letter",
      "primary_cause_label": "string or null — short plain cause area",
      "place_raw": "string or null — verbatim location cue",
      "place_refs": [],
      "legislation_refs": [],
      "financial_item_refs": []
    }
  ],
  "uncontested_items": [
    {
      "item_id": "string — U001, U002, …",
      "headline": "string — short label, max ~12 words",
      "outcome": "string — e.g. Approved, Adopted, Called",
      "vote": "string or null — e.g. 7-0, unanimous, voice vote",
      "primary_theme": "string or null — one exact label from the list above",
      "primary_cause_ntee": "string or null",
      "primary_cause_label": "string or null"
    }
  ]
}

<transcript>
[INSERT TRANSCRIPT HERE]
</transcript>
