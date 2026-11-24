---
pr: 889
branch: fix/888-admin-tabs-lighthouse-404
title: "fix(web_app): open Admin on Batch jobs and say plainly when a site has no Lighthouse audit"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions
head_sha: 133de1dd0875270101c55fa3fe447fd462297642
verdict: approve
---

# PR Review: fix(web_app): open Admin on Batch jobs and say plainly when a site has no Lighthouse audit

## Summary

Automated review (#648) for PR #889 on `fix/888-admin-tabs-lighthouse-404`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `web_app/src/App.tsx`
- `web_app/src/components/AdminLayout.tsx`
- `web_app/src/pages/LighthouseReportPage.tsx`
- `web_app/src/pages/Settings.tsx`
- `web_app/src/utils/apiErrorMessage.test.ts`
- `web_app/src/utils/apiErrorMessage.ts`
- `web_docs/docs/development/batch-load-tab.md`

## CI Status

See the PR checks on `133de1dd0875`.

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
