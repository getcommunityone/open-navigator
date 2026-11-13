"""Adapter interface, registry and loud failure for meeting platforms (CORE-3.1, #242).

A platform with no adapter must never look like a council with no meetings. ``adapter_for``
raises ``UnsupportedPlatformError`` instead of falling back to a generic scraper, and
``coverage_report`` lists every jurisdiction left uncovered, so the gap is visible in each run.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar

from loguru import logger

from ingestion.meetings.model import Meeting

UNKNOWN_PLATFORM = "unknown"


class MeetingAdapter(ABC):
    """Turns one platform's raw meeting record into a ``Meeting``."""

    platform_code: ClassVar[str]

    @abstractmethod
    def normalize(self, raw: Mapping[str, Any]) -> Meeting:
        """Return the meeting for ``raw``, or raise ``ValueError`` if the record can't identify one."""


_ADAPTERS: dict[str, type[MeetingAdapter]] = {}


def normalize_platform_code(platform_code: str | None) -> str:
    code = (platform_code or "").strip().lower()
    return code or UNKNOWN_PLATFORM


def register_adapter(adapter_cls: type[MeetingAdapter]) -> type[MeetingAdapter]:
    """Register an adapter class under its ``platform_code`` (usable as a class decorator)."""
    code = normalize_platform_code(getattr(adapter_cls, "platform_code", None))
    if code == UNKNOWN_PLATFORM:
        raise ValueError(f"{adapter_cls.__name__} needs a platform_code.")
    existing = _ADAPTERS.get(code)
    if existing is not None and existing is not adapter_cls:
        raise ValueError(f"Platform {code!r} already has an adapter: {existing.__name__}.")
    _ADAPTERS[code] = adapter_cls
    return adapter_cls


def supported_platforms() -> list[str]:
    return sorted(_ADAPTERS)


class UnsupportedPlatformError(LookupError):
    """No adapter exists for a jurisdiction's meeting platform."""

    def __init__(self, platform_code: str | None, jurisdiction_name: str) -> None:
        self.platform_code = normalize_platform_code(platform_code)
        self.jurisdiction_name = jurisdiction_name
        super().__init__(
            f"No meeting adapter for platform {self.platform_code!r} (jurisdiction {jurisdiction_name!r}). "
            f"Supported platforms: {', '.join(supported_platforms()) or 'none'}. "
            "Add an adapter in ingestion.meetings, or report the gap; never treat this source as having no meetings."
        )


def adapter_for(platform_code: str | None, *, jurisdiction_name: str) -> type[MeetingAdapter]:
    """Return the adapter class for a platform, or raise ``UnsupportedPlatformError``."""
    code = normalize_platform_code(platform_code)
    adapter = _ADAPTERS.get(code)
    if adapter is None:
        raise UnsupportedPlatformError(code, jurisdiction_name)
    return adapter


@dataclass
class CoverageReport:
    """Which jurisdictions a run can read, by platform, and which it can't."""

    supported: dict[str, int] = field(default_factory=dict)
    unsupported: dict[str, list[str]] = field(default_factory=dict)

    @property
    def unsupported_count(self) -> int:
        return sum(len(names) for names in self.unsupported.values())

    def log(self) -> None:
        """Log one success line for covered jurisdictions and one warning per unsupported platform."""
        covered = sum(self.supported.values())
        logger.success("Meeting adapters cover {:,} jurisdiction(s): {}", covered, self.supported)
        for platform_code, names in sorted(self.unsupported.items()):
            sample = ", ".join(names[:5]) + (" …" if len(names) > 5 else "")
            logger.warning(
                "No meeting adapter for platform {!r}: {:,} jurisdiction(s) uncovered ({})",
                platform_code, len(names), sample,
            )


def coverage_report(sources: Iterable[tuple[str, str | None]]) -> CoverageReport:
    """Group ``(jurisdiction_name, platform_code)`` pairs into supported counts and unsupported lists."""
    supported: Counter[str] = Counter()
    unsupported: dict[str, list[str]] = {}
    for jurisdiction_name, platform_code in sources:
        code = normalize_platform_code(platform_code)
        if code in _ADAPTERS:
            supported[code] += 1
        else:
            unsupported.setdefault(code, []).append(jurisdiction_name)
    return CoverageReport(supported=dict(supported), unsupported=unsupported)
