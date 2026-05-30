---
title: "Data Source Page Template"
description: "Canonical structure for every page under docs/data-sources. Copy this file when adding a new dataset."
tags: [internal, template]
---

{/*
  This file is a CONTRIBUTOR SCAFFOLD, not a public page. The leading underscore
  on the filename keeps Docusaurus from routing it (same convention as
  `_confirmed-datasets.md`). Copy it to `<your-source>.md`, drop the leading
  underscore, fill in the placeholders, delete this comment, and you're done.
*/}

# &lt;Data Source Name&gt;

**&lt;One-line value proposition / "Powered by ..." tagline&gt;**

&lt;Two or three plain-language sentences describing what this dataset is and why
a civic user or developer would reach for it. Avoid jargon in this paragraph —
later sections are the place for technical depth.&gt;

:::info At a glance
| | |
|---|---|
| **Provider** | &lt;organization / agency&gt; |
| **Coverage** | &lt;geographic + temporal scope&gt; |
| **Update cadence** | &lt;daily / quarterly / annual / static&gt; |
| **License** | &lt;SPDX id or short name&gt; · see [Legal](../legal/index.md) |
| **Cost** | &lt;free / API key / paid tier&gt; |
| **Access method** | &lt;REST API / GraphQL / bulk download / scrape / HF dataset&gt; |
| **Our pipeline** | &lt;bronze table · dbt model · loader script path&gt; |
:::

## Overview

&lt;What the source actually contains and how Open Navigator uses it. Two to four
short paragraphs is plenty — keep deep field-level detail for the next section.&gt;

## Data available

### Fields

&lt;One row per useful field. The `Coverage` column is the house style — fill it
with `100%`, `~80%`, `Rated orgs only`, etc. so readers can see at a glance
which fields are reliable.&gt;

| Field | Description | Type | Coverage |
|-------|-------------|------|----------|
| **&lt;field_name&gt;** | &lt;what it is&gt; | `string` | 100% |
| **&lt;field_name&gt;** | &lt;what it is&gt; | `integer` | ~80% |

### Grain & keys

- **Grain:** &lt;one row per ...&gt;
- **Primary key:** `<key>`
- **Joins to:** &lt;other dataset(s) and on which key&gt;

## How we ingest it

```bash
# Loader / dbt entry point — keep this runnable and current.
<command>
```

- **Source:** &lt;url / endpoint / bucket&gt;
- **Lands in:** `bronze.<table>` → `<staging model>` → `<mart>`
- **Refresh:** &lt;how a contributor re-pulls it&gt;

## Coverage & known gaps

&lt;Honest limitations: missing geographies, lag, partial fields, rate limits,
deprecated endpoints. Readers trust pages more when the warts are up top.&gt;

## Licensing & attribution

&lt;Required attribution text, redistribution terms, trademark notices, and a
link to the provider's full terms. If the provider mandates link-back HTML,
include the exact snippet.&gt;

## Related

- [&lt;related data source&gt;](./<slug>.md)
- [Data model ERD](./data-model-erd.md)
- [Citations](./citations.md)
