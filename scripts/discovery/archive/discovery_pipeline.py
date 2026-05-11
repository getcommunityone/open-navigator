"""
Jurisdiction discovery (Postgres bronze → bronze *_scraped).

CLI: ``python -m scripts.discovery.jurisdiction_discovery_pipeline`` (creates tables + runs).

Legacy imports: ``DiscoveryPipeline``, ``main``, etc.

``PYSPARK_AVAILABLE`` is always false — the pipeline is Postgres-only (no Delta/Spark).
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
    scraped_jurisdictions_ddl_path,
)

PYSPARK_AVAILABLE = False

__all__ = [
    "DiscoveryPipeline",
    "JurisdictionDiscoveryPipeline",
    "ensure_scraped_tables",
    "load_gsa_domain_set",
    "load_jurisdictions_from_postgres",
    "main",
    "scraped_jurisdictions_ddl_path",
]

if __name__ == "__main__":
    main()
