#!/usr/bin/env python3
"""Probe Google AI Studio Gemma ids: text stream + optional audio (see notebook §3b).

Run as a package module from the repo root::

  python -m llm.governance.probe_google_gemma_studio --models gemma-4-26b-a4b-it
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from .governance_meeting_llm import print_probe_google_gemma_studio


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--audio",
        type=Path,
        default=None,
        help="Small .opus/.mp3 clip to test audio modality (first ~30s ideal)",
    )
    p.add_argument(
        "--models",
        nargs="*",
        default=None,
        help="Model ids to probe (default: 26b-a4b, e2b, gemini flash)",
    )
    args = p.parse_args()
    key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
    if not key:
        raise SystemExit("Set GEMINI_API_KEY or GOOGLE_API_KEY")
    print_probe_google_gemma_studio(key, audio_path=args.audio, models=args.models)


if __name__ == "__main__":
    main()
