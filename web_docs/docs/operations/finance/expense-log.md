---
sidebar_position: 2
title: Expense log
description: What Open Navigator spent, by day and service, with the source of every figure.
---

# Expense log

Newest first. "Estimated" means token counts from the usage log multiplied by the rates in `prices.yaml`
(see the [overview](./overview.md)). "Reported" means the owner read it from the provider. Amounts are in US dollars.

## Balances and top-ups

| Date | Service | Event | Amount | Kind | Source |
|---|---|---|---|---|---|
| 2026-11-24 | DeepSeek | Prepaid balance ran out during the light analysis ("Insufficient Balance", error 402) | 20.00 | Reported | Owner, and the batch log of that day |
| 2026-11-24 | Google Gemini | Prepaid credit ran out ("Your prepayment credits are depleted", error 402); the meeting chat stopped answering | unknown | Reported | `logs/api.log` on the owner's machine; the balance that was bought is not recorded |

## Model usage, November 19 to 24, 2026

From `python -m llm.usage.report --since 2026-11-19 --by stage` on the owner's machine, read on November 24, 2026.
All rows are estimates. A failed call is counted in "Calls" but is not billed.

| Day | Service and model | Stage | Calls | Failed | Estimated cost |
|---|---|---|---|---|---|
| 2026-11-24 | DeepSeek `deepseek-flash` | part2 (reports) | 5,906 | 4,089 | 10.8699 |
| 2026-11-24 | DeepSeek `deepseek-flash` | part1 (analysis) | 4,867 | 4,483 | 4.6563 |
| 2026-11-23 | DeepSeek `deepseek-flash` | part2 (reports) | 2,399 | 1,029 | 6.7851 |
| 2026-11-23 | DeepSeek `deepseek-flash` | part1 (analysis) | 190 | 11 | 1.6980 |
| 2026-11-22 | Gemini `gemini-2.5-flash-lite` | part1 (analysis) | 1,172 | 212 | 12.8105 |
| 2026-11-22 | Gemini `gemini-2.5-flash-lite` | part2 (reports) | 759 | 23 | 1.7511 |
| 2026-11-22 | Jev `jev-1.14.0` | metadata screen | 24 | 0 | 0.0006 |
| 2026-11-21 | Gemini `gemini-2.5-flash-lite` | part1 (analysis) | 504 | 35 | 6.7883 |
| 2026-11-21 | Gemini `gemini-2.5-flash-lite` | part2 (reports) | 344 | 6 | 0.7577 |
| 2026-11-21 | Jev `jev-1.14.0` | transcript screen | 3,999 | 0 | 1.5643 |
| 2026-11-21 | Jev `jev-1.14.0` | metadata screen | 5,451 | 0 | 0.1426 |
| 2026-11-20 | Gemini `gemini-3.5-flash-lite` | model comparison | 3 | 0 | 0.0543 |
| 2026-11-20 | Claude `claude-haiku-5-5` | model comparison | 9 | 6 | 0.0292 |
| 2026-11-20 | Gemini `gemini-2.5-flash-lite` | model comparison | 3 | 0 | 0.0134 |
| 2026-11-19 | Jev `jev-1.14.0` | five trial stages | 6 | 0 | 0.0048 |

### Totals for the six days

| Service | Estimated cost |
|---|---|
| DeepSeek | 24.0093 |
| Google Gemini | 22.1753 |
| Jev | 1.7123 |
| Anthropic Claude | 0.0292 |
| **All** | **47.9261** |

### What the figures show

- **The estimate and the balance do not match for DeepSeek.** The report prices the two days at 24.01, and the balance
  that ran out was 20.00. The difference has not been explained. The report may be pricing some calls at the peak
  rate that DeepSeek charged at the off-peak rate, or the reverse; until it is reconciled, treat the report as
  accurate to within about a fifth.
- **Thinking tokens were most of the DeepSeek bill.** Over the two days DeepSeek reported 22,836,836 thinking tokens
  against 5,036,514 output tokens. See the [savings decision of November 24](./savings-decisions.md).
- **Screening is cheap next to analysis.** Jev made 3,999 transcript-screening calls for 1.56. Gemini's 1,676
  analysis calls cost 19.60.
- **Not in this table:** GPU time, hosting, the database, and anything before November 19. Those are unknown here.
