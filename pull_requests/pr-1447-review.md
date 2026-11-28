---
pr: 1447
branch: feat/1430-seo-sitelinks
title: "feat(seo): real sitemap, per-route head meta and crawlable nav for Sitelinks"
author: jcbowyer
reviewed_at: 2026-11-28
reviewer: github-actions
head_sha: 52f148305c26f85d203c5961917f174f81f244d0
verdict: approve
---

# PR Review: feat(seo): real sitemap, per-route head meta and crawlable nav for Sitelinks

## Summary

Automated review (#648) for PR #1447 on `feat/1430-seo-sitelinks`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `.huggingface/nginx.conf`
- `api/main.py`
- `api/routes/seo.py`
- `api/seo.py`
- `apps/open-navigator-web/build.sh`
- `tests/test_seo.py`
- `web_app/index.html`
- `web_app/public/sitemap-app.xml`
- `web_app/public/sitemap.xml`
- `web_app/src/App.tsx`
- `web_app/src/components/RouteMetaSync.tsx`
- `web_app/src/components/SiteHeader.tsx`
- `web_app/src/components/home/HomeTopicBar.tsx`
- `web_app/src/data/seo/routes.json`
- `web_app/src/data/seo/story-copy.json`
- `web_app/src/utils/dataStory.ts`
- `web_app/src/utils/routeMeta.test.ts`
- `web_app/src/utils/routeMeta.ts`
- `web_app/src/utils/topicStories.ts`
- `web_app/src/utils/useDocumentTitle.test.ts`
- `web_app/src/utils/useDocumentTitle.ts`
- `web_app/vite.config.ts`
- `web_docs/docs/operations/seo-sitelinks.md`
- `web_docs/sidebars.ts`

## CI Status

See the PR checks on `52f148305c26`.

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
