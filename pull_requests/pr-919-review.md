---
pr: 919
branch: fix/918-nest-service-worker-rule
title: "fix(hosting): nest the service worker no-cache rule where nginx will use it"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: 29198f98dbe0d4ad1587de0068585bd467a886e7
verdict: approve-with-nits
---

# PR Review: fix(hosting): nest the service worker no-cache rule where nginx will use it

## Summary

Corrects #914, which did not work on the live site: the service worker no-cache rule sat at server level, where nginx never tried it for .js files because a nested rule inside location / matched first. The rule now sits inside location /, ahead of the static-file rule, and the tests pin that placement.

Read by the coordinator against the diff and screenshots at desktop and phone sizes; the heuristic scan ran first.

## Scope of Change


- `.huggingface/nginx.conf`
- `tests/test_hf_nginx_cache.py`
- `web_docs/docs/deployment/huggingface-spaces.md`

## CI Status

Required checks are read on the head commit before merge. Locally: tsc clean, vitest passed, build ok.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean. Fabricated data: none. Personal data: none. Destructive changes: none.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

None.

### 🔵 Nit (Minor)

- nginx could not be run in the review container. The Docker build test and the next deploy are the proof; curl -I on /sw.js must show a single no-cache header.
- The first fix shipped with a test that only read the block's text. The new tests check placement, which is what failed.
- Devices that already cached the old service worker file may hold it for up to a day.

## Verdict

**approve-with-nits**
