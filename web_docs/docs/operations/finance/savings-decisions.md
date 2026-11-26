---
sidebar_position: 3
title: Savings decisions
description: Each decision taken to spend less on running Open Navigator, with its reason and whether the effect has been measured.
---

# Savings decisions

Newest first. Each entry says what was decided, why, what was expected, and what has been measured since. An effect
that has not been measured says so.

## 2026-11-24: the light analysis moves from DeepSeek to Claude Haiku

- **Decided:** the owner chose Claude Haiku 5.5 for the light analysis and its reports, in place of DeepSeek.
  Issue #871. Being built when this was written; no run has been made on it.
- **Why:** the owner judged a Chinese provider politically sensitive for American public meetings, and wanted the
  cheapest American alternative. Published rates per million tokens on the day: Haiku 0.10 input and 0.50 output
  (0.05 and 0.25 through the Batch API); DeepSeek Flash 0.15 and 0.60 off-peak, double at peak.
- **Expected:** from the token counts in the [expense log](./expense-log.md), about 93,000 input and 9,000 output
  tokens per analysed meeting, which at Haiku's live rates is a little over one cent a meeting. This is arithmetic,
  and Claude counts tokens differently from DeepSeek, so the real figure could be about a third higher.
- **Guards built in:** thinking held to low effort; a prompt over 100,000 tokens is skipped, not sent, because Haiku
  charges five times as much above that size.
- **Measured:** not yet. The first small run should be read in the usage report before a large one.
- **Not yet done:** the Batch API path, which would halve the rate.

## 2026-11-24: DeepSeek calls run with thinking off

- **Decided:** every DeepSeek call sends thinking off. `DEEPSEEK_THINKING` (`off`, `low`, `high`, `max`) turns it back
  on for a comparison. Issue #866.
- **Why:** DeepSeek turns thinking on by default at high effort and bills thinking tokens with the output. On
  November 23 and 24 thinking was 22,836,836 tokens against 5,036,514 output tokens, 82% of what was billed at the
  output rate. The work is extraction into a fixed shape, which the Gemini path already ran with thinking off.
- **Expected:** the output-side cost of a DeepSeek call falls by about four fifths; input cost is unchanged. For the
  light analysis and reports that is roughly a third of the earlier cost per meeting. This is arithmetic on the
  token counts above, not a measurement.
- **Measured:** not yet. No DeepSeek call has been made since the change (the balance is empty). After the next run,
  the usage report's thinking column for DeepSeek should be empty or zero.
- **Risk:** answers may be worse without thinking. Not tested. Check a sample with
  `python -m llm.gemini.public_comment_checks` before a large run.

## 2026-11-24: the meeting chat uses Claude Haiku

- **Decided:** the site's meeting chat calls Claude Haiku 5.5, not Gemini Flash-Lite. `CHAT_PROVIDER=gemini` switches
  back. Issue #848; details in [Meeting chat model](../../development/meeting-chat-model.md).
- **Why:** the owner intended Haiku, and the Gemini credit had run out, so the chat was down.
- **Rates on the day** (per million tokens, from each provider's pricing page): Haiku 0.10 input and 0.50 output for
  prompts up to 100,000 tokens; Gemini 2.5 Flash-Lite 0.10 and 0.40.
- **Expected:** about the same cost per answer; this was a reliability and preference decision more than a saving.
- **Measured:** not yet. No real question had been asked through Haiku when this was written.

## 2026-11-22: screen every transcript with Jev before paying for analysis

- **Decided:** every captioned video is screened by Jev first. Only videos it scores as real meetings go on to the
  paid analysis. Issue #702; design in [Jev-light cascade](../../development/jev-light-cascade-design.md).
- **Why:** full analysis of the whole backlog was priced at 85 to 120 dollars for one cohort, and prepaid Gemini keys
  were running out. Jev prices input tokens only and is about twenty times cheaper per video.
- **Measured:** on November 21 Jev made 3,999 transcript-screening calls for an estimated 1.56 (see the
  [expense log](./expense-log.md)). How many paid analyses the screen avoided has not been counted.

## Standing limits

These are not one-off decisions; they cap spending every day.

| Limit | Value | Where |
|---|---|---|
| Meeting chat spend per day | 1.00 dollar (`CHAT_DAILY_SPEND_CAP_USD`) | [Meeting chat model](../../development/meeting-chat-model.md) |
| Meeting chat questions per visitor | 60 an hour, 20 in five minutes | `.env.example` |
| Paid GPU runs | only on the owner's explicit yes for that run; never on the Kaggle account | [GPU compute decisions](../../development/gpu-compute-decisions.md) |
| Production database size | under Neon's free 512 MB, checked before each sync | [Neon serving scope](../../development/neon-serving-scope.md) |

## Considered, not decided

Options that would lower cost further. None is in effect.

| Option | What it would save | What is not known |
|---|---|---|
| Run DeepSeek analysis only in off-peak hours | Half the rate. DeepSeek's peak hours are 01:00 to 04:00 and 06:00 to 10:00 UTC, Monday to Friday | How much of the past spend fell in peak hours |
| Run the Haiku light analysis through the Batch API | Half the live rate: 0.05 input and 0.25 output per million tokens | Results arrive within a day, not at once; the pipeline would need to wait for them |
| Send less text per transcript | Input tokens are the larger share once thinking is off | Whether transcripts carry avoidable padding has not been measured |
| Fewer report calls per meeting | The report stage made between five and six successful calls for each successful analysis call and was about three quarters of the DeepSeek estimate | Why it makes that many, and whether they can be combined |
