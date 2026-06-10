"""
Cluster labeler — wraps the Gemini text client with a per-run call ceiling.

The labeler is the only billed component. It is gated behind ``use_llm``; when
off, callers supply a deterministic heuristic label built from real in-data text.
A hard ``max_calls`` ceiling aborts loudly so a misconfigured run can never fan
out into per-row billing (memory: a full-US analyze run burned ~$22).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from loguru import logger

from llm.policy_questions.label_prompts import parse_json


class CallCeilingExceeded(RuntimeError):
    pass


class Labeler:
    def __init__(self, use_llm: bool, max_calls: int = 600, model: Optional[str] = None):
        self.use_llm = use_llm
        self.max_calls = max_calls
        self.calls = 0
        self._key = None
        self._pool = 1
        self._model = model
        if use_llm:
            from llm.gemini.genai_text_client import (
                default_flash_model,
                resolve_gemini_api_key,
                resolve_gemini_api_keys,
            )

            self._key = resolve_gemini_api_key()
            self._pool = max(1, len(resolve_gemini_api_keys()))
            self._model = model or default_flash_model()
            logger.info("Labeler: LLM on (model={}, key_pool={}, ceiling={})",
                        self._model, self._pool, max_calls)
        else:
            logger.info("Labeler: heuristic (no-LLM) mode")

    def label(self, system: str, user: str, tag: str) -> Optional[Dict[str, Any]]:
        """Return parsed JSON from one Gemini call, or None on failure/heuristic."""
        if not self.use_llm:
            return None
        if self.calls >= self.max_calls:
            raise CallCeilingExceeded(
                f"Reached --max-llm-calls={self.max_calls}; aborting before overspend."
            )
        from llm.gemini.genai_text_client import call_gemini_text, call_with_genai_quota_retry

        def _call() -> str:
            res = call_gemini_text(
                api_key=self._key, model=self._model, user_text=user,
                system_instruction=system, temperature=0.1, max_output_tokens=400,
            )
            return res.text

        self.calls += 1
        try:
            text = call_with_genai_quota_retry(_call, label=tag, key_pool_size=self._pool)
            return parse_json(text)
        except Exception as exc:  # noqa: BLE001 — fall back to heuristic on any failure
            logger.warning("LLM label failed ({}); falling back to heuristic: {}", tag, exc)
            return None

    @property
    def model_tag(self) -> str:
        return self._model if self.use_llm else "heuristic"
