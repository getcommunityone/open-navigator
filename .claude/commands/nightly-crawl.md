---
description: Run the meeting crawl, dbt rebuild and Neon publish on this machine (WSL), under the Neon size budget, then report
argument-hint: "[skip-youtube | publish-only] (default: everything)"
---

Run Open Navigator's crawl, rebuild and publish **on this machine**, then report. This is meant for a Claude Code
session started in WSL from the repo root, often driven from the owner's phone through Remote Control
(`claude remote-control --name "open-navigator WSL"`; see `web_docs/docs/development/nightly-crawl.md`). Argument:
`$ARGUMENTS`.

- `skip-youtube`: run everything except step 3.
- `publish-only`: run step 0, then steps 5 and 6.

Follow `AGENTS.md` and `CLAUDE.md`. Rules for the whole run:

- Never print secrets (`.env` values, tokens, cookies). Check that a variable exists with `grep -c '^NAME=' .env`.
- Never change VPN or proxy settings, never delete `data/cache/`, never force-push, never touch uncommitted work.
- Run long steps in the background with a log file (`nohup … > logs/nightly-<step>-$(date +%F).log 2>&1 &`), and check
  progress by reading the log, so the session stays responsive.
- Keep the owner posted with one short line when each step finishes. Phone-sized: counts, not logs.

## 0. Preflight

Stop and report if a **hard** check fails. A **soft** failure skips only the step it affects.

- **Hard:** in the repo root; `git status --porcelain` is empty (if not, list the files and stop; don't stash or
  reset). Then `git checkout main && git pull --ff-only`.
- **Hard:** the local warehouse answers: `pg_isready -h localhost -p 5433`.
- **Hard:** `.venv/bin/python -c "import hosting.neon.sync_public_to_neon"` works.
- **Hard for YouTube (step 3):** the VPN is up. `.venv/bin/python -m scrapers.youtube.vpn_guard` prints the
  tunnel and home interfaces with masked IPs and exits 0. YouTube is only ever reached through Surfshark, never the
  home IP (#488): with the VPN off, every YouTube step (catalog, captions, yt-dlp) and
  `youtube_run_priority_states_last_n.sh` stop with **exit 5**, before any YouTube request, and a mid-run drop stops
  the run the same way after saving what it has. On exit 5, don't retry and don't set `YOUTUBE_REQUIRE_VPN=0`:
  skip step 3, run the rest, and report "Surfshark is off: connect it, then re-run".
- **Soft (YouTube, step 3):**
  - `.env` has `PROXY_USER_NAME` and `PROXY_PASSWORD` (Webshare, for the caption API);
  - `youtube_cookies.txt` exists. Warn if it's older than 7 days: a stale cookie file is the usual cause of "Sign in
    to confirm you're not a bot";
  - if `YOUTUBE_TRANSCRIPT_PROXY` is set, it must be reachable from WSL. A VPN running on Windows isn't at
    `127.0.0.1` inside WSL; it's at the Windows host IP (`ip route | awk '/default/ {print $3}'`). Say so if that's
    the problem.
- **Soft (publish, step 5):** Neon resolves. The sync's own preflight exits 3 on a VPN/DNS failure; wait 2 minutes,
  retry once, then skip publishing and report.

## 1. Agendas (Tuscaloosa, SuiteOne)

```bash
.venv/bin/python -m scrapers.suiteone.scrape --portal-url https://tuscaloosaal.suiteonemedia.com \
  --jurisdiction-id tuscaloosa_0177256 --state AL --homepage-url https://www.tuscaloosa.com
.venv/bin/python -m scrapers.suiteone.doctext --jurisdiction-id tuscaloosa_0177256 --doc-types agenda,minutes
```

Report the documents found and the texts extracted.

## 2. Data center sites (Epoch AI, CC BY 4.0)

```bash
.venv/bin/python -m ingestion.data_centers.epoch_sites --dry-run
```

Exit 3 means Epoch renamed a column: don't load, report the headers it printed (issue #249). Otherwise run it again
without `--dry-run`.

## 3. YouTube crawl and analysis

```bash
./packages/scrapers/scripts/youtube_run_priority_states_last_n.sh all
```

- Keep the script's careful defaults: `STATES=AL,FL,GA,IN,MA,MT,WA,WI`, `N=10`, `DELAY=10`, `PARALLEL=1`. YouTube
  throttles by IP address, so don't shorten the delay or add parallel caption fetches.
- The analysis calls Gemini, a paid API (not a GPU). It analyzes only new videos, with the current prompt (jobs claims
  and speaker roles, #246, #247).
- If the log says "Stopping after N consecutive blocks", or shows repeated "IP blocked" or "rate limited": don't retry
  or loop. Note the last jurisdiction and the block count, and go on to step 4 with what was saved. Blocked videos
  aren't marked done, so the next run retries them.
- Report the videos captioned and analyzed, and the Gemini cost if `packages/llm` usage reporting shows it.

## 4. Rebuild

```bash
cd dbt_project && .venv_dbt/bin/dbt build --select +meeting_browse +event_decision +event_meeting_document \
  +job_claim +data_center_site +data_center_agenda_item +area_concern
```

If a model or an error-severity test fails, **stop before publishing**. Report the failing node and its error line,
and open a `bug` issue (AGENTS.md) unless tonight's data obviously caused it. Warn-severity tests are fine; give
their count.

Then check freshness (see `web_docs/docs/development/data-freshness.md`):

```bash
cd dbt_project && .venv_dbt/bin/dbt source freshness; .venv_dbt/bin/dbt test --select tag:freshness
```

A stale table doesn't block publishing: report each stale source or warning by name, with how old it is. If the same
table was stale last night too, open an `action-item` issue for it.

## 5. Publish to Neon (production stays on Neon; the free tier caps the project at 512 MB)

1. `.venv/bin/python -m hosting.neon.sync_event_documents_to_neon --dry-run`. Run the real incremental load (no
   flags) only if the reported size keeps Neon at or under 480 MB; otherwise skip it and report the sizes.
2. `.venv/bin/python -m hosting.neon.sync_public_to_neon --dry-run`. It lists each table's estimated size and the
   total.
3. `.venv/bin/python -m hosting.neon.sync_public_to_neon`. Read the exit code:
   - **4:** the projected size passes 480 MB or the swap's peak passes 512 MB. It stopped before changing anything.
     Don't raise `--max-mb` or force anything. Report the size line and the largest tables, and suggest which table
     to slim or drop from `CIVIC_SERVING`.
   - **1 for one object** (a lock timeout behind a live read): re-run once with `--only <that object>`.
   - **3:** VPN or DNS; see preflight.

Never use `--target dev` unless production is unreachable, and never copy runtime-owned tables.

## 6. Check production

Count the items each of these returns:

- https://www.communityone.com/api/data-centers/sites?state=AL
- https://www.communityone.com/api/data-centers/agenda-items?state=AL&city=Tuscaloosa
- https://www.communityone.com/api/data-centers/job-claims?state=AL
- https://www.communityone.com/api/data-centers/concerns?state=AL&city=Tuscaloosa

Then say whether https://www.communityone.com/data-centers?state=AL&city=Tuscaloosa shows real data.

## Report

A few lines, plain words, full links:

- one line per step: what ran and the counts;
- YouTube blocks, and what to fix (cookies, VPN, Webshare);
- Gemini cost or the count of videos analyzed;
- the dbt result;
- Neon's size before and after, against the 480 MB budget;
- the production counts.

If the data center pages now show real data, mention that the Erin follow-up draft is ready to send from the
CommunityOne mailbox. Also say that epic #236 can be closed, but don't close it.
