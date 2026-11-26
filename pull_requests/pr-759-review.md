---
pr: 759
branch: docs/758-agent-merge-when-ready
title: "docs(agents): agents merge green PRs without waiting (#758)"
author: jcbowyer
reviewed_at: 2026-11-22
reviewer: coordinator
verdict: approve
---

# PR Review: docs(agents): agents merge green PRs without waiting (#758)

## Summary

Copies health-transformation-lab-nlp's standing merge rule (#497) into open-navigator agent docs so sessions squash-merge green PRs after a written rubric review, instead of leaving them parked on `REVIEW_REQUIRED`.

## Scope of Change

- `AGENTS.md`, `CLAUDE.md`, `.claude/commands/create-pr.md` only (docs / agent prompts)
- No application, warehouse, or CI workflow code

## CI Status

Required checks must be green on the head commit before merge (this PR).

## Scans (secrets, fabricated data, personal data, destructive data changes)

- Secrets: clean
- Fabricated data: none (docs only)
- Personal data: none
- Destructive data: none

## Strengths

- Aligns merge behavior with HTL, where the same owner already relies on agent auto-merge
- Keeps explicit exceptions for GPU/paid compute, external publish, destructive changes, and holds
- Documents `--admin` squash-merge under the existing required-review protection without turning off CI gates
- Points at #648 for CI enforcement of the review file (out of scope here, correctly)

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important)

None.

### 🔵 Nit (Minor)

None. Optional follow-up is already filed as #648 (existence check + Actions reviewer).

## Verdict

**approve** — docs match the intended standing rule; merge when required CI is green.
