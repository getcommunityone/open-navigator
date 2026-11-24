"""The Space's nginx must never cache the service worker files (#913).

The app is a PWA. A device keeps serving the old site from its cache until it sees a new
`sw.js`; when that file was sent with a day-long cache, a phone still showed the old Chat page
an hour after a deploy.
"""

from __future__ import annotations

import re
from pathlib import Path

CONF = (Path(__file__).resolve().parents[1] / ".huggingface" / "nginx.conf").read_text()


def _service_worker_block() -> str:
    m = re.search(r"location ~ (\S*sw\\\.js\S*) \{(.*?)\n        \}", CONF, re.S)
    assert m, "no location block for the service worker files in .huggingface/nginx.conf"
    return m.group(1) + m.group(2)


def test_service_worker_files_are_sent_no_cache():
    block = _service_worker_block()
    assert 'add_header Cache-Control "no-cache, no-store, must-revalidate";' in block
    assert "max-age" not in block and "expires" not in block


def test_the_block_covers_every_file_the_pwa_plugin_emits():
    pattern = _service_worker_block().split()[0]
    regex = re.compile(pattern)
    for path in ("/sw.js", "/registerSW.js", "/workbox-9c191d2f.js", "/manifest.webmanifest"):
        assert regex.search(path), path
    for path in ("/assets/index-abc.js", "/api/sw.js", "/index.html"):
        assert not regex.search(path), path
