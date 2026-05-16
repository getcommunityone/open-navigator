## Governance Meeting Transcript Deconstruction Prompt

## Objective
Your objective is to deconstruct a governance meeting transcript to expose the underlying logic of its outcomes. Do not provide a chronological summary; instead, pinpoint the specific drivers behind each decision, identify the key actors who steered the debate, and articulate the specific risks or resources at play.

**Competing Interpretations Requirements:**
For each decision, extract and contrast the rival ways stakeholders defined the problem — how they diagnosed its cause, assigned responsibility, proposed solutions, and ranked moral values. This analysis must explicitly capture:
- **Competing causal interpretations** (individual behavior vs system capacity, biology vs policy failure, etc.)
- **Moral value conflicts** (collective safety vs individual liberty, equity vs efficiency, etc.)
- **Normative tradeoffs** (whose interests are advanced, whose are constrained, which harms are accepted)
- **Dissenting diagnosis** (how opponents defined the problem, its cause, and what they proposed instead)
- **Staying power of the prevailing interpretation** (is this a new way of seeing the problem or an extension of prior ones, does it lock in a dominant narrative)

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

## Location and Postal Code Extraction
For each decision, extract the 5-digit ZIP code (postal_code), county FIPS code (county_fips), and county name (county) of the city or location associated with that decision. Determine these based on:
- The meeting location if the decision applies to that specific area
- The subject location if the decision pertains to a specific address, facility, parcel, or geographic area
- The jurisdiction's primary location if the decision is jurisdiction-wide
- Set to null if the location cannot be determined or if the decision applies to multiple locations

Priority order: specific subject location > meeting location > jurisdiction primary location. If a decision involves multiple distinct locations, use the primary location where the decision has the greatest impact.

**County extraction:** Based on the city name associated with the decision, determine:
- `county_fips`: The 5-digit FIPS code for the county (state FIPS + county FIPS, e.g., "01097" for Mobile County, Alabama)
- `county`: The full county name (e.g., "Mobile County", "Suffolk County", "Cook County")
- Use standard U.S. county naming conventions with "County" suffix (exceptions: Louisiana parishes use "Parish", Alaska boroughs use "Borough")
- Set to null only if the county cannot be determined from the city name or jurisdiction

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

## Mermaid Diagram Generation Rules

### Decision Timeline (diagram_timeline)
For each decision, generate a Mermaid timeline showing the chronological progression of that specific decision across meetings. Format as a valid Mermaid timeline string:
- Include `timeline` keyword at start
- Use timeline sections if the decision spans multiple meetings
- Quote all timestamps: `"09:00"`, `"14:30"`
- Use exactly one colon per entry
- Show: prior context → this meeting's action → next steps
- Keep entries concise (10 words or fewer per entry)
- Example format:
```
timeline
    title Budget Proposal FY2012
    section Prior Meetings
        "2011-09-15" : Initial budget draft presented
        "2011-10-05" : Public hearing held
    section This Meeting
        "09:00" : Final budget vote
        "09:45" : Amendments approved
    section Next Steps
        "2011-11-01" : Implementation begins
```

### Decision Mindmap (diagram_mindmap)
For each decision, generate a Mermaid mindmap showing the decision structure, stakeholders, and key relationships. Format as a valid Mermaid mindmap string:
- Include `mindmap` keyword at start
- Root node: decision topic
- Branch 1: Outcome and vote
- Branch 2: Key arguments (for/against)
- Branch 3: Stakeholders (decision makers, advocates, affected parties)
- Branch 4: Financial impacts if present
- Use indentation to show hierarchy (2 spaces per level)
- Keep node text concise (5-7 words max)
- Example format:
```
mindmap
  root((FY2012 Budget))
    Outcome
      APPROVED 4-1
      $2.1M total
    Arguments
      For
        Addresses critical needs
        Stays within levy cap
      Against
        Too high for recession
    Stakeholders
      Decision Makers
        Board voted 4-1
      Advocates
        Fire Chief supported
      Public
        3 residents opposed
    Financial
      $2.1M appropriation
      $50K contingency
```

## Output Instructions

Produce two documents in sequence. Follow the step instructions exactly.

### STEP 1 — JSON
Output the JSON object below and nothing else until you have closed the final curly brace of the root object. Do not include any text, labels, comments, or markdown outside the JSON structure itself. The JSON must be parseable by `JSON.parse()` with no modification.

**CRITICAL:** For each decision in the `decisions` array, populate both `diagram_timeline` and `diagram_mindmap` fields with valid Mermaid syntax strings following the rules above. These strings must be escaped for JSON (use `\n` for newlines, escape quotes). After the closing curly brace output exactly this token on its own line with no surrounding text:

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
- **Location:** [city name, county name if present, postal_code if present, or "jurisdiction-wide"]
- **Outcome:** [APPROVED/DENIED/etc] via [decision method]
- **Vote:** [if formal vote, summarize tally and note dissenting members]
- **What happened:** [synthesis of decision_statement and timeline.this_meeting]
- **Why it matters:** [synthesis of underlying_causes and tradeoffs]
- **Who influenced it:** [synthesis of power_map and arguments_for/against, explicitly noting lobbyist involvement where present]
- **How the problem was defined:**
  - **Prevailing interpretation:** [synthesis of narrative_analysis.dominant_narrative]
  - **Dissenting interpretations:** [synthesis of narrative_analysis.dissenting_interpretations]
  - **Competing explanations:** [synthesis of narrative_analysis.causal_interpretations showing rival diagnoses]
  - **Value conflict:** [synthesis of narrative_analysis.value_conflicts showing underlying tensions]
  - **Winners and losers:** [synthesis of narrative_analysis.tradeoff_analysis showing who gains/loses]
- **What was considered but rejected:** [from alternatives_considered if any]
- **Downstream effects:** [from consequences — immediate, medium, long-term]
- **Prior decisions this builds on:** [from precedents if any]
- **What must happen next for this to work:** [from dependencies if any]
- **What's unresolved:** [list unresolved items if any]
- **Financial impact:** [summarize linked financial_items if any]
- **Next steps:** [from timeline.next_steps if present]

**Financial Summary**
Table or list of all financial items with amount, type, and context

**People and Organizations**
Bullet list of key actors grouped by role with party affiliation and lobbyist status clearly marked

**Themes**
Summary of primary themes addressed with COFOG codes

Format all dollar amounts with commas and currency symbols. Use bold for section headers and key terms. Keep each section concise — front-load the most important information.

This is the final output — no additional document breaks or timeline sections follow.

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
      "postal_code": "string or null — 5-digit ZIP code of the city/location associated with this decision",
      "county_fips": "string or null — 5-digit FIPS code for the county associated with this decision",
      "county": "string or null — full county name e.g. 'Mobile County', 'Suffolk County'",
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
      "ntee_code": "string or null — primary cause area based on topic content analysis",
      "ntee_major_group": "string or null",
      "ntee_category_label": "string or null",
      "ntee_assignment_basis": "one of: Topic Content, Organization Fallback, Administrative — records why this NTEE code was chosen",
      "secondary_ntee_code": "string or null",
      "secondary_ntee_major_group": "string or null",
      "secondary_ntee_category_label": "string or null",
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
          "stakeholder_role": "one of: Decision Maker, Staff, Advocate, Lobbyist, Expert, Resident, Media, Referenced Only",
          "is_lobbyist": false,
          "headline": "string — 10 words or fewer",
          "rationale": "string"
        }
      ],
      "arguments_against": [
        {
          "person_id": "string or null",
          "org_id": "string or null",
          "stakeholder_role": "one of: Decision Maker, Staff, Advocate, Lobbyist, Expert, Resident, Media, Referenced Only",
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
          "cause_type": "one of: Structural, Proximate, Political, Resource, Legal, Crisis, Demand — Structural: long-term systemic conditions; Proximate: the immediate trigger; Political: who pushed for this and why; Resource: capacity or funding gap; Legal: mandate, statute, or liability; Crisis: acute emergency; Demand: public or stakeholder pressure",
          "headline": "string — 8 words or fewer, specific and contextual not generic",
          "detail": "string",
          "contested": "boolean — true if any party disputed this as the cause"
        }
      ],
      "alternatives_considered": [
        {
          "alternative_label": "string — 6 words or fewer",
          "description": "string — Smart Brevity: what was proposed and by whom",
          "rejected_by": ["string — person_id or org_id"],
          "rejection_rationale": "string",
          "rival_diagnosis_used_to_reject": "string or null — if opponents reframed the problem to defeat this alternative, describe how"
        }
      ],
      "consequences": {
        "immediate": [
          {
            "headline": "string — 8 words or fewer",
            "detail": "string",
            "affected_parties": ["string — person_id, org_id, or stakeholder group"],
            "certainty": "one of: Certain, Probable, Possible, Speculative"
          }
        ],
        "medium_term": [
          {
            "headline": "string — 8 words or fewer",
            "detail": "string",
            "affected_parties": ["string"],
            "certainty": "one of: Certain, Probable, Possible, Speculative"
          }
        ],
        "long_term": [
          {
            "headline": "string — 8 words or fewer",
            "detail": "string",
            "affected_parties": ["string"],
            "certainty": "one of: Certain, Probable, Possible, Speculative"
          }
        ]
      },
      "precedents": [
        {
          "precedent_type": "one of: Analogical, Statutory, Procedural, Political",
          "reference_label": "string — 6 words or fewer describing the prior case or decision",
          "decision_id_ref": "string or null — links to prior decision if in dataset",
          "external_ref": "string or null — citation to external case, law, or meeting",
          "invoked_by": ["string — person_id or org_id"],
          "how_used": "one of: To justify, To distinguish, To caution against, To establish baseline"
        }
      ],
      "dependencies": [
        {
          "dependency_type": "one of: Funding, Legal, Political, Operational, Intergovernmental",
          "description": "string — Smart Brevity: what must happen for this decision to take effect",
          "dependent_on": "string — the specific condition, action, or decision required",
          "owner": "string or null — person_id or org_id responsible for resolving it",
          "deadline": "YYYY-MM-DD or null",
          "risk_if_unmet": "string or null"
        }
      ],
      "power_map": {
        "formal_authority": [
          {
            "person_id_or_org_id": "string",
            "influence_intensity": "one of: Decisive, Significant, Marginal"
          }
        ],
        "influence": [
          {
            "person_id_or_org_id": "string",
            "influence_intensity": "one of: Decisive, Significant, Marginal"
          }
        ],
        "lobbyist_influence": [
          {
            "person_id_or_org_id": "string",
            "influence_intensity": "one of: Decisive, Significant, Marginal"
          }
        ],
        "affected_not_present": ["string — person_id, org_id, or stakeholder group"]
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
      "diagram_timeline": "string — valid Mermaid timeline syntax, newlines escaped as \\n for JSON",
      "diagram_mindmap": "string — valid Mermaid mindmap syntax, newlines escaped as \\n for JSON",
      "narrative_analysis": {
        "dominant_narrative": {
          "narrative_label": "string — 4-6 words identifying how the prevailing side defined the problem",
          "problem_diagnosis": "string — Smart Brevity: how is the problem defined by those who won the argument",
          "causal_story": "string — Smart Brevity: what they said caused this problem",
          "blame_assignment": "string — who or what is blamed",
          "moral_foundation": "string — underlying value (safety, liberty, fairness, fiscal responsibility, etc.)",
          "proposed_remedy": "string — what solution follows from this way of seeing the problem",
          "whose_interests_advanced": ["string — person_id, org_id, or stakeholder group"],
          "narrative_champions": ["string — person_id or org_id who pushed this interpretation"]
        },
        "dissenting_interpretations": [
          {
            "narrative_label": "string — 4-6 words identifying how opponents defined the problem",
            "problem_diagnosis": "string — Smart Brevity: how opponents defined the problem differently",
            "causal_story": "string — Smart Brevity: opponents' explanation of what caused this",
            "blame_assignment": "string — who or what opponents blamed",
            "moral_foundation": "string — underlying value opponents prioritized (liberty, autonomy, efficiency, etc.)",
            "proposed_remedy": "string or null — the alternative solution opponents argued for, if articulated",
            "whose_interests_constrained": ["string — person_id, org_id, or stakeholder group"],
            "narrative_champions": ["string — person_id or org_id who pushed this rival interpretation"]
          }
        ],
        "causal_interpretations": [
          {
            "causal_interpretation": "string — headline format: X caused Y",
            "evidence_cited": "string or null",
            "sponsored_by": ["string — person_id or org_id"],
            "accepted_or_rejected": "one of: Accepted by majority, Rejected by majority, Contested without resolution"
          }
        ],
        "value_conflicts": [
          {
            "value_tension": "string — format: X vs Y (e.g., collective safety vs individual liberty)",
            "proponent_priority": "string — which value the winning side prioritized",
            "opponent_priority": "string — which value the losing side prioritized",
            "resolution_method": "string — how was the value conflict resolved, deferred, or left unaddressed"
          }
        ],
        "tradeoff_analysis": [
          {
            "tradeoff_statement": "string — format: Advancing X by constraining Y",
            "interests_advanced": ["string — person_id, org_id, or stakeholder group"],
            "interests_constrained": ["string — person_id, org_id, or stakeholder group"],
            "acknowledged_explicitly": "boolean — was this tradeoff named openly in debate",
            "mitigation_proposed": "string or null"
          }
        ],
        "narrative_stability": {
          "narrative_novelty": "one of: New interpretation introduced, Extension of prior interpretation, Continuation of established narrative, Narrative reversal, Unknown",
          "prior_narrative_reference": "string or null — reference to earlier meeting or decision where this way of seeing the problem first appeared",
          "narrative_durability": {
            "locks_in_narrative": "boolean — does this decision make it harder to challenge the prevailing interpretation in future meetings",
            "durability_assessment": "string — Smart Brevity explanation of why or why not",
            "future_decisions_constrained": ["string — topic areas or subject slugs whose framing is now pre-determined by this decision"]
          },
          "narrative_evolution_note": "string or null — how the prevailing interpretation has shifted over time if multi-session"
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
- **Extract NTEE to decisions — CRITICAL HIERARCHY:**
  1. **First priority: Topic content analysis** — Analyze the decision topic, headline, and primary theme to determine if it relates to a specific cause area (health, education, environment, human services, youth, arts, etc.). Record basis as `"Topic Content"`.
  2. **Secondary NTEE codes** — If a topic spans multiple cause areas, assign a secondary NTEE code. For example: "School dental screening program" → Primary: E (Health Care > Dental & Oral Health), Secondary: B (Education)
  3. **Organization classification fallback** — If the topic is truly general administrative/governance (approving minutes, routine procedures), use the primary organization's NTEE code. Record basis as `"Organization Fallback"`.
  4. **Last resort: Public Policy (W)** — Only use "W - Public Policy" for purely procedural/administrative topics with no substantive cause area. Record basis as `"Administrative"`.
- **Examples of topic-based NTEE assignment (override organization's W code):**
  - "Youth program funding" → Primary: O (Youth Development), Secondary: null
  - "School lunch program" → Primary: K (Food Agriculture and Nutrition), Secondary: B (Education)
  - "Recycling education campaign" → Primary: C (Environment), Secondary: B (Education)
  - "Senior center renovation" → Primary: P (Human Services), Secondary: null
  - "Public health emergency" → Primary: E (Health Care), Secondary: M (Public Safety and Disaster Relief)
  - "Arts festival approval" → Primary: A (Arts Culture and Humanities), Secondary: null
  - "Disability awareness proclamation" → Primary: R (Civil Rights and Advocacy), Secondary: P (Human Services)
  - "Youth sports facility" → Primary: O (Youth Development), Secondary: N (Recreation and Sports)
- **Examples of truly Public Policy (W) topics:**
  - "Approve meeting minutes" → Primary: W (Administrative), Secondary: null
  - "Adopt council rules" → Primary: W (Administrative), Secondary: null
  - "Budget process timeline" → Primary: W (Administrative), Secondary: null
- When a decision involves multiple organizations with different NTEE codes, select the primary NTEE based on the most central organization
- Set decision-level NTEE fields to null only when the cause area is genuinely indeterminate from context
- **Always prioritize substantive cause areas (A-V, X-Y) over Public Policy (W)** — W should be the exception, not the default

### Underlying Causes Rules
- Make `underlying_causes` headlines specific and contextual — avoid generic abstractions like "Aging infrastructure" or "Statutory requirement"
- Root causes must explain WHY the decision was necessary not merely describe the category — e.g., prefer "Fire station roof leaking after 40 years" over "Aging infrastructure" or "State audit found gaps in payment records" over "Statutory requirement"
- Each underlying cause should be independently verifiable from the transcript — do not infer causes that were not discussed
- Assign a `cause_type` to every underlying cause using the controlled vocabulary: Structural, Proximate, Political, Resource, Legal, Crisis, or Demand
- Mark `contested: true` for any cause that was disputed by any party — these must also appear as competing entries in `narrative_analysis.causal_interpretations`
- Capture competing diagnoses of causality in `narrative_analysis.causal_interpretations` when stakeholders disagreed on root causes

### Alternatives Considered Rules
- Populate `alternatives_considered` whenever the transcript shows that another path was discussed, proposed, or implicitly rejected — even if briefly
- `rival_diagnosis_used_to_reject` captures the argumentative move where opponents redefined the problem to make an alternative seem irrelevant or harmful — this is the primary mechanism by which competing interpretations suppress options

### Consequences Rules
- Populate all three time horizons (`immediate`, `medium_term`, `long_term`) when effects were discussed or are clearly implied
- Use `certainty` to distinguish commitments from predictions: Certain = written into the decision; Probable = reasonably expected given stated plans; Possible = plausible but conditional; Speculative = asserted by one party without corroboration
- `affected_parties` must name specific person_ids, org_ids, or stakeholder groups — not generic categories like "the public"

### Precedents Rules
- Populate `precedents` whenever a prior decision, case, statute, or practice was cited — explicitly or implicitly — to justify or oppose the current decision
- `how_used` distinguishes between invoking a precedent to support an action ("To justify"), to argue this case is different ("To distinguish"), to warn of risks ("To caution against"), or to set a reference point ("To establish baseline")

### Dependencies Rules
- Populate `dependencies` whenever the decision cannot take effect on its own — it requires funding approval, legal authorization, another body's action, or operational steps
- `risk_if_unmet` should be specific: name the consequence of the dependency failing, not just "implementation delayed"

### Power Map Rules
- Every entry in `formal_authority`, `influence`, and `lobbyist_influence` must include an `influence_intensity` rating
- **Decisive**: this actor's position was necessary for the outcome — without them it likely fails
- **Significant**: this actor shaped the terms of debate or moved votes but was not singularly necessary
- **Marginal**: this actor participated but did not materially affect the outcome
- `affected_not_present` remains a flat array — these parties had no voice, so influence intensity is not applicable

### Competing Interpretations Rules
- Every decision must include a `narrative_analysis` object — do not omit this field
- Extract at minimum one dominant narrative and one dissenting interpretation where opposition exists
- `causal_interpretations` must capture competing diagnoses of causality not just competing outcomes
- `value_conflicts` must surface value tensions even when not explicitly named by participants
- `tradeoff_analysis` must identify whose interests are advanced and constrained as conscious choices
- Dissenting interpretations must extract problem/cause/remedy from opponents' perspective — not merely record that opposition existed
- `narrative_stability` must assess whether this decision establishes or extends a narrative arc for future policy on this subject
- When no dissenting interpretation was articulated (unanimous consent, no debate) set `dissenting_interpretations` to empty array and note absence of contest in `narrative_stability.narrative_durability.durability_assessment`

### URL and External References
- Where an official legislation or municipal code URL is determinable from context include it in the `url` field

### Diagram Requirements
- Every decision must include both `diagram_timeline` and `diagram_mindmap` fields
- Timeline must show decision chronology: prior context → this meeting → next steps
- Mindmap must show decision structure: outcome, arguments, stakeholders, financial impacts
- Both diagrams must use valid Mermaid syntax escaped for JSON (newlines as `\n`, quotes escaped)
- Always quote timestamps in timeline diagrams: `"09:00"`, `"14:30"`
- Keep diagram node text concise: 10 words or fewer per entry

### Output Format Requirements
- **Document 1 (JSON)** must be parseable by `JSON.parse()` with no modification
- Output the two documents separated by `---DOCUMENT_BREAK---` with no other text outside the documents
- No markdown code fences around the JSON in Document 1