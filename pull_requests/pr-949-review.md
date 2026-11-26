---
pr: 949
branch: fix/948-deploy-map-data
title: "fix(deploy): carry the generated census map data into the isolated HF deploy clone"
author: jcbowyer
reviewed_at: 2026-11-25
reviewer: coordinator
verdict: approve
---

# PR Review: fix(deploy): carry the generated census map data into the isolated HF deploy clone

## Summary

Production census maps are gray because the isolated deploy clone never had the gitignored, generated
`web_app/public/data`, and the force-add step silently skipped. The PR hard-links the data into the clone and makes a
deploy without `census-map/manifest.json` fail loudly, with an explicit opt-out. It's small, correct and verified.
Verdict: **approve**.

## Scope of Change

- Files changed: 2 (`packages/hosting/scripts/huggingface/deploy-huggingface.sh`, `web_docs/docs/deployment/huggingface-spaces.md`)
- Areas touched: packages (hosting script), web_docs

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean. The script still reads `.env`; nothing new is printed or committed.
- Fabricated data, personal data: n/a.
- Destructive: none. The clone's `trap 'rm -rf "$CLONE_DIR"'` deletes only the clone's hard links. The source files keep
  their own links (verified: link count 3 while the temp copy existed; the originals remained after removal).

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

None.

### 🔵 Nits / suggestions (Minor)

1. The script deploys the local `main` branch (`git checkout main` in the clone), not `origin/main`. It's documented now;
   making the script fetch `origin/main` itself would remove the trap. That's a behaviour change worth its own issue if
   wanted.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue first | ✅ | `fix/948-…`; `Closes #948`; four parts |
| Conventional Commits | ✅ | |
| Docs | ✅ | `deployment/huggingface-spaces.md` |
| Tests | ✅ (manual) | a shell deploy script with no test harness: `bash -n` plus a real run of the new copy step against the checkout (562 files, manifest present) |

## Test Coverage

- `bash -n`: OK. The copy step was run against the real checkout into a temp dir: 562 files, hard-linked, manifest present.
- The end-to-end proof is the deploy itself: after merge, `/data/census-map/manifest.json` must serve JSON.

## Verdict

**approve**: merge when green, then deploy from an up-to-date `main`.
