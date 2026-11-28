"""Find topic nonprofits' websites in their latest Form 990 e-file (#1347).

The 990 e-file names the organization's website (``WebsiteAddressTxt``). The XML is public on the GivingTuesday data
lake (anonymous HTTPS, the same objects ``ingestion.givingtuesday.efile`` reads). Only nonprofits already tied to a
curated topic (``gold.topic_organization``) are looked up, strongest evidence first.

Usage::

    python -m ingestion.org_events.websites --states GA,VA,AL --max-rank 3 --limit 600
    python -m ingestion.org_events.websites --dry-run
"""

from __future__ import annotations

import argparse
import time

import httpx
from loguru import logger

from ingestion.org_events.db import DDL, WEBSITE_TABLE, dsn
from ingestion.org_events.fetch import USER_AGENT, get_public_xml
from ingestion.org_events.parse import website_from_990_xml

CANDIDATES_SQL = f"""
with orgs as (
    select t.ein, min(t.evidence_rank) as best_rank
    from gold.topic_organization t
    where t.ein is not null
      and t.evidence_rank <= %(max_rank)s
      and (%(states)s::text[] is null or t.state_code = any(%(states)s::text[]))
    group by t.ein
),
latest as (
    select distinct on (f.ein) f.ein, f.tax_year, f.source_url
    from bronze.bronze_organizations_990_financials f
    join orgs o on o.ein = f.ein
    where f.source_url like 'https://%%.xml'
    order by f.ein, f.tax_year desc
)
select l.ein, l.tax_year, l.source_url
from latest l
join orgs o on o.ein = l.ein
left join {WEBSITE_TABLE} w on w.ein = l.ein
where w.ein is null or w.fetched_at < now() - interval '180 days'
order by o.best_rank, l.ein
limit %(limit)s
"""

UPSERT_SQL = f"""
insert into {WEBSITE_TABLE} (ein, website_url, source_url, tax_year, fetched_at)
values (%s, %s, %s, %s, now())
on conflict (ein) do update set website_url = excluded.website_url, source_url = excluded.source_url,
    tax_year = excluded.tax_year, fetched_at = now()
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--states", default="", help="Comma-separated state codes (default: all).")
    ap.add_argument("--max-rank", type=int, default=3, help="Evidence rank ceiling (1 named in a meeting .. 4 IRS category).")
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--pause", type=float, default=0.25, help="Seconds between data-lake requests.")
    ap.add_argument("--dsn", default="")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    import psycopg2

    states = [s.strip().upper() for s in args.states.split(",") if s.strip()] or None
    with psycopg2.connect(dsn(args.dsn)) as conn, conn.cursor() as cur:
        cur.execute(DDL)
        cur.execute(CANDIDATES_SQL, {"max_rank": args.max_rank, "states": states, "limit": args.limit})
        rows = cur.fetchall()
        logger.info("{:,} nonprofits to look up", len(rows))
        if args.dry_run:
            return 0
        found = 0
        with httpx.Client(timeout=30.0, headers={"User-Agent": USER_AGENT}) as http:
            for i, (ein, tax_year, url) in enumerate(rows, 1):
                try:
                    xml = get_public_xml(http, url)
                except httpx.HTTPError as err:
                    logger.warning("990 XML for {} unreadable ({})", ein, type(err).__name__)
                    continue
                site = website_from_990_xml(xml) if xml else None
                found += bool(site)
                cur.execute(UPSERT_SQL, (ein, site, url, tax_year))
                if i % 50 == 0:
                    conn.commit()
                    logger.info("{:,}/{:,} looked up, {:,} websites", i, len(rows), found)
                time.sleep(args.pause)
        conn.commit()
    logger.success("{:,} websites found for {:,} nonprofits", found, len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
