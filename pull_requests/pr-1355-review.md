---
pr: 1355
branch: feat/1349-topic-county-map
title: "feat(stories): topic stories draw the county and town map at state scope"
author: jcbowyer
reviewed_at: 2026-11-27
reviewer: claude (agent /pr-review, .claude/review-rubric.md)
head_sha: 2b6a42c0ec9c3ce6dfdffe7a8e62282ecaba157d
verdict: approve-with-nits
---

# PR Review: topic stories draw the county and town map at state scope

## Summary

This adds the `topic_place_meeting` mart, `GET /api/topics/{id}/places`, a `TopicCountyMap` wrapper that puts
`StoryCountyMap` on the topic Overview and the home topic card at a state, and removes the repeated sentences in the
Overview's left column. Closes #1349.

## Scans

- **Secrets:** none. `.env` is gitignored, and the worktree's `profiles.yml` and `dbt_packages` symlink are not committed.
- **Fabricated data:** none. Every count comes from `topic_place_meeting` or `topic_transcript_link`. Unplaced meetings are
  reported, never spread across places. Test stand-ins stay in the tests. Missing mart → `available: false` → the
  state outline.
- **Personal data / privacy:** aggregates per government only. No person is added. Hover passages reuse What-was-said rows,
  which already shorten resident names to "First L." on the server.
- **Keys:** PK `topic_place_meeting_id` and FKs to `civicsearch_topic` and `jurisdictions` are declared and enforced
  (`dbt build` PASS).

## Rules

- **Scope label = filter:** the map title and label name the state. A town opened from a ring shows all of the state,
  highlights the town's county, and says the town on its own isn't available yet.
- **No `scripts/` additions; no leading `+` selector; no Neon writes; no paid LLM.**
- **Docs:** `web_docs/docs/guides/data-stories.md` is updated in the same PR.

## Findings

- 🟡 Nit: the home card's drill hint says "Pick a county or a town" at a state scope even in the rare case where the
  outline fallback is drawn. Harmless, since a click still opens the story.
- 🟡 Nit: topic stories still have no city grain. A ring opens the state story with the town highlighted, not a
  town-only story. The page says so honestly.

No blocking findings.
