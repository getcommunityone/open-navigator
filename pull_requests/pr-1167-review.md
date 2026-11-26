---
pr: 1167
branch: docs/646-search-places-handoff
title: "docs(web): Search ↔ Places handoff design for #646"
author: claude (agent session)
reviewed_at: 2026-11-26
reviewer: coordinator only (the author reviewed its own change; no independent reviewer ran)
verdict: approve-with-nits
---

# PR Review: docs(web): Search ↔ Places handoff design for #646

## Summary
Adds the design page for #646 (a banner and an empty-state link from search's Jurisdictions tab to the Places
browser, no auto-redirect), with two fixes to the draft: the link helper's output parameter is `levels` (what the
Places page reads), and a stray `EOF` line is removed. Docs only; `Refs #646` because the code is still to come. No
blocking findings. This is the author's own review of a page the author also edited.

## Scope of Change
- Files changed: 2 (the design page and this review)
- Areas touched: web_docs
- Commits: `6fdb49a docs(web): Search ↔ Places handoff design for #646`, then `docs(web): handoff link carries levels, not jurisdiction_levels; drop stray EOF`
- Range reviewed: `main..HEAD`

## CI Status
| Check | Status |
|---|---|
| Documentation Build and PR conventions | Not read when this was written; check the PR's Checks tab before merging |

## Scans (secrets, fabricated data, personal data, destructive data changes)
All four clean. The page contains no figures or personal data.

## Strengths
- Explicit non-goals, and a clear split from the #647 URL bug.
- The `levels` correction is traced to the page that reads it.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
- The page's "place-like" wording for the empty state still hedges ("keep any heuristic simple"); a plain "any non-empty `q`" would be one fewer thing to test. Left as written because the design was already drafted that way.
- The page says "Links to #647"; that issue should be linked back to this page when #647's fix lands.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | `Refs #646` |
| Conventional Commits | Yes | Co-author trailer on the new commit |
| Docs | Yes | Under `web_docs/docs/development/`, kebab-case, frontmatter present |
| Tests | n/a | Docs only |

## Test Coverage
Not run: the Docusaurus build locally. Checked the `levels` parameter name against `JurisdictionsSearch.tsx`.

## Verdict
approve-with-nits. The owner should read the design before the implementation starts; merging this page does not start #646's code.
