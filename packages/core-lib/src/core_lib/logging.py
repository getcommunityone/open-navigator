"""Container-friendly JSON logging via loguru."""
from __future__ import annotations

import json
import sys

from loguru import logger


def _json_sink(message) -> None:
    record = message.record
    payload = {
        "ts": record["time"].isoformat(),
        "level": record["level"].name,
        "logger": record["name"],
        "msg": record["message"],
        **record["extra"],
    }
    if record["exception"] is not None:
        payload["exception"] = str(record["exception"])
    sys.stdout.write(json.dumps(payload, default=str) + "\n")
    sys.stdout.flush()


def setup_logging(level: str = "INFO") -> None:
    """Configure loguru to emit one JSON object per line on stdout."""
    logger.remove()
    logger.add(_json_sink, level=level)
