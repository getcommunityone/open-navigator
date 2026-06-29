import sys
from pathlib import Path

# Ensure packages/agents is on sys.path so the root __init__.py can import it
# during pytest collection without throwing ModuleNotFoundError.
agents_src = Path(__file__).parent / "packages" / "agents"
if agents_src.exists():
    sys.path.insert(0, str(agents_src))
