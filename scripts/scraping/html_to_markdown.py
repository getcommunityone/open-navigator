"""
Convert HTML to clean Markdown-ish text for LLM extraction.

Strips scripts, styles, nav chrome where possible, and avoids feeding raw nested
<div> trees to the model.
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString, Tag


_STRIP_TAGS = (
    "script",
    "style",
    "noscript",
    "svg",
    "template",
    "iframe",
    "object",
    "embed",
    "link",
    "meta",
    "head",
)


def html_to_markdown(
    html: str,
    *,
    source_url: str = "",
    max_chars: int = 120_000,
) -> str:
    """
    Produce compact Markdown-like text from HTML.

    Uses BeautifulSoup only (no html2text dependency). Truncates to ``max_chars``.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(list(_STRIP_TAGS)):
        tag.decompose()

    root = soup.find("main") or soup.find("article") or soup.find(id="content") or soup.body or soup
    parts: list[str] = []
    if source_url:
        parts.append(f"# Source\n\n{source_url}\n")

    _walk(root, parts, base_url=source_url)
    body = "\n\n".join(p for p in parts if p.strip())
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    if len(body) > max_chars:
        body = body[:max_chars] + "\n\n...[truncated for LLM context]..."
    return body


def _walk(node: Tag | NavigableString, parts: list[str], *, base_url: str, depth: int = 0) -> None:
    if isinstance(node, NavigableString):
        text = str(node).strip()
        if text:
            parts.append(text)
        return
    if not isinstance(node, Tag):
        return

    name = (node.name or "").lower()
    if name in _STRIP_TAGS:
        return

    if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
        level = int(name[1])
        inner = _inline_text(node).strip()
        if inner:
            parts.append(f"{'#' * level} {inner}")
        return

    if name == "a":
        href = (node.get("href") or "").strip()
        label = _inline_text(node).strip() or href
        if href and label:
            abs_url = urljoin(base_url, href) if base_url else href
            parts.append(f"[{label}]({abs_url})")
        elif label:
            parts.append(label)
        return

    if name == "li":
        inner = _inline_text(node).strip()
        if inner:
            parts.append(f"- {inner}")
        return

    if name in ("p", "div", "section", "article", "main", "td", "th", "tr", "ul", "ol", "table"):
        for child in node.children:
            _walk(child, parts, base_url=base_url, depth=depth + 1)
        return

    for child in node.children:
        _walk(child, parts, base_url=base_url, depth=depth + 1)


def _inline_text(node: Tag) -> str:
    return node.get_text(" ", strip=True)


def readable_txt_to_markdown(text: str, *, max_chars: int = 120_000) -> str:
    """Use an existing ``page_*.readable.txt`` sidecar (already stripped) as LLM input."""
    lines = text.splitlines()
    if lines and lines[0].startswith("Source:"):
        body = "\n".join(lines[2:]).strip() if len(lines) > 2 else text
    else:
        body = text.strip()
    if len(body) > max_chars:
        body = body[:max_chars] + "\n\n...[truncated]..."
    return body
