"""YouTube Data API key pool — Gemini-style numbered keys + free/paid (#716).

Env (same three Google accounts as Gemini when possible):

* ``YOUTUBE_API_KEY`` — legacy single key (included; tier from ``YOUTUBE_KEY_TIER``)
* ``YOUTUBE_API_KEY_1`` … ``YOUTUBE_API_KEY_10`` — rotated pool
* ``YOUTUBE_KEY_TIER`` / ``YOUTUBE_KEY_TIER_{N}`` — ``free`` | ``paid``
* ``YOUTUBE_USE_TIER`` — ``free`` | ``paid`` | ``all`` (default ``all``)
* ``YOUTUBE_API_KEYS`` — optional comma/space/newline list (untagged)

When ``YOUTUBE_USE_TIER=all``, keys are ordered **free → paid → untagged** so
default 10k/day projects are tried before billed/quota-increased ones.

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
_POOL_TIER: Optional[str] = None
_IDX: int = 0
_EXHAUSTED: set[str] = set()


def _strip_api_key(raw: str) -> str:
    return (raw or "").strip().strip('"').strip("'")


def _normalize_key_tier(raw: Optional[str]) -> str:
    t = (raw or "").strip().lower()
    if t in ("free", "paid"):
        return t
    return "untagged"


def _youtube_use_tier() -> str:
    use = (os.getenv("YOUTUBE_USE_TIER") or "all").strip().lower()
    if use in ("", "all", "*"):
        return "all"
    if use in ("free", "paid"):
        return use
    logger.warning("Unknown YOUTUBE_USE_TIER={!r}; using all", use)
    return "all"


def _repo_env_path() -> Path:
    try:
        from core_lib.paths import repo_root

        return repo_root(__file__) / ".env"
    except Exception:
        return Path(__file__).resolve().parents[5] / ".env"


def resolve_youtube_api_keys(
    *,
    env_path: Optional[os.PathLike[str]] = None,
    tier: Optional[str] = None,
) -> list[str]:
    """Configured YouTube Data API keys, de-duplicated.

    When ``tier``/``YOUTUBE_USE_TIER`` is ``all``, order is free → paid → untagged.
    """
    from dotenv import load_dotenv

    path = Path(env_path) if env_path is not None else _repo_env_path()
    if path.is_file():
        load_dotenv(path, override=False)

    tagged: list[tuple[str, str]] = []
    for k in (_strip_api_key(x) for x in re.split(r"[,\s]+", os.getenv("YOUTUBE_API_KEYS") or "")):
        if k:
            tagged.append((k, "untagged"))
    plain = _strip_api_key(os.getenv("YOUTUBE_API_KEY") or "")
    if plain:
        tagged.append((plain, _normalize_key_tier(os.getenv("YOUTUBE_KEY_TIER"))))
    for i in range(1, 11):
        k = _strip_api_key(os.getenv(f"YOUTUBE_API_KEY_{i}") or "")
        if k:
            tagged.append((k, _normalize_key_tier(os.getenv(f"YOUTUBE_KEY_TIER_{i}"))))

    use = (tier.strip().lower() if tier is not None else _youtube_use_tier())
    if use in ("", "all", "*"):
        use = "all"
    elif use not in ("free", "paid"):
        logger.warning("Unknown tier filter {!r}; using all", use)
        use = "all"

    free: list[str] = []
    paid: list[str] = []
    untagged: list[str] = []
    seen: set[str] = set()
    for k, key_tier in tagged:
        if not k or k in seen:
            continue
        if use != "all" and key_tier != use:
            continue
        seen.add(k)
        if key_tier == "free":
            free.append(k)
        elif key_tier == "paid":
            paid.append(k)
        else:
            untagged.append(k)

    if use == "all":
        out = [*free, *paid, *untagged]
    elif use == "free":
        out = free
    else:
        out = paid

    if use != "all" and not out:
        raise RuntimeError(
            f"YOUTUBE_USE_TIER={use!r} but no keys are tagged "
            f"YOUTUBE_KEY_TIER[_N]={use!r}. Tag keys in .env or set "
            f"YOUTUBE_USE_TIER=all."
        )
    return out


def reset_youtube_key_pool() -> None:
    """Clear cached pool / exhaustion (tests)."""
    global _POOL, _POOL_TIER, _IDX
    with _lock:
        _POOL = None
        _POOL_TIER = None
        _IDX = 0
        _EXHAUSTED.clear()


def _ensure_pool() -> list[str]:
    global _POOL, _POOL_TIER, _IDX
    use = _youtube_use_tier()
    with _lock:
        if _POOL is None or _POOL_TIER != use:
            _POOL = resolve_youtube_api_keys(tier=use)
            _POOL_TIER = use
            _IDX = 0
            if len(_POOL) > 1:
                logger.info(
                    "YouTube API key rotation enabled: {} keys (tier={}, free-first={})",
                    len(_POOL),
                    use,
                    use == "all",
                )
            elif _POOL:
                logger.info("YouTube API key pool: 1 key (tier={})", use)
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
