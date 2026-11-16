"""
Contact routes for submitting feedback and issues via GitHub.
"""
import hashlib
import os
import re
import time
from typing import Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, status
from loguru import logger
from pydantic import BaseModel, EmailStr, Field

router = APIRouter(prefix="/contact", tags=["contact"])

CATEGORY_LABELS: Dict[str, str] = {
    "bug": "bug",
    "feature": "enhancement",
    "question": "question",
    "feedback": "feedback",
}

_CONTROL_CHARS_RE = re.compile(r"[\r\n\t\x00-\x1f\x7f]+")

# Bounded in-memory rate-limiting and duplicate suppression state
_RATE_WINDOW_SECONDS: float = 300.0
_MAX_SUBMISSIONS_PER_SENDER: int = 5
_MAX_GLOBAL_SUBMISSIONS: int = 30
_DEDUP_WINDOW_SECONDS: float = 60.0
_MAX_TRACKED_SENDERS: int = 512

_sender_timestamps: Dict[str, List[float]] = {}
_global_timestamps: List[float] = []
_recent_fingerprints: Dict[str, float] = {}


def clear_contact_rate_limits() -> None:
    """Clear in-memory contact form rate-limit and deduplication state."""
    _sender_timestamps.clear()
    _global_timestamps.clear()
    _recent_fingerprints.clear()


def _sanitize_single_line(value: str) -> str:
    return _CONTROL_CHARS_RE.sub(" ", value or "").strip()


def _check_and_record_rate_limit(sender_key: str, fingerprint: str) -> None:
    now = time.monotonic()

    # Prune expired fingerprints
    expired_fp = [fp for fp, ts in _recent_fingerprints.items() if now - ts >= _DEDUP_WINDOW_SECONDS]
    for fp in expired_fp:
        _recent_fingerprints.pop(fp, None)

    if fingerprint in _recent_fingerprints:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Duplicate submission detected. Please wait before submitting the same message again.",
        )

    # Prune global window
    _global_timestamps[:] = [ts for ts in _global_timestamps if now - ts < _RATE_WINDOW_SECONDS]
    if len(_global_timestamps) >= _MAX_GLOBAL_SUBMISSIONS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many contact requests. Please try again later.",
        )

    # Prune sender window and bound tracked sender map
    if len(_sender_timestamps) >= _MAX_TRACKED_SENDERS and sender_key not in _sender_timestamps:
        stale_senders = [
            k for k, timestamps in _sender_timestamps.items()
            if not timestamps or now - timestamps[-1] >= _RATE_WINDOW_SECONDS
        ]
        for k in stale_senders:
            _sender_timestamps.pop(k, None)
        if len(_sender_timestamps) >= _MAX_TRACKED_SENDERS:
            oldest_sender = min(
                _sender_timestamps,
                key=lambda k: _sender_timestamps[k][-1] if _sender_timestamps[k] else 0.0,
            )
            _sender_timestamps.pop(oldest_sender, None)

    sender_history = [
        ts for ts in _sender_timestamps.get(sender_key, []) if now - ts < _RATE_WINDOW_SECONDS
    ]
    if len(sender_history) >= _MAX_SUBMISSIONS_PER_SENDER:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded for contact submissions. Please wait a few minutes and try again.",
        )

    sender_history.append(now)
    _sender_timestamps[sender_key] = sender_history
    _global_timestamps.append(now)
    _recent_fingerprints[fingerprint] = now


class ContactRequest(BaseModel):
    """Contact form submission"""
    name: str = Field(..., min_length=1, max_length=100, description="Name of the person contacting")
    email: EmailStr = Field(..., description="Email address for follow-up")
    subject: str = Field(..., min_length=1, max_length=200, description="Subject of the message")
    message: str = Field(..., min_length=10, max_length=5000, description="Detailed message")
    category: Optional[str] = Field(default="feedback", description="Type of contact: feedback, bug, feature, question")


class ContactResponse(BaseModel):
    """Response after submitting contact form"""
    success: bool
    message: str
    issue_url: Optional[str] = None


@router.post("/submit", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def submit_contact(request: ContactRequest):
    """
    Submit a contact form message as a GitHub issue.

    Creates an issue in the GitHub repository with the contact information.
    Requires GITHUB_TOKEN and GITHUB_REPO environment variables.
    """
    clean_name = _sanitize_single_line(request.name)
    clean_subject = _sanitize_single_line(request.subject)
    clean_message = (request.message or "").replace("\x00", "").strip()
    if not clean_name or not clean_subject or len(clean_message) < 10:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Name, subject, and message (at least 10 non-whitespace characters) are required.",
        )

    github_token = (os.getenv("GITHUB_TOKEN") or "").strip()
    github_repo = (os.getenv("GITHUB_REPO") or "getcommunityone/open-navigator").strip()

    if not github_token:
        logger.warning("GitHub token not configured - contact form submission failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Contact form is not configured. Please email us directly or submit an issue on GitHub.",
        )

    sender_key = str(request.email).strip().lower()
    fingerprint = hashlib.sha256(
        f"{sender_key}|{clean_subject.lower()}|{clean_message}".encode("utf-8")
    ).hexdigest()
    _check_and_record_rate_limit(sender_key, fingerprint)

    norm_category = _sanitize_single_line(request.category or "feedback").lower()
    safe_category = norm_category if norm_category in CATEGORY_LABELS else "feedback"
    label = CATEGORY_LABELS[safe_category]

    issue_title = f"[Contact Form] {clean_subject}"
    issue_body = f"""**From:** {clean_name} ({request.email})
**Category:** {safe_category}

---

{clean_message}

---
*This issue was automatically created from the contact form.*
"""

    github_api_url = f"https://api.github.com/repos/{github_repo}/issues"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {
        "title": issue_title,
        "body": issue_body,
        "labels": [label, "contact-form"],
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                github_api_url,
                json=payload,
                headers=headers,
                timeout=10.0,
            )

            if response.status_code == 201:
                issue_data = response.json()
                issue_url = issue_data.get("html_url")
                logger.info(f"Contact form submitted successfully: {issue_url}")
                return ContactResponse(
                    success=True,
                    message="Thank you for contacting us! We've received your message and will get back to you soon.",
                    issue_url=issue_url,
                )
            if response.status_code in (403, 429):
                logger.error(f"GitHub API rate limit / auth error: {response.status_code}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Contact submission service is temporarily rate-limited. Please try again later.",
                )
            logger.error(f"GitHub API error: {response.status_code} - {response.text}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to submit contact form. Please try again later.",
            )

    except HTTPException:
        raise
    except httpx.TimeoutException as exc:
        logger.error("GitHub API timeout")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Request timed out. Please try again.",
        ) from exc
    except httpx.RequestError as exc:
        logger.error(f"GitHub API request error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit contact form. Please try again later.",
        ) from exc
