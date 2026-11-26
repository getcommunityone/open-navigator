---
pr: 1037
issue: 1036
verdict: approve
---

# PR #1037 review

Reviewed against `.claude/review-rubric.md`.

- **Issue and branch:** `feat/1036-speaker-names-popup-quote`, `Closes #1036`; the issue has all four parts.
- **Scans:** no secrets and no fabricated data. Names come from the meeting analysis's `speaker_id`; null when only a role
  was heard. Personal data: speakers at public meetings are public record, and the name is shortened to "First L.", so
  no full surname is added to a served path. No data deletions.
- **Correctness:**
  - The macro strips the row's own `speaker_role` and common role words from the end of the slug before splitting, so
    `andrea_varela_chief_of_staff` gives "Andrea V." and `resident_2` gives null. Slugs with more than two name words
    fall back to the first name, so a middle name is never shown as an initial.
  - The API reads the column with `to_jsonb(p) ->> 'speaker_display_name'`, so it works on a serving copy that doesn't
    have the column yet (the prod copy until it is refreshed).
  - The popup quote is `Dot.quote = m.evidence`, the same verbatim text the dot already carries; it is not shown
    when absent.
- **Checks:** Frontend Build, Documentation Build, Backend Tests and API Types pass on the head commit.
- **Docs:** `data-center-who-spoke-up.md` describes the new column, its rule and the endpoint field.

No blocking findings.
