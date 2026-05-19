"""
Structured extraction via local Ollama (Gemma 4 or compatible).

Uses the Ollama HTTP API with JSON format; validates with Pydantic.
Optional LangChain path when ``langchain-ollama`` is installed.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional, Type, TypeVar

import httpx
from loguru import logger
from pydantic import BaseModel, ValidationError

from scripts.scraping.schemas import JurisdictionPageExtraction

T = TypeVar("T", bound=BaseModel)

DEFAULT_OLLAMA_BASE = "http://127.0.0.1:11434"
DEFAULT_MODEL = "gemma4"


def ollama_base_url() -> str:
    return (os.getenv("OLLAMA_HOST") or os.getenv("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE).rstrip("/")


def ollama_model() -> str:
    return (
        os.getenv("SCRAPED_MEETINGS_OLLAMA_MODEL")
        or os.getenv("OLLAMA_MODEL")
        or DEFAULT_MODEL
    ).strip()


def ollama_timeout_seconds() -> float:
    try:
        return float(os.getenv("SCRAPED_MEETINGS_OLLAMA_TIMEOUT_SECONDS", "300") or "300")
    except ValueError:
        return 300.0


def _ollama_connection_help(base: str) -> str:
    import platform
    import shutil

    lines = [
        f"Cannot reach Ollama at {base} (connection refused or unreachable).",
        "",
        "Linux / WSL — install and start the server:",
        "  curl -fsSL https://ollama.com/install.sh | sh",
        "  ollama serve &    # or: sudo systemctl start ollama",
        f"  ollama pull {ollama_model()}",
        "",
        "WSL with Ollama on Windows instead:",
        "  Install Ollama from https://ollama.com/download (Windows app).",
        "  In WSL, point at the Windows host (from /etc/resolv.conf nameserver):",
        "    export OLLAMA_HOST=http://$(grep -m1 nameserver /etc/resolv.conf | awk '{print $2}'):11434",
        "",
        "Then verify:",
        "  .venv/bin/python scripts/scraping/extract_page_structured.py --check-ollama",
        "  ./scripts/scraping/setup_ollama_gemma.sh",
    ]
    if not shutil.which("ollama"):
        lines.insert(2, "(``ollama`` is not on PATH in this environment.)")
    if "microsoft" in platform.uname().release.lower() or os.getenv("WSL_DISTRO_NAME"):
        lines.append("")
        lines.append("Detected WSL — if the Windows Ollama tray app is running, use OLLAMA_HOST above.")
    return "\n".join(lines)


def check_ollama_ready(*, model: Optional[str] = None) -> Dict[str, Any]:
    """Return ``{"ok": True, "models": [...]}`` or raise with a helpful message."""
    base = ollama_base_url()
    model = model or ollama_model()
    try:
        with httpx.Client(timeout=10.0) as client:
            tags = client.get(f"{base}/api/tags")
            tags.raise_for_status()
    except httpx.ConnectError as exc:
        raise RuntimeError(_ollama_connection_help(base)) from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Ollama HTTP error at {base}: {exc}") from exc

    names = [m.get("name", "") for m in tags.json().get("models", [])]
    if not any(n == model or n.startswith(f"{model}:") for n in names):
        raise RuntimeError(
            f"Ollama is up at {base} but model {model!r} is not pulled. "
            f"Run: ollama pull {model}\nInstalled: {names[:12]}"
        )
    return {"ok": True, "base": base, "model": model, "models": names}


def _schema_hint(model_cls: Type[BaseModel]) -> str:
    return json.dumps(model_cls.model_json_schema(), indent=2)


def extract_structured_ollama(
    markdown: str,
    *,
    model: Optional[str] = None,
    schema_cls: Type[T] = JurisdictionPageExtraction,
    extra_system: str = "",
) -> T:
    """
  Extract structured data from Markdown using Ollama ``/api/chat`` with ``format: json``.
    """
    if os.getenv("SCRAPED_MEETINGS_OLLAMA_USE_LANGCHAIN", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return _extract_via_langchain(markdown, model=model, schema_cls=schema_cls)

    model = model or ollama_model()
    check_ollama_ready(model=model)

    system = (
        "You are an expert data extraction agent for U.S. local government web pages. "
        "Extract only facts present in the text. Do not invent dates, emails, or meetings. "
        "For meeting_date prefer YYYY-MM-DD when the page states a single clear date; "
        "otherwise use the exact phrase from the page or leave null. "
        "Return JSON matching this JSON Schema exactly:\n"
        f"{_schema_hint(schema_cls)}"
    )
    if extra_system:
        system += "\n\n" + extra_system

    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    "Extract jurisdiction meeting and contact details from this page content:\n\n"
                    + markdown
                ),
            },
        ],
    }

    try:
        with httpx.Client(timeout=ollama_timeout_seconds()) as client:
            resp = client.post(f"{ollama_base_url()}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.ConnectError as exc:
        raise RuntimeError(_ollama_connection_help(ollama_base_url())) from exc

    raw = (data.get("message") or {}).get("content") or ""
    if not raw.strip():
        raise RuntimeError("Ollama returned empty content")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Ollama JSON parse failed: {exc}\nRaw:\n{raw[:2000]}") from exc

    try:
        return schema_cls.model_validate(parsed)
    except ValidationError as exc:
        logger.warning(f"Schema validation failed, attempting repair: {exc}")
        repaired = _coerce_common_keys(parsed, schema_cls)
        return schema_cls.model_validate(repaired)


def _coerce_common_keys(data: Dict[str, Any], schema_cls: Type[BaseModel]) -> Dict[str, Any]:
    """Best-effort normalization when the model omits list wrappers."""
    out = dict(data)
    if schema_cls is JurisdictionPageExtraction:
        if "meetings" not in out and out.get("agenda_items"):
            items = out.pop("agenda_items")
            out["meetings"] = [
                {"title": str(x), "meeting_date": out.get("meeting_date")}
                for x in (items if isinstance(items, list) else [items])
            ]
        out.setdefault("meetings", [])
        out.setdefault("contacts", [])
    return out


def _extract_via_langchain(
    markdown: str,
    *,
    model: Optional[str],
    schema_cls: Type[T],
) -> T:
    try:
        from langchain_ollama import ChatOllama
    except ImportError:
        from langchain_community.chat_models import ChatOllama  # type: ignore[no-redef]

    llm = ChatOllama(model=model or ollama_model(), base_url=ollama_base_url(), format="json")
    structured = llm.with_structured_output(schema_cls)
    prompt = (
        "Extract jurisdiction meeting and contact details from this page. "
        "Use only information in the text.\n\n"
        f"{markdown}"
    )
    return structured.invoke(prompt)  # type: ignore[return-value]
