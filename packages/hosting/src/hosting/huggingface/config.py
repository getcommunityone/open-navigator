"""Environment-resolved configuration for HuggingFace hosting.

Centralises the ``HF_TOKEN`` / ``HF_ORGANIZATION`` / ``HF_USERNAME`` /
``HF_DATASET_PREFIX`` resolution that the legacy ``scripts/huggingface/*``
uploaders each re-implemented.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

try:  # python-dotenv is a declared dependency, but stay import-safe.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - dotenv always present in the package
    pass


class HFConfigError(RuntimeError):
    """Raised when required HuggingFace configuration is missing."""


@dataclass
class HFConfig:
    """Resolved HuggingFace settings (read from the environment by default)."""

    token: str | None = field(default_factory=lambda: os.getenv("HF_TOKEN"))
    organization: str = field(
        default_factory=lambda: os.getenv("HF_ORGANIZATION", "CommunityOne")
    )
    username: str = field(
        default_factory=lambda: os.getenv("HF_USERNAME", "CommunityOne")
    )
    dataset_prefix: str = field(
        default_factory=lambda: os.getenv("HF_DATASET_PREFIX", "one")
    )

    def require_token(self) -> str:
        """Return the token or raise a helpful error if it is unset."""
        if not self.token:
            raise HFConfigError(
                "HuggingFace token required. Set HF_TOKEN in your environment or "
                ".env file. Get one at https://huggingface.co/settings/tokens"
            )
        return self.token

    def dataset_repo_id(self, name: str) -> str:
        """Build an ``org/prefix-name`` dataset repo id (e.g. ``CommunityOne/one-bills``)."""
        return f"{self.organization}/{self.dataset_prefix}-{name}"

    def dataset_prefix_repo(self, family: str) -> str:
        """Build the per-family repo prefix (e.g. ``CommunityOne/one-meetings``)."""
        return f"{self.organization}/{self.dataset_prefix}-{family}"
