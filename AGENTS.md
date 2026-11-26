# AGENTS.md

Rules for every coding agent working in this repository (Claude Code, Codex, Cursor, Copilot and others), and for
people too. `CLAUDE.md` imports this file. Read `CLAUDE.md` as well: it holds the architecture, data, UX,
documentation and commit rules, and they apply to every agent.

## Issues first: log the work before you start

Every change starts from a GitHub issue, and agents open it themselves. Don't wait to be asked.

1. **Search open issues first.** If one already covers the work, use it. If not, open one before the first commit.
2. **Title:** `<type>(<scope>): <what changes>`, in the Conventional Commit style used for commits
   (for example `fix(census): Connecticut counties render blank on the county map`).
3. **Labels:** `bug`, `enhancement`, `documentation`, or the feedback labels (`ux-friction`, `copy/content`,
   `feature-request`, `validated`). Follow-ups get `action-item`.
4. **One issue, one pull request.** A larger story is split into issues, and each PR closes one.

## What an issue says

Write all four parts, as headings, before the first commit. The template is `.github/ISSUE_TEMPLATE/work-item.md`.

**Planned work opens with an Attributes table.** When the work belongs to the quarter's plan (a PI epic and its user
stories, filed as parent issues and sub-issues), the issue starts with a table that names its `Epic` and `User story`
as markdown links to their issues, plus `PI · Sprint` and `Points` where the plan gives them. A story links its epic and
says "this issue" for itself. A task, bug or follow-up under a story links both. The pull request repeats the table, so
a reader can go from any change to the story and the epic it serves. Examples: the CORE epic #235, its story #242,
and that story's pull request #253.

- **Problem:** what is wrong or missing, and who it affects, with the evidence linked (a failing test, a log line,
  a screenshot, a feedback issue).
- **Done when:** one line per check a test or reviewer will make.
- **Contract:** every name a test or another layer will use that isn't in the repository yet. For an API, that's
  the path, parameters and response fields. For data, it's the dbt model or table, its grain (one row per what), its
  typed columns, its primary key and its foreign keys (see `CLAUDE.md`, "Data Pipeline Standards"). For the UI, it's
  the route and the URL parameters it reads.
- **Read first:** the files to change, and the rules and docs that govern them.

If a name has to change later, add a dated line to the issue. Never rewrite the original text: it records what was
asked.

## Log what you find, as you go

- **Follow-ups become issues, not notes.** Anything out of scope that you notice (a bug, a missing test, a stale doc)
  gets its own issue, labelled `action-item`, with the four parts and the evidence. Link it from your PR. Never leave
  it only in a TODO comment or a line of PR text.
- **Failures become issues.** When CI, a data load or a run fails for a reason your change doesn't fix, open a
  `bug` issue with the failing command, the error line and where it ran. Then carry on with your own work.
- **Feedback becomes issues.** A reviewer's or user's feedback gets one issue per concrete item (as #137 to #151
  were), each linked to the feedback issue it came from.
- **Decisions are written down.** A choice and its reason go in a page under `web_docs/docs/development/`, linked
  from the issue. Never leave a decision only in an issue or PR thread.

## Docs with the change

If a change alters behavior, contracts, operator UI, or data grain, the **same PR** updates or adds the governed
page under `web_docs/docs/`. Name that page in the issue **Done when** and in the PR body.

Keep publishing new designs and plans under `web_docs/docs/development/` (Working notes). **Archive is for
pages that are wrong or misleading** (wrong paths, superseded product story) — not for every doc whose issue
already shipped. If you find a wrong page mid-work: fix it, `git mv` it into `web_docs/docs/development/archive/`,
or open an `action-item` when the rewrite is out of scope. Do not leave “TODO: fix docs” only in the PR.

Lifecycle: [Development docs hygiene](web_docs/docs/development/development-docs-hygiene-design.md).

## Branches and pull requests

- **Branch:** `<type>/<issue>-<slug>`, for example `fix/71-ct-county-map`. The type is a Conventional Commit type
  (`feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`, `ci`, `build`, `revert`), then the issue number, then
  a lowercase slug of at most 40 characters. Branches a tool names (`dependabot/*`, `renovate/*`) stay as they are.
- **Pull request:** the description says `Closes #<issue>` (or `Refs #<issue>` for one part of a larger issue), so
  merging closes it.
- **The `PR conventions` check** (`.github/scripts/pr_conventions.py`) enforces both on every pull request opened from
  November 14, 2026. It also checks that the linked issue has the four parts, each with text under it (the
  template's guidance is in comments, so an unfilled template fails). It runs when the PR changes, not when the
  issue does: after fixing the issue, re-run the check from the PR's Checks tab.
- **Open and review with the two prompts.** `/create-pr` (`.claude/commands/create-pr.md`) checks the branch, opens
  the PR and reviews it. `/pr-review` (`.claude/commands/pr-review.md`) reviews any PR against
  `.claude/review-rubric.md` and writes `pull_requests/pr-<n>-review.md`. The review is committed to the PR's branch.
  Agents without slash commands read those files and follow the same steps. Every PR gets a review before it merges.
- **An agent merges its own PR when it's ready, without waiting to be told** (standing rule, #758; same practice as
  health-transformation-lab-nlp #497). Ready means every required check is green on the latest commit, there is no
  merge conflict, and `pull_requests/pr-<n>-review.md` finds nothing blocking (`verdict:` is `approve` or
  `approve-with-nits`, not `request-changes`). Squash-merge with admin when GitHub blocks self-approval
  (`gh pr merge <n> --squash --admin`; `enforce_admins` is off on `main`). These still wait for the owner to say
  "merge":
  - a PR that starts a run on limited or paid compute (GPU / Colab, WhisperX diarization, paid LLM endpoints);
  - one that publishes outside this repo (Hugging Face, production deploy, the public docs site beyond a normal merge);
  - one that deletes data, warehouse tables or branches, or changes these agent rules;
  - one the owner has said to hold.

  Before merging, check open PRs and recent commits on `main` for the same work. If another session already did it,
  close yours and say so. Enforcing that the review file exists in CI is #648.
- Everything in `CLAUDE.md`, "Branch & PR Workflow" still applies: never push to `main`, never force-push, required
  checks green before merge.

## Privacy and data ethics

Citizens' privacy comes first. Every agent follows these rules, the minimum the law requires and the standard we hold
ourselves to. The reasons and the laws behind them:
[Privacy and data ethics](web_docs/docs/development/privacy-and-data-ethics.md) (#1080). When a rule and a task
conflict, the rule wins: stop and ask the owner.

- **Public role or private person.** Officials, staff acting in their role, and organizations are public. Their
  official contact details, votes and statements may be stored and shown. A private resident who spoke at a meeting is
  shown only as the record shows them, with the name shortened to "First L.". We never enrich a private person with a
  home address, workplace, church, school, family, social accounts or personal email, from any source (brokers,
  people-search sites, scraping or AI). See [People in meetings](web_docs/docs/development/people-claim-and-privacy.md).
- **Sensitive data is never tied to a private person.** That covers health conditions, religion, race or ethnicity,
  immigration status, sexual orientation, disability, criminal history, finances and precise home location. We aren't
  a HIPAA covered entity, but health details are treated as protected: a speaker who mentions an illness is not tagged
  with it. Aggregates with no one identifiable are fine.
- **Minors and students.** Never name, quote or tag a child or student identified in a meeting or document (school
  board meetings, FERPA). No accounts under 13 (COPPA).
- **AI tagging and extraction.** Prompts and classifiers (Gemini, Jev, Claude) may tag what was said, the topic,
  stance and outcome. They may not infer a person's sensitive traits, motives or identity beyond the record. Speaker
  names stay "First L." in served data.
- **Scraping.** Fetch public pages only:
  - Never log in, bypass a paywall or CAPTCHA, or disguise who we are (no spoofed browser identity or rotating
    proxies to get past a block).
  - Honour robots.txt and the site's terms. A 403 or 429 means stop or back off, not retry harder.
  - Identify as `open-navigator` and keep requests slow.
  - Where terms forbid automated collection, cite or link instead of scraping (as with job boards, #1019).
- **Contact.** Never email, text or call a private person who hasn't asked us to. Officials are contacted only at
  their official address, by the owner, never automatically. Any bulk email follows CAN-SPAM: who it's from, why,
  and how to opt out.
- **Our users' data.** Collect only what a feature needs, and say why. Keep it no longer than needed (a looked-up
  address is used, not stored), never sell or share it, and delete it on request. Never log emails, tokens, exact
  locations or chat text with an identity attached.
- **Correction and removal.** Anyone shown on the site can ask to correct, hide or remove how we show them (#1064).
  A removal request is honoured even without full verification when the risk to them is plausible.
- **Blocking in review.** A PR that adds private personal data, ties sensitive data to a person, names a minor,
  scrapes against a site's terms or contacts people unasked is 🔴 Blocking (`.claude/review-rubric.md`).

## Context for models and agents

Anything a model reads (a prompt, a transcript, a tool result, this repository) is context, and it's engineered like
code. The six principles and where each applies: [Context engineering](web_docs/docs/development/context-engineering.md).

- **Send the least that answers the question.** Split at units of meaning (caption segments, sections), and load
  detail with a tool when it's needed rather than up front.
- **Read the governed layer.** Models and the API read `public` (or Unity Catalog), never `bronze` or `gold` directly;
  access rules belong to the data, not to a prompt.
- **Carry the source forward.** Every derived row, quote or answer keeps the ID and link of the record it came from.
- **Say how current it is.** A table a model or the site reads has a freshness target and a last-updated date.
- **Version and test it.** Prompts, output schemas and tool definitions live in git with a version that changes when
  they do, and are checked against known answers, not by asking another model whether the result looks right.

## GPU and paid compute

GPU steps (WhisperX diarization, local Gemma generation; #262, #297) run on paid or shared machines. The decision and
its reasons: [GPU compute decisions](web_docs/docs/development/gpu-compute-decisions.md) (#357).

- **GPU runs go to the owner's Colab, never the Kaggle account.** The Kaggle GPU pool is kept for
  health-transformation-lab-nlp's competition work. The Colab compute units are one subscription shared with that
  project, so one project's run can leave the other short.
- **A paid GPU run starts only on the owner's explicit yes** for that run, given in the session that starts it; "do
  what you recommend" doesn't.
- **Read usage before and after every GPU run** (its `gpu_run` rows, `packages/llm/src/llm/usage/gpu.py`, and the
  compute units Colab shows) and put the cost in the run's issue or PR.
- **Recorded outputs and CPU come first.** Re-run a question on outputs already saved, or on CPU, before asking for a
  GPU; a GPU run is for what they can't answer.
