---
pr: 1467
issue: 1438
branch: feat/1438-where-towns-stand
title: "feat(web): Where towns stand gauge page and ranking summary on Browse all topics (#1438)"
reviewed_at: 2026-11-28
reviewer: coordinator
verdict: approve-with-nits
---

# PR #1467 review

Reviewed against `.claude/review-rubric.md`.

- **Issue and branch:** `feat/1438-where-towns-stand`, `Closes #1438`; the issue has all four parts.
- **Scans:**
  - No secrets and no personal data: only places are named.
  - No fabricated numbers. Every count and title comes from `/api/rankings*`; fixtures live only in tests and the e2e check.
  - Empty and error states are explicit, and no `dangerouslySetInnerHTML` is used.
- **Scope label:**
  - The page reads `topic`, `band` and `state` from the URL, and the label ("National · all sizes", "Alabama · mid-size places") changes with the query. The takeaway is computed from the drawn places, so it matches the filter.
  - Fixed in review: the Browse all topics summary is national whatever the page scope, so its heading now says "Where towns stand · National". The header link carries only `state`, which the rankings page honours, instead of a city it would silently drop.
- **Evidence:** a dot links to `/browse-topics?topic_id=&state=&city=`, which shows real decision cards and meetings with its own naming rules. The page quotes nothing itself.
- **Privacy:** residents are never named; school districts were already excluded upstream (#1461).
- **Checks:**
  - vitest 22/22 (rankings utils, StanceGauge, topicsYoy) and `tsc --noEmit` pass.
  - The Playwright check passes at 1440x900 and Pixel 7, with no horizontal scroll.
  - Checked against the real local API on Pixel 7.
- **Nits left:**
  - The Browse all topics summary has no unit test. It renders nothing on failure.
  - The #1404 box flight was not reused (a CSS fade instead), as the PR says.

No blocking findings.
