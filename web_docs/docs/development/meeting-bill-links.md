---
title: How meetings are linked to state bills
description: The decision and rule behind meeting_bill_link (#1314, porting #1072's draft) — a meeting is tied to a state bill only when its transcript, a decision, its agenda or minutes, or the AI analysis writes the bill's number, in the same state — with the counts by method and what is left out.
---

# How meetings are linked to state bills

**Issue:** [#1314](https://github.com/getcommunityone/open-navigator/issues/1314) (ports the draft in
[#1072](https://github.com/getcommunityone/open-navigator/issues/1072)) · **Epic:**
[#1300](https://github.com/getcommunityone/open-navigator/issues/1300)

## Decision

A meeting is linked to a state bill **only when a record of that meeting writes the bill's number**, and the bill is in
the **same state**. No fuzzy title match, no "same topic, same time" guess, no LLM. A wrong link would put words in a
council's mouth about a bill it never discussed, so we take fewer links over unproven ones.

The evidence, strongest first (`match_method`):

| Method | Where the number is written | Rows (27 Nov 2026) |
|---|---|---|
| `transcript` | Said in the meeting (the caption transcript, `event_documents`) | 14,186 |
| `decision` | A decision's own headline or statement (`event_decision`) | 7 |
| `minutes` | The meeting's minutes (`event_meeting_document`) | 46 |
| `agenda` | The meeting's agenda (`event_meeting_document`) | 101 |
| `analysis` | The AI analysis's legislation number (`event_policy_bill.official_number`) | 13 |

In all: 14,353 links, 7,718 meetings, 7,174 distinct bills. 56 links are found by more than one method. `match_methods`
lists every method; `match_method` is the strongest.

A decision that cites "state law" or "the Code" without a bill number is **not** a link: there is no evidence of which
bill. A bill title said in a meeting is not matched either. OpenStates titles are long formal descriptions that are
rarely said word for word, and a trial over the topic bills' shorter titles was too slow to run on every build for the
few hits it could give. Both can come back with their own evidence rule.

## The rule

- **Forms read:** "HB 288", "H.B. 288", "House Bill 288", "SB 79", "S.B. 79", "Senate Bill 79", "AB 5" / "Assembly
  Bill 5", "HF 12" / "House File 12", "SF 3" / "Senate File 3", "LB 7" / "Legislative Bill 7", with an optional "No."
  Bare one-letter forms ("H 12") are skipped as too ambiguous in speech.
- **Kinds:** each reference and each OpenStates identifier becomes (kind, number): H, S, A, HF, SF, LB. "House Bill 12"
  finds "H 12" in Massachusetts and "HF 12" in Minnesota; "House File 12" only finds HF bills.
- **Session:** the bill in the meeting year's session, else the year before (two-year sessions); a regular session beats
  a special one. No bill, no row.
- **Evidence:** `match_text` is a verbatim excerpt of that record with the reference in `<mark>`. A row without one is
  dropped. `start_seconds` is the caption cue where it was said, and `url` opens the recording at that moment, the
  decision page or the document.
- **Grain and keys:** one row per (`meeting_key`, `bill_uid`). `meeting_key` is the recording's `video_id`, or
  `doc:<event_meeting_document_id>` for an agenda or minutes with no recording. PK `meeting_bill_link_id` =
  md5(meeting_key | bill_uid); FKs to `bills`, `event_meeting` and `event_meeting_document`, enforced.

## Where it shows

The story screen **What happened next** counts "meetings that named one of the topic's state bills": a link whose bill is
in `topic_legislation_bill` for the topic, in the scope. A meeting about data centers that also names a firefighter or
cannabis bill does not count for data centers. National counts: water fluoridation 5 meetings (3 bills, for example Fort
Worth, TX, on SB 2653), data centers 24 meetings (20 bills). Georgia fluoridation and Virginia data centers have none.

## Known limits

- The session-year rule can pick the wrong session when a speaker names an old bill ("the 2017 SB4"). The excerpt shows
  the words, so a reader can tell.
- The build reads every transcript that mentions a bill form; it took about 17 minutes on the local warehouse.
- The bill page and the meeting page don't show these links yet (#1072).
