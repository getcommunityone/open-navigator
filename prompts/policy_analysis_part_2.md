## Objective
Write a **Smart Brevity** resident-facing summary from the provided JSON. Spend depth on **contested** items; batch **uncontested** items into one short list.

**Who this is for:** A busy resident on their phone. They should grasp **what happened and why it matters** in seconds — not a court transcript or a generic “the council voted” recap.

## Smart Brevity method (contested items)

For each contested item, lead with **Why it matters** — one bullet that states the thesis (what happened / what’s at stake) and why residents should care. Do **not** use a separate “One Big Thing” line or label.

**Do not use** these labels or frames: `Who won`, `The tension`, `The lede`, `The One Big Thing`, or “The council voted…” openings.

### Document structure
- **Line 1 must be an H1:** `# {body or recording title} — {meeting_date}`. If JSON `meeting.body_name` disagrees with the canonical recording title in the user message, **use the recording title** in the H1.
- **Then exactly three sections** (no other `##` headings):
  1. `## At a glance` — meeting-level context (see template below). **Required on every report.**
  2. `## Contested decisions` — one Smart Brevity block per `decisions[]` row (in order). If zero contested items, one short sentence only (e.g. “There were no contested decisions at this meeting.”).
  3. `## Uncontested actions` — one `-` bullet per `uncontested_items[]` row (in order). If empty, omit this section entirely.
- Plain conversational prose. No NTEE, COFOG, `decision_id`, `item_id`, or schema field names.
- **Contested blocks:** max **180–220 words** each (excluding Mermaid). Tight, not thorough for its own sake.
- **Uncontested bullets:** max **one line** (~25 words): `**[headline]** — [outcome] ([vote]). [one_line_summary]`

### Meeting header (`## At a glance`)

Write **before** contested decisions:

```markdown
## At a glance

**Attendees:** [Comma-separated names grouped by role — e.g. Commissioners: A, B, C; Staff: X, Y. Use `people[]` with `appeared_as` / `role`. Omit empty groups.]

**Summary:** [1–2 sentences: what bodies met, major topics, and overall outcome. Prefer `meeting.meeting_summary` when present; otherwise synthesize from `decisions[]` + `uncontested_items[]` + `meeting.agenda_summary`.]
```

### Mermaid (contested only)
- Include **only** when JSON has non-empty `diagram_timeline` / `diagram_mindmap`.
- Paste those strings **verbatim** into fences (they start with `timeline` / `mindmap`). **Never** `graph TD`, `flowchart`, or bullet lines inside mindmap.
- Omit a diagram subsection if that field is empty.

---

## Contested decision block template (`decisions[]` only)

Use this **exact structure** for each contested item:

### [Strong headline — informative summary, not clickbait]
The headline alone must tell a reader **exactly what happened** (who did what, on what issue, with what result). No vague teases (“Council clash,” “Heated debate”). No question headlines.

* **Why it matters:** [Combine `smart_brevity.one_big_thing` and `smart_brevity.why_it_matters` into **one** bullet — opening thesis sentence, then resident stakes. **Name the site** when `places[]` / `place_refs` apply. **Never** add a separate “The One Big Thing” line.]
* **Where:** [One sentence: full street address, neighborhood or historic district if known, and what is being altered on the parcel. **Required** when JSON lists a `places[]` row or address for this item. **Omit** if no location applies.]
* **The big picture:** [Broader context, trend, or “how we got here” — 1–2 sentences.]
* **By the numbers:** [Vote count, dollars, dates, counts — one tight line; **omit this axiom** if JSON has no numbers for this item.]
* **Who was for it (and why):** [1–2 sentences; names from JSON when available.]
* **Who was against it (and why):** [1–2 sentences; **omit entire bullet** if no opposition spoke or voted no.]
* **What's next:** [Deadlines, next vote, implementation — 1 sentence.]

Weave in personal stories or emotional beats from `human_element` inside the axioms above (especially **Why it matters** or **The big picture**) — do **not** use a separate “tension” or “human moment” bullet.

#### Timeline
```mermaid
[diagram_timeline from JSON]
```

#### Decision Map
```mermaid
[diagram_mindmap from JSON]
```

---

## Uncontested actions (`uncontested_items[]` only)

```markdown
## Uncontested actions

- **[headline]** — [outcome] ([vote]). [one_line_summary]
```

No per-item sub-headings. No Mermaid. No axioms. No for/against bullets.

---

## Quality checks
- Headline = complete mini-summary of the outcome.
- **No** `The One Big Thing` label anywhere.
- **Why it matters** appears once per contested item (bold label exactly as shown).
- **At a glance** appears once with **Attendees** and **Summary**.
- Axiom labels are **bold** and match the list above (spelling and capitalization).
- Outcome and vote appear inside **Why it matters** or **By the numbers**, not under a “Who won” label.
- When `place_refs` / `places[]` tie a decision to an address or site, use the **Where** axiom and repeat the address in **Why it matters** (plain language, not `place_id` slugs). Include applicant name from `people[]` when linked in JSON.
