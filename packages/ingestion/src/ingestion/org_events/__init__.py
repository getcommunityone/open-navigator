"""Upcoming events of nonprofits, read from their own public websites (#1347).

- :mod:`ingestion.org_events.websites` finds each nonprofit's website in its latest Form 990 e-file
  (``WebsiteAddressTxt``, public GivingTuesday data lake) -> ``bronze.bronze_organization_website``.
- :mod:`ingestion.org_events.crawl` reads schema.org ``Event`` markup and iCal feeds the site publishes
  -> ``bronze.bronze_organization_event``.
- :mod:`ingestion.org_events.parse` holds the pure parsers (tested offline).

Rules (AGENTS.md, scraping): public pages only, robots.txt honoured, an honest ``open-navigator`` User-Agent,
one request at a time per host with a pause, and a 403/429 or a bot check stops that host. Decision page:
web_docs/docs/development/organization-events.md.
"""
