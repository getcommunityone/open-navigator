# Governance Meeting Transcript Deconstruction Prompt

## Objective
Your objective is to deconstruct a governance meeting transcript to expose the underlying logic of its outcomes. Do not provide a chronological summary; instead, pinpoint the specific drivers behind each decision, identify the key actors who steered the debate, and articulate the specific risks or resources at play.

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

- **Person slug rule:** normalize to `person_firstname_lastname_role_jurisdiction` all lowercase underscores no punctuation e.g. `person_jane_doe_council_member_college_place_wa`
- **Organization slug rule:** normalize to `org_shortname_jurisdiction` e.g. `org_goshen_fire_department_ny`
- **Legislation slug rule:** normalize to `leg_type_number_year_jurisdiction` e.g. `leg_ordinance_1042_2022_college_place_wa` — if no official number exists use a short descriptive label e.g. `leg_proposed_budget_fy2012_goshen_fire_ny`
- **Subject slug rule:** a subject is the specific real-world asset, policy, position, parcel, contract, or matter being acted on — distinct from the decision itself. Normalize to `subject_descriptive_name_jurisdiction` all lowercase underscores no punctuation e.g. `subject_fy2012_fire_department_budget_goshen_ny`. The subject slug must represent the underlying matter not the meeting action — the same subject must produce the same slug whether it surfaces in part one or part three of a multi-session meeting or across separate meetings entirely. If a legislation reference anchors the subject bind it via `canonical_leg_id`.

## Theme Classification
Classify each agenda item under a primary theme and at most one secondary theme from this fixed list:

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

## COFOG Mappings
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
Assign the most specific NTEE code determinable from context for organizations. NTEE codes will also be extracted to decision topics based on the primary organizations involved.

| Code | Category |
|---|---|
| A | Arts Culture and Humanities |
| B | Education |
| C | Environment |
| D | Animal-Related |
| E | Health Care |
| F | Mental Health and Crisis Intervention |
| G | Disease and Disorder Research |
| H | Medical Research |
| I | Crime and Legal Services |
| J | Employment |
| K | Food Agriculture and Nutrition |
| L | Housing and Shelter |
| M | Public Safety and Disaster Relief |
| N | Recreation and Sports |
| O | Youth Development |
| P | Human Services |
| Q | International and Foreign Affairs |
| R | Civil Rights and Advocacy |
| S | Community Improvement |
| T | Philanthropy and Grantmaking |
| U | Science and Technology |
| V | Social Science |
| W | Public Policy |
| X | Religion |
| Y | Mutual Benefit |
| Z | Unknown |

## Financial Items
Extract every dollar value mentioned in the transcript into `financial_items` regardless of whether it is tied to a formal vote — include estimates, bids, appropriations, contract values, grants, fees, levy amounts, tax rates, and bond amounts.

## Multi-Session Meetings
If a meeting is one session of a multi-part series record that in `session_info` and use consistent subject slugs across all parts so that items can be joined later.

## Organization Classification
Assign an `org_type` to every organization without exception — do not default to Unknown if context permits a more specific classification. Flag lobbyists explicitly at both the person and organization level where applicable — set `is_lobbyist` to false and `lobbyist_clients` to empty array for all others. Record party affiliation for elected officials and political organizations where stated or publicly determinable — set to Nonpartisan or Unknown where not applicable.

## Voting
Formal votes may not exist in all meeting types — if a decision is made by consensus, acclamation, or directive rather than recorded vote set `vote_tally` fields to null and note the decision method in `decision_statement`.

---

## Output Instructions

Produce three documents in sequence. Follow the step instructions exactly.

### STEP 1 — JSON
Output the JSON object below and nothing else until you have closed the final curly brace of the root object. Do not include any text, labels, comments, or markdown outside the JSON structure itself. The JSON must be parseable by `JSON.parse()` with no modification. After the closing curly brace output exactly this token on its own line with no surrounding text:

`---DOCUMENT_BREAK---`

### STEP 2 — Human-Readable Summary
After the first break token output a human-readable document that transforms the JSON into a narrative format optimized for human comprehension. Apply Smart Brevity principles throughout. Structure the document as follows:

**Meeting Overview**
- Meeting identification (body name, type, date, location)
- Attendance summary
- Session context if multi-part

**Key Decisions** (one section per decision)
For each decision provide:
- **Topic headline** (from decision.headline field)
- **Outcome:** [APPROVED/DENIED/etc] via [decision method]
- **Vote:** [if formal vote, summarize tally and note dissenting members]
- **What happened:** [synthesis of decision_statement and timeline.this_meeting]
- **Why it matters:** [synthesis of underlying_causes and tradeoffs]
- **Who influenced it:** [synthesis of power_map and arguments_for/against, explicitly noting lobbyist involvement where present]
- **Frame analysis:**
  - **Dominant frame:** [synthesis of frame_analysis.dominant_frame]
  - **Counter-frames:** [synthesis of frame_analysis.counter_frames]
  - **Causal contest:** [synthesis of frame_analysis.causal_frames showing competing diagnoses]
  - **Value conflict:** [synthesis of frame_analysis.moral_frames showing underlying tensions]
  - **Winners and losers:** [synthesis of frame_analysis.tradeoff_frames showing who gains/loses]
- **What's unresolved:** [list unresolved items if any]
- **Financial impact:** [summarize linked financial_items if any]
- **Next steps:** [from timeline.next_steps if present]

**Financial Summary**
Table or list of all financial items with amount, type, and context

**People and Organizations**
Bullet list of key actors grouped by role with party affiliation and lobbyist status clearly marked

**Themes**
Summary of primary themes addressed with COFOG codes

Format all dollar amounts with commas and currency symbols. Use bold for section headers and key terms. Keep each section concise — front-load the most important information. After the final section output exactly this token on its own line with no surrounding text:

`---DOCUMENT_BREAK---`

### STEP 3 — Mermaid Timeline
After the second break token output only a valid Mermaid timeline block. Do not include any text before or after the timeline block. Do not wrap it in markdown fences. Begin directly with the word `timeline` on its own line. Represent each decision and significant event in the order it occurred. Always quote clock times e.g. `"09:00"` or `"14:30"`. Use exactly one colon per entry. Where no timestamp exists use the decision_id sequence to order entries and label entries with the `topic` field from the decision. Group entries under Mermaid timeline section headers by primary theme where three or more decisions share a theme. Output nothing after the final line of the timeline.

---

## JSON Schema

```json
{
  "meeting": {
    "meeting_id": "string — derive from body name + date + session if multi-part e.g. GOSHEN_FIRE_BUDGET_2011-10-19_PT2",
    "body_name": "string",
    "body_type": "one of: Municipal Council, County Commission, Fire District, School Board, Planning Board, Utility Authority, Special District, State Legislature, Federal Body, Tribal Council, Quasi-Governmental, Unknown",
    "meeting_type": "one of: Regular Session, Budget Hearing, Public Hearing, Special Session, Work Session, Committee Meeting, Emergency Session, Unknown",
    "meeting_date": "YYYY-MM-DD",
    "meeting_start_time": "HH:MM 24hr or null",
    "meeting_end_time": "HH:MM 24hr or null",
    "location": "string or null",
    "quorum_present": "boolean or null",
    "members_present": ["string"],
    "members_absent": ["string"],
    "source_url": "string or null",
    "producer": "string or null",
    "jurisdiction": "string",
    "jurisdiction_type": "one of: Municipal, County, State, Federal, Special District, Fire District, School District, Unknown",
    "population": "integer or null",
    "session_info": {
      "is_multi_session": "boolean",
      "session_number": "integer or null",
      "total_sessions": "integer or null",
      "series_id": "string or null"
    }
  },
  "people": [
    {
      "person_id": "string — normalized slug",
      "full_name": "string",
      "role": "string",
      "org_id": "string or null",
      "party_affiliation": "string",
      "is_lobbyist": "boolean",
      "lobbyist_registration_number": "string or null",
      "lobbyist_clients": [],
      "wikidata_qid": "string or null",
      "appeared_as": "one of: Decision Maker, Staff, Department Head, Legal Counsel, Public Commenter, Advocate, Lobbyist, Expert Witness, Referenced Only"
    }
  ],
  "organizations": [
    {
      "org_id": "string — normalized slug",
      "org_name": "string",
      "org_type": "one of: Government Body, Fire District, School District, Nonprofit 501c3, Nonprofit 501c4, Foundation, Private Company, Public Agency, Advocacy Group, Lobbying Firm, Law Firm, Labor Union, Trade Association, Faith-Based, Educational Institution, Healthcare System, Political Party, PAC, Media, Individual, Unknown",
      "org_subtype": "string or null",
      "is_lobbyist_entity": "boolean",
      "lobbying_clients": [],
      "party_affiliation": "string or null",
      "ein": "string or null",
      "wikidata_qid": "string or null",
      "ntee_major_group": "string or null",
      "ntee_category_label": "string or null",
      "ntee_code": "string or null",
      "role_in_meeting": "string — Smart Brevity headline",
      "financial_interest": "string or null"
    }
  ],
  "legislation": [
    {
      "leg_id": "string — normalized slug",
      "leg_type": "one of: Ordinance, Resolution, Budget Proposal, Statute, Regulation, Federal Law, State Law, Municipal Code, Local Law, Executive Order, Policy, Unknown",
      "official_number": "string or null",
      "title": "string or null",
      "jurisdiction": "string",
      "year": "integer or null",
      "status": "one of: Proposed, Active, Amended, Repealed, Referenced Only",
      "relevance": "string — Smart Brevity headline",
      "url": "string or null"
    }
  ],
  "financial_items": [
    {
      "financial_item_id": "string — sequential e.g. FIN001",
      "decision_id": "string or null",
      "subject_id": "string or null",
      "event_description": "string — Smart Brevity headline",
      "item_description": "string",
      "amount": 0,
      "amount_type": "one of: Appropriation, Expenditure, Contract Award, Grant, Loan, Bond, Fee, Fine, Tax, Levy, Reimbursement, Estimate, Bid, Budget Allocation, Budget Request, Capital Outlay, Personnel Cost, Other",
      "amount_qualifier": "one of: Exact, Approximate, Maximum, Minimum, Proposed, Amended, Unknown",
      "currency": "USD",
      "item_date": "YYYY-MM-DD or null",
      "item_date_type": "string or null",
      "org_id": "string — must match an org_id",
      "org_role": "string or null",
      "authorized_by_person_id": "string or null",
      "funding_source": "string or null",
      "notes": "string or null"
    }
  ],
  "subjects": [
    {
      "subject_id": "string — normalized slug",
      "subject_label": "string",
      "subject_description": "string",
      "subject_type": "one of: Physical Asset, Policy or Ordinance, Budget Line, Land Parcel, Contract or Agreement, Position or Personnel, Program or Service, Financial Matter, Regulatory Matter, Equipment Purchase, Unknown",
      "jurisdiction": "string",
      "canonical_leg_id": "string or null",
      "canonical_official_number": "string or null",
      "parcel_id": "string or null",
      "external_url": "string or null",
      "first_seen_meeting_id": "string",
      "subject_status": "one of: Active, Resolved, Deferred, Recurring, Unknown"
    }
  ],
  "decisions": [
    {
      "decision_id": "string — sequential e.g. D001",
      "subject_id": "string — must match a subject_id",
      "agenda_item": "string or null",
      "timestamp_start": "HH:MM or null",
      "timestamp_end": "HH:MM or null",
      "decision_date": "YYYY-MM-DD",
      "topic": "string — 6 words or fewer",
      "headline": "string — Smart Brevity lead",
      "decision_statement": "string",
      "decision_method": "one of: Formal Vote, Consensus, Acclamation, Directive, Motion Failed, No Action, Discussion Only",
      "lineage_type": "one of: ORIGINATION | CONTINUATION | AMENDMENT | REVERSAL | CLOSURE | UNKNOWN",
      "lineage_note": "string or null",
      "primary_theme": "string",
      "primary_theme_cofog": "string",
      "secondary_theme": "string or null",
      "secondary_theme_cofog": "string or null",
      "ntee_code": "string or null — extracted from primary organization involved",
      "ntee_major_group": "string or null — extracted from primary organization involved",
      "ntee_category_label": "string or null — extracted from primary organization involved",
      "primary_org_ids": ["string — org_id values of main organizations this decision affects or involves"],
      "legislation_refs": [],
      "financial_item_refs": [],
      "outcome": "one of: APPROVED | DENIED | DEFERRED | TABLED | NO_ACTION | DISCUSSED_ONLY",
      "vote_tally": {
        "yes": null,
        "no": null,
        "abstain": null,
        "yes_members": [],
        "no_members": [],
        "abstain_members": []
      },
      "timeline": {
        "prior_context": "string — Smart Brevity: headline then detail",
        "this_meeting": "string — Smart Brevity: headline then detail",
        "next_steps": "string or null"
      },
      "arguments_for": [
        {
          "person_id": "string or null",
          "org_id": "string or null",
          "stakeholder_role": "string",
          "is_lobbyist": false,
          "headline": "string — 10 words or fewer",
          "rationale": "string"
        }
      ],
      "arguments_against": [
        {
          "person_id": "string or null",
          "org_id": "string or null",
          "stakeholder_role": "string",
          "is_lobbyist": false,
          "headline": "string — 10 words or fewer",
          "rationale": "string"
        }
      ],
      "tradeoffs": [
        {
          "headline": "string — 6 words or fewer",
          "detail": "string"
        }
      ],
      "underlying_causes": [
        {
          "headline": "string — 8 words or fewer",
          "detail": "string"
        }
      ],
      "power_map": {
        "formal_authority": [],
        "influence": [],
        "lobbyist_influence": [],
        "affected_not_present": []
      },
      "unresolved": [
        {
          "headline": "string — 8 words or fewer",
          "detail": "string"
        }
      ],
      "direct_quotes": [
        {
          "person_id": "string or null",
          "quote": "string"
        }
      ],
      "frame_analysis": {
        "dominant_frame": {
          "frame_label": "string — 4-6 words identifying the frame",
          "problem_diagnosis": "string — Smart Brevity: how is the problem defined",
          "causal_story": "string — Smart Brevity: what caused this problem",
          "blame_assignment": "string — who or what is blamed",
          "moral_foundation": "string — underlying value (safety, liberty, fairness, etc.)",
          "proposed_remedy": "string — what solution follows from this frame",
          "whose_interests_advanced": ["string"],
          "frame_sponsors": ["string — person_id or org_id"]
        },
        "counter_frames": [
          {
            "frame_label": "string — 4-6 words identifying the frame",
            "problem_diagnosis": "string — Smart Brevity: how opponents define the problem",
            "causal_story": "string — Smart Brevity: opponents' causal explanation",
            "blame_assignment": "string — who or what opponents blame",
            "moral_foundation": "string — underlying value (liberty, autonomy, efficiency, etc.)",
            "proposed_remedy": "string or null — alternative solution if articulated",
            "whose_interests_constrained": ["string"],
            "frame_sponsors": ["string — person_id or org_id"]
          }
        ],
        "causal_frames": [
          {
            "causal_interpretation": "string — headline format: X caused Y",
            "evidence_cited": "string or null",
            "sponsored_by": ["string — person_id or org_id"],
            "accepted_or_rejected": "one of: Accepted by majority, Rejected by majority, Contested without resolution"
          }
        ],
        "moral_frames": [
          {
            "value_tension": "string — format: X vs Y (e.g., collective safety vs individual liberty)",
            "proponent_priority": "string — which value proponents prioritize",
            "opponent_priority": "string — which value opponents prioritize",
            "resolution_method": "string — how was the value conflict resolved or deferred"
          }
        ],
        "tradeoff_frames": [
          {
            "tradeoff_statement": "string — format: Advancing X by constraining Y",
            "interests_advanced": ["string — person_id, org_id, or stakeholder group"],
            "interests_constrained": ["string — person_id, org_id, or stakeholder group"],
            "acknowledged_explicitly": "boolean — was this tradeoff named in debate",
            "mitigation_proposed": "string or null"
          }
        ],
        "frame_stability": {
          "frame_novelty": "one of: New frame introduced, Extension of prior frame, Continuation of established frame, Frame reversal, Unknown",
          "prior_frame_reference": "string or null — reference to earlier meeting or decision if applicable",
          "narrative_durability": "string — does this decision lock in a dominant frame for future policy",
          "frame_evolution_note": "string or null — how the frame has shifted over time if multi-session"
        }
      }
    }
  ]
}
```

---

## Enforcement Rules

### Field Requirements
- Every field must be populated or explicitly set to null — do not omit fields
- Do not flatten disagreements — preserve conflict in `arguments_against` and `unresolved`
- Each `decision_id` must be unique within the document

### Cross-Reference and Linking Rules
- Every decision must carry a `subject_id` as its primary cross-meeting and cross-session link
- For multi-part meetings use the same subject slug in every session so items can be joined across parts
- All cross-references must resolve — `person_id`, `org_id`, `leg_id`, `subject_id`, `financial_item_id`, and `decision_id` must each match a real entry in their respective arrays
- Normalized slugs must be deterministic — the same real-world entity must always yield the same slug regardless of how it is referenced in the transcript or across sessions

### Lineage Type Assignment
Assign `lineage_type` as:
- **ORIGINATION** for first appearance of a subject
- **CONTINUATION** if previously discussed without resolution
- **AMENDMENT** if modifying a prior decision
- **REVERSAL** if overturning a prior decision
- **CLOSURE** if resolving the matter

### Voting Rules
- If no formal vote occurred set all `vote_tally` fields to null and record `decision_method` accurately
- All `vote_tally` member arrays must use `person_id` values not display names

### Lobbyist and Organization Classification
- `is_lobbyist` in `arguments_for` and `arguments_against` must be true only if the person is registered as a lobbyist or appearing on behalf of a paying client — default to false otherwise
- `org_type` must reflect the most specific classification context permits — do not default to Unknown if context permits a more specific classification

### NTEE Classification Rules
- For every organization in the `organizations` array, populate all three NTEE fields (`ntee_major_group`, `ntee_category_label`, `ntee_code`) when context permits — do not leave these null if the organization's cause area is determinable
- For subcategories, use hierarchical notation with greater-than separator (e.g., "Health > Dental & Oral Health", "Food Agriculture and Nutrition > Food Banks, Food Pantries")
- If only the major group is determinable, set `ntee_category_label` equal to `ntee_major_group`
- **Extract NTEE to decisions:** For each decision, populate `primary_org_ids` with the main organizations affected or involved, then copy the NTEE fields (`ntee_code`, `ntee_major_group`, `ntee_category_label`) from the primary organization to the decision object
- If a decision involves multiple organizations with different NTEE codes, use the organization most central to the decision's outcome
- **When no organizations are involved:** If a decision has no organization references but the topic clearly relates to a specific cause area (health, education, environment, etc.), infer the most appropriate NTEE code from the topic and theme. For general governance/administrative topics with no specific cause area, use W (Public Policy)
- Set decision-level NTEE fields to null only when the cause area is genuinely indeterminate from context

### Underlying Causes Rules
- Make `underlying_causes` headlines specific and contextual — avoid generic abstractions like "Aging infrastructure" or "Statutory requirement"
- Root causes must explain WHY the decision was necessary not merely describe the category — e.g., prefer "Fire station roof leaking after 40 years" over "Aging infrastructure" or "State audit found gaps in payment records" over "Statutory requirement"
- Each underlying cause should be independently verifiable from the transcript — do not infer causes that were not discussed
- Capture competing diagnoses of causality in `frame_analysis.causal_frames` when stakeholders disagree on root causes

### Frame Analysis Rules
- Every decision must include a `frame_analysis` object — do not omit this field
- Extract at minimum one dominant frame and one counter-frame where opposition exists
- `causal_frames` must capture competing diagnoses of causality not just outcomes
- `moral_frames` must surface value tensions even when not explicitly named
- `tradeoff_frames` must identify whose interests are advanced and constrained as normative choices
- Counter-frames must extract problem/cause/remedy from opponents' perspective not merely record opposition
- `frame_stability` must assess whether this decision establishes or extends a narrative arc
- When no counter-frame is articulated (unanimous consent, no debate) set `counter_frames` to empty array and note in `frame_stability.narrative_durability`

### URL and External References
- Where an official legislation or municipal code URL is determinable from context include it in the `url` field

### Timeline Requirements (Document 3)
- Represent each decision and significant event in the order it occurred
- Always quote clock times e.g. `"09:00"` or `"14:30"`
- Use exactly one colon per entry
- Where no timestamp exists use the `decision_id` sequence to order entries and label entries with the `topic` field from the decision
- Group entries under Mermaid timeline section headers by primary theme where three or more decisions share a theme

### Output Format Requirements
- **Document 1 (JSON)** must be parseable by `JSON.parse()` with no modification
- Output the three documents separated by `---DOCUMENT_BREAK---` with no other text outside the documents
- No markdown code fences around the JSON in Document 1
- No markdown code fences around the Mermaid timeline in Document 3