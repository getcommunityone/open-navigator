"""HuggingFace Spaces deployment + inspection helpers.

Replaces the legacy ``deploy-space.py`` and ``check-hf-vars.py`` scripts.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

from loguru import logger

from .config import HFConfig

DEFAULT_SPACE_ID = "CommunityOne/open-navigator"

# Paths excluded when uploading the repo to a Space (from deploy-space.py).
DEFAULT_IGNORE_PATTERNS: list[str] = [
    ".git/*", ".git", ".gitignore",
    ".venv/*", ".venv", ".venv-intel/*", ".venv-intel", "venv/*", "venv",
    "node_modules/*", "**/node_modules/*", "node_modules",
    "data/*", "data",
    "logs/*", "logs",
    ".env*",
    "__pycache__/*", "**/__pycache__/*", "*.pyc",
    ".vscode/*", ".idea/*",
    "*.log",
    ".cache/*", "**/.cache/*",
    "*.swp", "*.swo", "*~", ".DS_Store",
    "gold_old/*", "gold_backup_*/*",
    ".VSCodeCounter/*",
    "web_docs/node_modules/*", "web_app/node_modules/*",
    "*.egg-info/*",
]


class SpaceDeployer:
    """Deploy a local folder to a HuggingFace Space via the Hub API."""

    def __init__(self, config: HFConfig | None = None):
        self.config = config or HFConfig()
        self.token = self.config.require_token()
        from huggingface_hub import HfApi

        self.api = HfApi(token=self.token)

    def deploy_folder(
        self,
        space_id: str = DEFAULT_SPACE_ID,
        folder: Path | str = ".",
        *,
        ignore_patterns: list[str] | None = None,
        commit_message: str = "Deploy via Hub API",
        dry_run: bool = False,
    ) -> int:
        """Upload ``folder`` to ``space_id``. In dry-run mode just count files.

        Returns the number of files uploaded (or that would be uploaded).
        """
        patterns = ignore_patterns or DEFAULT_IGNORE_PATTERNS
        if dry_run:
            return self._count_uploadable(Path(folder), patterns)

        from huggingface_hub import upload_folder

        logger.info("Uploading {} -> Space {}", folder, space_id)
        upload_folder(
            folder_path=str(folder),
            repo_id=space_id,
            repo_type="space",
            token=self.token,
            ignore_patterns=patterns,
            commit_message=commit_message,
        )
        logger.success("Deployed to https://huggingface.co/spaces/{}", space_id)
        return -1

    @staticmethod
    def _count_uploadable(folder: Path, patterns: list[str]) -> int:
        total_files = 0
        total_size = 0
        stripped = [p.rstrip("/*") for p in patterns]
        for file_path in folder.rglob("*"):
            if not file_path.is_file():
                continue
            rel = str(file_path.relative_to(folder))
            if any(
                fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(rel, f"{p}/*")
                for p in stripped
            ):
                continue
            total_files += 1
            total_size += file_path.stat().st_size
            if total_files <= 50:
                logger.info("  {}", rel)
        logger.info(
            "[dry-run] would upload {} files ({:.1f} MB)",
            total_files,
            total_size / (1024 * 1024),
        )
        return total_files

    def space_info(self, space_id: str = DEFAULT_SPACE_ID):
        return self.api.space_info(space_id)


def check_space_vars(
    space_id: str = "CommunityOne/www.communityone.com",
    config: HFConfig | None = None,
) -> None:
    """Print a HuggingFace Space's SDK/runtime/variables (best-effort)."""
    config = config or HFConfig()
    deployer = SpaceDeployer(config)
    try:
        info = deployer.space_info(space_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("Could not fetch space {}: {}", space_id, exc)
        logger.info(
            "Check manually: https://huggingface.co/spaces/{}/settings", space_id
        )
        return

    logger.info("Space: {}", info.id)
    logger.info("  SDK: {}", getattr(info, "sdk", "N/A"))
    logger.info("  Runtime: {}", getattr(info, "runtime", "N/A"))
    logger.info("  Last modified: {}", getattr(info, "last_modified", "N/A"))
    variables = getattr(info, "variables", None)
    if variables:
        for key, value in variables.items():
            masked = "***" if "TOKEN" in key or "SECRET" in key else value
            logger.info("  var {} = {}", key, masked)
    else:
        logger.info(
            "Variables/secrets are only visible in the web UI: "
            "https://huggingface.co/spaces/{}/settings",
            space_id,
        )


def check_env_vars() -> bool:
    """Verify the required HuggingFace env vars are present. Returns True if OK."""
    config = HFConfig()
    ok = True
    if config.token:
        logger.success("HF_TOKEN is set")
    else:
        logger.error("HF_TOKEN is not set")
        ok = False
    logger.info("HF_ORGANIZATION = {}", config.organization)
    logger.info("HF_USERNAME = {}", config.username)
    logger.info("HF_DATASET_PREFIX = {}", config.dataset_prefix)
    return ok
