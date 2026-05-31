---
displayed_sidebar: citationsSidebar
title: URL Datasets
description: Pre-existing civic-tech URL lists that seed jurisdiction and meeting-source discovery, ranked by coverage and quality.
tags: [data-source, jurisdictions, discovery, urls]
---

# URL Datasets

**Reuse the civic-tech community's validated meeting-source URLs instead of rediscovering them.**

Several open projects have already discovered and validated local-government
meeting URLs. Loading their lists gives far broader, higher-quality coverage than
matching jurisdictions to domains ourselves — which we keep only as a fallback for
the gaps the curated lists don't cover.

:::info At a glance
| | |
|---|---|
| **Provider** | Multiple civic-tech projects (see below) |
| **Coverage** | Thousands of US municipalities; varies by source |
| **Update cadence** | Per source — mostly static or project-maintained |
| **License** | Per-source · see [Terms and Privacy](../legal/index.md) |
| **Cost** | Free |
| **Access method** | Bulk download / repo clone / subdomain enumeration |
| **Our pipeline** | `bronze.*_urls` → jurisdiction matching → URL marts |
:::

## Overview

The goal is one deduplicated, priority-scored set of meeting-source URLs per
jurisdiction. We layer the sources below in priority order: curated lists first
(high quality, already validated), then pattern-based enumeration, then our own
domain matching to fill remaining gaps.

| Source | Approx. coverage | Quality | Priority |
|--------|------------------|---------|----------|
| Council Data Project | ~20 cities | Excellent | Highest |
| LocalView | 1,000–10,000 jurisdictions | High | High |
| City Scrapers | 100–500 agencies | Validated | Medium |
| Legistar subdomains | 1,000–3,000 | Good | Medium |
| Census + .gov matching | ~5,000 (projected) | Mixed | Fallback |

## Data available

### Council Data Project

Roughly 20 cities (Seattle, Portland, Denver, Boston, Oakland, Charlotte, and
others) with full, verified pipelines — meeting URLs plus transcripts and video.
Premium quality and our highest-priority source where available.

### LocalView (Harvard Dataverse)

The largest known database of local-government meetings, covering 1,000–10,000
jurisdictions with historical meetings through 2023.

- **Source:** [Harvard Dataverse — doi:10.7910/DVN/NJTBEM](https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/NJTBEM)
- Requires a manual browser download; see [Meeting Data](./meeting-data.md).

### City Scrapers

Spider lists from the City Scrapers project (Chicago, Pittsburgh, Detroit,
Cleveland, LA, and more). Each spider's `start_urls` is a validated agency URL.

- **Source:** [`city-scrapers/city-scrapers`](https://github.com/city-scrapers/city-scrapers)

### Legistar subdomains

Many cities run on Legistar at `{city}.legistar.com`. Enumerating that pattern
against our municipality list yields a large set of standardized-platform URLs.

### Census + .gov domain matching (fallback)

Matching Census jurisdictions against the CISA/GSA `.gov` domain list. Lower hit
rate and unverified, so we apply it only after the curated sources above.

### Grain & keys

- **Grain:** one row per (jurisdiction, source URL).
- **Primary key:** `jurisdiction_id` + `url`
- **Joins to:** the jurisdiction registry; deduplicated across sources.

## How we ingest it

```bash
# Integrate the external curated URL datasets into the bronze layer.
python -m discovery.external_url_datasets
```

- **Lands in:** `bronze.*_urls` (one table per source) → jurisdiction matching →
  a merged, deduplicated, priority-scored URL mart.
- **Refresh:** re-run per source; LocalView needs a manual Dataverse download first.

## Coverage & known gaps

- **LocalView** ends in 2023; current meetings come from
  [YouTube discovery](./youtube-discovery.md).
- **CivicBand**, **OpenTowns**, and most HuggingFace datasets are *not*
  bulk-downloadable as URL lists — see [HuggingFace Datasets](./huggingface-datasets.md)
  for what those do offer.
- Domain matching is unverified and overlaps the curated sources; dedupe by
  jurisdiction + URL before use.

## Licensing & attribution

Each source carries its own terms — Harvard Dataverse (LocalView), the project
repositories (Council Data Project, City Scrapers), and the public `.gov` domain
list. Confirm and attribute per source before redistributing; see
[Terms and Privacy](../legal/index.md).

## Related

- [HuggingFace Datasets](./huggingface-datasets.md)
- [Jurisdiction Discovery](./jurisdiction-discovery.md)
- [Meeting Data](./meeting-data.md)
- [Data and Citations](./citations.md)
