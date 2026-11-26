---
pr: 1153
branch: fix/1152-security-deps
title: "fix(deps): clear the open Dependabot security alerts (npm and Python)"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: github-actions
head_sha: 8bd60bc7f8a9da4ec164dafde412bfee728350ce
verdict: approve
---

# PR Review: fix(deps): clear the open Dependabot security alerts (npm and Python)

## Summary

Automated review (#648) for PR #1153 on `fix/1152-security-deps`. Heuristic rubric scans ran on
`BASE...HEAD`; a human or agent `/pr-review` may refine this file.

## Scope of Change

- `api/auth.py`
- `apps/open-navigator-web/requirements.txt`
- `apps/rag-chat-app/package-lock.json`
- `apps/rag-chat-app/package.json`
- `requirements-cpu.txt`
- `requirements.txt`
- `uv.lock`
- `web_app/package-lock.json`
- `web_app/package.json`
- `web_app/policy-dashboards/package-lock.json`
- `web_app/policy-dashboards/package.json`
- `web_docs/package-lock.json`
- `web_docs/package.json`

## CI Status

See the PR checks on `8bd60bc7f8a9`.

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
