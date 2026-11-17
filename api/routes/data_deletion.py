"""
Data deletion endpoints for OAuth provider compliance (Facebook, etc.)
"""
import base64
import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.database import get_db
from api.models import User

router = APIRouter()

_SAFE_USER_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class DataDeletionRequest(BaseModel):
    """Data deletion request from OAuth provider"""
    signed_request: str  # Facebook's signed request


class DataDeletionResponse(BaseModel):
    """Response to data deletion request"""
    url: str
    confirmation_code: str


def _b64url_decode(segment: str) -> bytes:
    cleaned = (segment or "").strip()
    if not cleaned:
        raise ValueError("Empty base64url segment")
    padding = "=" * (-len(cleaned) % 4)
    return base64.urlsafe_b64decode(cleaned + padding)


def parse_signed_request(signed_request: str, app_secret: str) -> dict:
    """
    Parse and validate Facebook's signed_request parameter.

    Format: base64url(signature).base64url(payload)
    Uses constant-time HMAC comparison and verifies HMAC-SHA256 algorithm header.
    """
    try:
        if not signed_request or "." not in signed_request or not app_secret:
            raise ValueError("Malformed signed_request or empty secret")

        encoded_sig, payload = signed_request.split(".", 1)
        sig = _b64url_decode(encoded_sig)
        raw_payload = _b64url_decode(payload)
        data = json.loads(raw_payload.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Signed request payload must be a JSON object")

        algorithm = data.get("algorithm")
        if algorithm is None or str(algorithm).upper() != "HMAC-SHA256":
            raise ValueError(f"Unsupported signed_request algorithm: {algorithm}")

        expected_sig = hmac.new(
            app_secret.encode("utf-8"),
            msg=payload.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()

        if not hmac.compare_digest(sig, expected_sig):
            raise ValueError("Invalid signature")

        return data
    except Exception as e:
        logger.error(f"Error parsing signed_request: {e}")
        raise HTTPException(status_code=400, detail="Invalid signed request") from e


async def _extract_signed_request(request: Request) -> Optional[str]:
    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        try:
            body = await request.json()
            if isinstance(body, dict):
                parsed = DataDeletionRequest(**body)
                return parsed.signed_request
        except Exception:
            return None
    try:
        form = await request.form()
        val = form.get("signed_request")
        return str(val) if val is not None else None
    except Exception:
        return None


@router.post("/data-deletion/facebook", response_model=DataDeletionResponse)
async def facebook_data_deletion_callback(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Facebook Data Deletion Request Callback

    Facebook requires apps to provide a data deletion callback URL.
    This endpoint receives deletion requests and processes them.

    Docs: https://developers.facebook.com/docs/development/create-an-app/app-dashboard/data-deletion-callback
    """
    signed_request = await _extract_signed_request(request)
    if not signed_request or not signed_request.strip():
        raise HTTPException(status_code=400, detail="Missing signed_request")

    app_secret = os.getenv("FACEBOOK_APP_SECRET")
    if not app_secret:
        logger.error("FACEBOOK_APP_SECRET not configured")
        raise HTTPException(status_code=500, detail="Server configuration error")

    data = parse_signed_request(signed_request.strip(), app_secret)
    raw_user_id = data.get("user_id")
    user_id = str(raw_user_id).strip() if raw_user_id is not None else ""

    if not user_id or not _SAFE_USER_ID_RE.match(user_id):
        raise HTTPException(status_code=400, detail="Missing or invalid user_id in signed request")

    logger.info(f"Data deletion request from Facebook user: {user_id}")

    user = db.query(User).filter(
        User.oauth_provider == "facebook",
        User.oauth_id == user_id,
    ).first()

    if user:
        try:
            # Never log the email: this request exists to erase it (#448).
            logger.info(
                "Deleting user account: user_id={} (Facebook ID: {})",
                getattr(user, "user_id", None),
                user_id,
            )
            db.delete(user)
            db.commit()
            deletion_status = "deleted"
        except Exception as exc:
            db.rollback()
            # Exception text can echo row values (bound parameters), so log only its type.
            logger.error(
                "Database error deleting Facebook user {}: {}", user_id, type(exc).__name__
            )
            raise HTTPException(status_code=500, detail="Failed to process data deletion") from exc
    else:
        logger.info(f"No user found for Facebook ID: {user_id}")
        deletion_status = "not_found"

    now_utc = datetime.now(timezone.utc)
    confirmation_code = f"DEL-{user_id}-{int(now_utc.timestamp())}"

    base_url = os.getenv("FRONTEND_URL", "https://www.communityone.com").rstrip("/")
    query_str = urlencode({"code": confirmation_code, "status": deletion_status})
    status_url = f"{base_url}/data-deletion-status?{query_str}"

    logger.info(f"Data deletion request processed: {confirmation_code}")

    return DataDeletionResponse(
        url=status_url,
        confirmation_code=confirmation_code,
    )


@router.get("/data-deletion/status")
async def data_deletion_status(code: str = None, status: str = None):
    """
    Data deletion status page (informational)

    Users are redirected here after Facebook processes their deletion request.
    """
    return {
        "confirmation_code": code,
        "status": status,
        "message": "Your data deletion request has been processed." if status == "deleted" else "No account found.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
