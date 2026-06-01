"""CivicSearch FETCH side.

CivicSearch (https://schools.civicsearch.org, https://civicsearch.org) is a
search layer over the LocalView transcript dataset. Each "meeting" is a YouTube
video (``vid_id``); on top of it CivicSearch adds policy-topic tagging and
timestamped transcript snippets. The public JSON API lives under
``https://schools.civicsearch.org/api/`` (GET-only, no auth).

This package is FETCH-only: it crawls the API and writes JSONL snapshots into
``data/cache/civicsearch/``. Landing those snapshots into
``bronze.bronze_events_civicsearch`` is the job of ``ingestion.civicsearch.events``.
"""
