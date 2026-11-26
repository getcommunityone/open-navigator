---
pr: 1092
branch: docs/1088-businesses-design
title: "docs(development): design for Businesses in search"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: claude-code
verdict: approve
---

# PR Review: docs(development): design for Businesses in search

## Summary

Refs #1088. It adds the design page for the Businesses search type:
- why Nonprofits shows 0;
- the owner's five decisions of 2026-11-26;
- the two served tables;
- the typing and placing rules;
- the order of work across #1089, #1090 and #1091.

The decisions match the owner's answers in the session that asked them. Docs only. Approve.

## Scope of change

- `web_docs/docs/development/businesses-search.md` (new).

## Checks

- **The cause it states is right:**
  - `search_organizations_pg` reads `mdm_organization` joined to `mdm_organization_nonprofit` (`api/routes/search_postgres.py`) and returns `[]` on any exception;
  - both tables are in `NON_SERVING` (`packages/hosting/src/hosting/neon/sync_public_to_neon.py`);
  - so the hosted count is 0 because the tables are missing, not because they are empty.
- **The budget it quotes is the code's:** `DEFAULT_MAX_MB=480`, `NEON_HARD_CAP_MB=512`.
- **Links:** the four sibling pages it links exist under `web_docs/docs/development/`. `AGENTS.md` is linked on GitHub, since it sits outside the docs tree.
- **Docs rules:** kebab-case lowercase filename, YAML frontmatter, under `web_docs/docs/`.
- **No figures without a source:** the only numbers are the 4.2 million organizations (about 1.7 GB) the issue research found in the model's own comments, and the code's budget.

## Findings

- 🔵 The rule "named in records from two or more states" makes a company a corporation. A regional chain named in two neighbouring states counts too. That is acceptable, and #1089's tests will show how many it affects.

## Rules

| Rule | Result |
|---|---|
| Issue first, four parts | #1088 has them; PR says `Refs #1088` |
| Decisions written down | This page is the record |
| Docs with the change | This PR is the doc; the code PRs link it |
| No fabricated data | No invented figures |

## Verdict

approve
