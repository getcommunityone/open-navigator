"""communityone-scrapers — FETCH-stage crawlers.

Each ``scrapers.<source>`` subpackage fetches raw data from a source's website
or API into ``data/cache/<source>/``. The matching ``ingestion.<source>``
pipeline then LANDs that cache into bronze. This split keeps web-crawling
concerns (httpx / BeautifulSoup / Playwright, retries, politeness, sanitization)
out of the DataSourcePipeline cache->bronze contract.
"""
