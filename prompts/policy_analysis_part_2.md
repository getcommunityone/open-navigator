## Objective
Write a resident-facing summary from the provided JSON. Spend depth on **contested** items; batch **uncontested** items into one short bulleted section.

**Who this is for:** A busy resident on their phone who needs the fights and surprises first, with routine votes acknowledged in one skim.

## Rules (All Non-Negotiable)
- **Two sections only** (after an optional one-line opener: body, date, city):
  1. `## Contested decisions` — full Smart Brevity blocks for **each** row in `decisions[]` (in order).
  2. `## Uncontested actions` — **one** bulleted list covering **every** row in `uncontested_items[]` (in order). If the array is empty, omit this section.
- **Do not** write a full Smart Brevity block per uncontested item — one bullet per `item_id` only.
- **Output real Markdown:** `###` headlines and `* **Who won:**` bullets for contested items; `-` bullets for uncontested.
- Mermaid (` ```mermaid `) **only** under contested items when JSON includes diagram fields.
- Plain conversational prose. No NTEE, COFOG, `decision_id`, `item_id`, or schema jargon.
- **Contested blocks:** max **150–200 words** each (excluding diagrams). Punchy bullets.
- **Uncontested bullets:** max **one line each** (~25 words). Format: `**[headline]** — [outcome] ([vote]). [one_line_summary]`

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
[Join `diagram_timeline_lines` or `diagram_timeline`]
```

#### Decision Map
```mermaid
[Join `diagram_mindmap_lines` or `diagram_mindmap`]
```

## Uncontested actions (`uncontested_items[]` only)

```markdown
## Uncontested actions

- **[headline]** — [outcome] ([vote]). [one_line_summary]
- **[headline]** — …
```

No sub-headings per item. No Mermaid. No "Who was for/against" bullets.
