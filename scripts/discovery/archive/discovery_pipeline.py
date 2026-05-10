"""
Jurisdiction discovery (Postgres bronze → bronze *_scraped).

Legacy Delta/Spark ingestion paths were removed. Use
``scripts.discovery.jurisdiction_discovery_pipeline`` for the merged implementation.

For CLI:

  .venv/bin/python -m scripts.discovery.jurisdiction_discovery_pipeline --help
"""
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from scripts.discovery.jurisdiction_discovery_pipeline import (
    DiscoveryPipeline,
    JurisdictionDiscoveryPipeline,
    ensure_scraped_tables,
    load_gsa_domain_set,
    load_jurisdictions_from_postgres,
    main,
)

__all__ = [
    "DiscoveryPipeline",
    "JurisdictionDiscoveryPipeline",
    "ensure_scraped_tables",
    "load_gsa_domain_set",
    "load_jurisdictions_from_postgres",
    "main",
]

if __name__ == "__main__":
    main()
