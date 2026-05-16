"""
Local Gemma 4 inference via Hugging Face Transformers.

**Hybrid default (hackathon notebook):** ``GOVERNANCE_LLM_BACKEND=google`` uses
AI Studio / ``google-genai`` for Gemma 4 models listed there (e.g. 26B A4B MoE,
EmbeddingGemma, ShieldGemma). Only **E2B** edge weights are loaded from Hugging Face
(``google/gemma-4-E2B-it``) because that checkpoint is not on the AI Studio API.

Set ``GOVERNANCE_LLM_BACKEND=huggingface`` to force every call through local weights.
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
    "GOVERNANCE_HF_MODEL_ID", "google/gemma-4-E2B-it"
).strip()

# Repos served from Hugging Face only (not on AI Studio ``models.list()``).
_HF_ONLY_REPO_IDS = frozenset(
    {
        "google/gemma-4-e2b-it",
        "google/gemma-4-e2b",
    }
)

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
    """True when every LLM call should use local Hugging Face weights."""
    return llm_backend() in ("huggingface", "hf", "local")


def model_requires_huggingface(model: str) -> bool:
    """
    True when this model id must run on Hugging Face (not on AI Studio).

    Default hybrid: only ``google/gemma-4-E2B`` / ``gemma-4-e2b-it`` and aliases.
    Override with env ``GOVERNANCE_HF_ONLY_MODELS`` (comma-separated ids).
    """
    if use_huggingface():
        return True
    if os.environ.get("GOVERNANCE_FORCE_GOOGLE", "0").strip() in ("1", "true", "yes"):
        return False
    extra = os.environ.get("GOVERNANCE_HF_ONLY_MODELS", "").strip()
    if extra:
        extras = {resolve_hf_model_id(x).lower() for x in extra.split(",") if x.strip()}
    else:
        extras = set()
    repo = resolve_hf_model_id(model or "").lower()
    return repo in _HF_ONLY_REPO_IDS or repo in extras


def use_huggingface_for_model(model: Optional[str] = None) -> bool:
    """Route a single call to HF when the global backend or this model requires it."""
    if use_huggingface():
        return True
    if model:
        return model_requires_huggingface(model)
    return False


def resolve_hf_token(cli_value: Optional[str] = None) -> str:
    """Hugging Face Hub token from CLI, ``HF_TOKEN`` env, or Colab Secret ``HF_TOKEN``."""
    if cli_value:
        return cli_value.strip()
    val = (os.environ.get("HF_TOKEN") or "").strip()
    if val:
        return val
    try:
        from google.colab import userdata  # type: ignore

        return (userdata.get("HF_TOKEN") or "").strip()
    except ImportError:
        pass
    return ""


def ensure_hf_token(cli_value: Optional[str] = None) -> str:
    """Return a Hub token and set ``HF_TOKEN`` in the environment."""
    token = resolve_hf_token(cli_value)
    if not token:
        raise RuntimeError(
            "Set HF_TOKEN (Colab Secret or environment). "
            "Create a token at https://huggingface.co/settings/tokens and accept "
            "the Gemma model license on the model page."
        )
    os.environ["HF_TOKEN"] = token
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


def _load_torch_dtype():
    import torch

    if torch.cuda.is_available():
        return torch.bfloat16
    return torch.float32


def _model_device(model: Any):
    """First real device for sharded or single-GPU models (never ``meta``)."""
    import torch

    if hasattr(model, "device"):
        dev = model.device
        if getattr(dev, "type", None) != "meta":
            return dev
    for p in model.parameters():
        if getattr(p.device, "type", None) != "meta":
            return p.device
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _move_batch_to_device(inputs: Any, device: Any) -> Any:
    import torch

    if hasattr(inputs, "to"):
        try:
            return inputs.to(device)
        except Exception:
            pass
    if isinstance(inputs, dict):
        return {
            k: v.to(device) if isinstance(v, torch.Tensor) else v
            for k, v in inputs.items()
        }
    return inputs


def _assert_transformers_supports_gemma4() -> None:
    """Gemma 4 Hub checkpoints use ``model_type=gemma4`` (transformers >= 5.5.0)."""
    try:
        import transformers
    except ImportError as exc:
        raise RuntimeError(
            'Hugging Face backend needs transformers>=5.5.0. '
            'Notebook §2: %pip install -q "transformers>=5.5.0" accelerate'
        ) from exc

    ver = getattr(transformers, "__version__", "0.0.0")
    try:
        from packaging.version import Version

        too_old = Version(ver) < Version("5.5.0")
    except Exception:
        too_old = ver < "5.5.0"
    if too_old:
        raise RuntimeError(
            f"transformers {ver} is too old for Gemma 4 (needs >= 5.5.0 for model_type "
            f"'gemma4'). Re-run notebook §2: "
            '%pip install -q "transformers>=5.5.0" accelerate then Runtime → Restart session.'
        )
    try:
        from transformers.models.auto.configuration_auto import CONFIG_MAPPING

        if "gemma4" not in CONFIG_MAPPING:
            raise RuntimeError(
                f"transformers {ver} is installed but does not register 'gemma4'. "
                'Upgrade: %pip install -q "transformers>=5.5.0" then restart the runtime.'
            )
    except RuntimeError:
        raise
    except Exception:
        pass


def load_gemma_hf(
    model_id: Optional[str] = None,
    *,
    needs_audio: bool = False,
    device_map: Optional[str] = "auto",
    dtype: Optional[Any] = None,
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
        logger.debug("HF cache hit %s (needs_audio=%s)", repo_id, use_mm)
        return _CACHE[cache_key]

    logger.info("Loading HF weights for %s (needs_audio=%s)…", repo_id, use_mm)
    _assert_transformers_supports_gemma4()
    try:
        from transformers import AutoProcessor
    except ImportError as exc:
        raise RuntimeError(
            "transformers is required for Hugging Face backend. "
            'Install with: pip install -q "transformers>=5.5.0" accelerate'
        ) from exc

    import torch

    token = resolve_hf_token() or None

    def _wrap_gemma4_load_error(exc: BaseException) -> None:
        msg = str(exc)
        if "gemma4" in msg or "model type" in msg.lower():
            raise RuntimeError(
                "Gemma 4 (google/gemma-4-E2B) needs transformers>=5.5.0. "
                "Re-run notebook §2, then Runtime → Restart session, then §3–§4. "
                f"Original error: {msg}"
            ) from exc
        raise exc

    try:
        processor = AutoProcessor.from_pretrained(
            repo_id, token=token, padding_side="left"
        )
    except (ValueError, KeyError) as exc:
        _wrap_gemma4_load_error(exc)

    torch_dtype = dtype if dtype is not None else _load_torch_dtype()
    load_kw: Dict[str, Any] = dict(
        token=token,
        torch_dtype=torch_dtype,
        attn_implementation="sdpa",
    )
    if device_map is not None and (device_map != "auto" or torch.cuda.is_available()):
        load_kw["device_map"] = device_map

    try:
        if use_mm:
            from transformers import AutoModelForMultimodalLM

            model = AutoModelForMultimodalLM.from_pretrained(repo_id, **load_kw)
            multimodal = True
            logger.info("Loaded %s via AutoModelForMultimodalLM (audio+image+text)", repo_id)
        else:
            from transformers import AutoModelForImageTextToText

            model = AutoModelForImageTextToText.from_pretrained(repo_id, **load_kw)
            multimodal = False
            logger.info("Loaded %s via AutoModelForImageTextToText", repo_id)
    except (ValueError, KeyError) as exc:
        _wrap_gemma4_load_error(exc)

    if "device_map" not in load_kw:
        model = model.to(torch_dtype).eval()

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
    # Gemma 4: vision budget belongs in processor_kwargs (not bare **kwargs).
    inputs = None
    for attempt in (
        lambda: bundle.processor.apply_chat_template(
            messages,
            processor_kwargs={"max_soft_tokens": max_soft},
            **template_kwargs,
        ),
        lambda: bundle.processor.apply_chat_template(
            messages, max_soft_tokens=max_soft, **template_kwargs
        ),
        lambda: bundle.processor.apply_chat_template(messages, **template_kwargs),
    ):
        try:
            inputs = attempt()
            break
        except TypeError:
            continue
    if inputs is None:
        inputs = bundle.processor.apply_chat_template(messages, **template_kwargs)

    device = _model_device(bundle.model)
    inputs = _move_batch_to_device(inputs, device)

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


def hf_weights_cached(repo_id: Optional[str] = None) -> Tuple[bool, bool]:
    """Return ``(image_text_loaded, audio_loaded)`` for the resolved repo."""
    repo = resolve_hf_model_id(model_id or DEFAULT_HF_MODEL_ID)
    return (repo, False) in _CACHE, (repo, True) in _CACHE


def ensure_hf_ready_for_triage(
    model_id: Optional[str] = None,
    *,
    kinds: Iterable[str] = ("pdf", "audio"),
    skip_if_cached: bool = True,
) -> str:
    """
    Load only the weight variants needed for Gatekeeper ``kinds`` (pdf → image+text only).

    Skips disk/network reload when §3 already warmed the in-process cache.
    """
    repo = resolve_hf_model_id(model_id or DEFAULT_HF_MODEL_ID)
    kinds_set = {str(k).strip().lower() for k in kinds if str(k).strip()}
    need_audio = "audio" in kinds_set
    loaded: List[str] = []

    if not skip_if_cached or (repo, False) not in _CACHE:
        load_gemma_hf(repo, needs_audio=False)
        loaded.append("image+text")
    if need_audio and _repo_supports_audio(repo):
        if not skip_if_cached or (repo, True) not in _CACHE:
            load_gemma_hf(repo, needs_audio=True)
            loaded.append("audio")

    if loaded:
        logger.info("HF weights ready for %s — loaded: %s", repo, ", ".join(loaded))
    else:
        logger.info("HF weights already in memory for %s (cache hit, no reload)", repo)
    return repo


def preload_gemma_hf(
    model_id: Optional[str] = None,
    *,
    load_audio_variant: bool = True,
) -> str:
    """
    Eager-load models for notebook §3. Prefer :func:`ensure_hf_ready_for_triage` in Gatekeeper.

    Set ``load_audio_variant=False`` when triaging PDFs only to save ~minutes of load + VRAM.
    """
    kinds = ("pdf", "audio") if load_audio_variant else ("pdf",)
    return ensure_hf_ready_for_triage(
        model_id, kinds=kinds, skip_if_cached=True
    )
