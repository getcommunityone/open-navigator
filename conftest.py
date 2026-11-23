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


def pytest_configure(config):
    """Tests never read or write the real saved-hosts file in data/cache (#767): a test that sends a request through
    the VPN bypass would otherwise save its fake host there. A test that needs the file sets its own path."""
    import os

    os.environ.setdefault("SCRAPE_DIRECT_HOSTS_FILE", "off")
