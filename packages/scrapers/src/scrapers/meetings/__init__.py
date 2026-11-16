"""
Meeting documents from the nationwide jurisdiction homepage crawl.

The crawl (``scripts/discovery/comprehensive_discovery_pipeline_jurisdiction``) and
its manifest loader land agenda/minutes PDFs for every state in
``bronze.bronze_events_meetings_{counties,municipalities,school_districts}_scraped``.
:mod:`scrapers.meetings.doctext` extracts their text into
``bronze.bronze_meeting_document_text`` so they are searchable in
``public.event_meeting_document`` (#392).
"""
