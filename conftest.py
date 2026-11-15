import sys
from pathlib import Path

# Ensure packages/agents is on sys.path so the root __init__.py can import it
# during pytest collection without throwing ModuleNotFoundError.
agents_src = Path(__file__).parent / "packages" / "agents"
if agents_src.exists():
    sys.path.insert(0, str(agents_src))


def pytest_collection_modifyitems(config, items):
    """Tests marked ``live`` reach real websites or local services: they run only with RUN_LIVE_TESTS=1 (#305), so the
    CI run stays deterministic and offline-safe."""
    import os

    import pytest

    if os.environ.get("RUN_LIVE_TESTS") == "1":
        return
    skip = pytest.mark.skip(reason="live: needs a website, the network or a local service; set RUN_LIVE_TESTS=1 to run")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)
