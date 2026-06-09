"""hosting.deploy — production deployment orchestration.

Runs a multi-step production deployment (database → Neon prod, web → HuggingFace
Spaces) as a single detached job, writing per-step status + logs that the
``/api/deployments`` dashboard reads. See :mod:`hosting.deploy.run_deployment`.
"""

from hosting.deploy.run_deployment import (  # noqa: F401
    DEFAULT_STEPS,
    STEP_DEFS,
    available_steps,
)

__all__ = ["DEFAULT_STEPS", "STEP_DEFS", "available_steps"]
