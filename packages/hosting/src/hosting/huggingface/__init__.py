"""HuggingFace hosting: publish gold datasets and deploy the app Space.

Public API::

    from hosting.huggingface import DatasetPublisher, HFConfig
    from hosting.huggingface import datasets, spaces

    publisher = DatasetPublisher()                  # reads HF_TOKEN from env/.env
    datasets.publish_gold_dir(publisher)            # data/gold/*.parquet
    datasets.publish_nonprofits(publisher)          # per-table nonprofit datasets

CLI: ``on-hf <command>`` or ``python -m hosting.huggingface <command>``.
"""

from __future__ import annotations

from .config import HFConfig, HFConfigError
from .publisher import (
    DatasetPublisher,
    UploadResult,
    dataset_name_from_stem,
    summarize,
)
from .spaces import SpaceDeployer, check_env_vars, check_space_vars

__all__ = [
    "HFConfig",
    "HFConfigError",
    "DatasetPublisher",
    "UploadResult",
    "dataset_name_from_stem",
    "summarize",
    "SpaceDeployer",
    "check_env_vars",
    "check_space_vars",
]
