
raw
Governance extraction prompt v2 · MD
## Objective
Your objective is to deconstruct a governance meeting transcript to expose the underlying logic of its outcomes. You are extracting structured data for an open-source civic tech platform. 
 
Do not provide a chronological summary. Pinpoint the specific drivers behind each decision, identify the key actors, articulate the specific risks or resources at play, and explicitly capture the human stakes.
 
## Complete decision coverage (CRITICAL)
 
Capture **every distinct council action**, but **split by debate** — do not put light unanimous items in `decisions[]`.
 
| Where | What goes there |
|-------|-----------------|
| **`decisions[]`** (`D001`, `D002`, …) | **Contested / debated only** — public hearing with tension, disagreement, personal stories, or non-routine stakes worth a full analysis |
| **`uncontested_items[]`** (`U001`, `U002`, …) | **Unanimous, consent agenda, or no debate** — resolutions adopted in a block, routine approvals, election calls read into the record, etc. |
 
**Do not merge** unrelated items. Example: liquor license (debated) → `D001`; school-supplies program + tax election (no debate) → `U001`, `U002`.
 
**You may omit:** pure housekeeping (approve minutes, roll call only).
 
**Do NOT** duplicate: an item appears in **either** `decisions[]` **or** `uncontested_items[]`, never both.
 
**Sanity check:** A full council session usually has **many** `uncontested_items` and **few** `decisions` (often 1–3 debated items). If everything is in `decisions[]`, you are wasting space — move non-debated votes to `uncontested_items[]`.
 
## The Human Element (CRITICAL)
Apply only to **`decisions[]`** (contested items). Do **not** add `human_element`, `competing_views`, or diagrams to `uncontested_items[]`.
- **Personal Stories:** Extract specific anecdotes used to argue a point. 
- **Humor:** Capture tension-breaking laughter, sarcasm, or procedural jokes.
- **Emotional Intensity Rubric:** You MUST classify the `intensity` of supporters and opponents using strictly these behavioral markers from the transcript:
    * **Low:** Routine business, unanimous consent, polite procedural questions, no disagreement.
    * **Moderate:** Polite disagreement, standard debate, probing questions, differing opinions expressed calmly.
    * **High:** Interruptions, explicitly stated frustration/anger, cross-talk, pleading, warnings from the chair to maintain order, heavy sighing/sarcasm.
    * **Very High:** Shouting, walkouts, gaveling down, personal attacks, explicit threats of legal action or electoral retaliation, crying.
    * **Not applicable:** Stakeholder group was **not present and did not speak at all** — no comments, no questions, nothing on the record.
    - **Floor rule:** If a group spoke *in any way* — even one polite question or a single neutral comment — the intensity is **at least Low**. Never pair "Not applicable" with a `plain_summary` that describes anything they said or asked. If you wrote a non-empty `plain_summary` for a group, its intensity cannot be "Not applicable".
## Strict Entity & Cross-Query Linking
- Person slug rule: `person_firstname_lastname_role_jurisdiction`
- Organization slug rule: `org_shortname_jurisdiction`
- Legislation slug rule: `leg_type_number_year_jurisdiction`
- Subject slug rule: `subject_descriptive_name_jurisdiction`
- **Place slug rule:** `place_{normalized_location}_{jurisdiction}` — lowercase, underscores, no punctuation. Same street address → same `place_id` across items.
## Places & addresses (CRITICAL)
 
Extract **every distinct real-world location** mentioned in the transcript: street addresses, intersections, subdivisions, facilities, bridges, campuses, and named neighborhoods **when tied to an agenda item**.
 
1. Build canonical rows in top-level **`places[]`** (dedupe by address/site).
2. Cross-link each **`decisions[]`** and **`uncontested_items[]`** row with **`place_refs`** (array of `place_id`).
3. Set **`primary_place_id`** on the row when one site is clearly primary.
4. Set **`subjects[].primary_place_id`** when the subject is a parcel, property, or facility.
**Per `places[]` row:**
- **`raw_text`**: verbatim cue from transcript (e.g. "3620 23rd Street", "Southern Gardens", "Ed Love water treatment plant").
- **`normalized_address`**: best-effort single line for geocoding (e.g. `3620 23rd St, Tuscaloosa, AL`). Use meeting city/state when spoken but omitted.
- **`place_type`**: one of `street_address`, `intersection`, `subdivision`, `facility`, `bridge`, `campus`, `neighborhood`, `corridor`, `jurisdiction_wide`, `other`.
- **`street_address`**, **`city`**, **`state`**: parsed components when known; `state` as 2-letter USPS if US.
- **`geocode_query`**: same as `normalized_address` unless a facility needs a name qualifier (e.g. `Ed Love Water Treatment Plant, Tuscaloosa, AL`).
- **`latitude`**, **`longitude`**: null in model output (filled by pipeline geocoder).
- **`geocode_status`**: `pending` | `ok` | `not_found` | `skipped` — default `pending`.
- **`linked_decision_ids`**, **`linked_item_ids`**: every `D00*` / `U00*` that references this place.
- **`mention_count`**: approximate times discussed.
**Do not** invent addresses. **Do** include approximate addresses ("3209 97th Street") and well-known local sites ("Woolsey Fenel bridge", "River Market") when the transcript supports them.
 
**Priority for geocoding:** street number + street > named facility in city > subdivision name in city.
 
## Theme Classification (controlled vocabulary)
Set `primary_theme` on **every** `decisions[]` and `uncontested_items[]` row to **one exact label** from this fixed list (do not invent labels, do not abbreviate). Pick the single best fit; use `Governance and Administrative Policy` for purely procedural items and only when nothing else fits. If the transcript gives no signal, set `primary_theme` to `null`.
 
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
## NTEE & COFOG Classification
Assign the most specific NTEE major group code determinable from context for organizations. For decisions, extract NTEE codes based on the primary cause area (e.g., E for Health Care, O for Youth Development). Prioritize substantive cause areas over W (Public Policy) unless it is strictly administrative. Set `primary_theme_cofog` based on the exact Theme labels above.
 
## Evidence Metrics (decisions[] only — CRITICAL)
For each contested decision, capture **every quantitative measure spoken in the transcript that an actor used to justify or attack a position**. A metric is any cited figure used as evidence: counts, percentages, dollars, rates, ratios, durations, distances, projections, rankings, scores, or benchmarks.
 
- **Only metrics actually voiced** to support an argument. Do NOT capture incidental numbers already structured elsewhere — vote tallies, agenda item numbers, addresses, or dates of the meeting itself.
- **`direction`** records the metric's rhetorical role:
    * `supports`   — cited to advance the position
    * `opposes`    — cited to argue against it
    * `contextual` — framing / scale-setting, no clear side
    * `contested`  — the figure itself is disputed (wrong number, bad methodology, irrelevant)
- **`reasoning_link`** is the causal claim that connects the number to the position (≤25 words) — the "so what." This is the field that makes the metric meaningful.
- Tie each metric to a side via **`supports_view`** = the `view_label` from `competing_views` it backs (or `"dominant"` / `"counter"`).
- **Same figure used by both sides to opposite ends** → two rows, opposite `direction`. **Figure's validity disputed** → one row, `direction: contested`, fill `contested_by_person_id` and `rebuttal`.
- If the metric is a dollar amount already in `financial_items[]`, set `financial_item_ref` instead of re-describing it.
- Never invent or extrapolate a figure. If a speaker gestures at a trend without a number ("crime is way up"), do not manufacture one — skip it.
- Keep `evidence_metrics` **off** `uncontested_items[]`.
## Output Instructions
Output the JSON object matching the schema below and NOTHING ELSE.
 
**Before you close the root JSON:** Re-scan all votes. Debated → `decisions[]`; routine/unanimous → `uncontested_items[]`. Confirm every quantitative claim used to argue a position is captured in `evidence_metrics` with a `direction` and a `reasoning_link`.
 
## Uncontested item attribution (required when transcript allows)
 
For **each** `uncontested_items[]` row, link people and timestamps when the transcript or `=== AGENDA SEGMENT HINTS ===` block supports it:
 
- **`presenter_person_ids`**: `people[].person_id` for staff who presented the item (e.g. Mike on sewer acceptance). Use `[]` only if truly unknown.
- **`council_question_person_ids`**: councilors who asked questions before the vote (often one ID).
- **`motion`**: `{ "moved_by_person_id", "seconded_by_person_id" }` when the transcript says who moved/seconded; else `null`.
- **`media_anchor`**: `{ "timestamp_start_seconds", "timestamp_end_seconds" }` for the discussion/vote span (from agenda hints or transcript timestamps). Do not invent times.
- **`financial_item_refs`**: match `financial_items[]` when dollars are discussed (same as contested decisions).
Keep `human_element` / diagrams / `evidence_metrics` **off** `uncontested_items[]` — only IDs, motion, and timestamps.
 
**Meeting summary (`meeting` object):** Fill `meeting_summary` (1–2 sentences: what was on the agenda and what the body did overall) and `agenda_summary` (optional short phrase listing major topics, e.g. “rezoning, capital contracts, budget amendment”).
 
**Smart Brevity capture (`decisions[]` only):** Fill `smart_brevity` on every contested row for Document 2. `one_big_thing` = thesis sentence (merged into Part 2 **Why it matters** — not a separate label). `why_it_matters` = resident stakes; `big_picture`, `by_the_numbers` (or null), `whats_next`, `for_it_summary`, `against_it_summary` (or null) in plain language — no “Who won” framing.
 
**No redundancy across blocks (CRITICAL for usability):** `smart_brevity`, `competing_views`, `human_element`, and `evidence_metrics` are shown as separate panels and must each add new information — do **not** restate the same sentence in more than one. Keep them in their lanes:
- `smart_brevity` = the *what/so-what* for a resident (outcome, stakes, numbers, next step).
- `competing_views` = the *reasoning* — each side's problem diagnosis → causal story → remedy. Do not repeat the outcome or the numbers here. Populate each view's `held_by` with the `people[].person_id` values of those who advanced it (so the UI can show who took each side); use an empty array when the side was argued by the public generally or no individual is identifiable. Every `held_by` id MUST resolve to a `people[]` entry.
- `human_element` = the *people* — who felt what, anecdotes, tone. Do not repeat the policy substance here.
- `evidence_metrics` = the *numbers-as-evidence* — each cited figure, who used it, which side it backs, and whether it was rebutted. Do not restate `by_the_numbers` here; that's a display digest, this is the argument graph.
Each `smart_brevity` field is one tight sentence (≤25 words); `by_the_numbers` is concrete figures only (votes, dollars, distances, dates), not prose. Set a field to `null` rather than padding it with a rephrasing of another field.
**Diagram rules (`decisions[]` only):** Populate **`diagram_timeline`** and **`diagram_mindmap`** as single strings with **valid Mermaid** (renders in Mermaid Live Editor). Also set `diagram_timeline_lines` / `diagram_mindmap_lines` as optional plain-text helpers. **Never** on `uncontested_items[]`.
 
* **`diagram_timeline`:** Must start with `timeline` on line 1, then `title …`, then `section …` groups, then events as `{time label} : {event}` (one colon per line). No `graph TD`. No clock times with colons in labels (`09:00` → use `09h00` or `2026-05-19`). Issue lifecycle (origins → this meeting → next steps), not a minute-by-minute log.
* **`diagram_mindmap`:** Must start with `mindmap` on line 1, then `root((Topic))`, then **indented** branches (2 spaces per level). **Section labels** (`Proposal`, `Problem`, `Solution`, `Funding`, `Timeline`, `Arguments For`, `Arguments Against`, `Stakeholders`, `Outcome`, etc.) are parents; put specific points **indented under** them (4 spaces under root, 6 spaces under a section). A flat list of siblings is wrong. No `graph TD`.
* Example timeline:
  ```
  timeline
      title Property repair extension
      section Prior
          Earlier : Council tabled case
      section This meeting
          2026-05-19 : 90-day extension granted
      section Next
          Next : Complete repairs and permit
  ```
* Example mindmap:
  ```
  mindmap
    root((2842 18th Street rezoning))
      Proposal
        Duplex construction
        MR1 to SFR5
      Arguments For
        Affordable housing
        Redevelopment
      Arguments Against
        Front yard parking concerns
      Stakeholders
        Applicant
        Neighbors
      Outcome
        Recommended approval 7-0
  ```
 
## JSON Schema
{
  "meeting": {
    "meeting_id": "string",
    "body_name": "string",
    "meeting_date": "YYYY-MM-DD",
    "jurisdiction": "string",
    "session_info": {
      "is_multi_session": "boolean",
      "session_number": "integer or null",
      "total_sessions": "integer or null"
    },
    "meeting_summary": "string — 1-2 sentences for Part 2 At a glance (overall meeting outcome)",
    "agenda_summary": "string — optional short list of major agenda topics (~25 words max)"
  },
  "people": [
    {
      "person_id": "string",
      "full_name": "string",
      "role": "string",
      "appeared_as": "string"
    }
  ],
  "organizations": [
    {
      "org_id": "string",
      "org_name": "string",
      "org_type": "string",
      "ntee_code": "string or null"
    }
  ],
  "legislation": [
    {
      "leg_id": "string — normalized slug",
      "leg_type": "string",
      "official_number": "string or null",
      "title": "string or null",
      "status": "string",
      "relevance": "string — Smart Brevity headline"
    }
  ],
  "financial_items": [
    {
      "financial_item_id": "string — sequential e.g. FIN001",
      "event_description": "string — Smart Brevity headline",
      "amount": 0,
      "amount_type": "string",
      "funding_source": "string or null"
    }
  ],
  "places": [
    {
      "place_id": "string — place_{slug}_{jurisdiction}",
      "raw_text": "string — verbatim transcript mention",
      "normalized_address": "string — one-line geocode-friendly address",
      "place_type": "street_address | intersection | subdivision | facility | bridge | campus | neighborhood | corridor | jurisdiction_wide | other",
      "street_address": "string or null",
      "city": "string or null",
      "state": "string or null — 2-letter if US",
      "geocode_query": "string",
      "latitude": "number or null",
      "longitude": "number or null",
      "geocode_status": "pending | ok | not_found | skipped",
      "linked_decision_ids": ["D001"],
      "linked_item_ids": ["U002"],
      "mention_count": "integer or null"
    }
  ],
  "subjects": [
    {
      "subject_id": "string — normalized slug",
      "subject_label": "string",
      "subject_description": "string",
      "canonical_leg_id": "string or null",
      "primary_place_id": "string or null — match places[] when subject is a site/parcel"
    }
  ],
  "uncontested_items": [
    {
      "item_id": "string — sequential U001, U002, …",
      "headline": "string — short label, max ~12 words",
      "outcome": "string — e.g. Approved, Adopted, Called",
      "vote": "string — e.g. 7-0, unanimous, voice vote",
      "one_line_summary": "string — one sentence, max ~25 words; what happened and why it matters briefly",
      "subject_id": "string or null — match subjects[] when applicable",
      "primary_place_id": "string or null — main site for this vote",
      "place_refs": ["string — place_id slugs; include all locations discussed for this item"],
      "legislation_refs": ["string — leg_id slugs, often empty"],
      "financial_item_refs": ["string — financial_item_id slugs, often empty"],
      "primary_theme": "string or null — one exact label from the Theme Classification list",
      "presenter_person_ids": ["string — people[].person_id who presented; [] if unknown"],
      "council_question_person_ids": ["string — councilors who asked questions; often []"],
      "motion": {
        "moved_by_person_id": "string or null",
        "seconded_by_person_id": "string or null"
      },
      "media_anchor": {
        "timestamp_start_seconds": "number or null",
        "timestamp_end_seconds": "number or null"
      }
    }
  ],
  "decisions": [
    {
      "decision_id": "string — sequential e.g. D001 (contested items only)",
      "subject_id": "string — must match a subject_id",
      "primary_place_id": "string or null — main site for this decision",
      "place_refs": ["string — place_id slugs for every address/site tied to this decision"],
      "legislation_refs": ["string — must match a leg_id"],
      "financial_item_refs": ["string — must match a financial_item_id"],
      "headline": "string — Smart Brevity lead",
      "decision_statement": "string",
      "primary_theme": "string or null — one exact label from the Theme Classification list",
      "outcome": "string",
      "vote_tally": {
        "yes": "number or null",
        "no": "number or null"
      },
      "human_element": {
        "personal_stories": [
          {
            "person_id": "string or null",
            "story_headline": "string — Smart Brevity headline",
            "story_detail": "string — the personal story in plain language",
            "why_it_mattered_to_the_decision": "string"
          }
        ],
        "humor_and_light_moments": [
          {
            "speaker_id": "string or null",
            "summary": "string",
            "tone": "one of: Humor, Sarcasm, Tension-breaking, Procedural joke, Other"
          }
        ],
        "emotional_tone": {
          "supporters": {
            "intensity": "one of: Low, Moderate, High, Very high, Not applicable",
            "primary_emotions": ["string"],
            "plain_summary": "string"
          },
          "opponents": {
            "intensity": "one of: Low, Moderate, High, Very high, Not applicable",
            "primary_emotions": ["string"],
            "plain_summary": "string"
          }
        }
      },
      "competing_views": {
        "dominant_view": {
          "view_label": "string",
          "problem_diagnosis": "string",
          "causal_story": "string",
          "proposed_remedy": "string",
          "held_by": ["string — people[].person_id of those who advanced this view (council members, staff, speakers); empty array if no one is individually identifiable"]
        },
        "counter_views": [
          {
            "view_label": "string",
            "problem_diagnosis": "string",
            "causal_story": "string",
            "held_by": ["string — people[].person_id of those who argued this side; empty array if no one is individually identifiable"]
          }
        ]
      },
      "evidence_metrics": [
        {
          "metric_id": "string — sequential within decision, e.g. M001",
          "metric_label": "string — what is measured (e.g. 'Affordable units produced per year')",
          "value": "string — figure exactly as cited (e.g. '500', '54%', '$40M')",
          "unit": "string or null — e.g. units/year, percent, dollars, days, trips/day, count",
          "baseline_or_comparison": "string or null — what it's measured against (e.g. 'up from $26M', 'vs prior year', 'national avg')",
          "metric_type": "one of: outcome | cost_input | trend | forecast | benchmark | threshold | other",
          "cited_by_person_id": "string or null — people[].person_id who introduced it",
          "supports_view": "string — competing_views view_label it backs, or 'dominant' / 'counter'",
          "direction": "one of: supports | opposes | contextual | contested",
          "reasoning_link": "string — causal claim linking metric to position (≤25 words)",
          "contested_by_person_id": "string or null — who disputed the figure, if anyone",
          "rebuttal": "string or null — how it was challenged (different number, methodology, relevance)",
          "financial_item_ref": "string or null — financial_items[] id if this is a dollar figure already captured",
          "media_anchor_seconds": "number or null — timestamp where the metric was cited"
        }
      ],
      "smart_brevity": {
        "one_big_thing": "string — thesis sentence (Part 2 merges into **Why it matters**; no separate label)",
        "why_it_matters": "string — immediate resident impact (paired with one_big_thing in Part 2)",
        "big_picture": "string — context or trend",
        "by_the_numbers": "string or null — vote, dollars, dates; null if none",
        "whats_next": "string — next step or deadline",
        "for_it_summary": "string — who supported and why (plain language)",
        "against_it_summary": "string or null — who opposed and why; null if none"
      },
      "diagram_timeline": "string — valid Mermaid timeline (required on every decisions[] row)",
      "diagram_mindmap": "string — valid Mermaid mindmap (required on every decisions[] row)",
      "diagram_timeline_lines": "array of strings — optional helper lines",
      "diagram_mindmap_lines": "array of strings — optional helper lines"
    }
  ]
}
 
<transcript>
[INSERT TRANSCRIPT HERE]
</transcript>T HERE]
</transcript>