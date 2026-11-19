---
title: Browser Gemini recent-meeting drip
description: Backfill recent meetings with the Gemini web subscription (no API dollars) via browser_policy_analysis.
---

# Browser Gemini recent-meeting drip

**What it's for:** enrich **recent** meetings in a pilot jurisdiction using the owner's
**Gemini web subscription** (Playwright → gemini.google.com), not the metered Gemini API,
Jev, or Colab GPU. Paid API and Colab runs stay blocked unless the owner says yes for that
run (`AGENTS.md`, GPU and paid compute).

Issue: [#624](https://github.com/getcommunityone/open-navigator/issues/624).

## Queue rules

`python -m llm.gemini.browser_policy_analysis` shortlist flags:

| Flag | Role |
|---|---|
| `--jurisdiction-id` | Required (e.g. `tuscaloosa_0177256`) |
| `--newest N` | Shortcut: newest N unanalyzed meetings, last 90 days |
| `--since-days N` | Meeting/upload day window (default 90 with `--newest`) |
| `--skip-analyzed` | Skip video_ids that already have a non-error `*_analysis.json` under `--output-dir` |
| `--only-has-transcript` | Optional: bronze transcript present (not required for web Gemini) |
| `--include-untyped-meetings` | Keep empty `meeting_type` (still drops OTHER/UNKNOWN); on with `--newest` |
| `--order-by published_at` | Newest first |
| `--dry-run` | List the queue only (no browser) |

`--newest N` sets `order_by=published_at`, `skip_analyzed`, and `since_days=90` when unset.
It does **not** require a local transcript — the browser path sends the YouTube URL.

## Dry-run (safe)

```bash
API_DB_SCHEMA=gold .venv/bin/python -m llm.gemini.browser_policy_analysis \
  --jurisdiction-id tuscaloosa_0177256 --newest 5 --dry-run
```

Needs `gold.event_youtube_with_jurisdiction` (dbt: `event_youtube_with_jurisdiction`).

## Drip run (subscription, you present)

1. Quit Chrome if you will reuse its profile, **or** start Chrome with remote debugging (WSL-friendly):

   ```bash
   google-chrome --remote-debugging-port=9222
   ```

2. Sign into Gemini in that Chrome window if needed.

3. Run a small batch (start with 1–5; stop when the free/day quota hits):

   ```bash
   API_DB_SCHEMA=gold .venv/bin/python -m llm.gemini.browser_policy_analysis \
     --jurisdiction-id tuscaloosa_0177256 --newest 3 \
     --cdp-url http://127.0.0.1:9222
   ```

Outputs land under `data/cache/gemini_browser_policy/<jurisdiction_id>/`. Re-running
`--newest` skips those video_ids.

## What not to do

- Do not point this at the national catalog or 200k videos.
- Do not fall back to `GEMINI_API_KEY` / Jev / Colab for catch-up while cash is tight.
- Prefer **this week's** meetings over historical backfill when the queue is long.
