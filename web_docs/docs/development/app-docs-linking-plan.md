# App → docs linking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every signed-in user one Documentation link from the avatar menu, and show a contextual Guide on admin screens that already have a known Docusaurus page — with batch jobs entering at AI Policy Analysis and drilling down to Data centers in the docs.

**Architecture:** A single `docsLinks.ts` module owns prod/local docs bases, intro URL, and an admin route→doc map. `SiteHeader` adds one menu anchor; `AdminLayout` looks up the map and renders at most one Guide link. The hub page `ai-policy-analysis.md` gains a Data centers section that links to the cohort (and sibling) docs.

**Tech Stack:** React + TypeScript (Vite), Vitest, Docusaurus markdown under `web_docs/docs/`.

**Spec / issue:** [app-docs-linking-design](./app-docs-linking-design.md) · [#714](https://github.com/getcommunityone/open-navigator/issues/714)

## Global Constraints

- Docs live only under `web_docs/docs/` (kebab-case, YAML frontmatter).
- Calendar years on the wire stay strings; N/A for this change.
- Do not invent metrics or placeholder stats in the hub rewrite.
- Batch jobs Guide must open `/development/ai-policy-analysis`, never deep-link the cohort page from the app.
- Lighthouse has no Guide in this plan.
- Branch: `feat/714-app-docs-linking`; Conventional Commits; `Closes #714`.
- One PR; required CI green before merge.

## File structure

| File | Role |
|---|---|
| `web_app/src/utils/docsLinks.ts` | `docsUrl`, `DOCS_INTRO`, `ADMIN_GUIDE_BY_PATH`, `adminGuideHref(pathname)` |
| `web_app/src/utils/docsLinks.test.ts` | Vitest for URL building and admin lookup |
| `web_app/src/components/SiteHeader.tsx` | Documentation menu item |
| `web_app/src/components/AdminLayout.tsx` | Contextual Guide ↗ |
| `web_docs/docs/development/ai-policy-analysis.md` | Hub + Data centers drill-down |
| `web_docs/docs/development/app-docs-linking-design.md` | Spec (already on branch) |
| `web_docs/docs/development/app-docs-linking-plan.md` | This plan |

---

### Task 1: `docsLinks` helper + Vitest

**Files:**
- Create: `web_app/src/utils/docsLinks.ts`
- Create: `web_app/src/utils/docsLinks.test.ts`
- Test: `web_app/src/utils/docsLinks.test.ts`

**Interfaces:**
- Consumes: `import.meta.env.PROD` (same pattern as `Home.tsx` / `OpenSource.tsx`)
- Produces:
  - `docsUrl(path: string): string`
  - `DOCS_INTRO: string`
  - `ADMIN_GUIDE_BY_PATH: Readonly<Record<string, string>>`
  - `adminGuideHref(pathname: string): string | null`

- [ ] **Step 1: Write the failing test**

Create `web_app/src/utils/docsLinks.test.ts`:

```typescript
import { describe, expect, it } from 'vitest'
import {
  ADMIN_GUIDE_BY_PATH,
  DOCS_INTRO,
  adminGuideHref,
  docsUrl,
} from './docsLinks'

describe('docsUrl', () => {
  it('joins the docs base with a rooted path', () => {
    const url = docsUrl('/development/ai-policy-analysis')
    expect(url.endsWith('/docs/development/ai-policy-analysis')).toBe(true)
    expect(url.includes('//docs/')).toBe(false)
  })

  it('normalizes a path missing the leading slash', () => {
    expect(docsUrl('intro')).toBe(docsUrl('/intro'))
  })
})

describe('DOCS_INTRO', () => {
  it('points at the docs intro page', () => {
    expect(DOCS_INTRO).toBe(docsUrl('/intro'))
  })
})

describe('ADMIN_GUIDE_BY_PATH / adminGuideHref', () => {
  it('maps the three admin screens from the contract', () => {
    expect(ADMIN_GUIDE_BY_PATH['/admin/batch-jobs']).toBe(
      '/development/ai-policy-analysis',
    )
    expect(ADMIN_GUIDE_BY_PATH['/admin/meeting-kinds']).toBe(
      '/development/jev-meeting-kind-gate',
    )
    expect(ADMIN_GUIDE_BY_PATH['/admin/application-links']).toBe(
      '/development/data-center-application-links',
    )
    expect(ADMIN_GUIDE_BY_PATH['/admin/lighthouse-report']).toBeUndefined()
  })

  it('resolves exact and nested admin paths to absolute guide URLs', () => {
    expect(adminGuideHref('/admin/batch-jobs')).toBe(
      docsUrl('/development/ai-policy-analysis'),
    )
    expect(adminGuideHref('/admin/batch-jobs/run/abc')).toBe(
      docsUrl('/development/ai-policy-analysis'),
    )
    expect(adminGuideHref('/admin/lighthouse-report')).toBeNull()
    expect(adminGuideHref('/settings')).toBeNull()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web_app && npm test -- --run src/utils/docsLinks.test.ts`

Expected: FAIL (module not found / cannot resolve `./docsLinks`)

- [ ] **Step 3: Write minimal implementation**

Create `web_app/src/utils/docsLinks.ts`:

```typescript
/** Absolute Docusaurus links for the Vite app (prod vs local docs origin). */

const DOCS_ORIGIN = import.meta.env.PROD
  ? 'https://www.communityone.com/docs'
  : 'http://localhost:3000/docs'

/** Build an absolute docs URL. `path` is under the docs root (e.g. `/intro`). */
export function docsUrl(path: string): string {
  const rooted = path.startsWith('/') ? path : `/${path}`
  return `${DOCS_ORIGIN}${rooted}`
}

export const DOCS_INTRO = docsUrl('/intro')

/**
 * Admin app path → docs path (no `/docs` prefix; `docsUrl` adds the origin).
 * Lighthouse intentionally omitted until a dedicated page exists.
 */
export const ADMIN_GUIDE_BY_PATH: Readonly<Record<string, string>> = {
  '/admin/batch-jobs': '/development/ai-policy-analysis',
  '/admin/meeting-kinds': '/development/jev-meeting-kind-gate',
  '/admin/application-links': '/development/data-center-application-links',
}

/** Absolute Guide href for an admin pathname, or null when unmapped. */
export function adminGuideHref(pathname: string): string | null {
  const entry = Object.entries(ADMIN_GUIDE_BY_PATH).find(
    ([appPath]) => pathname === appPath || pathname.startsWith(`${appPath}/`),
  )
  return entry ? docsUrl(entry[1]) : null
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web_app && npm test -- --run src/utils/docsLinks.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web_app/src/utils/docsLinks.ts web_app/src/utils/docsLinks.test.ts
git commit -m "$(cat <<'EOF'
feat(web): add docsLinks helper for intro and admin guides

Central prod/local docs URLs and ADMIN_GUIDE_BY_PATH for #714.

EOF
)"
```

---

### Task 2: Profile menu Documentation link

**Files:**
- Modify: `web_app/src/components/SiteHeader.tsx` (avatar dropdown, after Settings / before Data explorer)

**Interfaces:**
- Consumes: `DOCS_INTRO` from `../utils/docsLinks`
- Produces: menu anchor labeled `Documentation` opening intro in a new tab

- [ ] **Step 1: Import `DOCS_INTRO`**

At top of `SiteHeader.tsx`, add:

```typescript
import { DOCS_INTRO } from '../utils/docsLinks'
```

Keep existing `adminPaths` / `dataExplorerPaths` imports unchanged.

- [ ] **Step 2: Insert the Documentation menu item**

Inside the authenticated `showLoginMenu` block, **after** the Settings button and **before** the Data explorer button, add:

```tsx
<a
  href={DOCS_INTRO}
  target="_blank"
  rel="noopener noreferrer"
  onClick={() => setShowLoginMenu(false)}
  style={{ ...menuBtn, textDecoration: 'none' }}
>
  Documentation ↗
</a>
```

Do not admin-gate this item. Do not change Databricks / Sign out blocks.

- [ ] **Step 3: Sanity-check TypeScript**

Run: `cd web_app && npx tsc --noEmit -p tsconfig.json 2>&1 | tail -20`

Expected: no errors from `SiteHeader.tsx` / `docsLinks.ts`

- [ ] **Step 4: Commit**

```bash
git add web_app/src/components/SiteHeader.tsx
git commit -m "$(cat <<'EOF'
feat(web): add Documentation link to avatar menu

Signed-in users open docs intro in a new tab (#714).

EOF
)"
```

---

### Task 3: AdminLayout contextual Guide

**Files:**
- Modify: `web_app/src/components/AdminLayout.tsx`

**Interfaces:**
- Consumes: `adminGuideHref(pathname: string): string | null` from `../utils/docsLinks`
- Produces: at most one `Guide ↗` anchor in the admin header when mapped

- [ ] **Step 1: Import and resolve guide href**

Add import:

```typescript
import { adminGuideHref } from '../utils/docsLinks'
```

After the `onMeetingKinds` / tab booleans (still inside the component, after the admin gate), add:

```typescript
const guideHref = adminGuideHref(pathname)
```

- [ ] **Step 2: Render Guide in the header**

Change the header title row so Guide sits beside the title when present. Replace the lone `<h1>Admin</h1>` with:

```tsx
<div className="flex items-start justify-between gap-3">
  <h1 className="text-lg font-semibold leading-tight text-slate-900 sm:text-xl">
    Admin
  </h1>
  {guideHref ? (
    <a
      href={guideHref}
      target="_blank"
      rel="noopener noreferrer"
      className="shrink-0 text-sm font-medium text-teal-800 hover:underline"
    >
      Guide ↗
    </a>
  ) : null}
</div>
```

Leave tab nav and the existing helper paragraphs unchanged. On Lighthouse, `guideHref` is null → no Guide.

- [ ] **Step 3: Confirm lookup for the three mapped routes**

In a Vitest one-liner already covered by Task 1; optionally re-run:

Run: `cd web_app && npm test -- --run src/utils/docsLinks.test.ts`

Expected: PASS

Manual smoke (optional if docs + app running): open `/admin/batch-jobs` as admin → Guide goes to AI Policy Analysis; `/admin/lighthouse-report` → no Guide.

- [ ] **Step 4: Commit**

```bash
git add web_app/src/components/AdminLayout.tsx
git commit -m "$(cat <<'EOF'
feat(web): show contextual Guide link on admin screens

Batch jobs → ai-policy-analysis; meeting kinds and application links
map via docsLinks (#714).

EOF
)"
```

---

### Task 4: Hub doc — AI Policy Analysis + Data centers drill-down

**Files:**
- Modify: `web_docs/docs/development/ai-policy-analysis.md` (insert near the top, after the existing Overview / before Quick Start)

**Interfaces:**
- Consumes: existing sibling pages under `web_docs/docs/development/`
- Produces: operator-facing hub section with Data centers drill-down links (no fabricated numbers)

- [ ] **Step 1: Insert the operator hub section**

Immediately after the Overview bullet list (before `## Quick Start` / the garbled Quick Start heading), insert:

```markdown
## Operator hub (meeting analyze pipeline)

The live caption → screen → analyze path for jurisdiction meetings is operated
from **Admin → Batch jobs** (`/admin/batch-jobs`). Use this page as the entry
guide from that screen; drill down below for cohort and Jev details.

Related:

- [Jev transcript screening](./jev-transcript-screening.md) — chunked meeting-kind / decision / topic flags
- [Jev meeting-kind analysis gate](./jev-meeting-kind-gate.md) — keep-score gate before Gemini analyze
- [Jev-light cascade](./jev-light-cascade-design.md) — screen everyone, short blurb for keepers, full analyze for high-value keepers

### Data centers

For the **Data centers** cohort on the batch-jobs dashboard (site-belt ∪ mention
jurisdictions), start here then open the cohort contract:

- [Data centers cohort on batch jobs](./batch-jobs-data-centers-cohort.md) — launch `cohort=data_centers`, cascading filters, stage-report scope

Do not invent backlog counts or dollar figures on this page; pull live totals
from Admin → Batch jobs or the warehouse.
```

Keep the rest of the historical Ollama / bill-analysis content below; do not delete it in this task unless a paragraph directly contradicts the hub (if so, add one sentence pointing operators at Batch jobs for the current path).

- [ ] **Step 2: Verify relative links resolve**

Confirm these files exist on the branch:

- `web_docs/docs/development/batch-jobs-data-centers-cohort.md`
- `web_docs/docs/development/jev-meeting-kind-gate.md`
- `web_docs/docs/development/jev-transcript-screening.md`
- `web_docs/docs/development/jev-light-cascade-design.md`

Run: `ls web_docs/docs/development/{batch-jobs-data-centers-cohort,jev-meeting-kind-gate,jev-transcript-screening,jev-light-cascade-design}.md`

Expected: all four listed

- [ ] **Step 3: Docs build smoke (optional locally)**

Run: `cd web_docs && npm run build 2>&1 | tail -30`

Expected: build succeeds (or rely on CI Documentation Build)

- [ ] **Step 4: Commit**

```bash
git add web_docs/docs/development/ai-policy-analysis.md
git commit -m "$(cat <<'EOF'
docs(web_docs): AI policy hub with Data centers drill-down

Batch-jobs Guide lands here; cohort and Jev pages linked as siblings (#714).

EOF
)"
```

---

### Task 5: PR

**Files:**
- None new (push branch + open PR)

- [ ] **Step 1: Push branch**

```bash
git push -u origin HEAD
```

- [ ] **Step 2: Open PR**

```bash
gh pr create --base main --title "feat(web): profile Docs link and admin contextual guides" --body "$(cat <<'EOF'
## Summary

- One **Documentation** item on the avatar menu → docs intro
- Shared `docsLinks` map; Admin **Guide ↗** on batch jobs / meeting kinds / application links
- Batch jobs Guide → AI Policy Analysis hub with Data centers drill-down in docs

Closes #714

## Design

- [app-docs-linking-design](web_docs/docs/development/app-docs-linking-design.md)
- [app-docs-linking-plan](web_docs/docs/development/app-docs-linking-plan.md)

## Test plan

- [ ] Vitest: `cd web_app && npm test -- --run src/utils/docsLinks.test.ts`
- [ ] Signed in: avatar → Documentation opens intro (new tab)
- [ ] Admin → Batch jobs: Guide → ai-policy-analysis; Lighthouse: no Guide
- [ ] Hub page shows Data centers link to cohort doc
- [ ] CI: Frontend Build + Documentation Build green

EOF
)"
```

- [ ] **Step 3: Wait for required checks; merge when green**

Prefer review; solo maintainer may `gh pr merge <n> --squash --admin` only if that is the repo stopgap.

---

## Spec coverage (self-review)

| Spec requirement | Task |
|---|---|
| Profile Documentation → intro | Task 2 |
| `docsLinks` / `DOCS_INTRO` / map | Task 1 |
| Batch jobs → ai-policy-analysis | Tasks 1, 3 |
| Meeting kinds / application links Guides | Tasks 1, 3 |
| No Lighthouse Guide | Tasks 1, 3 |
| Hub Data centers drill-down | Task 4 |
| Out of scope product-wide Guides | Not scheduled |
| Issue + PR | Task 5 / #714 |
