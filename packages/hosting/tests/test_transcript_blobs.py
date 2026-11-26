"""Azure transcript blob key helpers (#630) — no live Azure required."""

from __future__ import annotations

import pytest

from hosting.azure.transcript_blobs import blob_name_for_video


def test_blob_name_for_video():
    assert blob_name_for_video("Sk0m1dHUJjg") == "transcripts/Sk0m1dHUJjg.json"


def test_blob_name_rejects_path_traversal():
    with pytest.raises(ValueError):
        blob_name_for_video("../etc/passwd")
    with pytest.raises(ValueError):
        blob_name_for_video("a/b")
