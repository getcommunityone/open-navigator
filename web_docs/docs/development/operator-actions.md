---
sidebar_position: 48
title: Operator actions (human-required)
description: Admin page and API for pipeline blockers that need a human, with standard response templates.
---

# Operator actions (human-required)

Decision recorded 2026-11-22. Issue
[#712](https://github.com/getcommunityone/open-navigator/issues/712).
Builds on Discover’s `ACTION_REQUIRED.md` rollup
([#710](https://github.com/getcommunityone/open-navigator/issues/710)).

## Problem

Pipeline blockers (YouTube Data API quota, Surfshark/VPN down, missing
`YOUTUBE_API_KEY`) showed up only as per-row log lines or a cache markdown
file. Operators had no admin surface for **open actions**, and no shared
playbooks for the recurring fixes.

## Goal

**C — both surfaces:**

1. **Admin page** `/admin/operator-actions` — live list of open human-required
   actions, linked from Batch Jobs when any exist.
2. **Docs playbooks** — standard response templates for v1 blockers (quota,
   VPN, missing API key).

Clearing: **auto-clear** when a clean Discover (or later pipeline) write has
no action buckets for a code, **plus manual dismiss** for stale items.

## Chosen approach

**File + templates (not a Postgres issue queue).**

- Writers (Discover today) keep updating
  `data/cache/batch_jobs/ACTION_REQUIRED.md` (and stamped copies).
- Also write `data/cache/batch_jobs/action_required.json` for the API.
- Dismissals live in `data/cache/batch_jobs/action_dismissals.json`
  (code → `{ dismissed_at, fingerprint }`).
- Template bodies are versioned in git (docs + Python catalog).

## Action codes (v1)

| Code | Trigger | Template |
|------|---------|----------|
| `youtube_api_quota` | uploads 403 / `quotaExceeded` | [quota](./operator-action-templates.md#youtube-api-quota) |
| `vpn_down` | `VpnRequiredError` / VPN wait | [VPN](./operator-action-templates.md#vpn-down) |
| `missing_youtube_api_key` | missing key reject | [API key](./operator-action-templates.md#missing-youtube-api-key) |

## API

- `GET /api/batch-jobs/operator-actions` → `{ open, templates, … }` (admin)
- `POST /api/batch-jobs/operator-actions/{code}/dismiss` body optional `{ fingerprint }`

## Admin UI

- `/admin/operator-actions` — open list + templates + Mark resolved
- Batch Jobs banner when `open.length > 0`

## Read first

- [Operator action templates](./operator-action-templates.md)
- `packages/scrapers/src/scrapers/youtube/discover_action_log.py`
- `api/batch_jobs/operator_actions.py`
