# Governance Meeting Transcript Deconstruction Prompt

## Objective
Your objective is to deconstruct a governance meeting transcript to expose the underlying logic of its outcomes. Do not provide a chronological summary; instead, pinpoint the specific drivers behind each decision, identify the key actors who steered the debate, and articulate the specific risks or resources at play.

**Frame Analysis Requirements:**
Extract competing problem frames: how stakeholders diagnose cause, assign blame, and rank values.
- **Causal contest:** Who/what caused this problem—individual failure, system capacity, biology, policy gap?
- **Value conflict:** Collective safety vs individual liberty, equity vs efficiency, harm reduction vs harm tolerance
- **Winners and losers:** Whose interests advance, whose get constrained, which harms get accepted
- **Counter-frames:** How opponents diagnose problem, assign blame, propose remedy
- **Frame durability:** New frame or extension of prior narrative, does it lock in dominance

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
Assign the most specific NTEE code determinable from context.

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
Extract every dollar value mentioned in the transcript regardless of whether it is tied to a formal vote — include estimates, bids, appropriations, contract values, grants, fees, levy amounts, tax rates, and bond amounts.

## Multi-Session Meetings
If a meeting is one session of a multi-part series record that in the session information and use consistent subject slugs across all parts so that items can be joined later.

## Organization Classification
Assign an organization type to every organization without exception — do not default to Unknown if context permits a more specific classification. Flag lobbyists explicitly at both the person and organization level where applicable. Record party affiliation for elected officials and political organizations where stated or publicly determinable — set to Nonpartisan or Unknown where not applicable.

## Voting
Formal votes may not exist in all meeting types — if a decision is made by consensus, acclamation, or directive rather than recorded vote, note the decision method in your analysis.

---

## Output Instructions

Output a single human-readable document optimized for human comprehension. Apply Smart Brevity principles throughout. Structure the document as follows:

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
  - **Dominant frame:** [Problem diagnosis + causal story + moral foundation + whose interests it advances]
  - **Counter-frames:** [Opposition's problem/cause/remedy + moral foundation + whose interests it protects]
  - **Causal contest:** [Competing explanations—what caused this, evidence cited, which won]
  - **Value conflict:** [X vs Y tension, which value won, how conflict was resolved or deferred]
  - **Winners and losers:** [Who gains, who loses, tradeoff acknowledged or hidden, mitigation offered]
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

**Meeting Timeline**

After all other sections, output a Mermaid timeline diagram showing the chronological flow of decisions and events. Wrap it in markdown code fences with the mermaid language identifier. 

**Critical Mermaid timeline syntax rules:**
- Start with `timeline` on its own line
- Use `title Meeting Name – Date` on second line
- Section headers: `section Theme Name` for grouping related events
- Time format: `HHhMM : Event description` (e.g., `19h00 : Meeting called to order`)
- **One colon per line** — separates time from description
- **No quotes on timestamps** — use `19h00` not `"19:00"`
- **Use en-dashes for vote tallies** — `(5–2)` not `(5-2)`
- **Parentheses allowed** for vote counts and clarifications
- Where no timestamp exists, omit the time and use format: `Event description`
- Group entries under section headers by primary theme

**Example valid timeline:**
```
timeline
  title City Council Meeting – January 15, 2024

  section Budget
    19h00 : Meeting called to order
    19h05 : Budget presentation by Finance Director
    19h30 : Public comment period opened
    20h15 : Budget approved (5–2)

  section Zoning
    20h30 : Rezoning request for Main Street presented
    21h00 : Motion to table until next meeting passed

```

**Frame Analysis Mindmap**

After the timeline, output a Mermaid mindmap visualizing the competing frames for the most contested decision. Wrap it in markdown code fences with the mermaid language identifier.

**Critical Mermaid mindmap syntax rules:**
- Start with `mindmap` on its own line
- Root node: `root((Decision Topic))`
- Child nodes: Indent with 2 spaces per level
- Text format: Simple text or `[Square brackets for emphasis]`
- Branch structure:
  - Root → Dominant Frame vs Counter Frame
  - Each frame → Problem, Cause, Values, Solution
  - Include Winners and Losers branches

**Example valid mindmap:**
```
mindmap
  root((COVID Mask Mandate))
    Dominant Frame: Public Health Emergency
      Problem: Rising hospitalizations threaten capacity
      Cause: Insufficient voluntary compliance
      Values: Collective safety over individual choice
      Solution: Indoor mask mandate
      Winners: Vulnerable populations, hospitals
    Counter Frame: Individual Liberty
      Problem: Government overreach
      Cause: Fear-based policymaking
      Values: Personal autonomy over mandates
      Solution: Education and voluntary measures
      Losers: Business owners, civil liberty advocates
```

---

## Content Requirements

### Analysis Requirements
- Do not flatten disagreements — preserve conflict in arguments against and unresolved items
- Each decision must be uniquely identified
- Use consistent entity identifiers across sessions and meetings for cross-referencing
- Distinguish decision lineage (origination, continuation, amendment, reversal, closure)
- Accurately record decision methods (formal vote, consensus, acclamation, directive)
- Flag lobbyists explicitly where applicable — only mark as lobbyist if registered or appearing on behalf of paying client
- Classify organizations specifically — avoid defaulting to Unknown when context permits classification

### Frame Analysis Requirements
- **Mandatory:** Every decision gets frame analysis—no exceptions
- **Minimum:** One dominant frame + one counter-frame (if opposition exists)
- **Causality:** Competing diagnoses of what caused the problem, not just who won
- **Values:** Surface moral tensions even when unstated (safety vs liberty, equity vs efficiency)
- **Power:** Name whose interests advance and whose get constrained—explicit normative stakes
- **Opposition structure:** Extract opponents' full problem/cause/remedy logic, not just "they opposed"
- **Narrative durability:** Does this lock in a frame for future decisions or reverse prior narrative
- **Unanimous votes:** Note absence of counter-frame in stability assessment

### URL and External References
- Where an official legislation or municipal code URL is determinable from context include it in the URL field

### Timeline Requirements
- **Syntax:** Valid Mermaid timeline syntax matching the example format
- **Time format:** `HHhMM : Description` (e.g., `19h00 : Meeting started`)
- **No quotes:** Use `19h00` not `"19:00"`
- **En-dashes:** Use `–` for vote tallies like `(5–2)`
- **Parentheses allowed:** For vote counts and brief clarifications
- **Chronological order:** Events in sequence as they occurred
- **Section grouping:** Use `section Theme Name` headers when 3+ decisions share a primary theme
- **Title required:** Format as `title Body Name – Date`

### Mindmap Requirements
- **Most contested decision:** Choose the decision with strongest opposing frames
- **Root node:** Format as `root((Decision Topic))`
- **Two main branches:** Dominant Frame and Counter Frame
- **Each frame shows:** Problem diagnosis, Causal story, Values prioritized, Proposed solution
- **Stakes visible:** Include Winners and Losers branches
- **Indentation:** 2 spaces per level
- **Clean labels:** Use colons for structure (e.g., `Problem: Rising cases`)

### Output Format Requirements
- Output a single markdown document with all sections in sequence
- Wrap the Mermaid timeline in markdown code fences with `mermaid` language identifier
- Wrap the Mermaid mindmap in markdown code fences with `mermaid` language identifier
- Use proper markdown formatting throughout (bold, lists, tables)