#!/usr/bin/env python3
"""
Create governance pipeline folders on a mounted Google Drive (WSL / Linux).

Uses the same paths as ``packages/llm/src/llm/governance/02_init_drive_layout.ipynb`` and
``GovernancePipelinePaths`` in ``core_lib.gdrive_paths``.

Environment (optional):
  LOG_GDRIVE_MOUNT                 Drive mount root (default: /mnt/g/My Drive)
  GOVERNANCE_PIPELINE_DATA_ROOT    Absolute override for pipeline root
  GOVERNANCE_PIPELINE_GDRIVE_BASE  Relative to mount (default: CommunityOne/hackathons/2026_Gemma_4_Good)

From repo root:
  .venv/bin/python scripts/utils/ensure_governance_pipeline_drive_layout.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_repo = Path(__file__).resolve().parents[2]
for _p in (str(_repo), str(_repo / "packages" / "core-lib" / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core_lib.gdrive_paths import GovernancePipelinePaths  # noqa: E402


def main() -> int:
    paths = GovernancePipelinePaths.resolve()
    try:
        paths.ensure_dirs()
    except OSError as exc:
        sys.stderr.write(
            f"Could not create directories under {paths.root} ({exc}).\n"
            "Mount Google Drive (see LOG_GDRIVE_MOUNT) or set GOVERNANCE_PIPELINE_DATA_ROOT "
            "to a writable folder.\n"
        )
        return 1
    print("Governance pipeline directories ready:")
    print(f"  root           {paths.root}")
    print(f"  raw_inputs     {paths.raw_inputs}")
    print(f"  orbis_files    {paths.orbis_files}")
    print(f"  transcripts    {paths.transcripts}")
    print(f"  gemma_json     {paths.gemma_json}")
    print(f"  human_summaries {paths.human_summaries}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
