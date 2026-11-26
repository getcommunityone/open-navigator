---
pr: 1024
branch: chore/1023-remove-plate-images
title: "chore(web_app): remove the unused license-plate images (56 MB) and their dead badge component"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: 836bbd4dc7f904c7b61b9e530ad053524f2ce93f
verdict: approve
---

# PR Review: chore(web_app): remove the unused license-plate images (56 MB) and their dead badge component

## Summary

Automated review (#648) for PR #1024 on `chore/1023-remove-plate-images`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `scripts/frontend/sync_wikicommons_plates_public.sh`
- `web_app/public/wikicommons/AK_latest.png`
- `web_app/public/wikicommons/AL_latest.jpg`
- `web_app/public/wikicommons/AL_latest.png`
- `web_app/public/wikicommons/AR_latest.jpg`
- `web_app/public/wikicommons/AS_latest.png`
- `web_app/public/wikicommons/AZ_latest.jpg`
- `web_app/public/wikicommons/CA_latest.jpg`
- `web_app/public/wikicommons/CO_latest.jpg`
- `web_app/public/wikicommons/CT_latest.tif`
- `web_app/public/wikicommons/CZ_latest.jpg`
- `web_app/public/wikicommons/DC_latest.jpg`
- `web_app/public/wikicommons/DE_latest.jpg`
- `web_app/public/wikicommons/FL_latest.jpg`
- `web_app/public/wikicommons/GA_latest.jpg`
- `web_app/public/wikicommons/GU_latest.png`
- `web_app/public/wikicommons/HI_latest.jpg`
- `web_app/public/wikicommons/IA_latest.jpg`
- `web_app/public/wikicommons/ID_latest.jpg`
- `web_app/public/wikicommons/IL_latest.jpg`
- `web_app/public/wikicommons/IN_latest.jpg`
- `web_app/public/wikicommons/KS_latest.jpg`
- `web_app/public/wikicommons/KY_latest.jpg`
- `web_app/public/wikicommons/LA_latest.jpg`
- `web_app/src/components/HeroLicensePlateBadge.tsx`
- `web_app/src/data/wikicommonsPlatesLatest.json`
- `web_app/src/utils/wikicommonsLicensePlate.ts`

## CI Status

See the PR checks on `836bbd4dc7f9`.

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

## Agent review (Claude Code)

- Pure removal of unused assets: no imports of the badge, helper or manifest remain. Build passes. data/cache untouched.

Verdict stands: approve.
