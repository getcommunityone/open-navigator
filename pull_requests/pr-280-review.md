---
pr: 280
branch: docs/278-readme-roles-deck
title: "docs(readme): role-based drill-downs and an HTML slideshow pitch"
author: jcbowyer
reviewed_at: 2026-11-14
reviewer: coordinator (self-review)
verdict: approve-with-nits
---

# PR Review: docs(readme): role-based drill-downs and an HTML slideshow pitch

## Summary

The README now opens with a short summary, the deck cover and a role table, with a collapsible drill-down per role,
and stale paths are gone. An 11-slide pitch is built from per-slide sources by a dependency-free Node script into a
reveal.js slideshow and a full-text page, and CI checks the built files match the slides. The docs site builds with
the new page and the slideshow in its output. No platform totals are quoted, since the docs disagree on them (#279).
Approve with nits.

## Scope of Change

- Files changed: 19 (+828 / -478), of which the built `web_docs/static/deck/index.html` and
  `web_docs/docs/pitch/full-text-and-notes.md` are generated.
- Areas touched: README, web_docs, ci.
- Commits: `docs(readme): role-based drill-downs and an HTML slideshow pitch`; a follow-up that points the full-text
  page's slideshow link at the live URL and adds this review; `docs(walkthrough): ...` adding the developers' code
  walkthrough (scope line added to #278).
- Range reviewed: `origin/main..docs/278-readme-roles-deck`.

## CI Status

| Check | Status |
|---|---|
| PR conventions (linked issue) | success |
| Detect Docker-relevant changes | success |
| Frontend Build, Backend Tests, API Types, Documentation Build | running at the time of writing; re-read before merge |

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean.
- Fabricated data: clean. The only figure is the Census count (91,438 local governments, 2025), cited on slide 3 and
  in the README. The policy-model example is labelled "Illustrative example, not a record". Nothing touches `api/` or
  `web_app/src/`.
- Personal data: clean. The contact address is the project's public one, already in the old README.
- Destructive or bulky changes: none. The cover PNG is 100 KB.

## Strengths

- Smart-brevity README: summary, table, then detail on demand; every relative link was checked to resolve.
- The deck builds from small slide files with shared styles, so editing one slide is a one-file change.
- `--check` in CI stops the built deck drifting from its sources.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

None.

### 🔵 Nits / suggestions (Minor)

- `README.md`: the slides link (`https://www.communityone.com/docs/deck/`) only works after this merges and the docs
  deploy. Verified by reading the deploy path: `web_docs/static/` is copied under the docs base URL. Check it once
  deployed.
- `.gitattributes`: adds a one-file exception so the cover PNG is a normal blob, not LFS, because this session can't
  upload LFS objects. Harmless, but the owner may prefer LFS for consistency.
- The builder is Node in `web_docs/scripts/`, not a Python package CLI. That is deliberate: it is docs tooling beside
  `check-mermaid.mjs`, and the "new Python in `packages/`" rule doesn't apply.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | #278 with four parts; `Closes #278`; follow-up #279 logged |
| Conventional Commits | Yes | `docs(readme): ...`, co-author trailer |
| No fabricated data | Yes | See scans |
| New Python in `packages/` | n/a | No Python added |
| Docs | Yes | New page under `web_docs/docs/pitch/`, kebab-case, front matter; no new root `.md` |
| Tests | Yes | `build-deck.mjs --check` in the Documentation Build job |

## Test Coverage

Code walkthrough: every relative docs link and every GitHub file link was checked to exist on the branch, and the API
paths were checked against the routers' prefixes in `api/main.py` and `api/routes/`. The docs build includes the page.


Run locally: `node web_docs/scripts/build-deck.mjs --check` (up to date); `npm ci && npm run build` in `web_docs`
(succeeds; existing broken-link warnings only); each slide rendered at 1920 × 1080 in Chrome with no overflow.

## Verdict

Approve with nits. Merge once the required checks are green.
