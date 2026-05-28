"""
Shared helpers for Esri FeatureServer/MapServer layer URLs and lightweight validation.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import requests

ESRI_HOST_MARKERS = ("featureserver", "mapserver")


def is_esri_layer_url(url: str | None) -> bool:
    """True when URL points at an Esri REST layer (not Hub experiences or AGOL items)."""
    if not url or not isinstance(url, str):
        return False
    lower = url.strip().lower()
    if "experience.arcgis.com" in lower or "/home/item.html" in lower:
        return False
    return any(marker in lower for marker in ESRI_HOST_MARKERS)


def normalize_layer_url(target_url: str) -> str:
    """Layer root URL without /query suffix."""
    url = target_url.strip().rstrip("/")
    if url.lower().endswith("/query"):
        return url[: -len("/query")]
    return url


def normalize_query_url(target_url: str) -> str:
    """Ensure the URL points at a layer /query endpoint."""
    url = normalize_layer_url(target_url)
    return f"{url}/query"


def layer_metadata_url(layer_or_query_url: str) -> str:
    """Derive .../FeatureServer/N from a layer or /query URL."""
    return normalize_layer_url(layer_or_query_url)


def extract_data_url(entry: dict[str, Any]) -> str | None:
    """Pull a service URL from an OpenAddresses layer entry."""
    raw = entry.get("data")
    if isinstance(raw, str):
        stripped = raw.strip()
        return stripped or None
    if isinstance(raw, dict):
        for key in ("url", "href"):
            val = raw.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return None


def validate_esri_layer(
    layer_url: str,
    *,
    timeout: int = 20,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """
    GET ?f=json on the layer and confirm it responds and supports Query.

    Returns a dict with keys: ok, queryable, http_status, error, capabilities, name, fields_count.
    """
    meta_url = layer_metadata_url(layer_url)
    client = session or requests
    result: dict[str, Any] = {
        "ok": False,
        "queryable": False,
        "http_status": None,
        "error": None,
        "capabilities": None,
        "name": None,
        "fields_count": None,
        "layer_url": meta_url,
    }
    try:
        resp = client.get(meta_url, params={"f": "json"}, timeout=timeout)
        result["http_status"] = resp.status_code
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        result["error"] = str(exc)
        return result
    except ValueError as exc:
        result["error"] = f"Invalid JSON: {exc}"
        return result

    if "error" in data:
        err = data["error"]
        result["error"] = err.get("message") if isinstance(err, dict) else str(err)
        return result

    caps = str(data.get("capabilities") or "")
    result["capabilities"] = caps or None
    result["name"] = data.get("name")
    fields = data.get("fields") or []
    result["fields_count"] = len(fields) if isinstance(fields, list) else None
    result["queryable"] = "query" in caps.lower()
    result["ok"] = result["queryable"]
    if not result["queryable"] and not result["error"]:
        result["error"] = "Layer metadata lacks Query capability"
    return result


def host_label(url: str) -> str:
    """Stable short label from URL host + service path tail."""
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    tail = "_".join(parts[-3:]) if parts else "layer"
    return f"{parsed.netloc.replace('.', '_')}_{tail}".lower()[:120]
