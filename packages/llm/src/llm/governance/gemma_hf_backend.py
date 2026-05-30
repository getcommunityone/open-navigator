"""
Local Gemma 4 inference via Hugging Face Transformers.

**Hybrid default (hackathon notebook):** ``GOVERNANCE_LLM_BACKEND=google`` uses
AI Studio for Gatekeeper (cheap triage), demos (26B A4B MoE), EmbeddingGemma, and
ShieldGemma. Local Hugging Face weights (~10GB) load only when
``GOVERNANCE_GATEKEEPER_FORCE_HF=1`` (``google/gemma-4-E2B-it``).

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

# Demo 4: native audio/video on Gemma 4 Edge (E2B / E4B) — not AI Studio 31B/26B.
DEFAULT_DEMO4_HF_MODEL_ID = os.environ.get(
    "GOVERNANCE_DEMO4_HF_MODEL", "google/gemma-4-E2B-it"
).strip()

# Demo 4a / plain transcription: E2B or E4B only (never 31B/26B MoE).
DEFAULT_TRANSCRIPTION_HF_MODEL_ID = os.environ.get(
    "GOVERNANCE_TRANSCRIPTION_HF_MODEL", "google/gemma-4-E2B-it"
).strip()

# Default Gatekeeper HF checkpoint when ``GOVERNANCE_GATEKEEPER_FORCE_HF=1``.
_HF_GATEKEEPER_REPO_DEFAULT = "google/gemma-4-E2B-it"

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


def demo4_use_huggingface() -> bool:
    """
    Demo 4 meeting audio/video uses local Gemma 4 E2B/E4B (native multimodal audio).

    Default **on** (``GOVERNANCE_DEMO4_USE_HF=1``). AI Studio only exposes audio on
    Edge models that are often absent from ``models.list()``; E2B/E4B on Hugging Face
    match the Gemma 4 docs. Set ``GOVERNANCE_DEMO4_USE_HF=0`` to try Google API instead.
    """
    if use_huggingface():
        return True
    return os.environ.get("GOVERNANCE_DEMO4_USE_HF", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def resolve_demo4_hf_model(requested: Optional[str] = None) -> str:
    """Hugging Face repo for Demo 4 (must be E2B or E4B for audio)."""
    raw = (requested or os.environ.get("GOVERNANCE_DEMO4_MODEL", "").strip() or DEFAULT_DEMO4_HF_MODEL_ID)
    repo = resolve_hf_model_id(raw)
    if not _repo_supports_audio(repo):
        logger.warning(
            "Demo 4 HF model %r has no native audio — falling back to %s",
            repo,
            DEFAULT_DEMO4_HF_MODEL_ID,
        )
        repo = resolve_hf_model_id(DEFAULT_DEMO4_HF_MODEL_ID)
    return repo


def resolve_transcription_hf_model(requested: Optional[str] = None) -> str:
    """
    Hugging Face repo for speech-to-text only (Demo 4a).

    Restricted to Gemma 4 **E2B** / **E4B** edge checkpoints — never 31B/26B MoE.
    """
    raw = (
        requested
        or os.environ.get("GOVERNANCE_TRANSCRIPTION_HF_MODEL", "").strip()
        or DEFAULT_TRANSCRIPTION_HF_MODEL_ID
    )
    repo = resolve_hf_model_id(raw)
    if not _repo_supports_audio(repo):
        logger.warning(
            "Transcription model %r is not E2B/E4B — falling back to %s",
            repo,
            DEFAULT_TRANSCRIPTION_HF_MODEL_ID,
        )
        repo = resolve_hf_model_id(DEFAULT_TRANSCRIPTION_HF_MODEL_ID)
    return repo


def configure_hf_hub_cache(cache_dir: Path) -> Path:
    """
    Point Hugging Face / transformers caches at ``cache_dir`` (e.g. Drive-backed).

    Uses ``setdefault`` so an explicit Colab/Drive env wins. Call once in notebook §2.
    """
    root = cache_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    hub = root / "hub"
    hub.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(root))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(root))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(hub))
    return root


def gatekeeper_use_huggingface() -> bool:
    """
    True when Gatekeeper should load local HF weights (slow ~10GB startup).

    Default **off**: Gatekeeper uses Google AI Studio (fast). Set
    ``GOVERNANCE_GATEKEEPER_FORCE_HF=1`` to load ``google/gemma-4-E2B-it`` from Hugging Face.
    """
    if use_huggingface():
        return True
    return os.environ.get("GOVERNANCE_GATEKEEPER_FORCE_HF", "0").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def model_requires_huggingface(model: str) -> bool:
    """
    True when demos / other calls must run on Hugging Face (not AI Studio).

    Gatekeeper is handled separately via :func:`gatekeeper_use_huggingface`.
    Optional ``GOVERNANCE_HF_ONLY_MODELS`` (comma-separated) for extra demo models on HF.
    """
    if use_huggingface():
        return True
    if os.environ.get("GOVERNANCE_FORCE_GOOGLE", "0").strip() in ("1", "true", "yes"):
        return False
    extra = os.environ.get("GOVERNANCE_HF_ONLY_MODELS", "").strip()
    if not extra:
        return False
    extras = {resolve_hf_model_id(x).lower() for x in extra.split(",") if x.strip()}
    repo = resolve_hf_model_id(model or "").lower()
    return repo in extras


def use_huggingface_for_model(
    model: Optional[str] = None,
    *,
    gatekeeper: bool = False,
    demo4: bool = False,
) -> bool:
    """Route a call to HF (local weights)."""
    if use_huggingface():
        return True
    if demo4 and demo4_use_huggingface():
        return True
    if gatekeeper:
        return gatekeeper_use_huggingface()
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
        mime_l = (mime or "").lower()
        if mime_l.startswith("audio/") or mime_l.startswith("video/"):
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


def _transformers_version_ok(ver: str) -> bool:
    try:
        from packaging.version import Version

        return Version(ver) >= Version("5.5.0")
    except Exception:
        return ver >= "5.5.0"


def _gemma4_registered() -> bool:
    try:
        from transformers.models.auto.configuration_auto import CONFIG_MAPPING

        return "gemma4" in CONFIG_MAPPING
    except Exception:
        return False


def _purge_transformers_modules() -> None:
    import sys

    for name in list(sys.modules):
        if name == "transformers" or name.startswith("transformers."):
            del sys.modules[name]


def _transformers_probe_subprocess() -> Tuple[str, bool]:
    """Fresh interpreter: (version, gemma4 in CONFIG_MAPPING)."""
    import subprocess
    import sys

    try:
        out = subprocess.check_output(
            [
                sys.executable,
                "-c",
                "import transformers as t\n"
                "from transformers.models.auto.configuration_auto import CONFIG_MAPPING\n"
                "print(t.__version__)\n"
                "print('gemma4' in CONFIG_MAPPING)",
            ],
            text=True,
        ).strip()
    except subprocess.CalledProcessError:
        return "0.0.0", False
    lines = out.splitlines()
    ver = lines[0].strip() if lines else "0.0.0"
    has = (lines[1].strip().lower() == "true") if len(lines) > 1 else False
    return ver, has


def ensure_transformers_gemma4_ready(*, auto_install: bool = True) -> str:
    """
    Colab-friendly: ``pip install -U transformers>=5.5.0`` then reload modules in-process.

    Returns the active ``transformers.__version__``. Raises :class:`SystemExit` if pip
    upgraded on disk but this kernel cannot pick up >= 5.5.0 (restart required).
    """
    import subprocess
    import sys

    disk_ver, disk_ok = _transformers_probe_subprocess()

    try:
        import transformers

        kernel_ver = transformers.__version__
    except ImportError:
        kernel_ver = "0.0.0"

    kernel_ok = _transformers_version_ok(kernel_ver) and _gemma4_registered()

    if disk_ok and kernel_ok:
        return kernel_ver

    if auto_install and not disk_ok:
        logger.info("Installing transformers>=5.5.0 for Gemma 4 (gemma4)…")
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-q",
                "-U",
                "transformers>=5.5.0",
                "accelerate",
            ]
        )
        disk_ver, disk_ok = _transformers_probe_subprocess()

    if disk_ok and not kernel_ok:
        logger.info(
            "Reloading transformers in this kernel (was %s, pip has %s)…",
            kernel_ver,
            disk_ver,
        )
        _purge_transformers_modules()
        import transformers  # noqa: F401

        kernel_ver = transformers.__version__
        kernel_ok = _transformers_version_ok(kernel_ver) and _gemma4_registered()

    if kernel_ok:
        logger.info("transformers %s ready (gemma4 registered)", kernel_ver)
        return kernel_ver

    if disk_ok and not kernel_ok:
        raise SystemExit(
            f"\n{'=' * 60}\n"
            f"pip has transformers {disk_ver} with gemma4, but this Colab kernel still "
            f"has {kernel_ver}.\n\n"
            "Fix (required):\n"
            "  1. Runtime → Restart session\n"
            "  2. Re-run §2 (install) then §3 (config)\n"
            f"{'=' * 60}\n"
        )

    raise SystemExit(
        f"\n{'=' * 60}\n"
        f"Could not install transformers>=5.5.0 (pip reports {disk_ver}).\n"
        "Try in a new cell:\n"
        "  !pip install -U 'transformers>=5.5.0' accelerate\n"
        "Then Runtime → Restart session.\n"
        f"{'=' * 60}\n"
    )


def _assert_transformers_supports_gemma4() -> None:
    """Gemma 4 Hub checkpoints use ``model_type=gemma4`` (transformers >= 5.5.0)."""
    ensure_transformers_gemma4_ready(auto_install=True)


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
        try:
            from .colab_timed_steps import log_line

            log_line(f"HF cache hit {repo_id} (needs_audio={use_mm})")
        except ImportError:
            logger.debug("HF cache hit %s (needs_audio=%s)", repo_id, use_mm)
        return _CACHE[cache_key]

    try:
        from .colab_timed_steps import log_line

        log_line(
            f"HF loading {repo_id} (needs_audio={use_mm}) — "
            "first run may download ~10GB to HF hub cache"
        )
    except ImportError:
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
        from .colab_timed_steps import log_phase

        proc_ctx: Any = log_phase(f"HF processor {repo_id}")
    except ImportError:
        from contextlib import nullcontext

        proc_ctx = nullcontext()
    with proc_ctx:
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

    weight_label = (
        f"HF weights {repo_id} (MultimodalLM audio+video)"
        if use_mm
        else f"HF weights {repo_id} (image+text)"
    )
    try:
        from .colab_timed_steps import log_phase

        weight_ctx: Any = log_phase(weight_label)
    except ImportError:
        from contextlib import nullcontext

        weight_ctx = nullcontext()
    try:
        with weight_ctx:
            if use_mm:
                from transformers import AutoModelForMultimodalLM

                model = AutoModelForMultimodalLM.from_pretrained(repo_id, **load_kw)
                multimodal = True
            else:
                from transformers import AutoModelForImageTextToText

                model = AutoModelForImageTextToText.from_pretrained(repo_id, **load_kw)
                multimodal = False
    except (ValueError, KeyError) as exc:
        _wrap_gemma4_load_error(exc)
    try:
        from .colab_timed_steps import log_line

        kind = "MultimodalLM" if multimodal else "ImageTextToText"
        log_line(f"HF ready {repo_id} via {kind}")
    except ImportError:
        logger.info("Loaded %s", repo_id)

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
        elif mime_l.startswith("audio/") or mime_l.startswith("video/"):
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
                "audio/opus": ".opus",
                "video/mp4": ".mp4",
                "video/webm": ".webm",
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
    need_audio = _needs_multimodal_lm(media_list)
    repo = resolve_demo4_hf_model(model) if need_audio else resolve_hf_model_id(model)
    bundle = load_gemma_hf(
        repo,
        needs_audio=need_audio,
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

    media_hint = ""
    if media_list:
        parts = [f"{mime}" for _, mime in media_list[:2]]
        media_hint = f" media={','.join(parts)}"

    try:
        from .colab_timed_steps import log_phase

        infer_ctx: Any = log_phase(
            f"HF generate {bundle.repo_id}",
            detail=f"max_new_tokens={max_output_tokens}{media_hint}",
        )
    except ImportError:
        from contextlib import nullcontext

        infer_ctx = nullcontext()
    with infer_ctx:
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
    repo = resolve_hf_model_id(repo_id or DEFAULT_HF_MODEL_ID)
    return (repo, False) in _CACHE, (repo, True) in _CACHE


def ensure_demo4_hf_ready(model_id: Optional[str] = None) -> str:
    """Load E2B/E4B multimodal weights (audio+video) for Demo 4; return resolved repo id."""
    ensure_hf_token()
    repo = resolve_demo4_hf_model(model_id)
    ensure_hf_ready_for_triage(repo, kinds=("audio",), skip_if_cached=True)
    return repo


def preload_demo4_hf(model_id: Optional[str] = None) -> str:
    """Notebook §3 eager load for Demo 4 (same as :func:`ensure_demo4_hf_ready`)."""
    return ensure_demo4_hf_ready(model_id)


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
