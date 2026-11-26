"""Every file `.gitattributes` sends through Git LFS is stored as an LFS pointer (#257).

When a rule such as `*.png filter=lfs` matches a file committed as a plain blob, every checkout shows that file as
modified, and a `git add -A` quietly moves it into LFS. A plain image that should stay plain needs a
`-filter -diff -merge` line after the LFS rules (as #224 did for `web_app/public/wikicommons/**`). The test reads the
committed blobs from the index, so it doesn't depend on whether git-lfs is installed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POINTER = b"version https://git-lfs.github.com/spec/v1"


def _git(*args: str, data: bytes | None = None) -> bytes:
    return subprocess.run(["git", "-C", str(ROOT), *args], input=data, capture_output=True, check=True).stdout


def _lfs_tracked() -> dict[str, str]:
    """Path -> blob id for every tracked file whose `filter` attribute is `lfs`."""
    entries = {}
    for rec in _git("ls-files", "-s", "-z").split(b"\0"):
        if rec:
            meta, path = rec.split(b"\t", 1)
            entries[path.decode()] = meta.split()[1].decode()
    attrs = _git("check-attr", "-z", "--stdin", "filter", data=b"\0".join(p.encode() for p in entries) + b"\0")
    parts = attrs.split(b"\0")
    return {parts[i].decode(): entries[parts[i].decode()]
            for i in range(0, len(parts) - 2, 3) if parts[i + 2] == b"lfs"}


def test_every_file_the_lfs_rules_claim_is_stored_as_an_lfs_pointer():
    tracked = _lfs_tracked()
    batch = _git("cat-file", "--batch", data="".join(f"{blob}\n" for blob in tracked.values()).encode())
    plain, pos = [], 0
    for path in tracked:
        header_end = batch.index(b"\n", pos)
        size = int(batch[pos:header_end].split()[2])
        body = batch[header_end + 1: header_end + 1 + size]
        if not body.startswith(POINTER):
            plain.append(path)
        pos = header_end + 1 + size + 1
    assert not plain, f"plain blobs that .gitattributes sends through LFS: {plain}"


def test_the_images_named_in_257_are_not_sent_through_lfs():
    named = [
        "apps/rag-chat-app/client/public/favicon.svg",
        "web_app/public/favicon.ico",
        "web_app/public/bugs/bug_map_year_play.png",
        "web_app/policy-dashboards/public/communityone_logo.jpg",
    ]
    out = _git("check-attr", "filter", "--", *named).decode()
    assert "filter: lfs" not in out, out


# --- #864: a PDF the site links to must survive the Hugging Face deploy -----------------------------------------
# The deploy drops every raw binary and keeps LFS pointers. `*.pdf filter=lfs` is case-sensitive, so a file named
# `.PDF` was a raw binary, was dropped, and the live site served the app's 404 page in its place.


def _tracked(prefixes: tuple[str, ...]) -> list[str]:
    return [p for p in _git("ls-files", "-z", "--", *prefixes).decode().split("\0") if p]


def test_every_served_pdf_is_in_lfs_whatever_the_case_of_its_extension():
    pdfs = [p for p in _tracked(("web_app/public", "web_docs/static")) if p.lower().endswith(".pdf")]
    assert pdfs, "expected at least the strategic plan"
    out = _git("check-attr", "filter", "--", *pdfs).decode().splitlines()
    not_lfs = [line for line in out if not line.endswith("filter: lfs")]
    assert not not_lfs, f"PDFs the deploy would drop (not in LFS): {not_lfs}"


def test_every_pdf_path_the_app_links_to_is_a_tracked_file():
    import re

    served = set(_tracked(("web_app/public",)))
    linked: set[str] = set()
    for path in _tracked(("web_app/src",)):
        if path.endswith((".tsx", ".ts")):
            text = (ROOT / path).read_text(encoding="utf-8", errors="replace")
            linked.update(re.findall(r"""["'](/pdf/[^"'?#\s]+\.[Pp][Dd][Ff])["']""", text))
    assert linked, "expected the home pages to link the strategic plan"
    missing = sorted(p for p in linked if f"web_app/public{p}" not in served)
    assert not missing, f"linked PDF paths with no file under web_app/public (paths are case-sensitive): {missing}"
