"""YouTube Data API key pool — numbered keys with rotation (#716).

Env:

* ``YOUTUBE_API_KEY`` — legacy single key (included in the pool)
* ``YOUTUBE_API_KEY_1`` … ``YOUTUBE_API_KEY_10`` — rotated pool
* ``YOUTUBE_API_KEYS`` — optional comma/space/newline list

YouTube has no Gemini-style free/paid product tier. Every Cloud Console
API key (``AIzaSy…``) on a project with YouTube Data API v3 enabled shares
the project's default daily quota (~10k units). Extra capacity is a Console
quota increase, not a key tag — so this pool does not read ``YOUTUBE_KEY_TIER*``.

On ``quotaExceeded``, call :func:`mark_youtube_key_exhausted` so the next
:func:`youtube_api_key` skips that key for the process lifetime.
"""

from __future__ import annotations

import os
import re
import threading
from pathlib import Path
from typing import Optional

from loguru import logger

_lock = threading.Lock()
_POOL: Optional[list[str]] = None
_IDX: int = 0
_EXHAUSTED: set[str] = set()


def _strip_api_key(raw: str) -> str:
    return (raw or "").strip().strip('"').strip("'")


def _repo_env_path() -> Path:
    try:
        from core_lib.paths import repo_root

        return repo_root(__file__) / ".env"
    except Exception:
        return Path(__file__).resolve().parents[5] / ".env"


def resolve_youtube_api_keys(
    *,
    env_path: Optional[os.PathLike[str]] = None,
) -> list[str]:
    """Configured YouTube Data API keys, de-duplicated, in declaration order."""
    from dotenv import load_dotenv

    path = Path(env_path) if env_path is not None else _repo_env_path()
    if path.is_file():
        load_dotenv(path, override=False)

    keys: list[str] = []
    for k in (_strip_api_key(x) for x in re.split(r"[,\s]+", os.getenv("YOUTUBE_API_KEYS") or "")):
        if k:
            keys.append(k)
    plain = _strip_api_key(os.getenv("YOUTUBE_API_KEY") or "")
    if plain:
        keys.append(plain)
    for i in range(1, 11):
        k = _strip_api_key(os.getenv(f"YOUTUBE_API_KEY_{i}") or "")
        if k:
            keys.append(k)

    out: list[str] = []
    seen: set[str] = set()
    for k in keys:
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(k)
    return out


def reset_youtube_key_pool() -> None:
    """Clear cached pool / exhaustion (tests)."""
    global _POOL, _IDX
    with _lock:
        _POOL = None
        _IDX = 0
        _EXHAUSTED.clear()


def _ensure_pool() -> list[str]:
    global _POOL, _IDX
    with _lock:
        if _POOL is None:
            _POOL = resolve_youtube_api_keys()
            _IDX = 0
            if len(_POOL) > 1:
                logger.info("YouTube API key rotation enabled: {} keys", len(_POOL))
            elif _POOL:
                logger.info("YouTube API key pool: 1 key")
            else:
                logger.warning(
                    "YouTube API key pool empty (set YOUTUBE_API_KEY or YOUTUBE_API_KEY_1)"
                )
        return list(_POOL)


def youtube_api_key() -> Optional[str]:
    """Current (non-exhausted) YouTube Data API key, or None."""
    global _IDX
    pool = _ensure_pool()
    with _lock:
        if not pool:
            return None
        n = len(pool)
        for offset in range(n):
            k = pool[(_IDX + offset) % n]
            if k not in _EXHAUSTED:
                _IDX = (_IDX + offset) % n
                return k
        return None


def mark_youtube_key_exhausted(key: str, *, reason: str = "quotaExceeded") -> Optional[str]:
    """Mark ``key`` exhausted; return the next usable key, or None if the pool is empty."""
    global _IDX
    k = _strip_api_key(key)
    if not k:
        return youtube_api_key()
    pool = _ensure_pool()
    with _lock:
        _EXHAUSTED.add(k)
        logger.warning(
            "YouTube API key exhausted ({}); {} / {} keys left in pool",
            reason,
            max(0, len(pool) - len(_EXHAUSTED & set(pool))),
            len(pool),
        )
        n = len(pool)
        if not n:
            return None
        for offset in range(1, n + 1):
            cand = pool[(_IDX + offset) % n]
            if cand not in _EXHAUSTED:
                _IDX = (_IDX + offset) % n
                logger.info("Rotated to next YouTube API key (index {})", _IDX)
                return cand
        return None


def is_youtube_quota_error(exc: BaseException) -> bool:
    """True when ``exc`` (or its message/body) looks like YouTube Data API quotaExceeded."""
    import urllib.error

    parts = [str(exc)]
    if isinstance(exc, urllib.error.HTTPError):
        parts.append(str(exc.code))
        try:
            parts.append(exc.read().decode("utf-8", errors="replace"))
        except Exception:
            pass
    blob = "\n".join(parts).lower()
    return "quotaexceeded" in blob or "youtube.quota" in blob or (
        "403" in blob and "quota" in blob
    )
