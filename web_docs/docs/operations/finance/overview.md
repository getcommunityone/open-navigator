---
sidebar_position: 1
title: Finance overview
description: What Open Navigator spends money on, where each figure comes from, and how the expense and savings logs are kept.
---

# Finance overview

This section keeps two records: what running Open Navigator costs, and what was decided to make it cost less.

- [Expense log](./expense-log.md): what was spent, by day and service.
- [Savings decisions](./savings-decisions.md): each decision taken to save money, its reason, and whether its effect has
  been measured.

This site is public. Nothing here should include a key, an account number or a card detail.

## What costs money

| What | Service | How it is billed | Where the rate is recorded |
|---|---|---|---|
| Screening transcripts (is this a meeting, topic flags) | TypeSafe Jev | per input token | `packages/llm/src/llm/usage/prices.yaml` |
| Light and full meeting analysis, reports | DeepSeek, Google Gemini | per input and output token; prepaid balance | `prices.yaml` |
| Meeting chat on the site | Anthropic Claude Haiku | per input and output token | `prices.yaml` |
| GPU steps (speaker diarization, local generation) | Google Colab compute units | subscription shared with another project | [GPU compute decisions](../../development/gpu-compute-decisions.md) |
| Production database | Neon | free tier, capped at 512 MB | [Neon serving scope](../../development/neon-serving-scope.md) |
| Hosting the site | Hugging Face Spaces | not recorded here yet | unknown |

A row marked unknown is a gap to fill, not a zero.

## Where the figures come from

Two kinds of figure appear in the logs, and each entry says which it is.

- **Estimated from usage.** Every model call is written to a usage log on the machine that made it. The report
  multiplies the logged token counts by the rates in `prices.yaml`:

  ```bash
  python -m llm.usage.report --since 2026-11-19 --by stage
  ```

  A rate is used only when it has a source and a read date; otherwise the cost shows as a dash. This is an estimate,
  not an invoice. It can differ from what the provider charged: DeepSeek, for example, charges double in peak hours,
  and the report prices a call by the hour it was made.
- **Reported by the owner.** An amount the owner read from a provider's billing page, or a prepaid balance that ran
  out. These are the closest thing to an invoice the project records.

How the usage log and report work: [LLM usage tracking](../../development/llm-usage-tracking.md). What one analysis
call costs and what was done about it earlier: [Transcript analysis cost](../../development/transcript-analysis-cost.md).

## Keeping the logs

- Add a row to the expense log after any paid run, and whenever a prepaid balance is topped up or runs out. Paste the
  report's figures; do not round them into a story.
- Add an entry to the savings decisions when a change is made to spend less, when a spending limit is set, or when
  an option is considered and turned down. Say what was expected, and come back to record what was measured.
- If a figure is not known, write "unknown" and what would be needed to find it.
