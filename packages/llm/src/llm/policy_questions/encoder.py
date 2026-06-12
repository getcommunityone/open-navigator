"""
Sentence-embedding encoder — mean-pooled transformer with a TF-IDF fallback.

The installed ``sentence-transformers`` (2.2.2) is broken against the newer
``huggingface_hub`` (the removed ``cached_download`` import), so we drive the same
MiniLM model through ``transformers`` + ``torch`` directly (mean pooling over the
token embeddings, then L2-normalize so cosine == dot product). If the model can't
be loaded (e.g. no network), we fall back to a deterministic TF-IDF + SVD encoder
(sklearn only) so the pipeline always runs — at reduced semantic quality, which is
logged loudly.
"""

from __future__ import annotations

import os
from typing import List, Optional

import numpy as np
from loguru import logger

_DEFAULT_MODEL = os.getenv("POLICY_QUESTIONS_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

_tok = None
_model = None
_loaded_name: Optional[str] = None
_backend: Optional[str] = None  # "transformer" | "tfidf"


def model_name() -> str:
    base = (_loaded_name or _DEFAULT_MODEL).split("/")[-1]
    return f"{base}+{_backend}" if _backend else base


def _try_load_transformer(name: str) -> bool:
    global _tok, _model, _loaded_name, _backend
    if _backend == "transformer" and _loaded_name == name:
        return True
    try:
        from transformers import AutoModel, AutoTokenizer

        _tok = AutoTokenizer.from_pretrained(name)
        _model = AutoModel.from_pretrained(name)
        _model.eval()
        _loaded_name, _backend = name, "transformer"
        logger.info("Encoder: transformer mean-pooling ({})", name)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Encoder: transformer load failed ({}); using TF-IDF fallback: {}", name, exc)
        _backend = "tfidf"
        return False


def _encode_transformer(texts: List[str], batch_size: int) -> np.ndarray:
    import torch

    out = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        enc = _tok(batch, padding=True, truncation=True, max_length=256, return_tensors="pt")
        with torch.no_grad():
            model_out = _model(**enc)
        tokens = model_out.last_hidden_state
        mask = enc["attention_mask"].unsqueeze(-1).float()
        summed = (tokens * mask).sum(dim=1)
        counts = mask.sum(dim=1).clamp(min=1e-9)
        mean = summed / counts
        mean = torch.nn.functional.normalize(mean, p=2, dim=1)
        out.append(mean.cpu().numpy().astype(np.float32))
    return np.vstack(out)


def _encode_tfidf(texts: List[str]) -> np.ndarray:
    from sklearn.decomposition import TruncatedSVD
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import normalize

    vec = TfidfVectorizer(max_features=4096, ngram_range=(1, 2), min_df=1, stop_words="english")
    tfidf = vec.fit_transform(texts)
    n_comp = int(min(256, tfidf.shape[0] - 1, tfidf.shape[1] - 1))
    if n_comp < 2:
        dense = tfidf.toarray().astype(np.float32)
        return normalize(dense).astype(np.float32)
    svd = TruncatedSVD(n_components=n_comp, random_state=42)
    reduced = svd.fit_transform(tfidf)
    return normalize(reduced).astype(np.float32)


def encode(texts: List[str], name: Optional[str] = None, batch_size: int = 64) -> np.ndarray:
    """Encode ``texts`` to an (n, dim) float32 array of unit vectors."""
    name = name or _DEFAULT_MODEL
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)
    if _backend != "tfidf" and _try_load_transformer(name):
        return _encode_transformer(texts, batch_size)
    return _encode_tfidf(texts)
