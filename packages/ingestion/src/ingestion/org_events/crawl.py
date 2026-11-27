"""Read upcoming events from topic nonprofits' own websites (#1347).

For each website found by :mod:`ingestion.org_events.websites`: the home page, then up to a few same-site links that
look like an events page or an iCal feed. Events come only from schema.org ``Event`` JSON-LD or an iCalendar feed:
what the site states, never inferred from prose. Only events from today on are kept.

robots.txt is honoured, the User-Agent says open-navigator, each host gets one request at a time with a pause, and a
403/429 or a bot check stops that host for the run.

Usage::

    python -m ingestion.org_events.crawl --states GA,VA,AL --limit 300
"""

from __future__ import annotations

import argparse
from datetime import date

import httpx
from loguru import logger

from ingestion.org_events.db import DDL, EVENT_TABLE, WEBSITE_TABLE, dsn
from ingestion.org_events.fetch import Blocked, Disallowed, PoliteClient
from ingestion.org_events.parse import OrgEvent, event_links, events_from_ical, events_from_jsonld, upcoming

TARGETS_SQL = f"""
select w.ein, w.website_url
from {WEBSITE_TABLE} w
where w.website_url is not null
  and (w.crawled_at is null or w.crawled_at < now() - interval '%(recrawl_days)s days')
  and exists (
      select 1 from gold.topic_organization t
      where t.ein = w.ein and (%(states)s::text[] is null or t.state_code = any(%(states)s::text[]))
  )
order by w.ein
limit %(limit)s
"""

EVENT_UPSERT = f"""
insert into {EVENT_TABLE} (event_key, ein, title, start_at, start_date, end_at, location, event_url, source_page_url,
                           source_format, fetched_at)
values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
on conflict (event_key) do update set title = excluded.title, start_at = excluded.start_at,
    end_at = excluded.end_at, location = excluded.location, event_url = excluded.event_url, fetched_at = now()
"""

STATUS_SQL = f"update {WEBSITE_TABLE} set crawl_status = %s, crawled_at = now(), events_found = %s where ein = %s"


def _parse(body: str, url: str, ein: str) -> list[OrgEvent]:
    if body.lstrip().startswith("BEGIN:VCALENDAR"):
        return events_from_ical(body, ein=ein, feed_url=url)
    return events_from_jsonld(body, ein=ein, page_url=url)


def crawl_site(client: PoliteClient, ein: str, site: str, today: date, *, max_links: int = 3) -> tuple[str, list[OrgEvent]]:
    """(status, upcoming events) for one site: ok | no_events | robots_disallowed | blocked | error."""
    try:
        home_url, home = client.get_text(site)
    except Disallowed:
        return "robots_disallowed", []
    except Blocked:
        return "blocked", []
    except (httpx.HTTPError, ValueError) as err:
        logger.debug("{}: {}", site, err)
        return "error", []
    found = _parse(home, home_url, ein)
    links = event_links(home, home_url, limit=max_links)
    for link in links:
        try:
            url, body = client.get_text(link)
        except Blocked:
            break
        except (Disallowed, httpx.HTTPError, ValueError):
            continue
        found += _parse(body, url, ein)
        # An events page often links its own feed: one level more, feeds only.
        if not body.lstrip().startswith("BEGIN:VCALENDAR"):
            for feed in [u for u in event_links(body, url, limit=2) if ".ics" in u.lower() or "ical=1" in u.lower()]:
                if feed in links:
                    continue
                try:
                    furl, fbody = client.get_text(feed)
                except (Blocked, Disallowed, httpx.HTTPError, ValueError):
                    continue
                found += _parse(fbody, furl, ein)
    events = upcoming(found, today)
    return ("ok" if events else "no_events"), events


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--states", default="")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--pause", type=float, default=2.0, help="Seconds between requests to one host.")
    ap.add_argument("--recrawl-days", type=int, default=7)
    ap.add_argument("--dsn", default="")
    args = ap.parse_args(argv)

    import psycopg2

    states = [s.strip().upper() for s in args.states.split(",") if s.strip()] or None
    today = date.today()
    totals: dict[str, int] = {}
    n_events = 0
    client = PoliteClient(min_interval=args.pause)
    try:
        with psycopg2.connect(dsn(args.dsn)) as conn, conn.cursor() as cur:
            cur.execute(DDL)
            cur.execute(TARGETS_SQL, {"states": states, "limit": args.limit, "recrawl_days": args.recrawl_days})
            targets = cur.fetchall()
            logger.info("{:,} websites to read", len(targets))
            for i, (ein, site) in enumerate(targets, 1):
                status, events = crawl_site(client, ein, site, today)
                totals[status] = totals.get(status, 0) + 1
                for e in events:
                    cur.execute(EVENT_UPSERT, (e.event_key, e.ein, e.title, e.start_at, e.start_date, e.end_at,
                                               e.location, e.event_url, e.source_page_url, e.source_format))
                n_events += len(events)
                cur.execute(STATUS_SQL, (status, len(events), ein))
                conn.commit()
                if i % 25 == 0:
                    logger.info("{:,}/{:,} sites, {:,} upcoming events, {}", i, len(targets), n_events, totals)
    finally:
        client.close()
    logger.success("{:,} upcoming events from {:,} sites ({}); {:,} requests", n_events, sum(totals.values()), totals, client.requests)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
