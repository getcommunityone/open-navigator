"""The Space's nginx must never cache the service worker files (#913, #918).

The app is a PWA. A device keeps serving the old site from its cache until it sees a new
`sw.js`; when that file was sent with a day-long cache, a phone still showed the old Chat page
an hour after a deploy.

#918: the first fix put the rule at server level, where it never applied to the `.js` files.
nginx tries the nested regex rules of the matched prefix location first, in order, and
`location /` has a nested rule for every `.js`. So the rule has to be nested in `location /`
and come before that one. These tests pin the placement, not just the text.
"""

from __future__ import annotations

import re
from pathlib import Path

CONF = (Path(__file__).resolve().parents[1] / ".huggingface" / "nginx.conf").read_text()
SW_RULE = re.compile(r"location ~ (\S*sw\\\.js\S*) \{")
STATIC_RULE = "location ~* \\.(js|css|"


def _block(text: str, start: int) -> str:
    """The text of the brace block that opens at or after ``start``."""
    i = text.index("{", start)
    depth = 0
    for j in range(i, len(text)):
        depth += text[j] == "{"
        depth -= text[j] == "}"
        if depth == 0:
            return text[i : j + 1]
    raise AssertionError("unbalanced braces in nginx.conf")


def _root_location() -> str:
    m = re.search(r"\n        location / \{", CONF)
    assert m, "no `location /` block in .huggingface/nginx.conf"
    return _block(CONF, m.start())


def test_service_worker_files_are_sent_no_cache():
    m = SW_RULE.search(CONF)
    assert m, "no location block for the service worker files"
    block = _block(CONF, m.start())
    assert 'add_header Cache-Control "no-cache, no-store, must-revalidate";' in block
    assert "max-age" not in block and "expires" not in block


def test_the_rule_covers_every_file_the_pwa_plugin_emits():
    regex = re.compile(SW_RULE.search(CONF).group(1))
    for path in ("/sw.js", "/registerSW.js", "/workbox-9c191d2f.js", "/manifest.webmanifest"):
        assert regex.search(path), path
    for path in ("/assets/index-abc.js", "/api/sw.js", "/index.html"):
        assert not regex.search(path), path


def test_the_rule_is_nested_in_the_root_location_before_the_static_file_rule():
    root = _root_location()
    sw = SW_RULE.search(root)
    assert sw, "the service worker rule must be inside `location /` (#918)"
    static = root.find(STATIC_RULE)
    assert static != -1, "expected the generic static-file rule inside `location /`"
    assert sw.start() < static, "the service worker rule must come before the generic .js rule (#918)"


def test_there_is_only_one_service_worker_rule():
    assert len(SW_RULE.findall(CONF)) == 1
