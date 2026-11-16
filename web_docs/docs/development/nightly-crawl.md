---
sidebar_position: 37
title: Running the nightly crawl from a phone
description: Start the meeting crawl, dbt rebuild and Neon publish on the WSL laptop from a phone, with Claude Code Remote Control and the /nightly-crawl command.
---

# Running the nightly crawl from a phone

The crawl has to run on the laptop: YouTube captions need its residential connection and VPN, and the build needs the
local warehouse on port 5433. `/nightly-crawl` runs every step there, and Claude Code's Remote Control lets you start
and watch it from your phone ([#395](https://github.com/getcommunityone/open-navigator/issues/395)).

## In short

1. At the laptop, in the WSL terminal: `cd` into the repo, then `claude remote-control --name "open-navigator WSL"`.
   Leave it open.
2. On your phone: Claude app → **Code** → the session with the green dot.
3. Type `/nightly-crawl`. Add `skip-youtube` to skip the YouTube step, or `publish-only` to only sync and check.

It reports one line per step and stops before publishing if anything fails. The Neon sync refuses to go past 480 MB
([size check](./neon-serving-scope.md)).

<details>
<summary>First-time setup</summary>

- **Claude Code 2.1.51 or later** in WSL (`claude --version`), signed in with the claude.ai account. Install or
  update: https://code.claude.com/docs/en/setup
- **Remote Control everywhere (optional):** in Claude Code, `/config` → "Enable Remote Control for all sessions".
- **Keep the laptop reachable:** Windows set to never sleep while plugged in, the VPN connected, and the terminal left
  open (closing it ends the WSL session). A session ends after about ten minutes offline.
- **YouTube:** `PROXY_USER_NAME` and `PROXY_PASSWORD` (Webshare) in `.env`, and a `youtube_cookies.txt` less than a
  week old. If the VPN runs on Windows, a proxy inside WSL is at the Windows host IP, not `127.0.0.1`.

</details>

<details>
<summary>Why not a cloud scheduled task</summary>

A cloud scheduled task can link to the laptop, but its shell is a sandboxed Linux machine: it sees only shared
folders, can't reach services on the laptop's `localhost` (the warehouse), and its internet goes through an
allow-list, not the VPN. Remote Control runs Claude Code in WSL itself, so it has everything the terminal has.

</details>

<details>
<summary>What the steps are</summary>

The command file is [`.claude/commands/nightly-crawl.md`](https://github.com/getcommunityone/open-navigator/blob/main/.claude/commands/nightly-crawl.md):

0. Preflight (clean tree, warehouse, proxy and cookies).
1. Tuscaloosa agendas (SuiteOne).
2. Epoch AI data center sites.
3. The YouTube crawl and Gemini analysis, with the careful defaults.
4. The dbt rebuild.
5. The Neon publish under the budget.
6. A check of the live data center endpoints.

</details>
