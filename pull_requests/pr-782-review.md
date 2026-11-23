---
pr: 782
branch: fix/779-shared-channel-unresolved-attribution
title: "fix(youtube): attribute the #777 unresolved shared-channel videos"
author: jcbowyer
reviewed_at: 2026-11-23
reviewer: coordinator
verdict: approve
---

# PR Review: fix(youtube): attribute the #777 unresolved shared-channel videos

## Summary
A data-only change. It adds 984 owner-approved rows to the `youtube_channel_attribution_override` seed, applied through the existing #514 repair. The seed's dbt tests pass (13, including the relationship to `int_jurisdictions`). The repair dry run produces the expected counts, and I listed and checked its only deletions (12 wrong `int_events_channels` links). Approve.

## Scope of Change
- Files: 3 (seed CSV +984 lines, docs bullet, this review)
- Areas: dbt_project (seed), web_docs

## Scans
- Secrets, fabricated data, personal data: clean. Every row's evidence is the verbatim YouTube title or a channel description.
- Destructive data changes: applying the repair deletes 12 `int_events_channels` rows. All are wrong links: non-government channels tied to towns, hptv15 tied to Highland Village TX and Middlesex, and Clayton tied to Barbour County AL. The owner approved removing them ("do what you recommend", 2026-11-23).

## Findings
### 🔴 Blocking
None.
### 🟡 Should fix
None.
### 🔵 Nits
- Union's per-video rows use title matching within MD. Mount Airy straddles Carroll and Frederick counties, but the id is the town, so this is correct.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Yes | `fix/779-...`, `Closes #779` |
| dbt for transformations | Yes | Seed plus the existing run-operation |
| Keys | Yes | Seed relationship test to `int_jurisdictions` passes |
| Docs | Yes | `youtube-discovery.md` |

## Verdict
approve. Merge when checks are green, then apply `repair_youtube_channel_attribution --args '{dry_run: false}'`.
