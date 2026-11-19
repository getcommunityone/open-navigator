"""A small client for TypeSafe's System One endpoint (Jev).

One call sends a ``state`` and named questions to ``POST /v1/systemone`` and gets
one typed answer per question::

    with JevClient() as client:  # reads TYPESAFE_API_KEY or JEV_API_KEY
        response = client.system_one(
            state=transcript_text,
            questions={"has_vote": noul("The body votes on a motion")},
        )
    response.answers["has_vote"].noul   # probability, 0 to 1

The official SDK (``typesafe-sdk``) does the same; this client uses httpx, which the
workspace already depends on, and writes one usage row per call through
``llm.usage.calls`` like the Gemini client does. 429 and 529 are retried with
exponential backoff, as the API docs ask.

API: https://docs.typesafe.ai/api/system-one.md
Limits and errors: https://docs.typesafe.ai/api/errors.md
"""

from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass, field
from typing import Any, Mapping

import httpx
from loguru import logger

from llm.usage.calls import LLMCallUsage, record_llm_call

DEFAULT_BASE_URL = "https://api.typesafe.ai"
DEFAULT_MODEL = "jev-latest"
ENDPOINT = "/v1/systemone"
LONG_CONTEXT_HEADER = "TypeSafe-Danger-Zone-Long-Context"
RETRY_STATUSES = frozenset({429, 529})
PROVIDER = "typesafe"


def _api_key_from_env() -> str:
    """``TYPESAFE_API_KEY`` first; ``JEV_API_KEY`` is the same key under a shorter name."""
    return (
        os.environ.get("TYPESAFE_API_KEY") or os.environ.get("JEV_API_KEY") or ""
    ).strip()


class JevError(RuntimeError):
    """A request Jev refused or that failed after every retry."""

    def __init__(
        self, message: str, *, status_code: int | None = None, body: Any = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def choice(instructions: str, criteria: Mapping[str, str]) -> dict[str, Any]:
    """A Choice question: pick one label. ``criteria`` maps each label to what it means."""
    if not criteria:
        raise ValueError("a Choice question needs at least one option")
    if len(criteria) > 255:
        raise ValueError("a Choice question takes at most 255 options")
    return {"type": "choice", "instructions": instructions, "criteria": dict(criteria)}


def score(instructions: str, levels: list[str]) -> dict[str, Any]:
    """A Score question: rate on an ordered rubric of 2 to 10 levels, lowest first."""
    if not 2 <= len(levels) <= 10:
        raise ValueError("a Score question takes 2 to 10 levels")
    return {"type": "score", "instructions": instructions, "criteria": list(levels)}


def noul(instructions: str) -> dict[str, Any]:
    """A Noul question: the probability that a statement about the state is true."""
    return {"type": "noul", "instructions": instructions}


@dataclass(frozen=True)
class JevAnswer:
    """One question's answer. Fields a question type doesn't return stay ``None``."""

    type: str
    choice: str | None = None
    score: float | None = None
    noul: float | None = None
    confidence: float | None = None
    probabilities: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_json(cls, raw: Mapping[str, Any]) -> "JevAnswer":
        def _num(key: str) -> float | None:
            value = raw.get(key)
            return float(value) if isinstance(value, (int, float)) else None

        probs = raw.get("probabilities") or {}
        return cls(
            type=str(raw.get("type") or ""),
            choice=raw.get("choice") if isinstance(raw.get("choice"), str) else None,
            score=_num("score"),
            noul=_num("noul"),
            confidence=_num("confidence"),
            probabilities={
                str(k): float(v)
                for k, v in probs.items()
                if isinstance(v, (int, float))
            },
        )


@dataclass(frozen=True)
class JevResponse:
    """The answers by question name, the versioned model that gave them, and token use."""

    model: str
    answers: dict[str, JevAnswer]
    input_tokens: int | None
    output_tokens: int | None
    raw: dict[str, Any]

    @classmethod
    def from_json(cls, raw: Mapping[str, Any]) -> "JevResponse":
        usage = raw.get("usage") or {}
        return cls(
            model=str(raw.get("model") or ""),
            answers={
                str(k): JevAnswer.from_json(v)
                for k, v in (raw.get("answers") or {}).items()
            },
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            raw=dict(raw),
        )


class JevClient:
    """Calls Jev. Reuse one client for many requests; close it (or use ``with``) when done."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 120.0,
        max_attempts: int = 5,
        backoff_seconds: float = 2.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Any = time.sleep,
    ) -> None:
        key = (api_key or _api_key_from_env() or "").strip()
        if not key:
            raise JevError(
                "Set TYPESAFE_API_KEY or JEV_API_KEY "
                "(get a key at https://console.typesafe.ai/keys)"
            )
        self.model = (
            model or os.environ.get("TYPESAFE_MODEL") or DEFAULT_MODEL
        ).strip()
        self.max_attempts = max(1, max_attempts)
        self.backoff_seconds = backoff_seconds
        self._sleep = sleep
        self._http = httpx.Client(
            base_url=(
                base_url or os.environ.get("TYPESAFE_BASE_URL") or DEFAULT_BASE_URL
            ).rstrip("/"),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
            transport=transport,
        )

    def __enter__(self) -> "JevClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def system_one(
        self,
        *,
        state: str | Mapping[str, Any] | list[Any],
        questions: Mapping[str, Mapping[str, Any]],
        long_context: bool = False,
        model: str | None = None,
    ) -> JevResponse:
        """Ask every question about ``state`` in one request and return the answers."""
        if not questions:
            raise ValueError("ask at least one question")
        body = {
            "model": model or self.model,
            "state": state,
            "questions": dict(questions),
        }
        headers = {LONG_CONTEXT_HEADER: "true"} if long_context else None

        started = time.monotonic()
        attempts = 0
        last_error: JevError | None = None
        while attempts < self.max_attempts:
            attempts += 1
            try:
                resp = self._http.post(ENDPOINT, json=body, headers=headers)
            except httpx.TransportError as exc:
                last_error = JevError(f"connection error: {exc}")
            else:
                if resp.status_code == 200:
                    result = JevResponse.from_json(resp.json())
                    self._record(
                        result.model or body["model"],
                        started,
                        attempts,
                        True,
                        None,
                        result,
                    )
                    return result
                last_error = JevError(
                    f"Jev returned {resp.status_code}: {_error_text(resp)}",
                    status_code=resp.status_code,
                    body=_safe_json(resp),
                )
                if resp.status_code not in RETRY_STATUSES:
                    break
            if attempts < self.max_attempts:
                delay = (
                    self.backoff_seconds
                    * (2 ** (attempts - 1))
                    * (1 + random.random() * 0.25)
                )
                logger.warning(
                    "{}; retrying in {:.1f}s ({}/{})",
                    last_error,
                    delay,
                    attempts,
                    self.max_attempts,
                )
                self._sleep(delay)

        assert last_error is not None
        error_type = (
            f"http_{last_error.status_code}" if last_error.status_code else "connection"
        )
        self._record(body["model"], started, attempts, False, error_type, None)
        raise last_error

    @staticmethod
    def _record(
        model: str,
        started: float,
        attempts: int,
        is_ok: bool,
        error_type: str | None,
        result: JevResponse | None,
    ) -> None:
        usage = LLMCallUsage(
            input_token_count=result.input_tokens if result else None,
            output_token_count=result.output_tokens if result else None,
            latency_seconds=time.monotonic() - started,
            attempt_count=attempts,
        )
        try:
            record_llm_call(
                provider=PROVIDER,
                model=model,
                usage=usage,
                is_ok=is_ok,
                error_type=error_type,
            )
        except Exception as exc:  # noqa: BLE001 - a usage-log failure must not lose the answer
            logger.warning("Could not write the Jev usage row: {}", exc)


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return resp.text[:500]


def _error_text(resp: httpx.Response) -> str:
    body = _safe_json(resp)
    if isinstance(body, dict):
        for key in ("detail", "message", "error"):
            if body.get(key):
                return str(body[key])[:300]
    return str(body)[:300]
