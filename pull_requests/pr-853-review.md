---
pr: 853
branch: feat/851-stance-responses-api
title: "feat(api): store agree / disagree answers and report where a player stands"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: cd1ecb4f539f084d0e69a1f56c1e1a77fc9c261a
verdict: approve-with-nits
---

# PR Review: feat(api): store agree / disagree answers and report where a player stands

## Summary

Adds the storage and reporting half of the "Where Do You Stand?" game: a versioned pack of eight data center
statements, a runtime-owned `public.stance_response` table, and four endpoints to list packs, answer, and read
results nationally, by state and by place. A group's split is withheld below a minimum sample. Unit-tested with a
stub pool, and the real SQL was run once against a scratch PostgreSQL. Not run against the warehouse or production.

The automated scan (#648) wrote the first version of this file; the agent that opened the PR refined it.

## Scope of Change

- `.env.example`
- `Makefile`
- `api/main.py`
- `api/routes/stance.py`
- `api/stance_packs/data_centers.json`
- `packages/hosting/src/hosting/neon/sync_public_to_neon.py`
- `tests/test_stance_api.py`
- `web_docs/docs/development/where-you-stand-game-design.md`

## CI Status

See the PR checks on `cd1ecb4f539f`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: clean (heuristic)
- Fabricated data / personal / destructive: clean. No count is seeded or defaulted; an empty table reports zero answers and no split. The table stores a random player id, an answer and a self-chosen place only; the rate-limit hash of IP and player id stays in memory and is not logged. The table is added to the runtime-owned list so a deploy cannot overwrite it.

## Strengths

- The suppression rule is tested at 0, 29 and 30 answers, and the split is null rather than zero when withheld.
- Results for a whole pack come from one grouped query, and answers to an old wording are excluded by version.
- The design decisions are written down in the same PR, including why the table has no foreign keys.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

- The eight statements are drafts written by the agent. They decide what the public is asked, so the owner should
  read them before the game screens (#852) go live. Changing one later needs a version bump.
- Anyone can post with a fresh random player id, so the per-visitor rate limit slows ballot stuffing but does not
  stop it. The design page says the results are "of people who played" and not a poll; the screens must keep to that.

### 🔵 Nit (Minor)

- `GET /stance/packs/{pack_id}` has no response model, so the OpenAPI schema shows a plain object.
- Place matching is exact on trimmed, lower-cased text, so "Tuscaloosa" and "City of Tuscaloosa" are different
  groups. The screens should offer places from a list rather than free text.
- The rate limiter is per process, like the chat's; several API workers each keep their own count.

## Verdict

**approve-with-nits**
