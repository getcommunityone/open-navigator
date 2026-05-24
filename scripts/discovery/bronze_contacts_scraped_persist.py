"""
DEPRECATED. Back-compat shim — the real implementation lives in
``scripts.discovery.bronze_persons_scraped_persist`` after the table rename
(``bronze.bronze_contacts_scraped`` -> ``bronze.bronze_persons_scraped``,
migration 043).

Import from the new module in new code:
    from scripts.discovery.bronze_persons_scraped_persist import insert_bronze_persons_scraped
"""

from __future__ import annotations

from scripts.discovery.bronze_persons_scraped_persist import (  # noqa: F401
    insert_bronze_contacts_scraped,   # back-compat alias of insert_bronze_persons_scraped
    insert_bronze_persons_scraped,
)
