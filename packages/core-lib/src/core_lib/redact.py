"""Keep API keys and tokens out of log lines (#878).

Client libraries put credentials in the request URL (the YouTube Data API sends its key as ``?key=…``), and their
error messages quote that URL. Logging the error as it is writes the key into the log file. ``redact_secrets``
blanks credentials in a piece of text; ``install_log_redaction`` applies it to every loguru message in the process.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping

from loguru import logger

MASK = "***"

# Query-string and form parameters that carry a credential.
_PARAM = re.compile(
    r"(?i)((?:^|[?&\s\"'(])(?:key|api_key|apikey|api-key|access_token|refresh_token|token|client_secret|password)=)"
    r"[^&\s\"'<>)]+"
)
# "Authorization: Bearer abc", "x-api-key: abc", "Bearer abc".
_HEADER = re.compile(r"(?i)\b((?:authorization|x-api-key|xi-api-key|api-key)\s*[:=]\s*(?:bearer\s+|token\s+)?)[^\s\"',;]+")
_BEARER = re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/=-]{12,}")
# Key shapes that are recognisable on their own, wherever they appear.
_SHAPES = (
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}"),  # Google API keys
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),  # OpenAI / Anthropic / DeepSeek style
    re.compile(r"\bhf_[A-Za-z0-9]{20,}"),  # Hugging Face tokens
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),  # GitHub tokens
)
# Environment variables whose values are credentials, by name.
_SECRET_ENV_NAME = re.compile(r"(?i)(?:_KEY|_KEY_\d+|_TOKEN|_SECRET|PASSWORD|_PASS)$")
_MIN_ENV_SECRET_LEN = 12


def env_secret_values(env: Mapping[str, str] | None = None) -> list[str]:
    """Values of environment variables that are named like credentials, longest first.

    Short values are left out: a short string can occur in ordinary text, and blanking it would garble logs.
    """
    env = os.environ if env is None else env
    values = {
        v.strip()
        for k, v in env.items()
        if _SECRET_ENV_NAME.search(k) and v and len(v.strip()) >= _MIN_ENV_SECRET_LEN
    }
    return sorted(values, key=len, reverse=True)


def redact_secrets(text: str, *, known_values: list[str] | None = None) -> str:
    """``text`` with credentials replaced by ``***``.

    Covers credential query parameters (``key=``, ``api_key=``, ``access_token=`` and similar), authorization
    headers, bearer tokens, a few recognisable key shapes, and any value in ``known_values`` (by default the
    values of credential-named environment variables). The parameter name is kept so the line still reads.
    """
    if not text:
        return text
    out = _PARAM.sub(lambda m: m.group(1) + MASK, text)
    out = _HEADER.sub(lambda m: m.group(1) + MASK, out)
    out = _BEARER.sub(lambda m: m.group(1) + MASK, out)
    for shape in _SHAPES:
        out = shape.sub(MASK, out)
    for value in env_secret_values() if known_values is None else known_values:
        if value and value in out:
            out = out.replace(value, MASK)
    return out


def _patch(record: dict) -> None:
    record["message"] = redact_secrets(record["message"])


def install_log_redaction() -> None:
    """Redact every loguru message in this process from now on, whatever sinks are added or removed later.

    Call it once at the start of an entry point. It covers the message text; a traceback rendered by loguru for
    ``logger.exception`` is formatted separately, so log an error's text with ``logger.error`` where its message
    can carry a URL.
    """
    logger.configure(patcher=_patch)
