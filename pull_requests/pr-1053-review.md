---
pr: 1053
branch: feat/1051-guns-topic
title: "feat(topics): a Guns topic tagged from what meetings say, with a Coming soon card"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: 0ea163188f76363c9cc6b9907048d9f589d28496
verdict: approve
---

# PR Review: feat(topics): a Guns topic tagged from what meetings say, with a Coming soon card

## Summary

Automated review (#648) for PR #1053 on `feat/1051-guns-topic`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `dbt_project/seeds/curated_topics.csv`
- `web_app/src/components/home/HomeTopicStrip.tsx`
- `web_docs/docs/development/browse-topics-catalog.md`

## CI Status

See the PR checks on `0ea163188f76`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: clean (heuristic)
- Fabricated data / personal / destructive: see findings

## Strengths

- Automated scans found no secret/credential patterns in added lines.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

None from automated heuristics.

### 🔵 Nit (Minor)

None from automated heuristics.

## Verdict

**approve**

## Agent review

- **Issue and branch:** `feat/1051-guns-topic`, `Closes #1051`; the issue has all four parts.
- **Scans:** no secrets, no personal data, no data deletions. No fabricated data: counts come from the transcript
  keyword link built by dbt; the card says Coming soon and shows no number.
- **Correctness:** the keywords are phrases or specific words only (no bare "gun"), so tool and idiom uses don't match;
  `int_transcript_keyword_topic` treats curated topics as one-hit matches, which explains the incidental tags noted in the
  docs. The seed id 100005 follows 100004 and the build created the topic row (checked in `gold.civicsearch_topic`).
- **Checks:** local dbt build of the topic models passed; tsc clean; CI runs on this commit.
- **Docs:** `browse-topics-catalog.md`.

No blocking findings.
