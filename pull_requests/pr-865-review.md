---
pr: 865
branch: fix/864-strategic-plan-pdf
title: "fix(web_app): store the strategic plan PDF in LFS so the live site can serve it"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: 03c19aea13631617c32a814167f39438c2e4feb2
verdict: approve-with-nits
---

# PR Review: fix(web_app): store the strategic plan PDF in LFS so the live site can serve it

## Summary

The Strategic Plan popup showed the app's 404 page on the live site because the PDF never reached the server: the
deploy drops raw binaries, and the file's upper-case `.PDF` extension was not matched by the case-sensitive
`*.pdf` LFS rule. The PR renames the file so it is stored in LFS, updates the two links, and adds two tests. The
cause was confirmed against the live site; the cure can only be confirmed after a deploy.

The automated scan (#648) wrote the first version of this file; the agent that opened the PR refined it.

## Scope of Change

- `tests/test_gitattributes_lfs.py`
- `web_app/public/pdf/c1_strategic_plan.PDF`
- `web_app/public/pdf/c1_strategic_plan.pdf`
- `web_app/src/pages/Home.tsx`
- `web_app/src/pages/HomeV9.tsx`
- `web_docs/static/pdf/c1_strategic_plan.PDF`
- `web_docs/static/pdf/c1_strategic_plan.pdf`

## CI Status

See the PR checks on `03c19aea1363`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: clean (heuristic)
- Fabricated data / personal / destructive: clean. The two deletions are the old names of the renamed file; its content is unchanged (same 136,930 bytes, now an LFS object).

## Strengths

- The cause is shown with evidence (the live URL returns HTML) and traced to the exact rule and deploy pass.
- The tests guard both halves: a served PDF outside LFS, and a linked path whose file name differs by case.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

- Unverified until a deploy. If the live path still returns HTML afterwards, check that the deploy's LFS pass
  fetched this object from GitHub before pushing to Hugging Face.

### 🔵 Nit (Minor)

- A developer machine without git-lfs will check the PDF out as a text pointer and the popup will not render it.
- Any outside link to the old upper-case path now gets the app's 404 page, as it already did on the live site.

## Verdict

**approve-with-nits**
