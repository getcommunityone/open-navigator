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


def is_genai_billing_error(exc: BaseException) -> bool:
    """True for prepaid billing exhaustion (HTTP 402), not free-tier daily 429 (#699).

    Google returns ``402 RESOURCE_EXHAUSTED`` with “prepayment credits are depleted”
    when AI Studio prepaid balance is empty. That will not clear at midnight Pacific.
    """
    code = _genai_http_code(exc)
    if code == 402:
        return True
    msg = str(exc).upper()
    if "PREPAYMENT CREDITS" in msg or "CREDITS ARE DEPLETED" in msg:
        return True
    if "402" in msg and (
        "RESOURCE_EXHAUSTED" in msg or "BILLING" in msg or "PREPAY" in msg
    ):
        return True
    return False


def is_genai_retryable(exc: BaseException) -> bool:
    """429/503/502 quota/overload and transient network disconnects — retry with backoff."""
    # Prepaid depletion is permanent until top-up — do not spin on it (#699).
    if is_genai_billing_error(exc):
        return False
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
    for token in ("429", "402", "502", "503", "504"):
        if token in msg:
            return int(token)
    return None


def classify_genai_error(exc: BaseException) -> str:
    """Short category for logs (billing vs quota vs overload vs gateway vs network)."""
    if is_genai_transient_network_error(exc):
        return "transient network disconnect"
    if is_genai_billing_error(exc):
        return "billing exhaustion (402 prepaid credits depleted)"
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
    """True for a quota / 429 / resource-exhausted failure (the daily-wall family).

    Prepaid ``402`` billing exhaustion is excluded — it will not reset at midnight (#699).
    """
    if is_genai_billing_error(exc):
        return False
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
    fn: Callable[[], T],
    *,
    label: str = "Gemini",
    key_pool_size: int = 1,
    stats: Optional[dict[str, Any]] = None,
) -> T:
    """Run ``fn`` with quota/network retries. When ``stats`` is given, its
    ``"attempts"`` entry counts every try (including the one that succeeded or
    finally failed), for the usage log."""
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
        if stats is not None:
            stats["attempts"] = int(stats.get("attempts", 0)) + 1
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
    # Token counts, latency and attempts for this call (llm.usage.calls.LLMCallUsage).
    usage: Any = None


def _record_usage(
    *,
    provider: str,
    model: str,
    usage: Any,
    started: float,
    attempts: int,
    error: Optional[BaseException] = None,
) -> Any:
    """Fill in latency and attempts, write the call's usage row, and return the
    usage. Never raises: a usage-log problem must not fail a model call."""
    try:
        from llm.usage.calls import LLMCallUsage, record_llm_call

        usage = usage or LLMCallUsage()
        usage.latency_seconds = time.monotonic() - started
        usage.attempt_count = attempts
        record_llm_call(
            provider=provider,
            model=model,
            usage=usage,
            is_ok=error is None,
            error_type=type(error).__name__ if error is not None else None,
        )
        return usage
    except Exception as exc:  # noqa: BLE001
        logger.warning("usage record skipped for {}: {}", model, exc)
        return usage


def default_flash_lite_model() -> str:
    return (
        os.environ.get("GEMINI_FLASH_LITE_MODEL")
        or os.environ.get("GOVERNANCE_GENAI_MODEL")
        or "gemini-2.5-flash-lite"
    ).strip()


def default_flash_model() -> str:
    """Default analysis model: ``gemini-3.5-flash-lite`` (#333).

    Google deprecated ``gemini-2.5-flash``: from December 1, 2026 its requests are
    routed to ``gemini-3.5-flash-lite`` and billed at that model's rates, which are the
    same as 2.5 Flash's. Naming the model the requests will reach keeps the usage log
    and the request settings honest. Overridable via ``GEMINI_FLASH_MODEL``.
    """
    return (os.environ.get("GEMINI_FLASH_MODEL") or "gemini-3.5-flash-lite").strip()


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
        # Pinned: google-genai 3.x defaults to "v1", which rejects thinking_config
        # and JSON mode ("... is not enabled for api version v1. Use api version
        # v1beta instead."). Older SDKs defaulted to v1beta, so this is a no-op there.
        api_version=os.environ.get("GENAI_API_VERSION", "v1beta").strip() or "v1beta",
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
        if is_genai_billing_error(exc):
            raise SystemExit(
                "Gemini prepaid credits are depleted (402 RESOURCE_EXHAUSTED). "
                "Top up at https://ai.studio/projects (AI Studio billing / prepay) "
                "or switch GEMINI_USE_TIER to a pool that still has balance. "
                "This is not a free-tier daily wall — it will not clear at midnight Pacific."
            ) from exc
        raise


def ensure_valid_gemini_api_key(
    *, env_path: Optional[os.PathLike[str]] = None, model: Optional[str] = None
) -> str:
    """Resolve a working key from the active ``GEMINI_USE_TIER`` pool (#699).

    Probes each key in pool order. Returns the first that validates. On total
    billing exhaustion, exits with a pool-size / tier summary (no secret material).
    Retries ``.env`` once if the shell had a stale invalid key.
    """
    path = Path(env_path) if env_path is not None else Path(__file__).resolve().parents[5] / ".env"
    try:
        keys = resolve_gemini_api_keys(env_path=path)
    except RuntimeError:
        keys = []
    if not keys:
        single = resolve_gemini_api_key(env_path=path)
        keys = [single] if single else []

    billing_fails = 0
    last_billing: Optional[BaseException] = None
    for key in keys:
        try:
            check_gemini_api_key(key, model=model)
            return key
        except SystemExit as exc:
            msg = str(exc)
            if "prepaid credits are depleted" in msg or "402 RESOURCE_EXHAUSTED" in msg:
                billing_fails += 1
                last_billing = exc
                continue
            # API_KEY_INVALID — try .env override once, then re-raise.
            if not path.is_file():
                raise
            from dotenv import load_dotenv

            load_dotenv(path, override=True)
            key_from_file = _strip_api_key(
                os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
            )
            if key_from_file and key_from_file != key:
                try:
                    check_gemini_api_key(key_from_file, model=model)
                    logger.info(
                        "Using GEMINI_API_KEY from {} (shell env had invalid key)", path
                    )
                    return key_from_file
                except SystemExit as exc2:
                    msg2 = str(exc2)
                    if "prepaid credits are depleted" in msg2 or "402 RESOURCE_EXHAUSTED" in msg2:
                        billing_fails += 1
                        last_billing = exc2
                        continue
                    raise
            raise

    tier = _gemini_use_tier()
    if billing_fails and billing_fails >= len(keys):
        raise SystemExit(
            f"Gemini prepaid credits depleted on all {billing_fails} key(s) in the "
            f"GEMINI_USE_TIER={tier!r} pool (402). Top up at https://ai.studio/projects "
            "or retag / switch tiers. This is billing exhaustion, not a free-tier daily wall."
        ) from last_billing
    raise SystemExit(
        "No usable GEMINI_API_KEY / GEMINI_API_KEYS found. "
        "Set a key at https://aistudio.google.com/apikey"
    )


# --- API key rotation across workers -----------------------------------------
_KEY_LOCK = threading.Lock()
_CLIENT_CACHE: dict[str, Any] = {}
_KEY_POOL: Optional[list[str]] = None
_KEY_POOL_TIER: Optional[str] = None
_KEY_IDX: Optional[int] = None


def _normalize_key_tier(raw: Optional[str]) -> str:
    """Normalize a tier tag to ``free``, ``paid``, or ``untagged``."""
    t = (raw or "").strip().lower()
    if t in ("free", "paid"):
        return t
    return "untagged"


def _gemini_use_tier() -> str:
    """Active pool filter from ``GEMINI_USE_TIER`` (``free`` | ``paid`` | ``all``)."""
    use = (os.getenv("GEMINI_USE_TIER") or "all").strip().lower()
    if use in ("", "all", "*"):
        return "all"
    if use in ("free", "paid"):
        return use
    logger.warning("Unknown GEMINI_USE_TIER={!r}; using all", use)
    return "all"


def resolve_gemini_api_keys(
    *,
    env_path: Optional[os.PathLike[str]] = None,
    tier: Optional[str] = None,
) -> list[str]:
    """Configured Gemini keys, de-duplicated, in order.

    Sources (merged): ``GEMINI_API_KEYS`` (comma/space/newline list),
    ``GEMINI_API_KEY`` / ``GOOGLE_API_KEY``, and ``GEMINI_API_KEY_1``..``10``.

    Tier filter (#654): set ``GEMINI_KEY_TIER`` (plain key) or
    ``GEMINI_KEY_TIER_{N}`` to ``free`` / ``paid``. ``GEMINI_USE_TIER`` (or the
    ``tier`` arg) selects the pool: ``free``, ``paid``, or ``all`` (default).
    Keys in ``GEMINI_API_KEYS`` and any key without a tier tag are ``untagged``
    and only appear when the filter is ``all``. A ``free``/``paid`` filter with
    no matching keys raises ``RuntimeError`` so a free run never silently falls
    back onto paid keys.

    When ``tier``/``GEMINI_USE_TIER`` is ``all`` (#719), keys are ordered
    **free → paid → untagged** so daily free quota is burned before prepaid.
    """
    from dotenv import load_dotenv

    path = Path(env_path) if env_path is not None else Path(__file__).resolve().parents[5] / ".env"
    if path.is_file():
        load_dotenv(path)

    # (key, tier_label) — first occurrence of a key wins.
    tagged: list[tuple[str, str]] = []
    for k in (_strip_api_key(x) for x in re.split(r"[,\s]+", os.getenv("GEMINI_API_KEYS") or "")):
        if k:
            tagged.append((k, "untagged"))
    plain = _strip_api_key(os.getenv("GEMINI_API_KEY") or "")
    if plain:
        tagged.append((plain, _normalize_key_tier(os.getenv("GEMINI_KEY_TIER"))))
    google = _strip_api_key(os.getenv("GOOGLE_API_KEY") or "")
    if google:
        # Same tier knob as GEMINI_API_KEY when used as an alias.
        tagged.append((google, _normalize_key_tier(os.getenv("GEMINI_KEY_TIER"))))
    for i in range(1, 11):
        k = _strip_api_key(os.getenv(f"GEMINI_API_KEY_{i}") or "")
        if k:
            tagged.append((k, _normalize_key_tier(os.getenv(f"GEMINI_KEY_TIER_{i}"))))

    use = (tier.strip().lower() if tier is not None else _gemini_use_tier())
    if use in ("", "all", "*"):
        use = "all"
    elif use not in ("free", "paid"):
        logger.warning("Unknown tier filter {!r}; using all", use)
        use = "all"

    # Preserve first-seen order within each tier; when use=all, emit free first (#719).
    free: list[str] = []
    paid: list[str] = []
    untagged: list[str] = []
    seen: set[str] = set()
    for k, key_tier in tagged:
        # No prefix filtering. Both "AIza…" (classic, 39 chars) and "AQ.…" strings
        # are valid Gemini API keys — verified live that an AQ. key authenticates via
        # x-goog-api-key (HTTP 200). An invalid/expired key surfaces at call time as a
        # clean 401 (non-retryable), which is the right layer to handle it — not a
        # brittle prefix guess that also drops perfectly good keys.
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
            f"GEMINI_USE_TIER={use!r} but no keys are tagged "
            f"GEMINI_KEY_TIER[_N]={use!r}. Tag keys in .env or set "
            f"GEMINI_USE_TIER=all."
        )
    return out


def _key_pool(fallback: str) -> list[str]:
    global _KEY_POOL, _KEY_POOL_TIER, _KEY_IDX
    use = _gemini_use_tier()
    if _KEY_POOL is None or _KEY_POOL_TIER != use:
        pool = resolve_gemini_api_keys(tier=use)
        if fallback and fallback not in pool and use == "all":
            # Keep free-first order: do not prepend an untagged fallback ahead of free.
            pool = [*pool, fallback]
        _KEY_POOL = pool or ([fallback] if fallback and use == "all" else pool)
        _KEY_POOL_TIER = use
        # Start at the front of the ordered pool (free first when use=all).
        # PID offset only for a single-tier filter so workers still spread load.
        _KEY_IDX = None if use != "all" else 0
        if len(_KEY_POOL) > 1:
            logger.info(
                "Gemini key rotation enabled: {} keys in pool (tier={}, free-first={})",
                len(_KEY_POOL),
                use,
                use == "all",
            )
        elif _KEY_POOL:
            logger.info("Gemini key pool: 1 key (tier={})", use)
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
    """Round-robin a client from the pool.

    When the pool was built with ``GEMINI_USE_TIER=all``, ``_KEY_IDX`` starts at
    0 so free-tagged keys are tried before paid (#719). For a single-tier
    filter, the first index is PID-offset so workers spread load. Retries
    advance the key, so a 429/quota error moves off the hot key.
    """
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


#: Allowed values of ``DEEPSEEK_THINKING``. ``off`` is the default (#866).
DEEPSEEK_THINKING_LEVELS = ("off", "low", "high", "max")


def deepseek_thinking_kwargs(setting: str | None) -> dict[str, Any]:
    """Extra request arguments that set DeepSeek's thinking mode (#866).

    DeepSeek turns thinking on by default, at effort ``high``, and bills the thinking tokens with the
    output. On the light analysis and its reports that was 82% of the output-rate tokens (22.8M
    thinking against 5.0M output over two days), for extraction the Gemini path runs with thinking
    off. So the default here is ``off``; ``low``, ``high`` or ``max`` turn it on at that effort for a
    quality comparison. The OpenAI SDK has no ``thinking`` argument, so it goes in ``extra_body``.
    """
    level = (setting or "off").strip().lower() or "off"
    if level not in DEEPSEEK_THINKING_LEVELS:
        raise ValueError(f"DEEPSEEK_THINKING must be one of {DEEPSEEK_THINKING_LEVELS}, not {setting!r}")
    if level == "off":
        return {"extra_body": {"thinking": {"type": "disabled"}}}
    return {"extra_body": {"thinking": {"type": "enabled"}}, "reasoning_effort": level}


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

    from llm.usage.calls import usage_from_openai_response

    # Read once per call, before any request, so a bad value fails here and is not retried (#866).
    thinking_kwargs = deepseek_thinking_kwargs(os.getenv("DEEPSEEK_THINKING"))

    max_attempts = 4
    last_exc: Optional[Exception] = None
    started = time.monotonic()

    def _failed(exc: BaseException, attempts: int) -> None:
        _record_usage(
            provider="deepseek", model=model, usage=None, started=started,
            attempts=attempts, error=exc,
        )  # fmt: skip

    for attempt in range(max_attempts):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=msgs,
                temperature=temperature,
                max_tokens=max_output_tokens,
                **thinking_kwargs,
            )
            content = (resp.choices[0].message.content or "").strip()
            if not content:
                empty = RuntimeError(f"Empty response from {model}")
                _failed(empty, attempt + 1)
                raise empty
            usage = _record_usage(
                provider="deepseek",
                model=model,
                usage=usage_from_openai_response(resp),
                started=started,
                attempts=attempt + 1,
            )
            return TextGenAIResult(text=content, model=model, raw_response=resp, usage=usage)
        except (openai.RateLimitError, openai.APIConnectionError) as exc:
            last_exc = exc
            if attempt == max_attempts - 1:
                break
        except openai.APIStatusError as exc:
            # Retry only server-side (5xx) failures. 4xx (402 Insufficient
            # Balance, 401 auth, 400 bad request) are permanent — fail fast so a
            # bulk run doesn't burn ~14s of backoff per item on a dead account.
            if exc.status_code < 500:
                _failed(exc, attempt + 1)
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
    if last_exc is not None:
        _failed(last_exc, max_attempts)
    raise RuntimeError(f"DeepSeek call failed for {model}: {last_exc}") from last_exc


def _anthropic_api_key() -> str:
    """``ANTHROPIC_API_KEY`` from the environment, else from the repo-root ``.env``."""
    key = _strip_api_key(os.getenv("ANTHROPIC_API_KEY", ""))
    if not key:
        from dotenv import load_dotenv

        env_file = Path(__file__).resolve().parents[5] / ".env"
        if env_file.is_file():
            load_dotenv(env_file, override=False)
            key = _strip_api_key(os.getenv("ANTHROPIC_API_KEY", ""))
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return key


def _claude_retry_delay(exc: BaseException, attempt: int) -> float:
    """Seconds to wait before retry ``attempt + 1``: the server's ``retry-after`` if it sent one,
    else 2s doubling; never more than 60s."""
    headers = getattr(getattr(exc, "response", None), "headers", None)
    try:
        hinted = float(headers.get("retry-after")) if headers is not None else None
    except (TypeError, ValueError):
        hinted = None
    return min(hinted if hinted is not None and hinted >= 0 else 2.0 * (2**attempt), 60.0)


def _call_claude_text(
    *,
    model: str,
    user_text: str,
    system_instruction: str = "",
    max_output_tokens: int = 32000,
) -> TextGenAIResult:
    """Single-turn generation on a Claude model through the official Anthropic SDK (#871).

    Builds on :func:`llm.claude.text_client.call_claude_analysis` (streaming, prompt caching,
    effort, the long-prompt guard). ``temperature`` is not taken: current Claude models reject it.
    At most 3 attempts; the SDK's own retries are turned off so the waits are not multiplied.
    Rate limits (honouring ``retry-after``), 5xx and connection errors are retried; 4xx, a refusal,
    a truncated answer and a too-long prompt are not.
    """
    import anthropic

    from llm.claude.text_client import call_claude_analysis, claude_effort, claude_max_prompt_tokens

    # Read once, before any request, so a bad value or a missing key fails here and is not retried.
    effort = claude_effort()
    max_prompt_tokens = claude_max_prompt_tokens()
    client = anthropic.Anthropic(api_key=_anthropic_api_key(), max_retries=0)

    max_attempts = 3
    started = time.monotonic()
    last_exc: Optional[BaseException] = None

    def _failed(exc: BaseException, attempts: int) -> None:
        _record_usage(
            provider="anthropic", model=model, usage=getattr(exc, "usage", None),
            started=started, attempts=attempts, error=exc,
        )  # fmt: skip

    for attempt in range(max_attempts):
        try:
            result = call_claude_analysis(
                model=model,
                system=system_instruction.strip(),
                user_text=user_text,
                max_tokens=max_output_tokens,
                effort=effort,
                max_prompt_tokens=max_prompt_tokens,
                client=client,
            )
            usage = _record_usage(
                provider="anthropic", model=model, usage=result.usage,
                started=started, attempts=attempt + 1,
            )  # fmt: skip
            return TextGenAIResult(
                text=result.text, model=model, raw_response=result.raw_response, usage=usage
            )
        except (anthropic.RateLimitError, anthropic.APIConnectionError) as exc:
            last_exc = exc
        except anthropic.APIStatusError as exc:
            if exc.status_code < 500:
                _failed(exc, attempt + 1)
                raise RuntimeError(f"Claude call failed for {model}: {exc}") from exc
            last_exc = exc
        except BaseException as exc:  # too long, refusal, truncated, empty, count failure
            _failed(exc, attempt + 1)
            raise
        if attempt < max_attempts - 1:
            delay = _claude_retry_delay(last_exc, attempt)
            logger.warning(
                "Claude {} error ({}): sleeping {:.0f}s, retry {}/{}",
                model, type(last_exc).__name__, delay, attempt + 1, max_attempts,
            )  # fmt: skip
            time.sleep(delay)
    _failed(last_exc, max_attempts)  # type: ignore[arg-type]
    raise RuntimeError(f"Claude call failed for {model}: {last_exc}") from last_exc


def supports_thinking_budget(model: str) -> bool:
    """Whether ``thinking_budget`` (including ``0`` = off) may be sent to ``model``.

    Only the 2.5 Flash family: it thinks by default on ``gemini-2.5-flash`` and
    takes a budget of 0 to turn that off. Other models are left alone — Gemma
    rejects a budget, 2.5 Pro cannot go to 0, and the 3.x models take a thinking
    *level* instead — so a request to them is sent unchanged.
    """
    return (model or "").strip().lower().startswith("gemini-2.5-flash")


# Thinking levels each model accepts, from Google's thinking docs ("Controlling
# thinking", read 2026-11-14), lowest first. The 2.5 models are left out on purpose:
# they keep the token budget (supports_thinking_budget), whose 0 is lower than any
# level. Matched by the longest prefix of the model id (#336).
THINKING_LEVEL_ORDER = ("minimal", "low", "medium", "high", "xhigh")
LOWEST_THINKING_LEVEL = "lowest"
_THINKING_LEVELS: dict[str, tuple[str, ...]] = {
    "gemini-4-hydrogen": ("low", "medium", "high", "xhigh"),
    "gemini-4": ("low", "medium", "high"),
    "gemini-3.8-flash": ("low", "medium", "high"),
    "gemini-3.6-flash": ("minimal", "low", "medium", "high"),
    "gemini-3.5-flash-lite": ("minimal", "low", "medium", "high"),
    "gemini-3.1-pro": ("low", "medium", "high"),
    "gemini-3.1-flash-lite-image": ("minimal", "high"),
    "gemini-3.1-flash-lite": ("minimal", "low", "medium", "high"),
    "gemini-3-flash": ("minimal", "low", "medium", "high"),
    "gemini-3-pro": ("low", "high"),
}


def _bare_model_id(model: str) -> str:
    name = (model or "").strip().lower()
    return name[len("models/") :] if name.startswith("models/") else name


def thinking_levels(model: str) -> Optional[tuple[str, ...]]:
    """The thinking levels ``model`` accepts, lowest first, or ``None`` when it
    takes no level (2.5 models, Gemma, DeepSeek, unknown ids)."""
    name = _bare_model_id(model)
    key = max((k for k in _THINKING_LEVELS if name.startswith(k)), key=len, default=None)
    return _THINKING_LEVELS[key] if key else None


def supports_thinking_level(model: str) -> bool:
    return thinking_levels(model) is not None


def resolve_thinking_level(model: str, level: Optional[str]) -> Optional[str]:
    """The level to send to ``model``: ``None`` when it takes none or ``level`` is
    ``None`` (keep the model's default). ``"lowest"`` is the model's lowest level
    (``minimal`` on 3.5 Flash-Lite, ``low`` on 3.8 Flash). A level the model doesn't
    accept becomes the nearest one above it, else its highest."""
    levels = thinking_levels(model)
    wanted = (level or "").strip().lower()
    if not levels or not wanted:
        return None
    if wanted == LOWEST_THINKING_LEVEL:
        return levels[0]
    if wanted in levels:
        return wanted
    if wanted not in THINKING_LEVEL_ORDER:
        raise ValueError(f"unknown thinking level {level!r}; one of {THINKING_LEVEL_ORDER} or 'lowest'")
    rank = THINKING_LEVEL_ORDER.index(wanted)
    above = [lvl for lvl in levels if THINKING_LEVEL_ORDER.index(lvl) >= rank]
    return above[0] if above else levels[-1]


_SAMPLING_PARAMS_IGNORED_FROM = (3, 6)


def supports_sampling_params(model: str) -> bool:
    """Whether ``temperature`` (and ``top_p``/``top_k``) may be sent to ``model`` (#333).

    Google's migration guide: from ``gemini-3.6-flash`` and ``gemini-3.5-flash-lite``
    on, "temperature, top_p, and top_k are deprecated. The API ignores these
    parameters and returns an error in future model generations." So they are left
    out for ``gemini-3.5-flash-lite``, ``gemini-3.6`` and later, and ``gemini-4*``.
    Every other model (2.x, 3.0–3.5 Flash, Gemma, DeepSeek) still gets them.
    """
    name = (model or "").strip().lower()
    if name.startswith("models/"):
        name = name[len("models/") :]
    if name.startswith("gemini-3.5-flash-lite"):
        return False
    m = re.match(r"gemini-(\d+)(?:\.(\d+))?", name)
    if not m:
        return True
    version = (int(m.group(1)), int(m.group(2) or 0))
    return version < _SAMPLING_PARAMS_IGNORED_FROM


def _rejected_generation_option(exc: BaseException, config_kwargs: dict[str, Any]) -> Optional[str]:
    """The optional config key a 400 says the model/API won't take, if any."""
    msg = str(exc).upper()
    if "400" not in msg and "INVALID_ARGUMENT" not in msg:
        return None
    if "thinking_config" in config_kwargs and "THINKING" in msg:
        return "thinking_config"
    if "response_mime_type" in config_kwargs and any(
        token in msg for token in ("JSON MODE", "RESPONSE_MIME_TYPE", "RESPONSE MIME TYPE", "MIME")
    ):
        return "response_mime_type"
    return None


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
    thinking_budget: Optional[int] = None,
    json_mode: bool = False,
    thinking_level: Optional[str] = None,
) -> TextGenAIResult:
    """Single-turn generation via AI Studio API (rotates across the key pool).

    When ``pdf_bytes`` is given, the document is attached as a native PDF part so
    Gemini reads it with vision — handling SCANNED PDFs that have no extractable
    text layer (plain text extraction returns empty for those).

    A ``deepseek-*`` model name routes to DeepSeek's OpenAI-compatible Chat
    Completions endpoint instead of Gemini (text-only; no ``pdf_bytes`` support).
    A ``claude-*`` model routes to the Anthropic SDK (:func:`_call_claude_text`, same limits;
    ``temperature`` is not sent).

    ``thinking_budget`` caps the model's thinking tokens (``0`` turns thinking
    off); they are billed as output and add latency. It is sent only to models
    :func:`supports_thinking_budget` names; ``None`` keeps the model's default.
    ``json_mode`` asks for ``application/json`` output. If the API rejects either
    setting with a 400, the call is retried once without it. ``temperature`` is left
    out for models that ignore it (:func:`supports_sampling_params`).
    ``thinking_level`` (``"lowest"``, ``"minimal"`` … ``"xhigh"``) is sent to the
    models that take a level instead of a budget (:func:`thinking_levels`); a
    caller can pass both, and each model gets the setting its family takes.
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

    if model.startswith("claude-"):
        if pdf_bytes:
            raise ValueError(
                "Claude calls here are text-only and cannot read pdf_bytes; "
                "extract text first or use a Gemini model for scanned PDFs."
            )
        return _call_claude_text(
            model=model,
            user_text=user_text,
            system_instruction=system_instruction,
            max_output_tokens=max_output_tokens,
        )

    from google.genai import types

    pool = _key_pool(api_key)
    parts = [types.Part.from_text(text=user_text)]
    if pdf_bytes:
        parts.append(types.Part.from_bytes(data=pdf_bytes, mime_type=pdf_mime))
    config_kwargs: dict[str, Any] = {"max_output_tokens": max_output_tokens}
    if supports_sampling_params(model):
        config_kwargs["temperature"] = temperature
    if system_instruction.strip():
        config_kwargs["system_instruction"] = system_instruction.strip()
    level = resolve_thinking_level(model, thinking_level)
    if thinking_budget is not None and supports_thinking_budget(model):
        config_kwargs["thinking_config"] = types.ThinkingConfig(
            thinking_budget=int(thinking_budget)
        )
    elif level is not None:
        config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_level=level.upper())
    if json_mode:
        config_kwargs["response_mime_type"] = "application/json"

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

    from llm.usage.calls import usage_from_genai_response

    started = time.monotonic()
    stats: dict[str, Any] = {"attempts": 0}
    raw: Any = None
    try:
        while True:
            try:
                text_raw, raw = call_with_genai_quota_retry(
                    _generate, label=model, key_pool_size=len(pool), stats=stats
                )
                break
            except Exception as exc:
                # A model or API version that won't take the thinking budget or JSON
                # mode answers 400. Drop that one setting and try again, rather than
                # fail a run over a cost optimisation. _generate reads config_kwargs
                # on each call, so the retry goes out without it.
                rejected = _rejected_generation_option(exc, config_kwargs)
                if rejected is None:
                    raise
                logger.warning(
                    "{}: API rejected {} — retrying without it ({})",
                    model,
                    rejected,
                    describe_genai_error(exc, max_len=160),
                )
                config_kwargs.pop(rejected)
        text = (text_raw or "").strip()
        if not text:
            raise RuntimeError(f"Empty response from {model}")
    except BaseException as exc:
        # A failed call is recorded too: its latency and attempts are the cost of
        # the retries, and an empty response still reports the tokens it used.
        _record_usage(
            provider="gemini",
            model=model,
            usage=usage_from_genai_response(raw),
            started=started,
            attempts=stats["attempts"],
            error=exc,
        )
        raise
    usage = _record_usage(
        provider="gemini",
        model=model,
        usage=usage_from_genai_response(raw),
        started=started,
        attempts=stats["attempts"],
    )
    return TextGenAIResult(text=text, model=model, raw_response=raw, usage=usage)


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
