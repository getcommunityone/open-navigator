"""
Text-only Google AI Studio calls (``google-genai``) with quota retry.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

import httpx
from loguru import logger

T = TypeVar("T")

# Per-request HTTP timeout for every google-genai analysis call, in SECONDS.
#
# THE 37-MINUTE HANG: a transcript-analysis shard called gemini-2.5-flash-lite,
# the API issued a gateway-timeout warning, then ``generate_content`` went SILENT
# for 37+ minutes while the process stayed alive (~5% CPU). The HTTP request hung
# inside a half-open connection (TCP connected, server stopped sending bytes), so
# the call never returned *or raised* — which means the quota/network retry loop
# and the server-overload model-rotation NEVER fire. The shard is simply wedged.
#
# A bounded per-request timeout converts that silent hang into an httpx
# ReadTimeout/TimeoutException, which ``is_genai_transient_network_error`` already
# classifies as a transient network error: it is retried within the transient
# budget (rotating keys), and on persistent failure raises GenAITransientGiveUp,
# which batch callers skip-and-continue on instead of hanging the whole shard.
#
# Default 300s (5 min): legit large-transcript generations have been observed
# taking up to ~2 min, so 300s comfortably allows real work while still killing a
# true half-open hang. Override seconds via GOVERNANCE_GENAI_REQUEST_TIMEOUT_SECONDS;
# a raw-millisecond override (GOVERNANCE_GENAI_HTTP_TIMEOUT_MS) still wins if set,
# for operators who tuned the old knob.
_DEFAULT_GENAI_REQUEST_TIMEOUT_SECONDS = 300


class GenAITransientGiveUp(RuntimeError):
    """Raised when retries are exhausted on a *transient infra* failure (network
    disconnect / server timeout) rather than a real data/logic error.

    Batch callers should treat this as "skip this item and continue" even when a
    ``--stop-on-error`` flag is set: Google flaking is not a reason to abort a
    whole run. Genuine errors raise plain exceptions and still honour stop-on-error.
    """


class GenAIDailyQuotaGiveUp(RuntimeError):
    """Raised when the retry budget is exhausted on a *quota / 429 / resource-exhausted*
    failure — i.e. every key in the pool is rate/daily-limited for the current model.

    Subclasses ``RuntimeError`` so every existing ``except Exception`` / ``except
    RuntimeError`` caller is unaffected (they keep catching it as today). Callers that
    want to react to a pool-wide quota wall — e.g. a model-cycling backlog driver — can
    catch this specific type to rotate to a different model or wait for the daily reset.
    A *generic* server give-up (502/503/504 overload, not quota) is
    :class:`GenAIServerOverloadGiveUp`.
    """


class GenAIServerOverloadGiveUp(RuntimeError):
    """Raised when the retry budget is exhausted on a *server-overload* failure —
    a sustained 502/503/504 / ``DEADLINE_EXCEEDED`` on the endpoint that is NOT a
    quota/429 wall. The endpoint (or the specific model) is congested right now.

    Subclasses ``RuntimeError`` so every existing ``except Exception`` / ``except
    RuntimeError`` caller is unaffected. A model-cycling driver catches this specific
    type to rotate *temporarily* off the congested model (a short cooldown), distinct
    from :class:`GenAIDailyQuotaGiveUp`, which is a hard daily wall warranting a wait
    until the Pacific quota reset. Previously this case was an un-typed ``RuntimeError``,
    so the driver never moved off a congested model and sat sleeping 8–55s per retry.
    """


class GenAIModelUnavailableGiveUp(RuntimeError):
    """Raised when the API rejects the *model itself* as gone — a 404 ``NOT_FOUND``
    whose message says the model is no longer available / not found (a retired or
    mistyped model name, e.g. ``gemini-2.0-flash-lite`` after its sunset).

    Subclasses ``RuntimeError`` so every existing ``except Exception`` / ``except
    RuntimeError`` caller is unaffected. Distinct from both :class:`GenAIDailyQuotaGiveUp`
    (a daily wall that clears at the Pacific reset) and :class:`GenAIServerOverloadGiveUp`
    (a transient congestion blip that clears on a short cooldown): a retired model never
    comes back, so a model-cycling driver catches this specific type to drop the model
    from the rotation *permanently* for the run (like a daily wall, but it stays dropped
    even across a Pacific reset — a re-rotation onto it simply re-detects the 404 and
    re-drops it via this same path). Previously a 404 was classified non-retryable and the
    raw ``ClientError`` escaped ``call_with_genai_quota_retry`` and crashed the shard.
    """


_RETRY_IN_RE = re.compile(r"retry in\s+([\d.]+)\s*s", re.IGNORECASE)
_RETRY_DELAY_RE = re.compile(
    r"""retryDelay['"]?\s*[:=]\s*['"]?(\d+(?:\.\d+)?)s?""",
    re.IGNORECASE,
)

_TRANSIENT_NETWORK_MARKERS = (
    "SERVER DISCONNECTED",
    "CONNECTION RESET",
    "CONNECTION REFUSED",
    "CONNECTION ERROR",
    "READ TIMEOUT",
    "READ TIMED OUT",
    "WRITE TIMEOUT",
    "TIMEOUT",
    "BROKEN PIPE",
    "REMOTE PROTOCOL",
    "ECONNRESET",
    "ETIMEDOUT",
    "NETWORK UNREACHABLE",
)


def is_genai_transient_network_error(exc: BaseException) -> bool:
    """HTTP client disconnects/timeouts — retry with shorter backoff."""
    exc_name = type(exc).__name__.upper()
    if any(
        token in exc_name
        for token in (
            "TIMEOUT",
            "PROTOCOL",
            "CONNECT",
            "NETWORK",
            "DISCONNECT",
        )
    ):
        return True
    msg = str(exc).upper()
    return any(marker in msg for marker in _TRANSIENT_NETWORK_MARKERS)


def is_genai_retryable(exc: BaseException) -> bool:
    """429/503/502 quota/overload and transient network disconnects — retry with backoff."""
    if is_genai_transient_network_error(exc):
        return True
    msg = str(exc).upper()
    if any(
        token in msg
        for token in (
            "429",
            "RESOURCE_EXHAUSTED",
            "503",
            "UNAVAILABLE",
            "502",
            "BAD_GATEWAY",
            "OVERLOADED",
            "HIGH DEMAND",
            # 504 gateway / deadline-exceeded: the server timed out on a slow
            # generation — transient, retry (often succeeds on a fresh attempt).
            "504",
            "DEADLINE_EXCEEDED",
            "GATEWAY TIMEOUT",
            "GATEWAY_TIMEOUT",
        )
    ):
        return True
    for attr in ("code", "status_code", "status"):
        val = getattr(exc, attr, None)
        if val is None:
            continue
        s = str(val).upper()
        if val in (429, 502, 503, 504) or s in (
            "429",
            "502",
            "503",
            "504",
            "RESOURCE_EXHAUSTED",
            "UNAVAILABLE",
            "DEADLINE_EXCEEDED",
        ):
            return True
    return False


def is_genai_quota_exhausted(exc: BaseException) -> bool:
    return is_genai_retryable(exc)


def _genai_http_code(exc: BaseException) -> Optional[int]:
    for attr in ("code", "status_code", "status"):
        val = getattr(exc, attr, None)
        if val is None:
            continue
        if isinstance(val, int):
            return val
        s = str(val).strip()
        if s.isdigit():
            return int(s)
    msg = str(exc)
    for token in ("429", "502", "503", "504"):
        if token in msg:
            return int(token)
    return None


def classify_genai_error(exc: BaseException) -> str:
    """Short category for logs (quota vs overload vs gateway vs network)."""
    if is_genai_transient_network_error(exc):
        return "transient network disconnect"
    code = _genai_http_code(exc)
    msg = str(exc).upper()
    if code == 429 or "RESOURCE_EXHAUSTED" in msg or "QUOTA" in msg:
        return "rate limit / quota (429)"
    if code == 503 or "UNAVAILABLE" in msg or "OVERLOADED" in msg or "HIGH DEMAND" in msg:
        return "service overloaded (503)"
    if code == 502 or "BAD_GATEWAY" in msg:
        return "upstream bad gateway (502)"
    if code == 504 or "DEADLINE_EXCEEDED" in msg or "GATEWAY TIMEOUT" in msg:
        return "gateway timeout / deadline (504)"
    if code:
        return f"HTTP {code}"
    return "transient API error"


def is_genai_quota_error(exc: BaseException) -> bool:
    """True for a quota / 429 / resource-exhausted failure (the daily-wall family)."""
    code = _genai_http_code(exc)
    msg = str(exc).upper()
    return code == 429 or "RESOURCE_EXHAUSTED" in msg or "QUOTA" in msg


def is_genai_server_overload_error(exc: BaseException) -> bool:
    """True for a server-overload failure: 502/503/504 / ``DEADLINE_EXCEEDED`` /
    ``UNAVAILABLE`` / bad-gateway / gateway-timeout that is NOT a quota wall.

    This is the signal a model-cycling driver uses to *temporarily* rotate off a
    congested model. Quota/429 (the daily wall) is deliberately excluded — it is
    classified by :func:`is_genai_quota_error` and handled as a hard daily wall.
    """
    if is_genai_quota_error(exc):
        return False
    code = _genai_http_code(exc)
    if code in (502, 503, 504):
        return True
    msg = str(exc).upper()
    return any(
        token in msg
        for token in (
            "503",
            "UNAVAILABLE",
            "OVERLOADED",
            "HIGH DEMAND",
            "502",
            "BAD_GATEWAY",
            "BAD GATEWAY",
            "504",
            "DEADLINE_EXCEEDED",
            "GATEWAY TIMEOUT",
            "GATEWAY_TIMEOUT",
        )
    )


def is_genai_model_unavailable_error(exc: BaseException) -> bool:
    """True for a 404 ``NOT_FOUND`` that says the *model* is gone (retired / not found).

    Specific to model-not-found 404s — a retired model name like
    ``gemini-2.0-flash-lite`` ("This model models/gemini-2.0-flash-lite is no longer
    available") or an unknown model. Deliberately does NOT swallow unrelated 404s (a
    missing file/resource that happens to be a NOT_FOUND): the message must mention the
    model AND an unavailable/not-found phrase, or carry an explicit ``models/`` path with
    a no-longer-available phrase. This is the signal a model-cycling driver uses to drop
    the model from rotation permanently for the run.
    """
    code = _genai_http_code(exc)
    msg = str(exc)
    upper = msg.upper()
    is_404 = code == 404 or "404" in upper or "NOT_FOUND" in upper or "NOT FOUND" in upper
    if not is_404:
        return False
    mentions_model = "MODEL" in upper or "MODELS/" in upper
    if not mentions_model:
        return False
    return any(
        phrase in upper
        for phrase in (
            "NO LONGER AVAILABLE",
            "NOT AVAILABLE",
            "IS NOT FOUND",
            "WAS NOT FOUND",
            "IS NOT SUPPORTED",
            "NOT SUPPORTED",
            "DOES NOT EXIST",
            "UNKNOWN MODEL",
        )
    )


def describe_genai_error(exc: BaseException, *, max_len: int = 220) -> str:
    """One-line detail for operators (type, code, API message)."""
    parts = [type(exc).__name__]
    code = _genai_http_code(exc)
    if code is not None:
        parts.append(f"HTTP {code}")
    msg = re.sub(r"\s+", " ", str(exc).strip())
    if msg:
        if len(msg) > max_len:
            msg = msg[: max_len - 1] + "…"
        parts.append(msg)
    return " — ".join(parts)


def genai_quota_retry_delay_seconds(exc: BaseException, attempt: int) -> float:
    # Cap every delay: a daily RESOURCE_EXHAUSTED can carry a "retry in 80000s"
    # hint, and sleeping that long is never what we want (we'd rather rotate keys
    # or give up). Default cap 60s, override via env.
    cap = max(1.0, float(os.environ.get("GOVERNANCE_GENAI_QUOTA_RETRY_MAX_SECONDS", "60")))
    msg = str(exc)
    m = _RETRY_IN_RE.search(msg)
    if m:
        return min(max(float(m.group(1)), 1.0), cap)
    m = _RETRY_DELAY_RE.search(msg)
    if m:
        return min(max(float(m.group(1)), 1.0), cap)
    if is_genai_transient_network_error(exc):
        base = float(os.environ.get("GOVERNANCE_GENAI_NETWORK_RETRY_BASE_SECONDS", "5"))
        return min(base * (1.0 + 0.5 * attempt), cap)
    base = float(os.environ.get("GOVERNANCE_GENAI_QUOTA_RETRY_BASE_SECONDS", "30"))
    return min(base * (1.0 + 0.2 * attempt), cap)


# --- Hard wall-clock guard around each Gemini attempt -----------------------
# HttpOptions.timeout (httpx read timeout) is the first line of defense, but it has
# been observed NOT to fire on a pathological half-open connection: a shard hung 37
# minutes on a single generate_content call WITH a 120s httpx timeout set (TCP
# connected, server silent, no exception ever raised). This wall-clock guard runs
# each attempt in a worker thread and abandons it after a hard deadline regardless
# of what the socket/SDK is doing, converting the hang into a retryable transient
# timeout so the retry wrapper rotates/retries and finally raises GenAITransientGiveUp
# (the batch skips-and-continues) instead of wedging forever. The abandoned worker
# cannot be killed in Python — it stays blocked on I/O (cheap) until the httpx
# timeout lets it die; a small shared, bounded pool caps and reuses the threads.
_DEFAULT_GENAI_WALLCLOCK_BUFFER_SECONDS = 30.0
_WALLCLOCK_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=max(1, int(os.environ.get("GOVERNANCE_GENAI_WALLCLOCK_WORKERS", "4"))),
    thread_name_prefix="genai-wallclock",
)


def _genai_wallclock_timeout_seconds() -> float:
    """Hard per-attempt wall-clock cap, in seconds.

    Defaults to the httpx request timeout + a buffer, so the httpx read timeout
    normally fires first/cleanly and this only catches the pathological hang where
    it didn't. Override with ``GOVERNANCE_GENAI_WALLCLOCK_TIMEOUT_SECONDS``.
    """
    override = os.environ.get("GOVERNANCE_GENAI_WALLCLOCK_TIMEOUT_SECONDS")
    if override is not None and override.strip():
        return max(1.0, float(override))
    buffer = float(
        os.environ.get(
            "GOVERNANCE_GENAI_WALLCLOCK_BUFFER_SECONDS",
            str(_DEFAULT_GENAI_WALLCLOCK_BUFFER_SECONDS),
        )
    )
    return (_genai_http_timeout_ms() / 1000.0) + buffer


def _call_with_walltimeout(fn: Callable[[], T], label: str) -> T:
    """Run one Gemini attempt under a hard wall-clock deadline.

    On expiry raise ``httpx.ReadTimeout`` (classified transient/retryable) so the
    surrounding retry wrapper rotates keys, retries, and on persistence raises
    ``GenAITransientGiveUp`` rather than hanging. A worker that raises propagates
    its exception unchanged via ``future.result()`` (so quota/overload/model
    classification is preserved); only a true wall-clock overrun is converted.
    """
    timeout_s = _genai_wallclock_timeout_seconds()
    future = _WALLCLOCK_EXECUTOR.submit(fn)
    try:
        return future.result(timeout=timeout_s)
    except concurrent.futures.TimeoutError as exc:
        # Do NOT cancel/join — the worker is wedged on a hung socket and cannot be
        # killed; let it leak (blocked on I/O) and move on.
        logger.warning(
            "{}: hard wall-clock timeout after {:.0f}s — abandoning call (likely hung connection)",
            label,
            timeout_s,
        )
        raise httpx.ReadTimeout(
            f"{label}: hard wall-clock timeout after {timeout_s:.0f}s"
        ) from exc


def call_with_genai_quota_retry(
    fn: Callable[[], T], *, label: str = "Gemini", key_pool_size: int = 1
) -> T:
    # Transient network disconnects (RemoteProtocolError etc.) get a larger budget
    # than quota errors: they're cheap to retry and a flaky window usually clears
    # within a minute, whereas quota waits are long. Tracked with separate counters.
    quota_retries = max(1, int(os.environ.get("GOVERNANCE_GENAI_QUOTA_RETRIES", "5")))
    # Each retry advances to the next key in the pool, so a 429 on one key clears by
    # rotating. Make sure the budget covers the whole pool (plus one) — otherwise a
    # static budget of 5 gives up mid-pool when there are more keys than that.
    quota_retries = max(quota_retries, key_pool_size + 1)
    net_retries = max(1, int(os.environ.get("GOVERNANCE_GENAI_NETWORK_RETRIES", "12")))
    buffer = float(os.environ.get("GOVERNANCE_GENAI_QUOTA_RETRY_BUFFER_SECONDS", "1.0"))
    rotate_delay = max(0.0, float(os.environ.get("GOVERNANCE_GENAI_KEY_ROTATE_DELAY_SECONDS", "1.0")))
    quota_used = 0
    net_used = 0
    while True:
        try:
            return _call_with_walltimeout(fn, label)
        except Exception as exc:
            if not is_genai_retryable(exc):
                # A 404 that says the *model* is retired/unavailable is non-retryable
                # (a fresh attempt on the same dead model can't succeed), but it must NOT
                # escape as a raw ClientError — that crashes a model-cycling driver. Give
                # it a typed give-up so the driver drops the model and rotates on.
                if is_genai_model_unavailable_error(exc):
                    detail = (
                        f"{label}: model is unavailable (retired / not found). "
                        f"{describe_genai_error(exc)}"
                    )
                    logger.error("{}: model unavailable — {}", label, describe_genai_error(exc))
                    raise GenAIModelUnavailableGiveUp(detail) from exc
                logger.error("{}: non-retryable API failure — {}", label, describe_genai_error(exc))
                raise
            transient = is_genai_transient_network_error(exc)
            if transient:
                net_used += 1
                used, limit = net_used, net_retries
            else:
                quota_used += 1
                used, limit = quota_used, quota_retries
            if used >= limit:
                kind = "network disconnect" if transient else "quota/server"
                logger.error(
                    "{}: gave up after {} {} attempt(s) — {}",
                    label,
                    limit,
                    kind,
                    describe_genai_error(exc),
                )
                detail = (
                    f"{label}: failed after {limit} attempt(s) ({classify_genai_error(exc)}). "
                    f"{describe_genai_error(exc)}"
                )
                # Transient infra give-ups get a distinct type so batch callers can
                # skip-and-continue without aborting the run on a Google-side flake.
                if transient:
                    raise GenAITransientGiveUp(detail) from exc
                # Pool-wide quota / 429 / resource-exhausted give-ups get their own
                # type so a model-cycling driver can wait for the daily reset.
                if is_genai_quota_error(exc):
                    raise GenAIDailyQuotaGiveUp(detail) from exc
                # A sustained server-overload give-up (502/503/504 / DEADLINE_EXCEEDED)
                # gets its own type so the driver can *temporarily* rotate off the
                # congested model (short cooldown) instead of sitting on a dead endpoint.
                if is_genai_server_overload_error(exc):
                    raise GenAIServerOverloadGiveUp(detail) from exc
                raise RuntimeError(detail) from exc
            # Quota/429 with more keys to try: rotate to the next key fast (a fresh
            # key likely still has quota) instead of sleeping the full backoff. Only
            # back off long once we've cycled the whole pool — i.e. every key is
            # quota-limited and waiting is the only option.
            if not transient and key_pool_size > 1 and quota_used < key_pool_size:
                delay = rotate_delay
                detail = f"rotating key {quota_used + 1}/{key_pool_size}"
            else:
                delay = genai_quota_retry_delay_seconds(exc, used) + buffer
                detail = describe_genai_error(exc, max_len=160)
            logger.warning(
                "{}: {} — sleeping {:.0f}s, retry {}/{} ({})",
                label,
                classify_genai_error(exc),
                delay,
                used + 1,
                limit,
                detail,
            )
            time.sleep(delay)


@dataclass
class TextGenAIResult:
    text: str
    model: str
    raw_response: Any = None


def default_flash_lite_model() -> str:
    return (
        os.environ.get("GEMINI_FLASH_LITE_MODEL")
        or os.environ.get("GOVERNANCE_GENAI_MODEL")
        or "gemini-2.5-flash-lite"
    ).strip()


def default_flash_model() -> str:
    """Healthy default analysis model.

    ``gemini-2.5-flash`` is the reliable, currently-healthy model. Prefer this over
    ``default_flash_lite_model()`` for analysis defaults: ``gemini-2.5-flash-lite`` is
    504-congested (it caused the 37-minute hang documented at the top of this module)
    and ``gemini-2.0-flash-lite`` was retired (404). Overridable via ``GEMINI_FLASH_MODEL``.
    """
    return (os.environ.get("GEMINI_FLASH_MODEL") or "gemini-2.5-flash").strip()


def _genai_http_timeout_ms() -> int:
    """Per-request HTTP timeout for google-genai clients, in MILLISECONDS.

    The google-genai SDK's ``HttpOptions(timeout=...)`` is millisecond-based, so the
    seconds-valued ``GOVERNANCE_GENAI_REQUEST_TIMEOUT_SECONDS`` (default 300s — see
    ``_DEFAULT_GENAI_REQUEST_TIMEOUT_SECONDS`` and the 37-minute-hang note) is
    converted seconds→ms here. A raw-millisecond override
    (``GOVERNANCE_GENAI_HTTP_TIMEOUT_MS``) still wins if set, so operators who tuned
    the old knob keep their value.

    Without an explicit timeout the SDK can block forever on a stalled response
    (TCP connected, server stops sending bytes), wedging the single-threaded shard
    indefinitely with no exception — so the quota/network retry wrapper never fires.
    A fired timeout instead raises an httpx ``ReadTimeout``/``TimeoutException`` that
    ``is_genai_transient_network_error`` classifies as a retryable transient error, so
    ``call_with_genai_quota_retry`` backs off, rotates keys, and (if persistent) raises
    ``GenAITransientGiveUp`` rather than hanging.
    """
    raw_ms = os.environ.get("GOVERNANCE_GENAI_HTTP_TIMEOUT_MS")
    if raw_ms is not None and raw_ms.strip():
        return max(1000, int(raw_ms))
    seconds = float(
        os.environ.get(
            "GOVERNANCE_GENAI_REQUEST_TIMEOUT_SECONDS",
            str(_DEFAULT_GENAI_REQUEST_TIMEOUT_SECONDS),
        )
    )
    return max(1000, int(seconds * 1000))


def _genai_http_options() -> Any:
    """``HttpOptions`` for google-genai clients, with the httpx connection pool
    tuned to avoid stale keep-alive reuse.

    The Gemini endpoint closes idle keep-alive sockets during the gaps between our
    calls (transcript load, Part 1, save, Part 2 — seconds apart). httpx's pool then
    hands out a dead connection and the next request fails instantly with
    ``RemoteProtocolError — Server disconnected without sending a response`` — which
    our retry wrapper then burns minutes of backoff on (worse on WSL2). Disabling
    keep-alive (a fresh connection per request) trades a small TLS handshake for
    eliminating those disconnect-retry storms, plus a couple of transport-level
    connect retries. Opt back into bounded keep-alive with ``GENAI_HTTP_KEEPALIVE=1``.
    """
    import httpx
    from google.genai import types

    if os.environ.get("GENAI_HTTP_KEEPALIVE", "0").strip().lower() in ("1", "true", "yes", "on"):
        expiry = float(os.environ.get("GENAI_HTTP_KEEPALIVE_EXPIRY_SECONDS", "5"))
        limits = httpx.Limits(max_keepalive_connections=10, keepalive_expiry=expiry)
    else:
        limits = httpx.Limits(max_keepalive_connections=0)
    retries = max(0, int(os.environ.get("GENAI_HTTP_CONNECT_RETRIES", "2")))
    return types.HttpOptions(
        timeout=_genai_http_timeout_ms(),
        client_args={"limits": limits, "transport": httpx.HTTPTransport(retries=retries)},
        async_client_args={"limits": limits, "transport": httpx.AsyncHTTPTransport(retries=retries)},
    )


def _strip_api_key(value: str) -> str:
    return value.strip().strip('"').strip("'")


def resolve_gemini_api_key(*, env_path: Optional[os.PathLike[str]] = None) -> str:
    """Read AI Studio key from env; fall back to ``.env`` when unset or blank.

    When only numbered keys are configured (``GEMINI_API_KEYS`` /
    ``GEMINI_API_KEY_1``..``GEMINI_API_KEY_10``) and no plain ``GEMINI_API_KEY``,
    return the first key from the rotation pool so single-key callers (entry
    validation) still start; ``call_gemini_text`` then rotates the full pool.
    """
    from dotenv import load_dotenv

    key = _strip_api_key(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "")
    if key:
        return key
    path = Path(env_path) if env_path is not None else Path(__file__).resolve().parents[5] / ".env"
    if path.is_file():
        load_dotenv(path, override=True)
        key = _strip_api_key(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "")
    if key:
        return key
    pool = resolve_gemini_api_keys(env_path=env_path)
    return pool[0] if pool else ""


def is_gemini_api_key_invalid(exc: BaseException) -> bool:
    msg = str(exc).upper()
    return "API_KEY_INVALID" in msg or (
        "API KEY NOT VALID" in msg and "INVALID_ARGUMENT" in msg
    )


def check_gemini_api_key(api_key: str, *, model: Optional[str] = None) -> None:
    """Fail fast with a clear message when the key is missing or rejected."""
    if not api_key:
        raise SystemExit(
            "Set GEMINI_API_KEY in .env (https://aistudio.google.com/apikey) "
            "or use --transcript-only"
        )
    from google import genai

    probe_model = (model or default_flash_lite_model()).strip()
    try:
        client = genai.Client(
            api_key=api_key,
            http_options=_genai_http_options(),
        )
        client.models.generate_content(model=probe_model, contents="ok")
    except Exception as exc:
        if is_gemini_api_key_invalid(exc):
            raise SystemExit(
                "GEMINI_API_KEY was rejected by Google AI Studio (API_KEY_INVALID). "
                "Create a new key at https://aistudio.google.com/apikey (AI Studio, not Vertex) "
                "and set GEMINI_API_KEY in .env. If your shell exports GEMINI_API_KEY or "
                "GOOGLE_API_KEY, that value overrides .env — run: unset GEMINI_API_KEY GOOGLE_API_KEY"
            ) from exc
        # A transient server overload (502/503/504 / UNAVAILABLE / DEADLINE_EXCEEDED)
        # on the probe says the server is busy, NOT that the key is bad — a Gemini
        # demand spike must not crash the whole run at startup. The real analysis
        # calls go through call_with_genai_quota_retry, which rotates keys/models and
        # cools down on overload, so proceed and let that machinery handle it.
        if is_genai_server_overload_error(exc):
            logger.warning(
                "Gemini key-validation probe hit a transient {} — skipping preflight "
                "and proceeding; the key is presumed valid (retry/rotation handles it).",
                classify_genai_error(exc),
            )
            return
        raise


def ensure_valid_gemini_api_key(
    *, env_path: Optional[os.PathLike[str]] = None, model: Optional[str] = None
) -> str:
    """Resolve key, probe API once, and retry ``.env`` if shell env had a stale invalid key."""
    path = Path(env_path) if env_path is not None else Path(__file__).resolve().parents[5] / ".env"
    key = resolve_gemini_api_key(env_path=path)
    try:
        check_gemini_api_key(key, model=model)
        return key
    except SystemExit:
        if not path.is_file():
            raise
        from dotenv import load_dotenv

        load_dotenv(path, override=True)
        key_from_file = _strip_api_key(
            os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
        )
        if key_from_file and key_from_file != key:
            check_gemini_api_key(key_from_file, model=model)
            logger.info("Using GEMINI_API_KEY from {} (shell env had invalid key)", path)
            return key_from_file
        raise


# --- API key rotation across workers -----------------------------------------
_KEY_LOCK = threading.Lock()
_CLIENT_CACHE: dict[str, Any] = {}
_KEY_POOL: Optional[list[str]] = None
_KEY_IDX: Optional[int] = None


def resolve_gemini_api_keys(*, env_path: Optional[os.PathLike[str]] = None) -> list[str]:
    """All configured Gemini keys, de-duplicated, in order. Sources (merged):
    ``GEMINI_API_KEYS`` (comma/space/newline list), ``GEMINI_API_KEY`` /
    ``GOOGLE_API_KEY``, and ``GEMINI_API_KEY_1``..``GEMINI_API_KEY_10``."""
    from dotenv import load_dotenv

    path = Path(env_path) if env_path is not None else Path(__file__).resolve().parents[5] / ".env"
    if path.is_file():
        load_dotenv(path)
    raw: list[str] = list(re.split(r"[,\s]+", os.getenv("GEMINI_API_KEYS") or ""))
    raw += [os.getenv("GEMINI_API_KEY") or "", os.getenv("GOOGLE_API_KEY") or ""]
    raw += [os.getenv(f"GEMINI_API_KEY_{i}") or "" for i in range(1, 11)]
    out: list[str] = []
    seen: set[str] = set()
    for k in (_strip_api_key(x) for x in raw):
        # No prefix filtering. Both "AIza…" (classic, 39 chars) and "AQ.…" strings
        # are valid Gemini API keys — verified live that an AQ. key authenticates via
        # x-goog-api-key (HTTP 200). An invalid/expired key surfaces at call time as a
        # clean 401 (non-retryable), which is the right layer to handle it — not a
        # brittle prefix guess that also drops perfectly good keys.
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _key_pool(fallback: str) -> list[str]:
    global _KEY_POOL
    if _KEY_POOL is None:
        pool = resolve_gemini_api_keys()
        if fallback and fallback not in pool:
            pool = [fallback, *pool]
        _KEY_POOL = pool or ([fallback] if fallback else [])
        if len(_KEY_POOL) > 1:
            logger.info("Gemini key rotation enabled: {} keys in pool", len(_KEY_POOL))
    return _KEY_POOL


def _client_for(key: str) -> Any:
    client = _CLIENT_CACHE.get(key)
    if client is None:
        from google import genai

        client = genai.Client(
            api_key=key,
            http_options=_genai_http_options(),
        )
        _CLIENT_CACHE[key] = client
    return client


def _next_client(pool: list[str]) -> Any:
    """Round-robin a client from the pool, offsetting the start by PID so separate
    worker processes don't all hit the same key first. Retries advance the key,
    so a 429/quota error moves off the hot key."""
    global _KEY_IDX
    with _KEY_LOCK:
        if _KEY_IDX is None:
            _KEY_IDX = os.getpid() % max(1, len(pool))
        key = pool[_KEY_IDX % len(pool)]
        _KEY_IDX += 1
    return _client_for(key)


def _stream_enabled() -> bool:
    """Whether to stream text generations (default on). Streaming avoids the
    idle-connection drop on long responses; set GEMINI_TEXT_STREAM=0 to disable."""
    return os.environ.get("GEMINI_TEXT_STREAM", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _call_deepseek_text(
    *,
    model: str,
    user_text: str,
    system_instruction: str = "",
    temperature: float = 0.1,
    max_output_tokens: int = 65536,
) -> TextGenAIResult:
    """Single-turn generation via DeepSeek's OpenAI-compatible Chat Completions API.

    DeepSeek speaks the OpenAI protocol at ``https://api.deepseek.com``, so we use
    the ``openai`` SDK pointed at that base URL. Text-only: callers must extract any
    PDF text first (the ``call_gemini_text`` dispatch rejects ``pdf_bytes`` upfront).

    Retries are handled by a small self-contained loop here rather than
    ``call_with_genai_quota_retry`` — that classifier is google-genai-specific and
    does not understand ``openai`` exception types.
    """
    import openai
    from openai import OpenAI

    key = _strip_api_key(os.getenv("DEEPSEEK_API_KEY", ""))
    if not key:
        # Fall back to the repo-root .env, mirroring resolve_gemini_api_key so a
        # key dropped into .env (not exported) is still picked up.
        from dotenv import load_dotenv

        env_file = Path(__file__).resolve().parents[5] / ".env"
        if env_file.is_file():
            load_dotenv(env_file, override=False)
            key = _strip_api_key(os.getenv("DEEPSEEK_API_KEY", ""))
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY not set")

    client = OpenAI(api_key=key, base_url="https://api.deepseek.com")

    msgs: list[dict[str, str]] = []
    if system_instruction.strip():
        msgs.append({"role": "system", "content": system_instruction.strip()})
    msgs.append({"role": "user", "content": user_text})

    max_attempts = 4
    last_exc: Optional[Exception] = None
    for attempt in range(max_attempts):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=msgs,
                temperature=temperature,
                max_tokens=max_output_tokens,
            )
            content = (resp.choices[0].message.content or "").strip()
            if not content:
                raise RuntimeError(f"Empty response from {model}")
            return TextGenAIResult(text=content, model=model, raw_response=resp)
        except (openai.RateLimitError, openai.APIConnectionError) as exc:
            last_exc = exc
            if attempt == max_attempts - 1:
                break
        except openai.APIStatusError as exc:
            # Retry only server-side (5xx) failures. 4xx (402 Insufficient
            # Balance, 401 auth, 400 bad request) are permanent — fail fast so a
            # bulk run doesn't burn ~14s of backoff per item on a dead account.
            if exc.status_code < 500:
                raise RuntimeError(
                    f"DeepSeek call failed for {model}: {exc}"
                ) from exc
            last_exc = exc
            if attempt == max_attempts - 1:
                break
            delay = 2.0 * (2**attempt)
            logger.warning(
                "DeepSeek {} error ({}): sleeping {:.0f}s, retry {}/{}",
                model,
                type(exc).__name__,
                delay,
                attempt + 1,
                max_attempts,
            )
            time.sleep(delay)
    raise RuntimeError(f"DeepSeek call failed for {model}: {last_exc}") from last_exc


def call_gemini_text(
    *,
    api_key: str,
    model: str,
    user_text: str,
    system_instruction: str = "",
    temperature: float = 0.1,
    max_output_tokens: int = 65536,
    pdf_bytes: Optional[bytes] = None,
    pdf_mime: str = "application/pdf",
) -> TextGenAIResult:
    """Single-turn generation via AI Studio API (rotates across the key pool).

    When ``pdf_bytes`` is given, the document is attached as a native PDF part so
    Gemini reads it with vision — handling SCANNED PDFs that have no extractable
    text layer (plain text extraction returns empty for those).

    A ``deepseek-*`` model name routes to DeepSeek's OpenAI-compatible Chat
    Completions endpoint instead of Gemini (text-only; no ``pdf_bytes`` support).
    """
    if model.startswith("deepseek"):
        if pdf_bytes:
            raise ValueError(
                "DeepSeek is text-only and cannot read pdf_bytes; "
                "extract text first or use a Gemini model for scanned PDFs."
            )
        return _call_deepseek_text(
            model=model,
            user_text=user_text,
            system_instruction=system_instruction,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

    from google.genai import types

    pool = _key_pool(api_key)
    parts = [types.Part.from_text(text=user_text)]
    if pdf_bytes:
        parts.append(types.Part.from_bytes(data=pdf_bytes, mime_type=pdf_mime))
    config_kwargs: dict[str, Any] = dict(
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )
    if system_instruction.strip():
        config_kwargs["system_instruction"] = system_instruction.strip()

    def _generate():
        client = _next_client(pool)
        cfg = types.GenerateContentConfig(**config_kwargs)
        contents = [types.Content(role="user", parts=parts)]
        if _stream_enabled():
            # Stream the generation so the connection receives tokens immediately
            # instead of sitting idle for the whole (sometimes 60s+) response.
            # Non-streaming generate_content on long policy analyses leaves the
            # connection idle until the full answer is ready, and an intermediary
            # kills it at ~60s — surfacing as "Server disconnected without sending
            # a response" (RemoteProtocolError) and burning the retry budget. A
            # disconnect mid-stream raises out of the loop and the whole call is
            # retried fresh (no partial-text corruption). Opt out: GEMINI_TEXT_STREAM=0.
            chunks: list[str] = []
            last: Any = None
            for chunk in client.models.generate_content_stream(
                model=model, contents=contents, config=cfg
            ):
                last = chunk
                piece = getattr(chunk, "text", None)
                if piece:
                    chunks.append(piece)
            return "".join(chunks), last
        resp = client.models.generate_content(model=model, contents=contents, config=cfg)
        return (getattr(resp, "text", None) or ""), resp

    text_raw, raw = call_with_genai_quota_retry(
        _generate, label=model, key_pool_size=len(pool)
    )
    text = (text_raw or "").strip()
    if not text:
        raise RuntimeError(f"Empty response from {model}")
    return TextGenAIResult(text=text, model=model, raw_response=raw)


def extract_json_from_model_text(text: str) -> Optional[dict[str, Any]]:
    """Best-effort JSON object from fenced or bare model output."""
    raw = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL | re.IGNORECASE)
    if fence:
        raw = fence.group(1).strip()
    start = raw.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(raw)):
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(raw[start : i + 1])
                    if isinstance(obj, dict):
                        return obj
                except json.JSONDecodeError:
                    return None
    return None
