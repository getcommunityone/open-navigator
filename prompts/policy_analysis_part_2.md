## Objective
Write a resident-facing summary from the provided JSON. Spend depth on **contested** items; batch **uncontested** items into one short bulleted section.

**Who this is for:** A busy resident on their phone who needs the fights and surprises first, with routine votes acknowledged in one skim.

## Rules (All Non-Negotiable)

### Document structure
- **Line 1 must be an H1:** `# {body or recording title} — {meeting_date}` (e.g. `# Tuscaloosa Pre-Council Briefing — 2026-05-19`). If JSON `meeting.body_name` disagrees with the canonical recording title in the user message, **use the recording title** in the H1.
- **Then exactly two sections** (no other `##` headings):
  1. `## Contested decisions` — full Smart Brevity blocks for **each** row in `decisions[]` (in order). If zero contested items, write one sentence under this heading (e.g. "There were no contested decisions at this meeting.") and do not invent items.
  2. `## Uncontested actions` — **one** bulleted list covering **every** row in `uncontested_items[]` (in order). If the array is empty, **omit** this entire section.
- **Do not** write a full Smart Brevity block per uncontested item — one bullet per `item_id` only.
- Use consistent Markdown bullets: `-` for uncontested; `*` for contested sub-bullets (`* **Who won:**` …).
- Plain conversational prose. No NTEE, COFOG, `decision_id`, `item_id`, or schema jargon.
- **Contested blocks:** max **150–200 words** each (excluding diagrams). Punchy bullets.
- **Uncontested bullets:** max **one line each** (~25 words). Format: `**[headline]** — [outcome] ([vote]). [one_line_summary]`

### Mermaid (contested items only)
- Include diagrams **only** when JSON has non-empty `diagram_timeline` and/or `diagram_mindmap` on that decision.
- **Copy the JSON strings verbatim** into fenced blocks. They already use valid syntax.
- **Timeline block** — heading `#### Timeline`, then:
  ```mermaid
  {paste diagram_timeline exactly}
  ```
- **Decision Map block** — heading `#### Decision Map`, then:
  ```mermaid
  {paste diagram_mindmap exactly}
  ```
- **Forbidden:** `graph TD`, `graph LR`, `flowchart`, or any diagram type other than `timeline` / `mindmap`.
- If a diagram field is missing or empty, **omit** that subsection (do not substitute a flowchart).

## Contested decision block (`decisions[]` only)

### [Punchy, Action-Oriented Headline]
[The Lede: one sharp sentence — conflict, stakes, or surprise. Do not start with "The council voted..."]

* **Who won:** [outcome + vote]
* **Who was for it (and why):** [1–2 sentences]
* **Who was against it (and why):** [1–2 sentences; omit if no opposition]
* **The tension:** [personal stories or emotional beats from JSON; omit if none]
* **What's next:** [1 sentence]

#### Timeline
```mermaid
[diagram_timeline from JSON — must start with `timeline`]
```

#### Decision Map
```mermaid
[diagram_mindmap from JSON — must start with `mindmap`]
```

## Uncontested actions (`uncontested_items[]` only)

```markdown
## Uncontested actions

- **[headline]** — [outcome] ([vote]). [one_line_summary]
- **[headline]** — …
```

No sub-headings per item. No Mermaid. No "Who was for/against" bullets.
