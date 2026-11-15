---
pr: 346
branch: test/322-youtube-channel-rules
title: "test(scrapers): settle the two YouTube channel rules the owner decided"
author: jcbowyer
reviewed_at: 2026-11-15
reviewer: coordinator (self-review)
verdict: approve
---

# PR Review: test(scrapers): settle the two YouTube channel rules the owner decided

## Summary

The owner decided both open YouTube channel rules from #322 (November 15, 2026) and kept the code both times. A
`county-general` channel that the county's website links to qualifies without a meeting signal. "Town of Nantucket" is
Nantucket County's own channel. The tests now assert the decided behaviour, the two `xfail` marks are gone, and a new
docs page records the decisions. Closes #322. Approve.

## Scope of Change

- Files changed: 3: two test files and the new page `web_docs/docs/development/youtube-channel-rules.md`
- Areas touched: tests and docs. No library code.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Clean on all four. The channel names are public government channels already in the tests.

## Findings

None blocking, none to fix.

- **Test edits.** Changing a test to match the code is right here: the owner chose the code, which is what #322 asked
  for. It isn't a test skipped to get green.
- **The old rule.** Its case that still holds keeps a test: a `county-general` channel with no website link either way
  is still rejected as `channel_purpose_not_meeting_focused`. The reason was checked against the code before it was
  asserted.
- **The page.** It sits in `web_docs/docs/development/` (kebab-case, front matter), as `CLAUDE.md` requires, and says
  when to revisit the decisions.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #322 has all four parts; `Closes #322` |
| Conventional Commits | Yes | `test(scrapers): ...` with the co-author trailer |
| Decisions written down | Yes | `youtube-channel-rules.md`, linked from both tests |
| Tests | Yes | 20 passed in the two files; whole suite 1443 passed, 40 skipped |

## Verdict

Approve once the required checks are green.
