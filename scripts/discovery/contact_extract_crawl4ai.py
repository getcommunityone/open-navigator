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
import sys
from typing import List, Optional

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
        schema=ContactDirectory.model_json_schema(),
        extraction_type="schema",
        instruction=instruction,
        input_format="markdown",
        apply_chunking=False,
        extra_args={"temperature": 0.0, "max_tokens": 2000},
    )
    browser_config = BrowserConfig(headless=True, enable_stealth=True, magic=True)
    run_config = CrawlerRunConfig(
        extraction_strategy=llm_strategy,
        cache_mode=CacheMode.BYPASS,
        process_iframes=True,
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
