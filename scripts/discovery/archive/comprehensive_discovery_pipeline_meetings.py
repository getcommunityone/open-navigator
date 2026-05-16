"""
Backward-compatible module path for the jurisdiction meetings + contacts scraper.

Prefer: ``python -m scripts.discovery.comprehensive_discovery_pipeline_jurisdiction``
"""

from scripts.discovery.comprehensive_discovery_pipeline_jurisdiction import (  # noqa: F401
    ComprehensiveDiscoveryPipelineJurisdiction as ComprehensiveDiscoveryPipelineMeetings,
    main,
)

if __name__ == "__main__":
    main()
