---
pr: 592
branch: chore/378-otel-pins
title: "chore(deps): group OpenTelemetry security updates and record why"
author: jcbowyer
reviewed_at: 2026-11-18
reviewer: AI agent (Cursor subagent), read-only; this is a written review, not a GitHub approval
verdict: approve-with-nits
---

# PR Review: chore(deps): group OpenTelemetry security updates and record why

## Summary
The PR adds `.github/dependabot.yml` (a `pip` entry for `/` and for `/apps/open-navigator-web`, each with an
`opentelemetry` group, `applies-to: security-updates`, pattern `opentelemetry-*`, `open-pull-requests-limit: 0`) and a
decision page, `opentelemetry-pins.md`. The config parses and CI is green. The page's table of which OpenTelemetry package
needs which is accurate (checked against installed metadata). The PR is honest that it cannot show the real goal, "the
next advisory doesn't produce a failing PR". The repo's own Dependabot history makes that goal unlikely to be met by this
change, for two reasons: the failing PRs came from the `uv` ecosystem, which this file does not configure, and Dependabot
already grouped them and still bumped only the vulnerable package. Nothing here can break anything, so this is
approve-with-nits. `Closes #378` should become `Refs #378`, and the page should record the evidence below.

## Scope of Change
- Files changed: 2 (+98 / -0, no generated files)
- Areas touched: ci (Dependabot config), web_docs
- Commits: `216faba6` chore(deps): group OpenTelemetry security updates and record why
- Range reviewed: `0ba4fcd2..216faba6` (`origin/main` merge-base to head; base branch is `main`)

## CI Status
| Check | Status |
|---|---|
| Frontend Build (TypeScript + Vite) | success |
| Documentation Build (Docusaurus) | success |
| Backend Tests (Python) | success |
| API Types (OpenAPI -> TypeScript) | success |
| PR conventions (linked issue) | success |
| Detect Docker-relevant changes | success |
| Docker Build Test (Full Stack) | skipped (not required) |

## Scans (secrets, fabricated data, personal data, destructive data changes)
- **Secrets:** clean. A pattern scan of the diff found no keys, tokens or credentialed URLs.
- **Fabricated data in a served path:** clean. Nothing under `api/` or `web_app/src/`. The only figures in the diff are
  package versions, and they match the repo.
- **Personal data:** clean.
- **Destructive or bulky data changes:** clean. Two small text files are added and nothing is deleted.

## Strengths
- It writes the decision under `web_docs/docs/development/` with frontmatter and a dated issue link, as `AGENTS.md`
  asks. The "What is not proven" section is candid, and the PR body repeats it.
- The dependency table is accurate. I checked it against the `.venv` metadata (1.42.0 / 0.63b0): `opentelemetry-sdk` needs
  `api==` and `semantic-conventions==`, and `instrumentation-fastapi` needs `semantic-conventions==`, `instrumentation==`
  and `util-http==` at the twin version. `exporter-otlp-proto-http` needs `common==`, `proto==` and `sdk~=` the same
  minor. The metadata for the asyncpg instrumentation package isn't installed locally, so I could not check it.
- The incident dates and PR numbers (#364, #375, #376 on 2026-11-15) match GitHub.
- The manual family bump is a usable fallback. Version updates stay off, and `uv` was left out rather than guessed at.
- `sidebar_position: 39` is unique in `development/`. The YAML parses with `yaml.safe_load` and has the expected shape.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **`.github/dependabot.yml:14-33`: the config covers `pip`, but the three PRs that broke the install were `uv`
   PRs.** #364, #375 and #376 have head branches `dependabot/uv/uv-…` and titles "bump the **uv** group". The Dependabot
   commit on #375 edited `uv.lock`, `packages/*/pyproject.toml` and all of `requirements.txt`,
   `requirements-cpu.txt` and `apps/open-navigator-web/requirements.txt`; its `requirements.txt` diff is
   `-opentelemetry-api==1.42.0` / `+opentelemetry-api==1.45.2` with `opentelemetry-sdk==1.42.0` unchanged.
   The same advisory also produced `pip` PRs (#377, closed, 3 updates including `opentelemetry-api`). This config
   shapes only `pip`. After merging, the next `opentelemetry-*` advisory still makes the `uv` ecosystem open the
   one-line api bump that fails `pip install`. The PR body says `uv` was left out on purpose because a bad entry "could
   disable security updates for it". That is a real risk but unverified. The body does not say that the failing PRs
   were `uv` PRs, so the reader would think the config addresses them. *Verified:* `gh pr view 364|375|376` (branch,
   body, commit diff); `gh pr list --author app/dependabot` shows 12 `uv` and 3 `pip` PRs.
   *Fix:* either add a `uv` entry with the same group (for `/` and `/apps/open-navigator-web`) after reading
   GitHub's docs for it, or state on the page and in the PR that this config does not cover the ecosystem that produced
   #364, #375 and #376.

2. **`opentelemetry-pins.md` "What is not proven": the repo's history already answers the first open question, and
   the answer is the unwelcome one.** The question is whether a group pulls in family members that have no advisory.
   The existing default groups ("pip group", "uv group" in #364, #376 and #377) are already groups. Their bodies list
   only the packages that had advisories: #375 lists only `opentelemetry-api`, and #377 lists only `aiohttp`,
   `opentelemetry-api` and `python-jose`. Dependabot security updates change only vulnerable packages, so a group named
   `opentelemetry` will most likely hold only `opentelemetry-api` when only the api has an advisory. That is the same
   one-line PR as before. *Verified:* PR bodies for #364, #375, #376 and #377. I did not run Dependabot, so the claim
   is "most likely", not shown. *Fix:* add this evidence to the page. Keep the issue open until an advisory is seen to
   produce a working PR. The "Done when" line "the next OpenTelemetry advisory doesn't produce a PR that fails install"
   is not met by this change, so use `Refs #378` rather than `Closes #378`. Consider recording a deterministic fallback
   next to the manual bump, such as dropping the separate `opentelemetry-api` pin so the sdk pin alone sets the api.
   That option is in #378 and the page says why it wasn't chosen.

### 🔵 Nits / suggestions (Minor)
3. **`opentelemetry-pins.md:46-47`: "Whether Dependabot reads `requirements-cpu.txt`" is already answered.**
   #375 and #377 (both Dependabot) edited `requirements-cpu.txt` (and #375 `requirements-intel.txt`). Say so on the page.
4. **`.github/dependabot.yml:12`: the header says other ecosystems keep default behavior, but `pip` itself is now
   configured.** Security-update groups defined in `dependabot.yml` replace the repo's default grouping for that
   ecosystem and directory. Other `pip` advisories (aiohttp, python-jose) may now open individual PRs instead of one
   "pip group" PR. I could not verify this without running Dependabot. Note it on the page as a possible side effect.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Issue first | Partial | Branch `chore/378-otel-pins` and `Closes #378` are correct in form. #378 has Problem, Done when, Contract and Read first. The "Done when" check is not met (finding 2), so `Refs` fits better |
| Conventional Commits | Yes | `chore(deps): …` (no agent co-author trailer seen; not required unless an agent wrote it) |
| No fabricated data | Yes | Scan clean |
| New Python in `packages/` | n/a | No Python |
| dbt for transformations | n/a | |
| Naming / Keys / Calendar years | n/a | |
| Scope label / match evidence | n/a | No UI |
| Docs | Yes | `web_docs/docs/development/opentelemetry-pins.md`, kebab-case, frontmatter, decision recorded; Documentation Build is green |
| Telemetry and logging | n/a | |
| Tests | n/a | A config and a doc change. Nothing here can be unit-tested; the claim can be tested only by the next advisory |
| Shared libraries | n/a | No `packages/` change |

## Test Coverage
- No code changed, so no pytest, ruff, tsc or dbt run was needed. dbt and the warehouse were not touched.
- **Run locally:** `yaml.safe_load(.github/dependabot.yml)` parses with the expected keys. The `.venv` metadata for
  `opentelemetry-sdk`, `-instrumentation-fastapi`, `-instrumentation` and `-exporter-otlp-proto-http` was compared with
  the page's table.
- **Not testable here (unverified):** that `applies-to: security-updates` plus `patterns` pulls in the family, and
  that adding this file leaves other `pip` security updates grouped as before. This depends on Dependabot itself.
  I checked the PR's claims about Dependabot only against the repo's own PR history.

## Verdict
**approve-with-nits.** The change is safe to merge, and its documentation is accurate and honest about its limits.
Before merging, switch `Closes #378` to `Refs #378` so the issue stays open until a real advisory shows the result.
Record in the page that the failing PRs were `uv` PRs, which this file doesn't cover (finding 1), and that default
groups already included only the vulnerable packages (finding 2). The two nits can go in the same edit.
