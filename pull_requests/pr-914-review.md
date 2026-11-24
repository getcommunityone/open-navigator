---
pr: 914
branch: fix/913-no-cache-service-worker
title: "fix(hosting): never cache the service worker files on the Space"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: 76656979cfb6f3e6d2f2bef225c1cf7c68ecc6c2
verdict: approve-with-nits
---

# PR Review: fix(hosting): never cache the service worker files on the Space

## Summary

The Space's nginx now sends sw.js, registerSW.js, workbox-*.js and manifest.webmanifest with no-cache, so a phone that visited before checks for a new version on every visit. Before this, sw.js had a day-long cache and the owner's phone still showed the old Chat page an hour after a deploy.

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

- nginx was not run here; the block follows the file's existing location blocks, and a test pins the header and the four file names. The next deploy proves it with curl -I on /sw.js.
- A device already holding the old service worker may take up to a day to see this first fix, or needs its site data cleared once.

## Verdict

**approve-with-nits**
