"""
Clustering primitives — HDBSCAN over unit vectors, centroids, exemplars.

Uses the native ``sklearn.cluster.HDBSCAN`` (sklearn >= 1.3), so no compiled
``hdbscan`` dependency is needed. HDBSCAN is chosen because the number of
recurring families is unknown and it has an explicit noise bucket (label ``-1``)
for one-off decisions that should NOT be forced into a fake "misc" question.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np
from sklearn.cluster import HDBSCAN


@dataclass
class Cluster:
    label: int
    member_idx: List[int]
    centroid: np.ndarray
    # member indices sorted by descending cosine similarity to the centroid
    exemplar_idx: List[int] = field(default_factory=list)


def hdbscan_labels(vectors: np.ndarray, min_cluster_size: int, min_samples: int | None = None) -> np.ndarray:
    """Return per-row cluster labels (-1 = noise). Tiny partitions are all-noise."""
    n = vectors.shape[0]
    if n < max(min_cluster_size, 2):
        return np.full(n, -1, dtype=int)
    clusterer = HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric="euclidean",  # on unit vectors, euclidean rank == cosine rank
    )
    return clusterer.fit_predict(vectors)


def build_clusters(vectors: np.ndarray, labels: np.ndarray, top_k_exemplars: int = 15) -> List[Cluster]:
    """Group rows by non-noise label; compute unit centroid + ranked exemplars."""
    clusters: List[Cluster] = []
    for label in sorted(set(int(x) for x in labels) - {-1}):
        idx = [i for i, lab in enumerate(labels) if int(lab) == label]
        sub = vectors[idx]
        centroid = sub.mean(axis=0)
        norm = np.linalg.norm(centroid)
        if norm > 0:
            centroid = centroid / norm
        sims = sub @ centroid
        order = np.argsort(-sims)
        exemplars = [idx[i] for i in order[:top_k_exemplars]]
        clusters.append(Cluster(label=label, member_idx=idx, centroid=centroid, exemplar_idx=exemplars))
    return clusters


def cosine_to(centroid: np.ndarray, vector: np.ndarray) -> float:
    """Cosine similarity of a unit ``vector`` to a unit ``centroid``."""
    return float(np.dot(centroid, vector))


def nearest_centroid(vector: np.ndarray, centroids: np.ndarray) -> tuple[int, float]:
    """Index + score of the closest centroid (centroids: (k, dim) unit rows)."""
    if centroids.shape[0] == 0:
        return -1, -1.0
    sims = centroids @ vector
    best = int(np.argmax(sims))
    return best, float(sims[best])
