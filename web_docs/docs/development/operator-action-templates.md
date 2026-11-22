---
sidebar_position: 49
title: Operator action templates
description: Standard playbooks for pipeline blockers (YouTube API quota, VPN, missing API key).
---

# Operator action templates

Canonical playbooks for human-required pipeline blockers. Admin page:
`/admin/operator-actions`. Spec: [operator-actions](./operator-actions.md) ·
Issue [#712](https://github.com/getcommunityone/open-navigator/issues/712).

Codes: `youtube_api_quota` · `vpn_down` · `missing_youtube_api_key`.

---

## YouTube API quota {#youtube-api-quota}

**Code:** `youtube_api_quota`  
**Symptoms:** Discover rejects with `uploads_fetch_failed` / HTTP 403 /
`quotaExceeded` while channel URLs were still found.

**Do:**

1. Open [YouTube Data API v3 Quotas](https://console.cloud.google.com/apis/api/youtube.googleapis.com/quotas)
   for the GCP project that owns `YOUTUBE_API_KEY`.
2. Confirm the daily quota is at the cap (often 10,000).
3. Wait for ~midnight Pacific reset, **or** switch `.env` `YOUTUBE_API_KEY` to a
   key with remaining quota, **or** request a quota increase.
4. Re-run Discover for states that rejected with uploads 403.
5. Confirm `/admin/operator-actions` auto-clears, or **Mark resolved** if stale.

**Do not:** Set `YOUTUBE_REQUIRE_VPN=0` to “fix” quota.

---

## VPN down {#vpn-down}

**Code:** `vpn_down`  
**Symptoms:** `VpnRequiredError: Surfshark is off…`; Discover waits on
`VPN_WAIT_POLL_SECONDS` or shell exit 5.

**Do:**

1. Connect **Surfshark** full tunnel on the Windows host.
2. Confirm: `.venv/bin/python -m scrapers.youtube.vpn_guard` → `vpn_up: true`.
3. Let Discover resume, or re-kick from Batch Jobs.
4. **Mark resolved** if the row is stale after a clean run.

**Do not:** Override with `YOUTUBE_REQUIRE_VPN=0` except deliberate diagnosis.

---

## Missing YouTube API key {#missing-youtube-api-key}

**Code:** `missing_youtube_api_key`  
**Symptoms:** Reject reason `missing_youtube_api_key`.

**Do:**

1. Set `YOUTUBE_API_KEY` in `.env` (YouTube Data API v3 enabled).
2. Restart API / Discover so they reload env.
3. Re-run Discover for affected states.
4. Confirm clear or **Mark resolved**.

If the key is present but calls return `quotaExceeded`, use the
[quota](#youtube-api-quota) playbook.
