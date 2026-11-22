---
sidebar_position: 48
---

# App → docs linking

**Issue:** [#714](https://github.com/getcommunityone/open-navigator/issues/714)  
**Status:** approved design (2026-11-22)

## Problem

Signed-in people reach Docusaurus only from scattered Home / Open Source / Explore / 404 links. The avatar menu has no Documentation item. Admin screens that already have guides (`/admin/batch-jobs`, meeting kinds, application links) do not surface them, so operators search the docs tree by hand.

## Decision

Ship **both**:

1. One stable **Documentation** link on the profile (avatar) menu → docs intro.
2. Contextual **Guide** links on admin screens that already have a known page, driven by a single route→doc map.

Batch jobs does **not** deep-link the Data centers cohort page. The Guide opens **AI Policy Analysis**; that hub drills down to Data centers (and sibling Jev / cascade pages) inside the docs.

## Approach

Central map module (recommended over ad-hoc `href`s or frontmatter sync). One place owns prod/local bases and the admin mappings.

## Contract

### `web_app/src/utils/docsLinks.ts`

| Export | Behavior |
|---|---|
| `docsUrl(path)` | Absolute docs URL. `path` like `/intro` or `/development/ai-policy-analysis` (leading slash). Prod origin `https://www.communityone.com/docs`; local `http://localhost:3000/docs`. |
| `DOCS_INTRO` | `docsUrl('/intro')` — profile menu target. |
| `ADMIN_GUIDE_BY_PATH` | Exact admin route → docs path (see table below). |

| App path | Guide docs path |
|---|---|
| `/admin/batch-jobs` | `/development/ai-policy-analysis` |
| `/admin/meeting-kinds` | `/development/jev-meeting-kind-gate` |
| `/admin/application-links` | `/development/data-center-application-links` |
| `/admin/lighthouse-report` | *(none — omit Guide until a page exists)* |

Lookup: match `pathname` to a key, or `pathname.startsWith(key + '/')` for subroutes. At most one Guide control.

### Profile menu (`SiteHeader`)

- Label: **Documentation**
- Placement: after Settings, before Data explorer
- Behavior: open `DOCS_INTRO` in a new tab (`target="_blank"`, `rel="noopener noreferrer"`)
- Visibility: every signed-in user (not admin-gated)

### Admin Guide (`AdminLayout`)

- When the current path has a map entry, show one **Guide ↗** in the admin header (near the short description / tabs).
- Opens `docsUrl(mappedPath)` in a new tab.
- No Guide when unmapped (Lighthouse).

### Hub doc (`ai-policy-analysis.md`)

Retarget the page as the **analyze-pipeline / AI policy** operator hub (keep useful existing content; do not invent metrics).

Add a **Data centers** section that links down to:

- [Data centers cohort on batch jobs](./batch-jobs-data-centers-cohort.md)
- Related siblings as needed (e.g. Jev meeting-kind gate, Jev-light cascade, transcript screening) — links only, no duplicated runbooks.

The app never deep-links past this hub for batch jobs.

## Out of scope

- Guide chips on every product browse/search page
- Frontmatter `related_app_path` sync / CI check
- Changing Home footer / Open Source CTAs beyond optional later use of `docsUrl`
- A Lighthouse docs page

## Done when

Matches [#714](https://github.com/getcommunityone/open-navigator/issues/714) Done when / Contract.

## Read first

- `web_app/src/components/SiteHeader.tsx`
- `web_app/src/components/AdminLayout.tsx`
- `web_app/src/utils/adminPaths.ts`
- `web_docs/docs/development/ai-policy-analysis.md`
- `web_docs/docs/development/batch-jobs-data-centers-cohort.md`
