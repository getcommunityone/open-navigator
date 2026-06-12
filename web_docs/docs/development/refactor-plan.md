---
title: Refactor & Tech-Debt Plan
description: Recommended, prioritized plan to reduce tech debt, remove dead code, and improve usability across the Open Navigator monorepo.
---

# Refactor & Tech-Debt Plan

A prioritized, measured plan for reducing tech debt, removing dead/duplicated code, and
improving contributor usability. It complements — and does not duplicate — the
[Cleanup Roadmap](./cleanup-roadmap.md) (the `scripts/ → packages/` backlog) and the
standing rules in `CLAUDE.md`.

## Snapshot (measured 2026-06-10)

- **2,215 files / ~547k LOC.** Python ~155k (787 files), TSX/TS ~47k, SQL ~24k,
  Markdown ~69k (271 files).
- `scripts/` (legacy, frozen): **176 `.py` / ~49k LOC across 22 subdirs** — only `colab`
  fully ported so far.
- `packages/` (target workspace): **475 `.py` / ~116k LOC** — the port is real but ~⅓ done.

The core (api, dbt, packages, `web_app/src`) is healthy. The debt is a crust of
**duplicated assets, stray entry points, orphaned tech stacks, and tracked build/log
artifacts** — most of it low-risk to remove.

## Themes

### 1. Ambiguous / heavyweight entry point
`main.py` (root) is the documented launcher (`start-all.sh → python main.py serve →
api.main:app`). Its module-level imports of `agents.*`, `ingestion.delta_lake`, and
`config` resolve only via editable-installed workspace packages
(`agents`→`packages/agents`, `config`→`packages/core`, `ingestion`→`packages/ingestion`;
`visualization` is already gone). Consequences:

- The lightweight `serve` path needlessly imports the entire agent/Delta-Lake stack.
- The flat top-level `agents` name **collides** with `packages/agents/agents`.
- A clone that has not run `uv sync` cannot start the API the documented way.

**Fix:** move the `agents.*` / `ingestion` imports into the commands that use them
(lazy imports); keep only what module init needs. `serve` then depends on just
`uvicorn` + `api.main:app`. (Done in the P0 PR.)

### 2. Duplicated static asset trees (largest bulk win)
`web_app/public/wikimedia/` (157 files) is **byte-identical** to `api/static/wikimedia/`.
Multi-MB state images (`GA_latest.jpg` 36 MB, `KS` 6 MB, `AK` 3.9 MB…) are committed in
**both** `api/static/wikicommons/` and `web_app/public/wikicommons/`. A built Vite bundle
(`api/static/assets/index-*.js`) is also checked in.

**Fix:** single source of truth in `web_app/public/`; have the build/deploy copy into
`api/static/`. Move large images to Git LFS/Xet. Stop committing built bundles.

### 3. Tracked junk & build artifacts
Tracked in git: `shard0/1/2.out`, `analyze_backlog_shard1.out`, `civicsearch_harvest.out`,
`tuscaloosa_run.out` (run logs, some actively appended by background shards), plus an
empty file literally named `git`. Untracked clutter: `, psycopg2`, `analyze.log`,
`debug.log`, `wget-log`, root `__pycache__/`.

**Fix:** `git rm` the artifacts, extend `.gitignore`, delete the junk filenames.
(Started in the P0 PR.)

### 4. Packaging sprawl
Root carries `pyproject.toml` + `setup.py` + **9 `requirements-*.txt`** + `uv.lock`, while
`CLAUDE.md` makes **uv canonical**. Four virtualenvs on disk (`.venv`, `.venv-dbt`,
`venv`, `dbt_project/.venv_dbt`) compound the ambiguity.

**Fix:** make `uv` + `pyproject.toml`/`uv.lock` authoritative; demote the
`requirements-*.txt` to clearly-labelled generated extras (or `uv export` outputs);
remove `setup.py` if unused; document the single bootstrap (`uv sync`) + the dbt sidecar.

### 5. Orphaned / out-of-scope stacks
`video_dont_know/` (182 MB manim project), `r/local_view/` (R), `django_ocd/` (106-LOC
Django stub), `scripts/**/archive/` (dead by definition), and
`web_app/policy-dashboards/` (a separate nested Vite app whose source includes a single
~17.5k-line checked-in bundle).

**Fix:** decide keep-vs-archive per item; move unrelated stacks to a separate repo or
`archive/` branch; delete `scripts/**/archive/`; if `policy-dashboards` is live, exclude
/ regenerate its bundle rather than tracking it.

### 6. Finish `scripts/ → packages/` (headline refactor)
22 `scripts/` subdirs remain. Priorities: triage `scripts/discovery/` (62 files / ~23k
LOC, much may be dead/superseded by dbt); clean ports next (`nccs`, `naco`, `ballotpedia`,
`nces`, `enrichment`, `enrichment_ai`); complex last (`wikidata`, `youtube`,
`google_civic`, `irs`). Triage-for-dead before porting. Route via
`python-packages-specialist`. Also fold the `scripts/` subdirs that live *inside*
`packages/hosting` and `packages/scrapers` into proper modules.

## Usability enhancements

1. **One-command clean-clone bring-up** (`uv sync && ./start-all.sh`) once Themes 1 & 4
   land; add a `make doctor` preflight (PG on :5433, dbt venv, node, required env).
2. **Trim onboarding docs** — 271 markdown files; add a single "Start here" page; prune
   the stale `guides/hackathon/` content (this is production work, not a hackathon).
3. **Split the 24 KB `.env.example`** into "required to boot" vs "optional integrations".
4. **Document real entry points** after Theme 1 and drop references to the broken path.

## Sequencing

| Phase | Work | Risk | Payoff |
|---|---|---|---|
| **P0** | Theme 3 junk sweep + `.gitignore`; Theme 1 lazy-import fix | Very low | Clean clone boots; de-littered |
| **P1** | Theme 2 de-dup assets + LFS images + stop committing bundles | Low | Largest size/dup win |
| **P2** | Theme 4 packaging → uv; Theme 5 archive orphan stacks | Low–med | Onboarding clarity |
| **P3** | Theme 6 finish `scripts/ → packages/`, triage-dead-first | Med | Retires legacy tree |
| **P4** | Usability docs / `make doctor` / `.env` split | Low | Contributor velocity |

## Guardrails

Branch per phase + PR (never push `main`); a parallel auto-committer is active — stage
only your own files and verify via `git log`; run touched-package `pytest` before any
`packages/` change; verify the dbt DAG before touching models; never delete `data/cache/`.
