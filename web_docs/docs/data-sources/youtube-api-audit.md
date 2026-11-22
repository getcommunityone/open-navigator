---
displayed_sidebar: developersSidebar
title: YouTube API Services audit
description: Architecture, user flow, endpoints, and quota answers for the YouTube Data API compliance audit (#737).
---

import ZoomableImage from '@site/src/components/ZoomableImage';

# YouTube API Services audit

Operator notes for the [YouTube API Services — Audit and Quota Extension Form](https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits).
CommunityOne uses the Data API **read-only** (API key, public metadata) and embeds or links out to YouTube for playback. We do **not** upload videos or use YouTube OAuth.

Related: [Privacy Policy §9](../legal/privacy-policy.md#9-youtube-api-services) · [Terms — YouTube API Services](../legal/terms-of-service.md) · [YouTube channel discovery](./youtube-discovery.md) · [YouTube channel rules](../development/youtube-channel-rules.md)

Evidence PNGs/JPEGs for the form live under `web_docs/static/img/legal/youtube-api-audit/` (served as `/docs/img/legal/youtube-api-audit/…`). Editable draw.io sources: `diagrams/youtube-api-audit/`.

---

## Architecture

Read + embed only: public YouTube → API key pool → Data API v3 (`search` / `channels` / `videos` / `playlistItems`) → bronze → staging → marts → FastAPI → meeting pages (iframe or open on YouTube). No upload, update, delete, Authorized Data, or user OAuth.

<ZoomableImage
  src="/img/legal/youtube-api-audit/architecture-diagram.png"
  alt="CommunityOne YouTube API Services architecture"
  title="Architecture diagram"
/>

| Layer | What happens |
|-------|----------------|
| Source | Public meeting channels and videos on YouTube |
| Ingest | Server-side `YOUTUBE_API_KEY_*` pool; scrapers/loaders call list endpoints only |
| Warehouse | `bronze_event_youtube` → `stg_youtube__event` → public meeting/event marts |
| Serve | Meeting pages embed YouTube or link “Open on YouTube”; legal footer → Privacy / Terms |
| Consumers | Citizens, advocates, operators (keys / quota / inventory) |

---

## User flow

Citizen path: homepage search → meeting page → in-page YouTube embed **or** open on youtube.com. Optional stop at Privacy §9 / Terms. **Not** in this journey: upload via CommunityOne, or YouTube OAuth through CommunityOne.

<ZoomableImage
  src="/img/legal/youtube-api-audit/user-flow-diagram.png"
  alt="User flow: citizen watches a meeting recording"
  title="User flow diagram"
/>

---

## Project #1 — form answers (fill-in)

Use these when completing the audit form for the Cloud project that owns the production YouTube API key.

| Field | Answer |
|-------|--------|
| Application name | **CommunityOne** |
| Client URL | **https://www.communityone.com** |
| Docs | **https://www.communityone.com/docs** |
| Use case categories | **Education & Research** and **Websites & Mobile Apps** only |
| OAuth 2.0 / Google sign-in for YouTube? | **No** — API key only |
| Demo / login | No login required for public meeting/video discovery. Example embed: `https://www.communityone.com/meetings/14313` |

### Endpoints to select

Check **only**:

- `youtube.search.list`
- `youtube.channels.list`
- `youtube.videos.list`
- `youtube.playlistItems.list`

Leave unchecked: `youtube.videos.insert` and every caption / comment / live / upload / write method.

### Quota

| Field | Value |
|-------|--------|
| **Total per day quota** (all endpoints except `search.list` / `videos.insert`) | **100000** |
| **`search.list` quota** (separate bucket, if asked) | **1000** |
| **`videos.insert` quota** | leave blank / **0** |

Default allocations (about 10,000 units/day general and 100 `search.list`/day) are insufficient for nationwide municipal discovery and daily refresh; we already hit `quotaExceeded`. Prefer a smaller first ask (**50000** total / **500** search) if reviewers push back.

### Detailed justification (paste)

```
CommunityOne (communityone.com) is a 501(c)(3) civic transparency product. We use the YouTube Data API v3 with an API key only (no YouTube OAuth, no uploads) to discover and catalog public local-government and community meeting videos so residents can find them on our site and watch on YouTube.

Endpoints used: search.list, channels.list, videos.list, playlistItems.list.
- channels.list + playlistItems.list: resolve jurisdiction channels and list uploads
- videos.list: public video metadata (title, description, duration, captions flag)
- search.list: completed live streams and topic/place discovery (e.g. community / data-center meetings)

Default allocations (10,000 units/day general; 100 search.list/day) are insufficient for nationwide municipal discovery and daily refresh; we already hit quotaExceeded. We request 100,000 units/day for non-search/non-insert methods and 1,000 search.list/day. We cache results, avoid repeating searches within a refresh window, and do not shard this use case across Cloud projects. We do not call videos.insert or any write APIs.
```

### Conditional evidence

| Form item | Needed? | Notes |
|-----------|---------|--------|
| a) OAuth flow screenshots | **No** (OAuth = No) | Privacy §9 states API key only |
| b) Upload interface | **No** | We do not upload; see `other-supporting-no-youtube-upload.png` |
| c) Player / embed | **Yes** | Meeting page YouTube iframe (Education & Research / Websites & Mobile Apps) |
| d) Dashboard / feature | **No** unless Internal/Analytics was checked | Do not check those use cases |

### Section 6 — additional evidence

| Item | Value |
|------|--------|
| Privacy Policy | https://www.communityone.com/docs/legal/privacy-policy/#9-youtube-api-services |
| Terms | https://www.communityone.com/docs/legal/terms-of-service |
| Homepage | https://www.communityone.com/ |
| Architecture diagram | `/img/legal/youtube-api-audit/architecture-diagram.png` |
| User flow diagram | `/img/legal/youtube-api-audit/user-flow-diagram.png` |
| Other supporting | No YouTube upload script/screencast — N/A |

Form evidence quality: ≥1280×720, readable text, browser address bar for web shots, one file &lt;10 MB per upload field. Descriptive filenames under `web_docs/static/img/legal/youtube-api-audit/`.

---

## Rebuild diagrams

```bash
cd diagrams/youtube-api-audit/_build
# see render.md for one-time draw.io webapp setup
python3 build_drawio.py && python3 build_user_flow_drawio.py
python3 render_drawio.py ../yt1_architecture.drawio ../yt2_user_flow.drawio
# copy PNGs to web_docs/static/img/legal/youtube-api-audit/ as architecture-diagram.png / user-flow-diagram.png
```
