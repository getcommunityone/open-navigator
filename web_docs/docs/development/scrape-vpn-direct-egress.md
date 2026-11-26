---
sidebar_position: 40
title: Scraping with the VPN on
description: How site scrapes retry outside the VPN without turning it off, which pages count as blocked, and the settings that control it.
---

# Scraping with the VPN on

YouTube work needs the VPN on ([#488](https://github.com/getcommunityone/open-navigator/issues/488)). Some county
and city sites refuse VPN addresses, or answer with a block page or a page that is nearly empty (for example
coffeecounty.us, reported November 23, 2026). The site scrapers in
`packages/scrapers/src/scrapers/discovery/scrape_http.py` handle this without turning the VPN off: they retry that
one request outside the tunnel and remember the host ([#767](https://github.com/getcommunityone/open-navigator/issues/767)).

## When a request is retried outside the VPN

A request goes out normally first, through the VPN. It is retried once outside the VPN when:

- it raised a connection, TLS, proxy or timeout error;
- it came back 403, 407, 502, 503 or 504;
- it came back 200 but `looks_blocked_or_partial` says the page is a block page or a near-empty page.

If the retry works (a status under 400, and for a 200, not a block page), the host is remembered and later requests
to it go outside the VPN first. YouTube URLs never go outside the VPN.

## What counts as a block page or a partial load

`looks_blocked_or_partial(response)` judges only successful HTML responses. A PDF, JSON or image is never judged, and
neither is an error status. An HTML 200 counts as blocked or partial when any of these hold:

| Check | Why |
|---|---|
| The title has a block-page marker (`BLOCK_PAGE_MARKERS`: Access Denied, Attention Required, a Cloudflare challenge, captcha, Request blocked, an Akamai "Reference #", Checking your browser, Just a moment, Pardon our interruption, web application firewall) | firewall and bot-check pages |
| The page is under 20,000 bytes and its text has one of those markers | block pages are small; in a large page the same words are ordinary content |
| The page is under 2,048 bytes, or has no `<title>` | an empty shell or a cut-off response |
| Fewer than 30 visible words and fewer than 3 links | a script-only shell that loaded nothing |

For scale: coffeecounty.us loaded without the VPN is about 105 KB, with a title, about 388 visible words and 57 links.

## Settings

| Variable | Default | What it does |
|---|---|---|
| `SCRAPE_VPN_BYPASS_RETRY` | on | `0` turns off every retry outside the VPN |
| `SCRAPE_DIRECT_INTERFACE` | detected when a VPN tunnel is up | the home network interface to bind the retry to; `off` disables binding |
| `SCRAPE_DIRECT_PROXY` | none | a proxy URL for the retry, used instead of binding to an interface |
| `SCRAPE_DIRECT_HOSTS_FILE` | `data/cache/scrape_direct_hosts.json` | where remembered hosts are kept between runs (a JSON list of host names); `off` keeps them in memory only |

The hosts file is merged on every write, so two runs at once don't drop each other's hosts. A file that can't be read
or written only logs a warning. Like everything in `data/cache/`, don't delete it; to forget a host, edit the list.

## When binding to an interface doesn't work

Binding needs Linux (`/proc/net/route`) and a VPN client that leaves the home route in place. It doesn't work in
native Windows Python, or when the VPN's kill switch blocks traffic outside the tunnel. There, run a small local proxy
whose program the VPN client is told to bypass (split tunnelling by app, for example Surfshark's "Bypasser"), and point
the scrapers at it:

```bash
SCRAPE_DIRECT_PROXY=http://127.0.0.1:8899
```

Any HTTP proxy works, for example `pproxy -l http://127.0.0.1:8899` from `pip install pproxy`. Add the proxy's
program (its `python.exe` or the `pproxy` executable) to the VPN client's bypass list, and keep YouTube work on the
VPN as before.

## A 429 means slow down

A 429 ("too many requests") is never retried from another address. That would ignore what the site asked
([#1081](https://github.com/getcommunityone/open-navigator/issues/1081),
[Privacy and data ethics](./privacy-and-data-ethics.md)). The scraper waits instead, then retries on the same route:

- it waits as long as the site's `Retry-After` header says (seconds or a date), or else an exponential back-off of
  `SCRAPE_429_BASE_SECONDS` × 2^attempt (default 5 s);
- every wait is capped at `SCRAPE_429_MAX_WAIT_SECONDS` (default 120 s);
- after `SCRAPE_429_MAX_RETRIES` tries (default 2) it gives up, returns the 429 and logs `scrape_rate_limited_gave_up`.

A host normally reached outside the VPN is backed off on that route too; it never falls through to the VPN.
