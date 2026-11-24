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

## Public comment stance (`public_participation[]`)
One row per **member of the public or outside stakeholder** who addressed the body (not members of the body, not staff).
- `speaker_id`: a slug `firstname_lastname_role` from the name as spoken (e.g. `david_craig_resident`). Skip a speaker who is not named; never invent a name.
- `decision_id`: the `decisions[].decision_id` or `uncontested_items[].item_id` the comment is about; `null` for general public comment.
- `stance` toward **the action being decided**, exactly one of: `For`, `Against`, `Asked questions` (only asked questions or sought information), `Mixed or neutral` (conditions, delay requests, information only), `Not stated` (does not address the action). Never infer a stance from a role or name.
- `stance_evidence`: the speaker's own words showing the stance, verbatim, 25 words or fewer; else `null`.
- `heat`: how heated this speaker's comment was, a whole number 1 to 5, judged only from their words and what the transcript records (captions carry no tone of voice):
    * **1:** calm; information or a neutral question.
    * **2:** polite, a mild preference or concern.
    * **3:** firm or emphatic; urges the body to act.
    * **4:** states anger, frustration or alarm; accusations or warnings.
    * **5:** personal attacks, threats of legal or electoral retaliation, shouting noted in the transcript, or cut off or gaveled by the chair.
  `null` when too little was said to judge. Never raise the number because of the topic or the speaker's side.
- `speaker_role`: the capacity the speaker gave for themselves, exactly one of: Resident, Property owner, Business owner, Advocacy group, Expert, Union worker, Applicant or developer, Student, Other, Not stated. Use what they said ("I live on Oak Street" is `Resident`; "I own the lot next door" is `Property owner`; "I'm with the Rivers Alliance" is `Advocacy group`; an engineer, doctor or attorney speaking from that expertise is `Expert`). `Not stated` when they gave none. Never infer a role from a name or from their stance.
Emit at most 40 rows. If more people spoke, keep the comments tied to a `decisions[]` item first, then those on uncontested items, then general comment; never drop a speaker to shorten another field.
If no member of the public spoke, emit `"public_participation": []`.

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
  "public_participation": [
    {
      "speaker_id": "string — firstname_lastname_role slug",
      "decision_id": "string or null — D00x or U00x the comment is about",
      "stance": "one of: For, Against, Asked questions, Mixed or neutral, Not stated",
      "stance_evidence": "string or null — verbatim quote, 25 words or fewer",
      "heat": "integer 1-5 or null",
      "speaker_role": "one of: Resident, Property owner, Business owner, Advocacy group, Expert, Union worker, Applicant or developer, Student, Other, Not stated"
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
