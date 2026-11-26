---
sidebar_position: 38
title: Jev metadata gate validation results
description: Half-A/B threshold table from the multi-state validation sample.
---

# Jev metadata gate validation results

Seed `20261121`, states `IL, NC, TX, MI, NV, ID, AZ, AR`, N=1000.
Design: [validation design](./jev-meta-gate-validation-design.md). Issue
[#666](https://github.com/getcommunityone/open-navigator/issues/666).

| Field | Value |
|---|---|
| Phase-1 pool (meta-screened) | 2,500 |
| Final sample | 1,000 (A=500, B=500) |
| Stratum `band` [0.3, 0.7] | **35** (pool is bimodal — most meta scores ≈0 or ≈1) |
| Stratum `srs` | 965 |
| Disagreements at chosen T | 48 (95.2% agree) |

The band half could not be filled: only ~1.4% of the scored pool landed in
[0.3, 0.7]. All band members were taken; the rest of the sample is SRS with
sampling weights. Re-run with a much larger pool if a 50/50 band mix is required.

## Half A (exploratory)

| T | n | wrong skip | wrong keep | ws rate | wk rate |
|---|---:|---:|---:|---:|---:|
| 0.3 | 500 | 5 | 9 | 0.0147 | 0.0147 |
| 0.4 | 500 | 9 | 8 | 0.0147 | 0.0140 |
| 0.5 | 500 | 8 | 9 | 0.0112 | 0.0147 |
| 0.6 | 500 | 11 | 10 | 0.0133 | 0.0182 |

## Half B (binding)

| T | n | wrong skip | wrong keep | ws rate | ws 95% CI | wk rate | wk 95% CI |
|---|---:|---:|---:|---:|---|---:|---|
| 0.3 | 500 | 9 | 11 | 0.0208 | [0.0103, 0.0416] | 0.0172 | [0.0080, 0.0367] |
| 0.4 | 500 | 11 | 14 | 0.0196 | [0.0095, 0.0399] | 0.0242 | [0.0126, 0.0459] |
| 0.5 | 500 | 12 | 15 | 0.0152 | [0.0067, 0.0340] | 0.0248 | [0.0131, 0.0467] |
| 0.6 | 500 | 9 | 18 | 0.0083 | [0.0028, 0.0242] | 0.0293 | [0.0162, 0.0524] |

## Chosen threshold

- **Chosen T:** `0.6` (lowest half-B wrong-skip upper bound among candidates)
- **Meets wrong-skip UB ≤ 2%:** `False` (T=0.6 UB = **2.42%**; point estimate **0.83%**)
- **Extra transcripts (wrong keeps on half B):** **18** (weighted wrong-keep rate ≈ 2.9%)

No candidate satisfied the binding 2% upper-bound rule. Caption-gate Phase 3
should stay opt-in at T=0.6 and treat the 2.42% UB as the current evidence
ceiling until a larger holdout or band-enriched sample tightens the interval.
Hand-check rows: `data/cache/jev_meta_gate_validation_disagreements.csv`
(`human_decision` column empty).

## Artifacts

| Path | Role |
|---|---|
| `data/cache/jev_meta_gate_validation_sample.csv` | Full labeled sample + weights |
| `data/cache/jev_meta_gate_validation_disagreements.csv` | Meta≠transcript @ T=0.6 |
| `data/cache/jev_meta_gate_validation_report.json` | Machine-readable rates / pick |
