---
sidebar_position: 60
title: YouTube channel rules
description: Which YouTube channels count as a jurisdiction's own, and the decisions behind two edge cases.
---

# YouTube channel rules

API compliance audit (architecture, user flow, quota form answers): [YouTube API Services audit](../data-sources/youtube-api-audit.md).

A jurisdiction's YouTube channel enters the canonical table only when
`qualifies_for_bronze_jurisdiction_youtube` (`packages/scrapers/src/scrapers/discovery/youtube_channel_verification.py`)
accepts it. `rejection_reason_for_channel` names the first rule a channel fails. This page records decisions about
cases where more than one answer could be argued.

## Decisions (November 15, 2026, #322)

**A county channel that the county's own website links to qualifies without a meeting signal.** Example: "Walton
County Georgia Government", described as "News about services, programs and events". Channels classed
`county-general` normally need a meeting signal in their title or description. That check is skipped when the channel
was found through the jurisdiction's own website, or links back to it (ffe865a5, May 26). The owner kept that rule,
because the link itself shows the channel is the county's official one. A `county-general` channel with no such link
still needs a meeting signal.

**A town channel counts as the county's when the two cover the same area.** "Town of Nantucket" for the jurisdiction
"Nantucket County" is the county's own channel, not a city channel under the county, because the town and the county
of Nantucket are one area. `_looks_like_city_channel_for_county` returns false for it.

Tests: `tests/test_youtube_channel_purpose.py` and `tests/test_youtube_city_channel_remap.py`.

Revisit these if a linked `county-general` channel turns out to carry no meetings at all, or if another county shares
its area with a town that keeps a separate channel.
