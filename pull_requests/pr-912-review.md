---
pr: 912
branch: fix/911-restore-lfs-static
title: "fix(hosting): restore real files in place of Git LFS pointers when the Space starts"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: fde13b781d8eed0f1a917266439125af93f2737d
verdict: approve-with-nits
---

# PR Review: fix(hosting): restore real files in place of Git LFS pointers when the Space starts

## Summary

At container start a script replaces served Git LFS pointer files with the real objects, downloaded from the Space's own repository and accepted only when the SHA-256 equals the pointer oid. It runs beside the services and never fails the start. Fixes the strategic plan PDF and logos being served as 130-byte pointer text.

Read by the coordinator against the diff and screenshots at desktop and phone sizes; the heuristic scan ran first.

## Scope of Change


- `.huggingface/restore_lfs_static.sh`
- `.huggingface/start.sh`
- `Dockerfile.huggingface`
- `tests/test_restore_lfs_static.py`
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

- Confirmed from outside that the Space address returns the PDF with the matching hash (136,930 bytes). Not yet confirmed: that SPACE_ID is set inside the running container. The next deploy proves it.
- For a short time after each start a request can still get a pointer, until the restore reaches that file.
- Hashed docs images are matched by object id, so they are covered, but that path was not exercised in the tests.

## Verdict

**approve-with-nits**
