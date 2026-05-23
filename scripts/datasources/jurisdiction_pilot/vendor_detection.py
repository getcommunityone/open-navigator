"""
Detect government website vendors (Legistar, Granicus, CivicPlus, etc.) and provide
vendor-specific scraping optimizations.

This module inspects HTML headers, meta tags, script sources, and DOM patterns
to identify the hosting platform, then returns appropriate scraping strategies.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

VENDOR_SIGNATURES = {
    "legistar": {
        "patterns": [
            r"legistar\.com",
            r'data-legistar',
            r'class=.*legistar',
            r'id=.*legistar',
            r'src=.*legistar\.com',
        ],
        "meta_keywords": ["legistar", "city council", "municipal"],
        "scrapers": ["legistar-sdk"],  # Use python-legistar-scraper
    },
    "granicus": {
        "patterns": [
            r"granicus\.com",
            r'data-granicus',
            r'class=.*granicus',
            r'GranicusGovGateway',
            r'src=.*granicus\.com',
        ],
        "meta_keywords": ["granicus", "government"],
        "scrapers": ["granicus-sdk"],  # Use official SDK
    },
    "civicplus": {
        "patterns": [
            r"civicplus\.com",
            r"civiccms\.com",
            r'class=.*civicplus',
            r'data-civicplus',
            r'src=.*civicplus\.com',
        ],
        "meta_keywords": ["civicplus", "civic cms"],
        "scrapers": ["civicplus-scraper"],
    },
    "esri": {
        "patterns": [
            r"arcgis\.com",
            r"esri\.com",
            r'class=.*esri',
            r'data-esri',
        ],
        "meta_keywords": ["esri", "arcgis", "mapping"],
        "scrapers": ["arcgis-rest-api"],
    },
    "wordpress": {
        "patterns": [
            r"wp-content",
            r'class=.*wordpress',
            r'<meta.*generator.*wordpress',
            r'src=.*wp-json',
        ],
        "meta_keywords": ["wordpress"],
        "scrapers": ["wordpress-scraper", "rest-api"],
    },
    "drupal": {
        "patterns": [
            r"/sites/default/",
            r'class=.*drupal',
            r'<meta.*generator.*drupal',
            r'Drupal\.settings',
        ],
        "meta_keywords": ["drupal"],
        "scrapers": ["drupal-scraper"],
    },
}


def detect_vendor(html: str, url: str | None = None) -> dict[str, Any]:
    """
    Detect government website vendor/platform.

    Args:
        html: Page HTML content
        url: Optional page URL (helps with domain-based detection)

    Returns:
        {
            "vendor": "legistar" | "granicus" | etc,
            "confidence": 0.0-1.0,
            "signals": ["signal1", "signal2"],  # What matched
            "scrapers": ["sdk-name"],  # Recommended SDKs/libraries
            "api_available": bool,
            "notes": "Additional context"
        }
    """
    if not html:
        return {
            "vendor": None,
            "confidence": 0.0,
            "signals": [],
            "scrapers": [],
            "api_available": False,
            "notes": "Empty HTML",
        }

    results: dict[str, tuple[float, list[str]]] = {}  # vendor -> (confidence, signals)

    # Check each vendor
    for vendor, signatures in VENDOR_SIGNATURES.items():
        signals: list[str] = []
        score = 0.0

        # Check patterns in HTML
        for pattern in signatures.get("patterns", []):
            if re.search(pattern, html, re.IGNORECASE):
                signals.append(f"pattern:{pattern[:30]}")
                score += 0.3

        # Check meta keywords/descriptions
        if BeautifulSoup:
            try:
                soup = BeautifulSoup(html, "html.parser")

                # Check meta generator
                generator = soup.find("meta", {"name": "generator"})
                if generator and vendor.lower() in generator.get("content", "").lower():
                    signals.append("meta:generator")
                    score += 0.4

                # Check title
                title = soup.title
                if title and vendor.lower() in title.string.lower():
                    signals.append("title")
                    score += 0.2

                # Check script sources
                for script in soup.find_all("script", src=True):
                    src = script.get("src", "").lower()
                    if vendor.lower() in src:
                        signals.append(f"script:{vendor}")
                        score += 0.3

                # Check for API endpoints
                for script in soup.find_all("script"):
                    if script.string and f"{vendor}_api" in script.string.lower():
                        signals.append("api:mentioned")
                        score += 0.2

            except Exception:
                pass

        # Check URL domain
        if url:
            domain = urlparse(url).netloc.lower()
            if vendor.lower() in domain:
                signals.append(f"domain:{vendor}")
                score += 0.5

        if score > 0:
            results[vendor] = (min(score, 1.0), signals)

    # Return highest confidence match
    if not results:
        return {
            "vendor": None,
            "confidence": 0.0,
            "signals": [],
            "scrapers": [],
            "api_available": False,
            "notes": "No known vendor detected; may be custom CMS",
        }

    best_vendor = max(results.items(), key=lambda x: x[1][0])
    vendor_name, (confidence, signals) = best_vendor

    return {
        "vendor": vendor_name,
        "confidence": confidence,
        "signals": signals,
        "scrapers": VENDOR_SIGNATURES[vendor_name].get("scrapers", []),
        "api_available": confidence > 0.5,
        "notes": _get_vendor_notes(vendor_name),
    }


def _get_vendor_notes(vendor: str) -> str:
    """Get optimization notes for a specific vendor."""
    notes = {
        "legistar": (
            "Use python-legistar-scraper SDK. Provides structured access to "
            "meetings, agendas, minutes. Stable API. Rate-limit friendly."
        ),
        "granicus": (
            "Use official Granicus API (SwaggerHub). RESTful, well-documented. "
            "May require authentication. Check terms of service."
        ),
        "civicplus": (
            "CivicPlus sites often use iframes and dynamic content. "
            "Check for REST API endpoints (/api/...). May need Playwright for JS rendering."
        ),
        "esri": (
            "Use ArcGIS REST API (open standard). Good for data lookup & mapping queries. "
            "Rate limits apply; respect them."
        ),
        "wordpress": (
            "Use WordPress REST API (/wp-json/wp/v2/...). Check robots.txt for /wp-admin/ restrictions. "
            "Often has contact/staff plugins."
        ),
        "drupal": (
            "Drupal sites may expose REST API via /jsonapi/ endpoint. "
            "Check /admin/rest/resource for enabled resources."
        ),
    }
    return notes.get(vendor, "No specific optimization notes.")


def should_use_sdk(detect_result: dict[str, Any]) -> bool:
    """Determine if an official SDK should be used."""
    return (
        detect_result.get("confidence", 0) > 0.6
        and len(detect_result.get("scrapers", [])) > 0
    )


def get_scraping_strategy(html: str, url: str | None = None) -> dict[str, Any]:
    """
    Get full scraping strategy (vendor detection + recommendations).

    Returns:
        {
            "vendor": "...",
            "use_sdk": bool,  # Should use official library?
            "use_api": bool,  # API available?
            "custom_scraper": bool,  # Fall back to HTML scraping?
            "render_js": bool,  # Need Playwright/Puppeteer?
            "recommendations": ["tip1", "tip2"],
        }
    """
    detect = detect_vendor(html, url)
    vendor = detect.get("vendor")

    strategies = {
        "legistar": {
            "use_sdk": True,
            "use_api": True,
            "custom_scraper": False,
            "render_js": False,
            "recommendations": [
                "Use python-legistar-scraper for meetings/agendas/minutes",
                "Check if site exposes contacts page (/api/v1/bodies...)",
                "Cache results (data changes infrequently)",
            ],
        },
        "granicus": {
            "use_sdk": True,
            "use_api": True,
            "custom_scraper": False,
            "render_js": False,
            "recommendations": [
                "Check Granicus SwaggerHub for API docs",
                "Look for /Granicus/ API endpoints",
                "May require API key (check publicly available first)",
            ],
        },
        "civicplus": {
            "use_sdk": False,
            "use_api": False,
            "custom_scraper": True,
            "render_js": True,  # Often uses JS
            "recommendations": [
                "Look for /api/ endpoints in Network tab",
                "Check for embedded PowerBI/Tableau reports",
                "Use Playwright for JS-heavy pages",
                "Contacts often in /departments or /staff sections",
            ],
        },
        "wordpress": {
            "use_sdk": False,
            "use_api": True,
            "custom_scraper": True,
            "render_js": False,
            "recommendations": [
                "Use /wp-json/wp/v2/ REST API for posts/pages",
                "Check for custom endpoints via /wp-json/",
                "Look for contact form plugins (gravity forms, ninja forms)",
                "Respect /robots.txt restrictions",
            ],
        },
    }

    strategy = strategies.get(vendor, {
        "use_sdk": False,
        "use_api": False,
        "custom_scraper": True,
        "render_js": False,
        "recommendations": [
            "No known vendor optimization available",
            "Use standard HTML scraping approach",
            "Check for API endpoints manually",
        ],
    })

    return {
        **detect,
        **strategy,
    }
