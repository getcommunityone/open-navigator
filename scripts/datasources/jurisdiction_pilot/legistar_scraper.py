"""
Scrape Legistar platform for meetings, council members, and official contacts.

Legistar is the most common municipal government software in the US. This module
leverages the python-legistar-scraper library (opencivicdata) to extract:
- Council members and their contact info
- Meeting agendas and minutes
- Voting records
- Event calendars
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    from legistar.scraper import LegistarScraper
except ImportError:
    LegistarScraper = None


def get_legistar_council_members(
    legistar_url: str,
) -> list[dict[str, Any]]:
    """
    Extract council members from a Legistar instance.

    Args:
        legistar_url: Base URL of the Legistar instance (e.g., "https://chicago.legistar.com")

    Returns:
        List of dicts with name, title, email, etc.
    """
    if not LegistarScraper:
        logger.warning("python-legistar-scraper not installed. Install with: pip install legistar")
        return []

    if not legistar_url:
        return []

    try:
        scraper = LegistarScraper(legistar_url)
        members = []

        for person in scraper.councillors:
            member = {
                "person_name": person.get("name", ""),
                "title_or_role": person.get("role", "Council Member"),
                "email": person.get("email") or person.get("contact_form"),
                "phone": person.get("phone"),
                "profile_url": person.get("url"),
                "extraction_method": "legistar_api",
                "source_platform": "legistar",
            }
            if member["person_name"]:
                members.append(member)

        logger.info("Extracted %d council members from Legistar", len(members))
        return members

    except Exception as exc:
        logger.error("Failed to scrape Legistar %s: %s", legistar_url, exc)
        return []


def get_legistar_meetings(
    legistar_url: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    Extract recent meetings from Legistar.

    Returns list of meetings with date, agenda, minutes URLs, etc.
    """
    if not LegistarScraper:
        return []

    if not legistar_url:
        return []

    try:
        scraper = LegistarScraper(legistar_url)
        meetings = []

        for event in scraper.events(limit=limit):
            meeting = {
                "date": event.get("date"),
                "title": event.get("title", ""),
                "description": event.get("description"),
                "location": event.get("location"),
                "agenda_url": event.get("agenda_url"),
                "minutes_url": event.get("minutes_url"),
                "video_url": event.get("video_url"),
            }
            meetings.append(meeting)

        logger.info("Extracted %d meetings from Legistar", len(meetings))
        return meetings

    except Exception as exc:
        logger.error("Failed to scrape Legistar meetings: %s", exc)
        return []


def infer_legistar_subdomain(city_name: str, state_code: str) -> str | None:
    """
    Infer Legistar subdomain from city/state.

    Most US cities follow pattern: https://{city_slug}.legistar.com

    Example:
        ("Chicago", "IL") -> "https://chicago.legistar.com"
        ("San Francisco", "CA") -> "https://sanfrancisco.legistar.com"
    """
    if not city_name:
        return None

    # Convert to slug (lowercase, remove spaces/punctuation)
    slug = city_name.lower().replace(" ", "").replace("-", "")

    # Handle common replacements
    slug = slug.replace("saint", "st").replace("san ", "").replace("city of ", "")

    return f"https://{slug}.legistar.com"
