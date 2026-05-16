"""
Local Gemma 4 inference via Hugging Face Transformers.

Default model: ``google/gemma-4-E4B-it`` with ``AutoProcessor`` +
``AutoModelForImageTextToText`` for image+text. When the prompt includes audio
(E2B/E4B only), loads ``AutoModelForMultimodalLM`` instead.

Enable with ``GOVERNANCE_LLM_BACKEND=huggingface`` (see ``02_run_meeting_llm.ipynb``).
"""

from __future__ import annotations

import io
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

# AI Studio-style ids → Hugging Face repo ids (Gemma 4 repos use capital E2B/E4B).
HF_MODEL_ALIASES: Dict[str, str] = {
    "google/gemma-4-e4b-it": "google/gemma-4-E4B-it",
    "google/gemma-4-E2B-it": "google/gemma-4-E2B-it",
    "google/gemma-4-E4B": "google/gemma-4-E4B-it",
    "google/gemma-4-E2B": "google/gemma-4-E2B-it",
    "gemma-4-e4b-it": "google/gemma-4-E4B-it",
    "gemma-4-e2b-it": "google/gemma-4-E2B-it",
    "gemma-4-26b-a4b-it": "google/gemma-4-26B-A4B-it",
    "gemma-4-31b-it": "google/gemma-4-31B-it",
    "google/gemma-4-26B-A4B-it": "google/gemma-4-26B-A4B-it",
    "google/gemma-4-31B-it": "google/gemma-4-31B-it",
}

DEFAULT_HF_MODEL_ID = os.environ.get(
    "GOVERNANCE_HF_MODEL_ID", "google/gemma-4-E4B-it"
).strip()

# Gemma 4 vision soft-token budget (matches governance_meeting_llm TOKEN_BUDGET_*).
_SOFT_TOKENS_BY_RESOLUTION = {
    "LOW": 70,
    "MEDIUM": 280,
    "HIGH": 1120,
}

_AUDIO_CAPABLE_REPOS = ("google/gemma-4-E4B-it", "google/gemma-4-E2B-it")


def llm_backend() -> str:
    """``google`` (AI Studio / google-genai) or ``huggingface``."""
    return os.environ.get("GOVERNANCE_LLM_BACKEND", "google").strip().lower()


def use_huggingface() -> bool:
    return llm_backend() in ("huggingface", "hf", "local")


def resolve_hf_token(cli_value: Optional[str] = None) -> str:
    """Hugging Face Hub token from CLI, env, or Colab Secret ``HF_TOKEN``."""
    if cli_value:
        return cli_value.strip()
    for env in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HF_TOKEN"):
        val = os.environ.get(env)
        if val:
            return val.strip()
    try:
        from google.colab import userdata  # type: ignore

        for secret_name in ("HF_TOKEN", "HF_TOKEN"):
            val = userdata.get(secret_name)
            if val:
                return val.strip()
    except ImportError:
        pass
    return ""


def ensure_hf_token(cli_value: Optional[str] = None) -> str:
    """Return a Hub token and mirror it into ``HF_TOKEN`` / Hub env vars."""
    token = resolve_hf_token(cli_value)
    if not token:
        raise RuntimeError(
            "Set HF_TOKEN (Colab Secret or environment). "
            "Create a token at https://huggingface.co/settings/tokens and accept "
            "the Gemma model license on the model page."
        )
    os.environ["HF_TOKEN"] = token
    os.environ.setdefault("HUGGING_FACE_HUB_TOKEN", token)
    os.environ.setdefault("HF_TOKEN", token)  # libraries that still read HF_TOKEN
    return token


def resolve_hf_model_id(requested: str) -> str:
    """Map short Gemma aliases to a Hugging Face ``repo_id``."""
    raw = (requested or DEFAULT_HF_MODEL_ID).strip()
    return HF_MODEL_ALIASES.get(raw.lower(), raw)


def list_hf_model_catalog() -> List[str]:
    """Known Gemma 4 repos for this pipeline (not a live Hub query)."""
    return sorted(set(HF_MODEL_ALIASES.values()))


def print_hf_model_catalog(
    *,
    requested: Optional[Iterable[str]] = None,
    role: str = "Hugging Face",
) -> List[str]:
    catalog = list_hf_model_catalog()
    print(f"\n── {role}: configured Hugging Face Gemma 4 repos ──")
    requested_list = [resolve_hf_model_id(r) for r in (requested or []) if r and str(r).strip()]
    for repo in catalog:
        marker = "  ← requested" if repo in requested_list else ""
        print(f"  {repo}{marker}")
    if requested_list:
        for req in requested_list:
            if req not in catalog:
                print(f"  ✓ will load {req!r} (not in default catalog)")
    print(f"\nDefault: {DEFAULT_HF_MODEL_ID}\n")
    return catalog


@dataclass
class _HFBundle:
    repo_id: str
    processor: Any
    model: Any
    multimodal: bool  # True when AutoModelForMultimodalLM (audio-capable)


_CACHE: Dict[Tuple[str, bool], _HFBundle] = {}


def _repo_supports_audio(repo_id: str) -> bool:
    return any(repo_id.endswith(suffix) or repo_id == suffix for suffix in _AUDIO_CAPABLE_REPOS)


def _needs_multimodal_lm(media: Iterable[Tuple[Any, str]]) -> bool:
    for _, mime in media:
        if (mime or "").lower().startswith("audio/"):
            return True
    return False


def _soft_tokens(media_resolution: Optional[str]) -> int:
    if not media_resolution:
        return _SOFT_TOKENS_BY_RESOLUTION["HIGH"]
    return _SOFT_TOKENS_BY_RESOLUTION.get(
        media_resolution.upper(), _SOFT_TOKENS_BY_RESOLUTION["HIGH"]
    )


def load_gemma_hf(
    model_id: Optional[str] = None,
    *,
    needs_audio: bool = False,
    device_map: str = "auto",
    dtype: str = "auto",
) -> _HFBundle:
    """
    Load (or return cached) processor + model for ``model_id``.

    Uses ``AutoModelForImageTextToText`` for image+text-only runs on E4B/E2B.
    Uses ``AutoModelForMultimodalLM`` when ``needs_audio=True`` on audio-capable repos.
    """
    repo_id = resolve_hf_model_id(model_id or DEFAULT_HF_MODEL_ID)
    use_mm = needs_audio and _repo_supports_audio(repo_id)
    cache_key = (repo_id, use_mm)
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    try:
        from transformers import AutoProcessor
    except ImportError as exc:
        raise RuntimeError(
            "transformers is required for Hugging Face backend. "
            'Install with: pip install -U "transformers>=4.50" torch accelerate'
        ) from exc

    token = resolve_hf_token() or None
    processor = AutoProcessor.from_pretrained(repo_id, token=token)

    if use_mm:
        from transformers import AutoModelForMultimodalLM

        model = AutoModelForMultimodalLM.from_pretrained(
            repo_id,
            dtype=dtype,
            device_map=device_map,
            token=token,
        )
        multimodal = True
        logger.info("Loaded %s via AutoModelForMultimodalLM (audio+image+text)", repo_id)
    else:
        from transformers import AutoModelForImageTextToText

        model = AutoModelForImageTextToText.from_pretrained(
            repo_id,
            dtype=dtype,
            device_map=device_map,
            token=token,
        )
        multimodal = False
        logger.info("Loaded %s via AutoModelForImageTextToText", repo_id)

    bundle = _HFBundle(repo_id=repo_id, processor=processor, model=model, multimodal=multimodal)
    _CACHE[cache_key] = bundle
    return bundle


def _media_to_content_parts(
    media: Iterable[Tuple[Any, str]],
) -> Tuple[List[dict], List[str]]:
    """Build HF chat ``content`` parts; return (parts, temp_files_to_cleanup)."""
    from PIL import Image

    parts: List[dict] = []
    temp_paths: List[str] = []
    for item, mime in media:
        mime_l = (mime or "").lower()
        if isinstance(item, (bytes, bytearray)):
            data = bytes(item)
        else:
            data = Path(item).read_bytes()

        if mime_l.startswith("image/"):
            img = Image.open(io.BytesIO(data)).convert("RGB")
            parts.append({"type": "image", "image": img})
        elif mime_l.startswith("audio/"):
            suffix = {
                "audio/mpeg": ".mp3",
                "audio/mp3": ".mp3",
                "audio/wav": ".wav",
                "audio/x-wav": ".wav",
                "audio/mp4": ".m4a",
                "audio/m4a": ".m4a",
                "audio/webm": ".webm",
                "audio/ogg": ".ogg",
                "audio/flac": ".flac",
            }.get(mime_l, ".wav")
            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            tmp.write(data)
            tmp.close()
            temp_paths.append(tmp.name)
            parts.append({"type": "audio", "audio": tmp.name})
        else:
            logger.warning("Skipping unsupported HF media mime %r", mime)
    return parts, temp_paths


def _build_messages(
    *,
    system_instruction: str,
    user_text: str,
    media: Iterable[Tuple[Any, str]],
) -> Tuple[List[dict], List[str]]:
    messages: List[dict] = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction.strip()})
    user_content, temp_paths = _media_to_content_parts(media)
    user_content.append({"type": "text", "text": user_text})
    messages.append({"role": "user", "content": user_content})
    return messages, temp_paths


def _decode_generation(
    bundle: _HFBundle,
    outputs: Any,
    input_len: int,
    *,
    enable_thinking: bool,
) -> Tuple[str, str]:
    """Return ``(answer_text, thoughts_text)``."""
    raw = bundle.processor.decode(
        outputs[0][input_len:], skip_special_tokens=False
    )
    thoughts = ""
    answer = raw
    parse_fn = getattr(bundle.processor, "parse_response", None)
    if parse_fn is not None:
        try:
            parsed = parse_fn(raw)
            if isinstance(parsed, dict):
                answer = (
                    parsed.get("content")
                    or parsed.get("text")
                    or parsed.get("answer")
                    or answer
                )
                thoughts = (
                    parsed.get("thought")
                    or parsed.get("thinking")
                    or parsed.get("reasoning")
                    or ""
                )
                if isinstance(thoughts, list):
                    thoughts = "\n".join(str(t) for t in thoughts)
            elif isinstance(parsed, str):
                answer = parsed
        except Exception:
            logger.debug("processor.parse_response failed; using raw decode", exc_info=True)
    if enable_thinking and not thoughts and "<|channel>thought" in raw:
        # Fallback: strip thought channel heuristically.
        thoughts = raw
        answer = raw.split("<|turn>model", 1)[-1]
    return (str(answer or "").strip(), str(thoughts or "").strip())


@dataclass
class HFGenAIResult:
    text: str
    thoughts: str
    raw_response: Any


def call_gemma_hf_multimodal(
    *,
    model: str,
    system_instruction: str,
    user_text: str,
    media: Iterable[Tuple[Any, str]] = (),
    temperature: float = 0.1,
    max_output_tokens: int = 8192,
    media_resolution: Optional[str] = None,
    include_thoughts: bool = False,
    thinking_budget: Optional[int] = None,
) -> HFGenAIResult:
    """
    Hugging Face equivalent of ``governance_meeting_llm.call_google_genai_multimodal``.
    """
    import torch

    media_list = list(media)
    bundle = load_gemma_hf(
        model,
        needs_audio=_needs_multimodal_lm(media_list),
    )
    messages, temp_paths = _build_messages(
        system_instruction=system_instruction,
        user_text=user_text,
        media=media_list,
    )

    max_soft = _soft_tokens(media_resolution)
    template_kwargs: Dict[str, Any] = dict(
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
        add_generation_prompt=True,
        enable_thinking=bool(include_thoughts or thinking_budget),
    )
    # max_soft_tokens is supported on Gemma4Processor (transformers >= 4.50).
    try:
        inputs = bundle.processor.apply_chat_template(
            messages,
            max_soft_tokens=max_soft,
            **template_kwargs,
        )
    except TypeError:
        inputs = bundle.processor.apply_chat_template(messages, **template_kwargs)

    device = bundle.model.device
    inputs = inputs.to(device)
    if hasattr(inputs, "to") and bundle.multimodal:
        try:
            inputs = inputs.to(device, dtype=bundle.model.dtype)
        except TypeError:
            pass

    input_len = inputs["input_ids"].shape[-1]
    gen_kwargs: Dict[str, Any] = dict(
        max_new_tokens=max_output_tokens,
        do_sample=temperature > 0,
    )
    if temperature > 0:
        gen_kwargs["temperature"] = temperature

    with torch.inference_mode():
        outputs = bundle.model.generate(**inputs, **gen_kwargs)

    text, thoughts = _decode_generation(
        bundle,
        outputs,
        input_len,
        enable_thinking=bool(include_thoughts or thinking_budget),
    )

    for p in temp_paths:
        try:
            os.unlink(p)
        except OSError:
            pass

    return HFGenAIResult(text=text, thoughts=thoughts, raw_response=outputs)


def preload_gemma_hf(
    model_id: Optional[str] = None,
    *,
    load_audio_variant: bool = True,
) -> str:
    """
    Eager-load models for notebook startup. Returns the resolved ``repo_id``.

    When ``load_audio_variant`` is True on E4B/E2B, also warms the MultimodalLM
    weights used for gatekeeper audio triage.
    """
    repo = resolve_hf_model_id(model_id or DEFAULT_HF_MODEL_ID)
    load_gemma_hf(repo, needs_audio=False)
    if load_audio_variant and _repo_supports_audio(repo):
        load_gemma_hf(repo, needs_audio=True)
    return repo
