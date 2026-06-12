---
sidebar_label: Developing on Windows
---

# Developing on Windows

Notes for getting the Python workspace and its test suite running on Windows.

The `Makefile`, `install.sh`, and `make` targets are Unix-oriented (they call
`./install.sh` and `source venv/bin/activate`), so they don't work as-is from a
Windows shell. These steps cover the [`uv`](https://docs.astral.sh/uv/) workspace
path, which installs the local `packages/*` so imports such as
`from llm.gemini.transcript_cache_paths import ...` resolve. PowerShell is assumed.

## Prerequisites

- Python 3.11+ (the workspace targets `>=3.11`)
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- Git

## Setup

From the repository root:

```powershell
uv sync
```

This creates `.venv` and installs the workspace members (`communityone-core`,
`communityone-llm`, `communityone-scrapers`, …) in editable mode, which is what
makes the top-level `llm`, `scrapers`, `ingestion`, … imports work.

Then install two things `uv sync` does **not** pull in:

```powershell
uv pip install pytest black ruff
uv pip install yt-dlp
```

Why these are needed on the `uv` path:

- **Test/lint tools.** `pytest`, `black`, and `ruff` are listed in the root
  `requirements.txt`, but `uv sync` resolves only the workspace packages'
  declared dependencies and there is no `uv` dev-dependency group, so they are
  not installed. (The pip path below installs them via `requirements.txt`.)
- **`yt-dlp`.** Importing the Gemini transcript-cache modules transitively pulls
  in `scrapers.youtube`, which imports `yt_dlp` at module load. `yt-dlp` is in
  `requirements.txt` but is not declared as a dependency of any workspace
  package, so `uv sync` leaves it out. Without it, test collection fails with
  `ModuleNotFoundError: No module named 'yt_dlp'`.

## Running tests on Windows

Run the test suite through the venv's own interpreter:

```powershell
.venv\Scripts\python -m pytest tests\test_transcript_cache_geography.py -v --basetemp=.pytest_basetemp
```

Two Windows-specific reasons for this exact form:

- **`.venv\Scripts\python -m pytest`, not a bare `pytest` or `uv run pytest`.**
  A bare `pytest` can resolve to a different interpreter on `PATH` (for example
  an Anaconda base environment) where the workspace packages are not installed,
  giving `ModuleNotFoundError: No module named 'llm'`. `uv run` re-syncs the
  environment first, which can drop the ad-hoc `uv pip install`ed tools above.
  Invoking the venv's Python directly avoids both.
- **`--basetemp=.pytest_basetemp`.** Pytest's default temp directory
  (`%LOCALAPPDATA%\Temp\pytest-of-<user>`) can raise
  `PermissionError: [WinError 5] Access is denied` on some Windows setups.
  Pointing `--basetemp` at a folder inside the repo sidesteps it. (Add
  `.pytest_basetemp/` to your local ignores if it isn't already covered.)

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `ModuleNotFoundError: No module named 'llm'` | pytest ran under a different Python (e.g. Anaconda base) | run `.venv\Scripts\python -m pytest …` |
| `ModuleNotFoundError: No module named 'yt_dlp'` | not in the `uv` workspace closure | `uv pip install yt-dlp` |
| `pytest` / `black` / `ruff` not recognised | not in the `uv` workspace closure | `uv pip install pytest black ruff` |
| `PermissionError: [WinError 5] Access is denied` during test setup | Windows temp-dir permissions | add `--basetemp=.pytest_basetemp` |
| Tools disappear after `uv run` | `uv run` re-syncs and drops ad-hoc installs | use `.venv\Scripts\python -m pytest` |

## Alternative: the pip path

CI installs the backend with pip rather than `uv`, and `requirements.txt`
includes `pytest`, `black`, `ruff`, and `yt-dlp`. To mirror that locally:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install --no-deps -e packages/core -e packages/datamodels -e packages/agents -e packages/ingestion -e packages/llm
```

The `-e packages/*` editable installs are what make `llm`, `ingestion`, etc.
import as top-level modules (see `.github/workflows/ci-build-test.yml`).
