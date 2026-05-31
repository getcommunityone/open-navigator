---
displayed_sidebar: citationsSidebar
title: HuggingFace Datasets
description: Public meeting-summarization and civic datasets on HuggingFace that seed Open Navigator's meeting and transcript pipelines.
tags: [data-source, meetings, transcripts, huggingface]
---

# HuggingFace Datasets

**Public, ready-to-load civic datasets that bootstrap the meeting and transcript pipelines.**

HuggingFace hosts several openly licensed datasets of local-government meetings —
transcripts, audio, and human-written summaries. We use them as a head start:
real meeting text to validate extraction and keyword detection against before the
live scrapers fill in current coverage.

:::info At a glance
| | |
|---|---|
| **Provider** | Community researchers, via the HuggingFace Hub |
| **Coverage** | A handful of large US cities; historical (varies by dataset) |
| **Update cadence** | Static research releases |
| **License** | Per-dataset (CC-BY / CDLA) · see [Terms and Privacy](../legal/index.md) |
| **Cost** | Free |
| **Access method** | `datasets` library / bulk download |
| **Our pipeline** | `bronze.meetingbank_meetings` → staging → meeting marts |
:::

## Overview

The most directly useful dataset is **MeetingBank**, a benchmark built for meeting
summarization. The others below either overlap with sources we already ingest
(LocalView, Council Data Project) or are not available as bulk downloads
(CivicBand). This page covers what each one offers and which we actually load.

| Dataset | Available here | Role in Open Navigator |
|---------|----------------|------------------------|
| MeetingBank | Yes (HuggingFace) | Primary — transcripts + reference summaries |
| LocalView | Via Harvard Dataverse | Covered on [URL Datasets](./url-datasets.md) |
| Council Data Project | Via project deployments | Covered on [URL Datasets](./url-datasets.md) |
| CivicBand | Platform only | Validation list, not bulk URLs |

## Data available

### MeetingBank

A benchmark dataset of **1,366 city-council meetings** from six US cities —
Alameda CA, Boston MA, Denver CO, King County WA, Long Beach CA, and Seattle WA.
Each meeting ships with a full transcript (≈28k tokens on average), human-written
summaries used as evaluation ground truth, and links back to the source city.

| Field | Description | Type | Coverage |
|-------|-------------|------|----------|
| **id** | Meeting identifier | `string` | 100% |
| **transcript** | Full meeting transcript | `string` | 100% |
| **summary** | Human-written summary (ground truth) | `string` | 100% |
| **city / state** | Source jurisdiction | `string` | 100% |
| **source_url** | Link to the city's record | `string` | Partial |

- **Text:** [`huuuyeah/meetingbank`](https://huggingface.co/datasets/huuuyeah/meetingbank)
- **Audio:** [`huuuyeah/MeetingBank_Audio`](https://huggingface.co/datasets/huuuyeah/MeetingBank_Audio)
- **Archive:** [Zenodo 7989108](https://zenodo.org/record/7989108)
- **Paper:** *MeetingBank: A Benchmark Dataset for Meeting Summarization*, ACL 2023 — [arXiv:2305.17529](https://arxiv.org/abs/2305.17529)

### Grain & keys

- **Grain:** one row per meeting (segment-level instances also available).
- **Primary key:** `id`
- **Joins to:** our meeting marts via `source_url` / jurisdiction match.

## How we ingest it

```bash
# Pull MeetingBank and land it in the bronze layer.
python -m ingestion.huggingface.load_meetingbank
```

- **Source:** HuggingFace Hub (`huuuyeah/meetingbank`).
- **Lands in:** `bronze.meetingbank_meetings` → meeting staging models → meeting marts.
- **Refresh:** static dataset; re-run only to pick up an upstream revision.

The transcripts double as a fixture for evaluating keyword detection and
AI summarization: the human-written summaries give us a reference to score
generated output against.

## Coverage & known gaps

- Six cities only — large metros, useful for prototyping, not national coverage.
- Historical snapshots; current meetings come from the live scrapers and
  [YouTube discovery](./youtube-discovery.md).
- **CivicBand** (≈1,031 municipalities at [civic.band](https://civic.band/)) is
  browsable but offers no bulk export; we use its municipality list only to
  validate jurisdiction matches, not as a URL source.
- **LocalView** and **Council Data Project** are richer for URLs and are
  documented on the [URL Datasets](./url-datasets.md) page rather than duplicated here.

## Licensing & attribution

MeetingBank is released for research use; cite the ACL 2023 paper
([arXiv:2305.17529](https://arxiv.org/abs/2305.17529)) when redistributing
derived data. Confirm each dataset's license on its HuggingFace card before
republishing. See [Terms and Privacy](../legal/index.md) for our redistribution policy.

## Related

- [URL Datasets](./url-datasets.md)
- [YouTube Discovery](./youtube-discovery.md)
- [Data model ERD](./data-model-erd.md)
- [Data and Citations](./citations.md)
