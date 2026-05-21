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
    * **Not applicable:** Stakeholder group was not present or did not speak.

## Strict Entity & Cross-Query Linking
- Person slug rule: `person_firstname_lastname_role_jurisdiction`
- Organization slug rule: `org_shortname_jurisdiction`
- Legislation slug rule: `leg_type_number_year_jurisdiction`
- Subject slug rule: `subject_descriptive_name_jurisdiction`

## NTEE & COFOG Classification
Assign the most specific NTEE major group code determinable from context for organizations. For decisions, extract NTEE codes based on the primary cause area (e.g., E for Health Care, O for Youth Development). Prioritize substantive cause areas over W (Public Policy) unless it is strictly administrative. Set `primary_theme_cofog` based on the exact Theme labels.

## Output Instructions
Output the JSON object matching the schema below and NOTHING ELSE.

**Before you close the root JSON:** Re-scan all votes. Debated → `decisions[]`; routine/unanimous → `uncontested_items[]`.

**Diagram rules (`decisions[]` only):** Output `diagram_timeline_lines` and `diagram_mindmap_lines` as string arrays (one line per item). **Never** on `uncontested_items[]`.
* **Issue Lifecycle, Not Meeting Clock:** Timelines track the subject/event lifecycle (origins → today's action → next steps), not a minute-by-minute meeting log.
* Time labels must not use quotes (e.g., use `2023-05` or `Next Month`, not `"2023-05"`).
* Preserve indentation using spaces in the string items.

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
    }
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
  "subjects": [
    {
      "subject_id": "string — normalized slug",
      "subject_label": "string",
      "subject_description": "string",
      "canonical_leg_id": "string or null"
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
      "legislation_refs": ["string — leg_id slugs, often empty"],
      "primary_theme": "string or null — short theme label only"
    }
  ],
  "decisions": [
    {
      "decision_id": "string — sequential e.g. D001 (contested items only)",
      "subject_id": "string — must match a subject_id",
      "legislation_refs": ["string — must match a leg_id"],
      "financial_item_refs": ["string — must match a financial_item_id"],
      "headline": "string — Smart Brevity lead",
      "decision_statement": "string",
      "primary_theme": "string",
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
          "proposed_remedy": "string"
        },
        "counter_views": [
          {
            "view_label": "string",
            "problem_diagnosis": "string",
            "causal_story": "string"
          }
        ]
      },
      "diagram_timeline_lines": "array of strings — required on every decisions[] row",
      "diagram_mindmap_lines": "array of strings — required on every decisions[] row"
    }
  ]
}

<transcript>
[INSERT TRANSCRIPT HERE]
</transcript>