---
title: Crawling meetings nationwide
description: How to crawl agendas, minutes and YouTube meeting videos for every jurisdiction, load them into the warehouse, and publish within the Neon budget.
sidebar_position: 7
---

# Crawling meetings nationwide

Open Navigator collects local meetings in two ways. Both already run for any state with jurisdiction
homepages in the warehouse, not just one city:

1. **Agenda and minutes crawl.** Visits each jurisdiction's official homepage, finds its meeting pages
   (Legistar, Granicus, CivicClerk, CivicPlus, Simbli, SuiteOne, WordPress and plain HTML), and downloads the
   agenda and minutes PDFs.
2. **YouTube meeting crawl.** Lists each jurisdiction's meeting channel, pulls captions, and analyzes new
   videos with Gemini.

The SuiteOne scraper (`scrapers.suiteone`) is a separate, single-portal tool for Tuscaloosa. It is not the
way to cover the country (see [SuiteOne is a special case](#suiteone-is-a-special-case)).

Tracked in [#391](https://github.com/getcommunityone/open-navigator/issues/391).

## What reaches production today

| Crawl | Lands in | Reaches `public` / Neon |
|---|---|---|
| Agenda and minutes crawl, all states | `data/cache/scraped_meetings/` then `bronze.bronze_events_meetings_*_scraped` | Yes, from [#392](https://github.com/getcommunityone/open-navigator/issues/392): agendas and minutes with a real meeting day go to `event_meeting_document` (`source = 'scraped_meetings'`). Its YouTube channel links also feed the YouTube crawl |
| SuiteOne (Tuscaloosa) | `bronze.bronze_events_meetings_municipalities_scraped` (`suiteone:` rows) | Yes: `event_meeting_document` and the data center agenda items |
| YouTube crawl, all states | `bronze.bronze_event_youtube*` | Yes: meetings, decisions, job claims |

A crawled PDF is published only if the crawl classified it as an agenda or minutes and found a real meeting
day in its link text, filename or URL. PDFs dated only by their folder year, and unclassified PDFs, stay in
bronze. Text for search and the data center agenda items comes from step 3b.

## Before you start

Run everything from the repo root, inside WSL on the home laptop. That's where the `.venv`, the warehouse on
`localhost:5433`, and the VPN are. A Claude Code session started in that WSL terminal can run these steps too. The
Claude desktop app's connected folders run in a separate VM that can't reach the warehouse.

```bash
cd ~/path/to/open-navigator
git status --porcelain              # must be empty before a run
pg_isready -h localhost -p 5433
.venv/bin/python -m playwright install chromium   # once; on WSL also: sudo .venv/bin/python -m playwright install-deps
```

Optional tools the crawl uses when they are on `PATH`: `ffmpeg` (meeting audio to Opus), `libreoffice`
(Word to PDF), and `poppler-utils` (PDF page images).

Never delete `data/cache/`. The crawl resumes from the manifests stored there.

## Step 1: check the homepage list

Every crawl starts from `intermediate.int_jurisdiction_websites`, the warehouse's list of official homepages
(GSA .gov domains, USCM, state leagues, NCES, NACo and curated overrides). A jurisdiction missing from it is never
crawled. Refresh it and see how many homepages each state has:

```bash
(cd dbt_project && uv run dbt build --select +int_jurisdiction_websites)
psql -h localhost -p 5433 -U postgres open_navigator -c "
  select state_code, jurisdiction_type, count(*)
  from intermediate.int_jurisdiction_websites
  group by 1, 2 order by 1, 2;"
```

To fix a wrong or missing homepage, add a row to the `jurisdiction_website_url_overrides` seed and run
`dbt seed --select jurisdiction_website_url_overrides`. See
[Jurisdiction website enrichment](./jurisdiction-website-enrichment.md).

## Step 2: crawl agendas and minutes

One state, every jurisdiction type (counties, cities, school districts, townships):

```bash
.venv/bin/python -m scripts.discovery.comprehensive_discovery_pipeline_jurisdiction \
    --batch-from-db --state AL --type all --concurrency 6 --timeout 120
```

Every state, one after another (this takes days; run it in `tmux` or over several nights):

```bash
for st in AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY \
          NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY; do
  .venv/bin/python -m scripts.discovery.comprehensive_discovery_pipeline_jurisdiction \
      --batch-from-db --state "$st" --type all --concurrency 6 --timeout 120 \
      2>&1 | tee -a "/tmp/meetings-crawl-$st.log"
done
```

Useful flags:

| Flag | Use |
|---|---|
| `--type county` / `municipality` / `school` / `all` | Limit the batch to one jurisdiction type (default `county`) |
| `--retry-failed-shallow` | Re-crawl only sites whose last manifest fetched 0 pages (failed) or fewer than `--shallow-max-pages` (default 6) |
| `--resume --max-pages 500 --max-pdfs 800` | Go deeper on one site, merging with its cached manifest |
| `--geoid 0177256 --type municipality --from-db` | Crawl a single jurisdiction |
| `--meeting-seed-urls URL,...` | Start from a known meetings page when the homepage hides it |
| `--civicclerk-tenant <slug>` | Also sync a CivicClerk portal through its OData API |

Defaults are 80 pages and 80 PDFs per jurisdiction. The crawl writes one folder per jurisdiction, with a
`_manifest.json` plus the PDFs, under
`data/cache/scraped_meetings/{state}/{jurisdiction_type}/{jurisdiction_id}/{year}/`. It doesn't write to the
database. Set `SCRAPED_MEETINGS_ROOT` to put the files somewhere else, and use the same value in step 3.

## Step 3: load the manifests into bronze

```bash
.venv/bin/python scripts/discovery/load_scraped_meetings_manifests_to_bronze.py --state AL --dry-run
.venv/bin/python scripts/discovery/load_scraped_meetings_manifests_to_bronze.py --state AL
```

The loader writes one row per page, link or PDF, and replaces only its own rows for each jurisdiction. Since
[#393](https://github.com/getcommunityone/open-navigator/issues/393) it leaves SuiteOne rows alone, so the order
of the manifest load and the SuiteOne scrape doesn't matter.

**Never pass `--apply-ddl` on a populated warehouse.** It drops and recreates the scraped meetings tables,
SuiteOne rows included.

### Step 3b: extract the PDF text

```bash
.venv/bin/python -m scrapers.meetings.doctext --state AL --dry-run --limit 20
.venv/bin/python -m scrapers.meetings.doctext --state AL
```

This extracts text for the documents step 6 publishes. It reads each PDF from the crawl cache when the file is
still there and downloads it otherwise. It skips documents that already have text, so it picks up where it
stopped. Scanned PDFs are marked `empty_needs_ocr`. The text is what makes a document searchable and what the
data center agenda items match on. It is also the biggest thing this adds to Neon, so run the Neon dry run
(step 6) after each large state.

## Step 4: add the channels the crawl found

The crawl records the YouTube channels linked from official sites. Promote them into the channel list the YouTube
crawl reads:

```bash
(cd dbt_project && uv run dbt run --select int_jurisdictions int_jurisdiction_meetings_scrape_youtube_channels)
.venv/bin/python scripts/discovery/sync_bronze_jurisdiction_youtube_from_meetings_scrape.py --states AL --dry-run
.venv/bin/python scripts/discovery/sync_bronze_jurisdiction_youtube_from_meetings_scrape.py --states AL
```

## Step 5: crawl YouTube for every state

`youtube_run_priority_states_last_n.sh` covers only AL, GA, IN, MA, MT, WA and WI. For the whole country, use
the national runner. It reads the states that have channels in `bronze.bronze_event_youtube` and takes a few
jurisdictions from each state in turn:

```bash
MAX_JURISDICTIONS=100 ./packages/scrapers/scripts/youtube_run_all_jurisdictions.sh
STATES=AL,GA,TX MAX_JURISDICTIONS=50 ./packages/scrapers/scripts/youtube_run_all_jurisdictions.sh
```

For each jurisdiction it lists the newest videos, pulls captions, then runs the Gemini analysis (`N=10` videos per
place by default). Keep the conservative defaults:

- **Cap each night with `MAX_JURISDICTIONS`.** The order rotates through states, so nightly runs of 50–100
  places spread coverage instead of finishing one state at a time.
- **Keep `DELAY=10` and no caption parallelism.** YouTube throttles by IP. When the log says "Stopping after N
  consecutive blocks", stop. Don't loop. The usual fixes are a fresh `youtube_cookies.txt` (re-export it if it's
  older than a week), the Webshare proxy (`PROXY_USER_NAME` / `PROXY_PASSWORD` in `.env`), or a VPN reachable
  from WSL at the Windows host IP (`ip route | awk '/default/ {print $3}'`). Blocked videos aren't tombstoned, so
  the next night retries them.
- **Gemini is paid.** Each new video is one analysis call, so cost grows with jurisdictions × `N`. Record the
  analyzed-video count (and cost, from the `packages/llm` usage rows) in the run's issue.

## Step 6: rebuild and publish

```bash
(cd dbt_project && uv run dbt build --select +meeting_browse +event_decision +event_meeting_document +job_claim)
.venv/bin/python -m hosting.neon.sync_event_documents_to_neon --dry-run
.venv/bin/python -m hosting.neon.sync_public_to_neon --dry-run
.venv/bin/python -m hosting.neon.sync_public_to_neon
```

Production Neon is capped at 512 MB for the whole project, and the sync keeps it under 480 MB. If it exits 4,
nothing has changed. Don't raise `--max-mb`. Slim or drop the largest table in the dry-run listing instead. More
states mean more transcripts, so expect this to become the binding limit before crawl time does. See
[What production serves from Neon](../development/neon-serving-scope.md).

## SuiteOne is a special case

`scrapers.suiteone` reads one SuiteOne Media portal's full meeting index (agenda and minutes PDFs with the real
meeting date from the listing), and `scrapers.suiteone.doctext` extracts their text. It takes one portal per
command, and only Tuscaloosa is set up:

```bash
.venv/bin/python -m scrapers.suiteone.scrape --portal-url https://tuscaloosaal.suiteonemedia.com \
    --jurisdiction-id tuscaloosa_0177256 --state AL --homepage-url https://www.tuscaloosa.com
.venv/bin/python -m scrapers.suiteone.doctext --jurisdiction-id tuscaloosa_0177256 --doc-types agenda,minutes
```

The nationwide crawl in step 2 already recognizes SuiteOne portals on any site and downloads their agendas. Don't
add more cities by copying these commands. Improve the nationwide crawl instead.

## Suggested nightly order

1. Agenda crawl for one or two states (step 2), or `--retry-failed-shallow` for states already crawled.
2. Load those states' manifests (step 3), extract their text (step 3b), and run the SuiteOne scrape.
3. Promote new channels (step 4).
4. YouTube national runner with `MAX_JURISDICTIONS` (step 5).
5. dbt build, Neon dry run, Neon sync (step 6).

## Where the code lives

The agenda crawl, manifest loader and channel sync are still legacy modules under `scripts/discovery/`, waiting to
be ported into `packages/` (see the [cleanup roadmap](../development/cleanup-roadmap.md)). Run them as shown.
Put new crawl features in `packages/scrapers`, not in `scripts/`.
