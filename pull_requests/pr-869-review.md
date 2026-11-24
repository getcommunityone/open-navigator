---
pr: 869
branch: docs/868-operations-finance
title: "docs(web_docs): add an Operations tab with a Finance section"
author: jcbowyer
reviewed_at: 2026-11-24
reviewer: github-actions, coordinator
head_sha: 34b8a3cfe28e066c7d87b8d2d70e3c8a9f02fed2
verdict: approve-with-nits
---

# PR Review: docs(web_docs): add an Operations tab with a Finance section

## Summary

Adds an "Operations" tab to the docs with a Finance section: an overview of what costs money and where each figure
comes from, an expense log seeded with the owner's usage report for November 19 to 24, and a log of decisions taken
to save money. Documentation only.

The automated scan (#648) wrote the first version of this file; the agent that opened the PR refined it.

## Scope of Change

- `web_docs/docs/operations/finance/expense-log.md`
- `web_docs/docs/operations/finance/overview.md`
- `web_docs/docs/operations/finance/savings-decisions.md`
- `web_docs/docusaurus.config.ts`
- `web_docs/sidebars.ts`

## CI Status

See the PR checks on `34b8a3cfe28e`.

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets / credentials: clean (heuristic)
- Fabricated data / personal / destructive: clean. Every figure is copied from the owner's usage report, a provider's pricing page or an existing design page; totals were recomputed from the rows; expectations are labelled as arithmetic; unknown amounts are written as unknown. No keys or account details.

## Strengths

- Each expense row says whether it is an estimate or an owner-reported amount, and names its source.
- The mismatch between the DeepSeek estimate (24.01) and the balance that ran out (20.00) is stated, not smoothed over.
- Each decision records whether its effect has been measured; none has yet, and the page says so.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

- The docs site is public, so the amounts are public. The PR asks the owner to confirm that is acceptable.

### 🔵 Nit (Minor)

- The logs are kept by hand. Nothing yet reminds anyone to add a row after a paid run; a standing rule in
  `AGENTS.md` would be a separate, owner-approved change.
- Hosting and GPU costs are listed as unknown.

## Verdict

**approve-with-nits**
