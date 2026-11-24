---
pr: 919
branch: fix/918-nest-service-worker-rule
title: "fix(hosting): nest the service worker no-cache rule where nginx will use it"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: 29198f98dbe0d4ad1587de0068585bd467a886e7
verdict: approve
---

# PR Review: fix(hosting): nest the service worker no-cache rule where nginx will use it

## Summary

Automated review (#648) for PR #919 on `fix/918-nest-service-worker-rule`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `.huggingface/nginx.conf`
- `tests/test_hf_nginx_cache.py`
- `web_docs/docs/deployment/huggingface-spaces.md`

## CI Status

See the PR checks on `29198f98dbe0`.

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
