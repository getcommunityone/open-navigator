---
pr: 1327
issue: 1320
verdict: approve-with-nits
---

# PR #1327 review

Reviewed against `.claude/review-rubric.md`. Refines the automated review (#648).

- **Issue and branch:** `feat/1320-decision-supporters`, `Closes #1320`; the issue has all four parts.
- **Scans:** no secrets, no data changes. No fabricated data: every name comes from a slug in `event_decision.competing_views` / `decision_speakers`, canonical names and titles from `person_government`; a side with no names says so ("Opposition recorded; no names on record"), and nothing is shown when the record has no views. Test slugs follow the record's shapes; official rows are marked stand-ins.
- **Privacy (AGENTS.md):** officials (public role) by full name; everyone else "First L." with no role and only with a first and last name on record. Students and minors (slug tokens) are never shown; residents are never shown for a school-board decision (school_district jurisdiction, or a school-board name or title). A slug that runs a description into the name (one seen in the data says "former homeless drug addict") is dropped, so no sensitive trait can reach a card; a slug without a role word is a name only as exactly "first last". Tests pin each case.
- **Correctness:**
  - Role only when reliable: the official record's title, else the slug's own title word; a title used as address stays in the name ("Chief Sky", no role).
  - `person_government` match needs exactly one current official of the decision's own government ("[place] Government", same state), by first and last name (or surname alone); ambiguous matches fall back to the slug.
  - Optional everywhere: a database without `person_government` or `decision_speakers` keeps the slug-only names or none; older servers' clients see no new lines.
- **Verification:** pytest (decision people 16, topic said 20, topics, DC decisions) pass; vitest 833 passed; tsc clean; Playwright at 1440 and Pixel 7 on guns AL/national Decisions and data-centers national/AL Decisions.
- **Docs:** `web_docs/docs/guides/data-stories.md`, "Who supported and opposed each decision".

Nits (non-blocking):
- "Supported by" restates the record's dominant view, which is the view most speakers held, not always a vote for the motion; the main view's label (`supported_view`) is served for a future tooltip.
- Slug parsing is heuristic by design; more official titles can be added to `_ROLE_PHRASES` as they show up.

No blocking findings.
