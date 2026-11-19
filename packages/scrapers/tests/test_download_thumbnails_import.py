"""download_thumbnails must import on main (#491): it once pointed at the removed scripts.discovery path."""

from __future__ import annotations

import importlib


def test_download_thumbnails_imports_and_uses_the_package_slugifier():
    mod = importlib.import_module("scrapers.youtube.download_thumbnails")
    naming = importlib.import_module("scrapers.discovery.meeting_document_naming")
    assert mod.slugify_meeting_filename is naming.slugify_meeting_filename
