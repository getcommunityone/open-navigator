---
sidebar_position: 32
title: Meeting audio source decision
description: Why meeting audio for diarization is downloaded from YouTube, where it is stored, and the limits every run keeps.
---

# Meeting audio source decision

Decided November 27, 2026, by the owner, in session. Logged in
[#1255](https://github.com/getcommunityone/open-navigator/issues/1255). Follow-up to prefer government
portals: [#1256](https://github.com/getcommunityone/open-navigator/issues/1256).

## What was decided

Speaker diarization ([#1251](https://github.com/getcommunityone/open-navigator/issues/1251)) and the
comment-level dataset ([#1232](https://github.com/getcommunityone/open-navigator/issues/1232)) need the
meeting audio, not only captions. The owner's words: **"YouTube too, my call."** He accepts the
terms-of-service risk of downloading public government meeting recordings from YouTube.

- **Scope:** the 2026 data-center meetings (the videos behind `public.data_center_meeting_mention` and
  `public.data_center_meeting_lean` with a 2026 `meeting_date`), minus the rows
  `public.meeting_video_kind` marks as not a public meeting. On November 27, 2026 that was 942 videos.
- **Where the audio goes:** the owner's **personal** OneDrive, never the "OneDrive - CDC" employer
  account. The existing `CommunityOne` YouTube audio folder holds YouTube audio; other sources get
  sibling folders under `CommunityOne` (`suiteone_audio`, `granicus_audio`), set by `--source`.
  Uploads go through the OneDrive API (rclone), not the synced folder under `C:\Users\…\OneDrive`,
  because C: is nearly full.
- **Don't download twice** (owner, November 27, 2026): every run first inventories what we hold
  (the OneDrive folder, the bronze tracking columns, `data/cache/youtube_audio`) keyed by `video_id`
  and skips it. A file held only locally is uploaded, not downloaded again.

## The conflict with AGENTS.md

AGENTS.md, "Privacy and data ethics", says to honour a site's terms and to cite or link where the terms
forbid automated collection. YouTube's terms forbid downloading. The repo's downloader also uses a
cookies file and yt-dlp's EJS challenge solver so YouTube lists formats at all. This page records the
owner's exception for this scope. It does not widen the rule anywhere else.

## Limits every run keeps

- **Polite and slow:** one download at a time, several seconds' sleep (default 8 s plus jitter) between
  videos.
- **Back off, then stop:** a 403, a 429 or a YouTube bot check doubles the pause; three in a row stop the
  run (exit code 3). Never retry harder.
- **No rotating proxies, no Webshare,** no identity spoofing beyond what yt-dlp needs to work (its
  default client headers, the existing `youtube_cookies.txt` if it already exists, the EJS solver). No
  new accounts or new cookies. YouTube is reached only through the VPN guard
  ([#488](https://github.com/getcommunityone/open-navigator/issues/488)).
- **Audio only,** re-encoded to 64 kbps Opus (about 28 MB per hour).
- **Public government meetings only.**

## Preferred source

When a government portal (SuiteOne, Granicus) hosts the same meeting, the portal is the better source:
its terms allow access. Preferring it is [#1256](https://github.com/getcommunityone/open-navigator/issues/1256).

## How to run it

`packages/scrapers/src/scrapers/youtube/README_AUDIO_DOWNLOAD.md`, section "Meeting audio to OneDrive".
