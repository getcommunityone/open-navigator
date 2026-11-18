"""Meeting-platform readers (#536): Granicus portals and the Legistar Web API.

- :mod:`scrapers.platforms.legistar` — ``webapi.legistar.com/v1/<client>/events`` (+ event items).
- :mod:`scrapers.platforms.granicus` — ``<host>/ViewPublisher.php?view_id=N`` (+ RSS, caption tracks).
- :mod:`scrapers.platforms.store` — idempotent bronze writes.
- :mod:`scrapers.platforms.run` — CLI: ``python -m scrapers.platforms.run --data-center --apply``.
"""
