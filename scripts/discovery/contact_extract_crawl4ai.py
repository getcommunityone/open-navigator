#!/usr/bin/env python3
"""
LLM-backed contact-directory extraction via `crawl4ai` + Groq.

Standalone alternative to the heuristic extractor in
``scripts.discovery.contact_extract_from_html`` for pages whose roster is
prose-shaped (e.g. ``https://applingcountyga.org/?page_id=1464``: "L – R
Standing — County Manager Reid Lovett; Commissioner Daryl Edwards, District 3;
…"). Renders the page in a headless browser, hands the LLM the cleaned
markdown, and asks for a strict JSON object matching :class:`ContactDirectory`.

Setup (once):

.. code:: bash

    pip install -U crawl4ai pydantic litellm
    crawl4ai-setup
    export GROQ_API_KEY=...

CLI:

.. code:: bash

    python -m scripts.discovery.contact_extract_crawl4ai \
        https://applingcountyga.org/?page_id=1464
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
import threading
from typing import List, Optional
from urllib.parse import urljoin

from pydantic import BaseModel, Field


class ContactRecord(BaseModel):
    name: Optional[str] = Field(
        None,
        description=(
            "Full personal name of the official as written on the page, with honorific "
            "stripped (e.g. 'Reid Lovett', not 'County Manager Reid Lovett'). Keep "
            "suffixes like 'Jr.' / 'III'. Null if only a role is listed."
        ),
    )
    title: Optional[str] = Field(
        None,
        description=(
            "Government role or office held. Use the exact honorific text from the page "
            "(e.g. 'Commissioner', 'Chairman', 'Vice Chairman', 'Mayor', 'Vice Mayor', "
            "'County Manager', 'County Administrator', 'Council Member', 'Alderman', "
            "'Supervisor', 'Trustee', 'Clerk', 'Sheriff', 'Tax Commissioner', "
            "'Probate Judge', 'Treasurer', 'Assessor', 'Superintendent')."
        ),
    )
    district: Optional[str] = Field(
        None,
        description=(
            "District / ward / seat label if the official represents one, copied verbatim "
            "(e.g. 'District 3', 'Ward 2', 'At-Large', 'Post 4'). Null when not listed."
        ),
    )
    email: Optional[str] = Field(
        None,
        description="Official email if shown on the page. Null if not present.",
    )
    phone: Optional[str] = Field(
        None,
        description="Office phone number if shown on the page (with extension if listed).",
    )
    profile_image_url: Optional[str] = Field(
        None,
        description=(
            "Absolute URL of the individual's headshot/portrait image when one is "
            "visibly tied to this person. Skip site logos, banners, group photos, and "
            "social-media icons."
        ),
    )
    social_profiles: List[str] = Field(
        default_factory=list,
        description=(
            "Absolute URLs of social-media profiles for THIS official (LinkedIn, X, "
            "Facebook, Instagram). Do not include the jurisdiction's own social pages."
        ),
    )


class ContactDirectory(BaseModel):
    contacts: List[ContactRecord] = Field(
        default_factory=list,
        description=(
            "Distinct elected officials, appointed officers, and senior staff named on "
            "the page. Each person appears at most once."
        ),
    )


_DEFAULT_PROVIDER = "groq/llama-3.1-8b-instant"
_DEFAULT_INSTRUCTION = (
    "You are extracting a roster of U.S. local-government officials from a county, "
    "city, or town website (board of commissioners, city council, mayor / staff "
    "directory, etc.).\n"
    "\n"
    "INCLUDE only people who hold a government office or senior staff role at this "
    "jurisdiction. Valid roles include (non-exhaustive): Commissioner, Chairman, "
    "Vice Chairman, Mayor, Vice Mayor, Council Member, Alderman, Supervisor, "
    "Trustee, County Manager, County Administrator, City Manager, City "
    "Administrator, Clerk, Sheriff, Tax Commissioner, Probate Judge, Treasurer, "
    "Assessor, Superintendent, Department Director / Head.\n"
    "\n"
    "EXCLUDE: web-page authors (Wordpress 'Posted by ...', JSON-LD Article "
    "authors), blog commenters, photographers, contractors, vendors, generic "
    "'webmaster' / 'info@' mailboxes, navigation labels, and any name that only "
    "appears in a footer copyright line or breadcrumb.\n"
    "\n"
    "Watch for prose-style rosters where multiple officials are concatenated in a "
    "single sentence with semicolons or commas, e.g. 'L – R Standing — County "
    "Manager Reid Lovett; Commissioner Daryl Edwards, District 3; Commissioner "
    "Jakharis Jones, District 2.' Split these into one record per person.\n"
    "\n"
    "Strip the honorific from the `name` field and put it in `title`. Put any "
    "'District N' / 'Ward N' / 'Post N' / 'At-Large' label into `district`. Leave "
    "any field null when the page does not state it — do not guess. De-duplicate "
    "people who appear in multiple sections (e.g. once in a photo caption and once "
    "in a contact list); merge their fields. Return a single JSON object matching "
    "the schema; the `contacts` array may be empty if the page is not a roster."
)


async def extract_contact_directory(
    url: str,
    *,
    provider: str = _DEFAULT_PROVIDER,
    api_token: Optional[str] = None,
    instruction: str = _DEFAULT_INSTRUCTION,
) -> ContactDirectory:
    """Fetch ``url`` with crawl4ai and return contacts as a validated :class:`ContactDirectory`.

    ``api_token`` defaults to ``$GROQ_API_KEY``. Raises ``RuntimeError`` if neither
    is set, ``ImportError`` if ``crawl4ai`` is not installed, or the underlying
    crawl error if the page cannot be loaded.
    """
    token = api_token or os.getenv("GROQ_API_KEY")
    if not token:
        raise RuntimeError("GROQ_API_KEY is not set (or pass api_token=...).")

    try:
        from crawl4ai import (
            AsyncWebCrawler,
            BrowserConfig,
            CacheMode,
            CrawlerRunConfig,
            LLMConfig,
        )
        from crawl4ai.extraction_strategy import LLMExtractionStrategy
    except ImportError as exc:
        raise ImportError(
            "crawl4ai is not installed. Run `pip install -U crawl4ai litellm` "
            "and `crawl4ai-setup` once to install the headless browser."
        ) from exc

    llm_config = LLMConfig(provider=provider, api_token=token)
    llm_strategy = LLMExtractionStrategy(
        llm_config=llm_config,
        schema=ContactRecord.model_json_schema(),
        extraction_type="schema",
        instruction=instruction,
        input_format="markdown",
        apply_chunking=False,
        extra_args={"temperature": 0.0, "max_tokens": 2000},
    )
    browser_config = BrowserConfig(headless=True, enable_stealth=True)
    run_config = CrawlerRunConfig(
        extraction_strategy=llm_strategy,
        cache_mode=CacheMode.BYPASS,
        process_iframes=True,
        magic=True,
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=url, config=run_config)

    if not result.success:
        raise RuntimeError(f"crawl4ai failed for {url}: {result.error_message}")

    raw = (result.extracted_content or "").strip()
    if not raw:
        return ContactDirectory()

    payload = json.loads(raw)
    if isinstance(payload, list):
        payload = {"contacts": payload}
    return ContactDirectory.model_validate(payload)


def ai_record_to_structured_row(
    rec: ContactRecord,
    *,
    source_page_url: str,
    page_classification: str = "ai_crawl4ai",
    directory_score: int = 0,
    extraction_method: str = "crawl4ai_llm",
) -> dict:
    """Map a :class:`ContactRecord` to the structured-contacts row shape used by
    ``scripts.discovery.contacts_bundle`` and the manifest's ``structured_contacts``.

    District goes into ``department`` to stay compatible with
    ``normalize_structured_contact_row``'s existing district handling.
    """
    name = (rec.name or "").strip() or None
    title = (rec.title or "").strip() or None
    district = (rec.district or "").strip() or None
    email = (rec.email or "").strip().lower() or None
    phone = (rec.phone or "").strip() or None
    profile_image = (rec.profile_image_url or "").strip() or None
    if profile_image and not re.match(r"^https?://", profile_image, re.I):
        profile_image = urljoin(source_page_url, profile_image)
    return {
        "person_name": name,
        "title_or_role": title,
        "department": district,
        "email": email,
        "phone": phone,
        "mailing_address": None,
        "profile_url": None,
        "profile_image_url": profile_image,
        "source_page_url": source_page_url,
        "page_classification": page_classification,
        "directory_score": int(directory_score),
        "extraction_method": extraction_method,
        "raw_row": rec.model_dump(mode="json"),
    }


_COMMISSIONER_URL_PATTERNS: tuple = (
    "board-of-commissioner",
    "board_of_commissioner",
    "/commissioners",
    "/commissioner-",
    "county-commission",
    "/boc",
)

_COMMISSIONER_HEADING_RE = re.compile(
    r"(?i)\b(board\s+of\s+(?:county\s+)?commissioners?"
    r"|county\s+commission(?:ers?)?"
    r"|board\s+of\s+county\s+commissioners?)\b"
)

_ROSTER_URL_PATTERNS: tuple = (
    "board-of-commissioner",
    "board_of_commissioner",
    "/commissioners",
    "/commissioner-",
    "county-commission",
    "/boc",
    "city-council",
    "town-council",
    "village-council",
    "board-of-education",
    "school-board",
    "elected-official",
    "county-official",
    "/officials",
    "department-head",
    "/leadership",
    "/staff",
    "contact-directory",
)

_ROSTER_HEADING_RE = re.compile(
    r"(?i)\b("
    r"board\s+of\s+(?:county\s+)?commissioners?"
    r"|county\s+commission(?:ers?)?"
    r"|city\s+council|town\s+council|village\s+council"
    r"|board\s+of\s+education|school\s+board"
    r"|elected\s+officials?|county\s+officials?"
    r"|mayor\s+(?:and|&)\s+council"
    r"|leadership|department\s+heads?|administration"
    r")\b"
)


def looks_like_commissioner_page(url: str, html: Optional[str] = None) -> bool:
    """Return True when a page is likely a county board-of-commissioners roster.

    Cheap gate so the LLM is only spent on pages the heuristic extractor most
    often gets wrong (Wix-style ``<h2>Name, District</h2>`` + sibling headshot
    ``<img>`` layouts in particular). Matches by URL slug or, failing that, by
    an ``<h1>``/``<h2>``/``<h3>`` heading mentioning "Board of Commissioners" /
    "County Commission".
    """
    u = (url or "").lower()
    if any(p in u for p in _COMMISSIONER_URL_PATTERNS):
        return True
    if html:
        for m in re.finditer(r"<h[1-3][^>]*>(.*?)</h[1-3]>", html, flags=re.I | re.S):
            text = re.sub(r"<[^>]+>", " ", m.group(1))
            if _COMMISSIONER_HEADING_RE.search(text):
                return True
    return False


def looks_like_contact_roster_page(url: str, html: Optional[str] = None) -> bool:
    """Cheap gate for likely contact-roster pages (officials/council/board/staff)."""
    u = (url or "").lower()
    if any(p in u for p in _ROSTER_URL_PATTERNS):
        return True
    if html:
        for m in re.finditer(r"<h[1-3][^>]*>(.*?)</h[1-3]>", html, flags=re.I | re.S):
            text = re.sub(r"<[^>]+>", " ", m.group(1))
            if _ROSTER_HEADING_RE.search(text):
                return True
    return False


def _html_to_markdown(html: str) -> str:
    """Convert HTML to compact markdown for LLM extraction.

    Strips ``<script>`` / ``<style>`` / ``<nav>`` / ``<footer>`` (junk that
    inflates the prompt without changing the roster), preserves heading levels
    and image ``alt`` text (Wix headshots are named ``headshot_<Person>.jpg``
    in their ``alt`` attribute — that signal carries the roster).
    """
    from markdownify import markdownify

    md = markdownify(
        html,
        heading_style="ATX",
        strip=["script", "style", "nav", "footer", "noscript"],
    )
    return re.sub(r"\n{3,}", "\n\n", md).strip()


def _ensure_litellm() -> "object":
    try:
        import litellm  # noqa: F401
    except ImportError as exc:  # pragma: no cover - import error path
        raise ImportError(
            "litellm is not installed. Run `pip install -U litellm`."
        ) from exc
    return litellm


def _contact_ai_retry_attempts() -> int:
    try:
        return max(1, min(6, int((os.getenv("SCRAPED_CONTACT_AI_RETRY_ATTEMPTS") or "3").strip())))
    except ValueError:
        return 3


def _contact_ai_retry_base_delay_s() -> float:
    try:
        return max(0.1, min(10.0, float((os.getenv("SCRAPED_CONTACT_AI_RETRY_BASE_DELAY_S") or "1.0").strip())))
    except ValueError:
        return 1.0


def _contact_ai_retry_max_delay_s() -> float:
    try:
        return max(0.2, min(60.0, float((os.getenv("SCRAPED_CONTACT_AI_RETRY_MAX_DELAY_S") or "12.0").strip())))
    except ValueError:
        return 12.0


def _looks_like_token_or_rate_limit_error(exc: Exception) -> bool:
    s = str(exc).lower()
    return (
        "rate_limit" in s
        or "rate limit" in s
        or "tokens per minute" in s
        or "request too large" in s
        or "tpm" in s
        or "too many requests" in s
    )


def _extract_retry_after_seconds(exc: Exception) -> float:
    m = re.search(r"retry\s*after\s*(\d+(?:\.\d+)?)", str(exc), flags=re.I)
    if not m:
        return 0.0
    try:
        return max(0.0, min(120.0, float(m.group(1))))
    except ValueError:
        return 0.0


_GROQ_CALL_THROTTLE_LOCK = threading.Lock()
_GROQ_CALL_NEXT_ALLOWED_AT = 0.0


def _contact_ai_min_call_interval_s(provider: str) -> float:
    """Global pacing gate between LLM calls.

    Groq on-demand is token-per-minute constrained, so we default to a conservative
    one-minute spacing for Groq-backed calls unless the caller overrides it.
    """
    raw = (os.getenv("SCRAPED_CONTACT_AI_MIN_CALL_INTERVAL_S") or "").strip()
    if raw:
        try:
            return max(0.0, min(300.0, float(raw)))
        except ValueError:
            pass
    prov = (provider or "").lower()
    if "groq" in prov:
        return 60.0
    return 0.0


def _throttle_before_llm_call(provider: str) -> None:
    """Sleep before a request so we don't burst past provider TPM limits."""
    interval_s = _contact_ai_min_call_interval_s(provider)
    if interval_s <= 0:
        return
    global _GROQ_CALL_NEXT_ALLOWED_AT
    with _GROQ_CALL_THROTTLE_LOCK:
        now = time.monotonic()
        wait_s = max(0.0, _GROQ_CALL_NEXT_ALLOWED_AT - now)
        _GROQ_CALL_NEXT_ALLOWED_AT = max(_GROQ_CALL_NEXT_ALLOWED_AT, now) + interval_s
        if wait_s > 0:
            time.sleep(wait_s)


def _call_llm_for_contacts(
    markdown: str,
    *,
    page_url: str,
    provider: str,
    api_token: str,
    instruction: str,
    max_chars: Optional[int] = None,
) -> ContactDirectory:
    """Send page markdown to ``provider`` via litellm; parse JSON into ContactDirectory.

    ``max_chars`` caps markdown length sent to the model. If omitted, uses
    ``SCRAPED_CONTACT_AI_MAX_MARKDOWN_CHARS`` when set, else provider-aware
    defaults tuned for cost/speed and TPM limits.
    """
    litellm = _ensure_litellm()
    if max_chars is None:
        env_raw = (os.getenv("SCRAPED_CONTACT_AI_MAX_MARKDOWN_CHARS") or "").strip()
        if env_raw:
            try:
                max_chars = max(2_000, min(80_000, int(env_raw)))
            except ValueError:
                max_chars = None
    if max_chars is None:
        prov = (provider or "").lower()
        if "groq/llama-3.1-8b-instant" in prov:
            max_chars = 12_000
        elif "groq/" in prov:
            max_chars = 18_000
        else:
            max_chars = 30_000
    def _truncate_markdown(src: str, limit: int) -> str:
        if len(src) <= limit:
            return src
        head = int(limit * 0.7)
        tail = limit - head
        return src[:head] + "\n\n... [TRUNCATED] ...\n\n" + src[-tail:]

    effective_max_chars = int(max_chars)
    markdown = _truncate_markdown(markdown, effective_max_chars)
    schema = ContactRecord.model_json_schema()
    system_prompt = (
        f"{instruction}\n\n"
        "Return a single JSON object of the form "
        '{"contacts": [ContactRecord, ...]} with no commentary. Each '
        f"ContactRecord matches this schema: {json.dumps(schema)}"
    )
    user_prompt = f"Source URL: {page_url}\n\nPage content (markdown):\n\n{markdown}"
    retry_attempts = _contact_ai_retry_attempts()
    retry_base_delay_s = _contact_ai_retry_base_delay_s()
    retry_max_delay_s = _contact_ai_retry_max_delay_s()

    resp = None
    last_exc: Optional[Exception] = None
    for attempt in range(1, retry_attempts + 1):
        try:
            _throttle_before_llm_call(provider)
            resp = litellm.completion(  # type: ignore[attr-defined]
                model=provider,
                api_key=api_token,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )
            break
        except Exception as exc:
            last_exc = exc
            if attempt >= retry_attempts:
                raise
            # If rate/token constrained, shrink prompt and retry.
            if _looks_like_token_or_rate_limit_error(exc):
                effective_max_chars = max(3000, int(effective_max_chars * 0.75))
                retry_user_prompt = _truncate_markdown(markdown, effective_max_chars)
                user_prompt = f"Source URL: {page_url}\n\nPage content (markdown):\n\n{retry_user_prompt}"
            retry_after = _extract_retry_after_seconds(exc)
            delay_s = max(
                retry_after,
                min(retry_max_delay_s, retry_base_delay_s * (2 ** (attempt - 1))),
            )
            time.sleep(delay_s)

    if resp is None:
        if last_exc is not None:
            raise last_exc
        return ContactDirectory()
    raw = (resp["choices"][0]["message"]["content"] or "").strip()
    if not raw:
        return ContactDirectory()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return ContactDirectory()
    if isinstance(payload, list):
        payload = {"contacts": payload}
    if not isinstance(payload, dict) or "contacts" not in payload:
        return ContactDirectory()
    return ContactDirectory.model_validate(payload)


def extract_contact_directory_from_html_sync(
    html: str,
    page_url: str,
    *,
    provider: str = _DEFAULT_PROVIDER,
    api_token: Optional[str] = None,
    instruction: str = _DEFAULT_INSTRUCTION,
) -> ContactDirectory:
    """Extract a contact roster from already-fetched HTML (no headless browser).

    Companion to :func:`extract_contact_directory_sync`: the same LLM prompt
    and pydantic schema, but the input is the cached ``_crawl_html/page_*.html``
    snapshot rather than a live URL. Used by the refresh script to recover
    rosters from Wix-style pages whose ``<h2>Name, District</h2>`` blocks the
    heuristic extractor can't pair with their sibling headshot ``<img>`` tags.
    """
    token = api_token or os.getenv("GROQ_API_KEY")
    if not token:
        raise RuntimeError("GROQ_API_KEY is not set (or pass api_token=...).")
    md = _html_to_markdown(html or "")
    if not md:
        return ContactDirectory()
    return _call_llm_for_contacts(
        md,
        page_url=page_url,
        provider=provider,
        api_token=token,
        instruction=instruction,
    )


def extract_contact_directory_sync(
    url: str,
    *,
    provider: str = _DEFAULT_PROVIDER,
    api_token: Optional[str] = None,
    instruction: str = _DEFAULT_INSTRUCTION,
) -> ContactDirectory:
    """Blocking wrapper around :func:`extract_contact_directory` for sync callers."""
    return asyncio.run(
        extract_contact_directory(
            url, provider=provider, api_token=api_token, instruction=instruction
        )
    )


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1] if __doc__ else None)
    p.add_argument("url", help="Page URL to crawl and extract contacts from.")
    p.add_argument(
        "--provider",
        default=_DEFAULT_PROVIDER,
        help=f"LiteLLM provider string (default: {_DEFAULT_PROVIDER}).",
    )
    p.add_argument(
        "--api-token-env",
        default="GROQ_API_KEY",
        help="Env var that holds the LLM API token (default: GROQ_API_KEY).",
    )
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)
    token = os.getenv(args.api_token_env)
    if not token:
        print(f"Error: ${args.api_token_env} is not set.", file=sys.stderr)
        return 2
    try:
        directory = asyncio.run(
            extract_contact_directory(args.url, provider=args.provider, api_token=token)
        )
    except (ImportError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(directory.model_dump(mode="json"), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
