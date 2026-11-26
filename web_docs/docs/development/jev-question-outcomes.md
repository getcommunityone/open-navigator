---
title: Jev question links and outcomes
description: How Jev's classifier readings (which policy questions a meeting debates, and what happened to its data center or short-term rental item) reach the question pages, with verbatim passages.
---

# Jev question links and outcomes

Issues: [#1029](https://github.com/getcommunityone/open-navigator/issues/1029) (the screen) and
[#1032](https://github.com/getcommunityone/open-navigator/issues/1032) (surfacing). Added 2026-11-26.

## Why

Decisions and questions come from the paid Gemini analysis. Only 187 of 1,859 data center meetings had been analyzed,
so the question pages showed 25 data center decisions. Jev (TypeSafe) is a classifier: it can't write text, but it can
judge, per transcript, which policy questions a meeting debates and what happened to an item. It's priced on input
tokens only, at $0.042 per million.

## The screen

`llm.typesafe.screen_transcripts` asks, in one request per meeting:

- `dc_outcome` and `str_outcome` (Choices): approved, denied, tabled_or_deferred, moratorium, discussed_no_action, or no item;
- one Noul per featured policy question (`question_probabilities`);
- the existing meeting-kind and topic flags, plus `mentions_short_term_rentals`.

Run on 2026-11-26 with `--cohort data-centers,short-term-rentals`: 5,880 meetings, 128,963,764 input tokens, about $5.42.

## On the site

`meeting_policy_question_jev` has one row per (meeting, question) for **"Should we allow new data centers?"** and
**"Should we allow short-term rentals?"**: the two questions with a verbatim passage on record (from
`data_center_meeting_mention` or `topic_transcript_link`).

- **What's kept:** government meetings and town halls only (Jev's own `meeting_kind`), where P(debated) is at least 0.5
  or an action was read. PK `meeting_policy_question_jev_id`; FK `question_id` → `policy_question`.
- **The API:** `GET /api/policy-question/{id}/jev?state=&city=&outcome=` returns the counts per outcome and the newest
  meetings, actions first, each with its passage and the moment to hear it.
- **The question card** (Browse Questions) shows a "Meetings screened by Jev" block. Each outcome count filters the list.
  The block says plainly that these are a classifier's readings, not the analyzed decisions above it.

The other featured questions (bike lanes, license plate readers, no-bid contracts) are screened but not shown. They
have no stored passage to quote yet, and a tile without its matched passage isn't shown (CLAUDE.md).
