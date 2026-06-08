"""
SuiteOne Media meeting-portal scraper.

Many municipalities publish their agendas and minutes on a SuiteOne Media
portal (``<slug>.suiteonemedia.com``) rather than as plain PDF links on their
homepage — which is why the generic homepage crawler captured 0 documents for
e.g. Tuscaloosa even though hundreds exist. This package follows the SuiteOne
listing and lands one bronze row per agenda / minutes document, with the REAL
per-meeting date parsed from the listing (not the year-only guess the legacy
homepage crawler produced).

FETCH + parse lives in :mod:`scrapers.suiteone.portal`; the bronze landing CLI
is :mod:`scrapers.suiteone.scrape` (``python -m scrapers.suiteone.scrape``).
"""
