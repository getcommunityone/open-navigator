"""
Champ Digital Solutions (ChampDS / EarthChannel) API helpers.

Gwinnett County embeds TV Gwinnett via ``play.champds.com/{customer}/archive/{id}``.
The browser loads JSON from ``playapi.champds.com`` (``play`` + ``api.`` + rest of host).
VOD HLS URLs are built from ``ServicesAndMachineInfo`` + ``MediaInfo.VOD2`` on each event.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence
from urllib.parse import urlparse

import requests

_DEFAULT_UA = "OpenNavigatorChampDS/1.0"
_PLAY_HOST_RE = re.compile(
    r"^https?://play\.champds\.com/(?P<customer>[a-zA-Z0-9_]+)/archive/(?P<archive_id>\d+)",
    re.I,
)


@dataclass(frozen=True)
class ChampDsArchiveConfig:
    customer_access_id: str
    archive_id: int
    archive_title: str = ""
    archive_groups: tuple[dict[str, Any], ...] = ()


@dataclass
class ChampDsEvent:
    customer_event_id: int
    event_title: str
    event_datetime_utc: str
    event_datetime_local: str = ""
    media_info: dict[str, Any] = field(default_factory=dict)
    agenda_attachments: list[dict[str, Any]] = field(default_factory=list)
    minutes_attachments: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def has_media(self) -> bool:
        mi = self.media_info or {}
        return bool((mi.get("MediaType") or "").strip()) and (
            (mi.get("VOD2") or "").strip() or (mi.get("MediaPath") or "").strip()
        )


def champds_api_host(play_host: str) -> str:
    """``play.champds.com`` → ``playapi.champds.com`` (see ``cds.common.js``)."""
    host = (play_host or "play.champds.com").strip().lower()
    parts = host.split(".")
    if len(parts) >= 3 and parts[0] == "play":
        return f"{parts[0]}api.{parts[1]}.{parts[2]}"
    return host


def parse_champds_archive_embed_url(url: str) -> tuple[str, int] | None:
    m = _PLAY_HOST_RE.match((url or "").strip())
    if not m:
        return None
    return m.group("customer"), int(m.group("archive_id"))


class ChampDsClient:
    def __init__(
        self,
        *,
        customer_access_id: str,
        play_host: str = "play.champds.com",
        session: requests.Session | None = None,
        user_agent: str = _DEFAULT_UA,
    ) -> None:
        self.customer_access_id = (customer_access_id or "").strip()
        if not self.customer_access_id:
            raise ValueError("customer_access_id is required")
        self.play_host = (play_host or "play.champds.com").strip()
        self.api_host = champds_api_host(self.play_host)
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", user_agent)
        self.session.headers.setdefault("Accept", "application/json, text/javascript, */*; q=0.01")
        self._warmed = False

    @property
    def play_base(self) -> str:
        return f"https://{self.play_host}"

    @property
    def api_base(self) -> str:
        return f"https://{self.api_host}/{self.customer_access_id}"

    def warm_session(self, *, customer_event_id: int | None = None) -> None:
        """Set cookies so ``playapi`` returns full event JSON (not just ``Customer``)."""
        if self._warmed and customer_event_id is None:
            return
        path = (
            f"/{self.customer_access_id}/event/{int(customer_event_id)}"
            if customer_event_id is not None
            else f"/{self.customer_access_id}/archive/1"
        )
        self.session.get(
            f"{self.play_base}{path}",
            timeout=60,
            headers={"Referer": self.play_base},
        )
        self._warmed = True

    def _get_json(self, path: str, *, referer: str | None = None) -> Any:
        url = f"{self.api_base}{path}"
        ref = referer or self.play_base
        r = self.session.get(url, timeout=120, headers={"Referer": ref})
        r.raise_for_status()
        return r.json()

    def fetch_archive(self, archive_id: int) -> ChampDsArchiveConfig:
        self.warm_session()
        data = self._get_json(f"/archive/{int(archive_id)}")
        arch = data.get("Archive") or {}
        groups = tuple(data.get("ArchiveGroups") or [])
        return ChampDsArchiveConfig(
            customer_access_id=self.customer_access_id,
            archive_id=int(archive_id),
            archive_title=str(arch.get("ArchiveTitle") or ""),
            archive_groups=groups,
        )

    def list_events_with_media(self, archive_group_id: int) -> list[dict[str, Any]]:
        self.warm_session()
        data = self._get_json(f"/archiveGroupListWithMedia/{int(archive_group_id)}")
        if not isinstance(data, list):
            return []
        return [row for row in data if isinstance(row, dict)]

    def fetch_event(self, customer_event_id: int) -> dict[str, Any]:
        self.warm_session(customer_event_id=int(customer_event_id))
        data = self._get_json(f"/event/{int(customer_event_id)}")
        if not isinstance(data, dict):
            return {}
        return data

    def resolve_event(self, row: Mapping[str, Any]) -> ChampDsEvent:
        agenda = row.get("Agenda") if isinstance(row.get("Agenda"), dict) else {}
        minutes = row.get("Minutes") if isinstance(row.get("Minutes"), dict) else {}
        return ChampDsEvent(
            customer_event_id=int(row.get("CustomerEventID") or 0),
            event_title=str(row.get("EventTitle") or "").strip(),
            event_datetime_utc=str(row.get("EventDateTimeUTC") or "").strip(),
            event_datetime_local=str(row.get("EventDateTimeLocal") or "").strip(),
            media_info=dict(row.get("MediaInfo") or {}),
            agenda_attachments=list(agenda.get("Attachments") or []),
            minutes_attachments=list(minutes.get("Attachments") or []),
            raw=dict(row),
        )

    def enrich_event(self, event: ChampDsEvent) -> ChampDsEvent:
        if not event.customer_event_id:
            return event
        detail = self.fetch_event(event.customer_event_id)
        ev = detail.get("Event") if isinstance(detail.get("Event"), dict) else {}
        agenda = detail.get("Agenda") if isinstance(detail.get("Agenda"), dict) else {}
        minutes = detail.get("Minutes") if isinstance(detail.get("Minutes"), dict) else {}
        media = detail.get("MediaInfo") if isinstance(detail.get("MediaInfo"), dict) else event.media_info
        return ChampDsEvent(
            customer_event_id=int(ev.get("CustomerEventID") or event.customer_event_id),
            event_title=str(ev.get("EventTitle") or event.event_title).strip(),
            event_datetime_utc=str(ev.get("EventDateTimeUTC") or event.event_datetime_utc).strip(),
            event_datetime_local=str(ev.get("EventDateTimeLocal") or event.event_datetime_local).strip(),
            media_info=dict(media or {}),
            agenda_attachments=list(agenda.get("Attachments") or []),
            minutes_attachments=list(minutes.get("Attachments") or []),
            raw=detail,
        )


def _svc_info_map(services: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in (services or {}).items():
        out[str(k)] = v
    return out


def vod_stream_url(services_and_machine_info: Mapping[str, Any], media_info: Mapping[str, Any]) -> str:
    """
    Build HLS (or legacy path) URL for a VOD row.

    Mirrors ``/_COMMON/players/vjs2026/embed.js`` (``VOD2`` preferred over ``MediaPath``).
    """
    svc_map = _svc_info_map(services_and_machine_info)
    svc = svc_map.get("2048") or svc_map.get(2048)
    if not svc:
        svc = svc_map.get("8") or svc_map.get(8)
    if not svc or not isinstance(svc, dict):
        raise ValueError("missing ServicesAndMachineInfo VOD service (8/2048)")

    url_base = str(svc.get("URLBase") or "").rstrip("/")
    if not url_base:
        raise ValueError("empty URLBase in ServicesAndMachineInfo")

    vod2 = str(media_info.get("VOD2") or "").strip()
    media_path = str(media_info.get("MediaPath") or "").strip()
    if vod2:
        path = vod2 if vod2.startswith("/") else f"/{vod2}"
        return f"{url_base}{path}"

    tmpl = str(svc.get("URLFilename") or "%MEDIA_PATH%")
    clip = tmpl.replace("%MEDIA_PATH%", media_path)
    if not clip.startswith("/"):
        clip = f"/{clip}"
    return f"{url_base}{clip}"


def attachment_download_url(
    customer_access_id: str,
    attachment: Mapping[str, Any],
    *,
    play_host: str = "play.champds.com",
) -> str | None:
    loc = str(attachment.get("MediaFileLocation") or "").strip()
    name = str(attachment.get("MediaFileName") or "").strip()
    if attachment.get("MediaTypeID") == 2:
        url = str(attachment.get("MediaFileName") or "").strip()
        return url if url.lower().startswith("http") else None
    if not loc or not name:
        return None
    return f"https://{play_host}/ATT/{customer_access_id}/{loc}/{name}"


def _parse_event_dt(event: ChampDsEvent) -> datetime:
    for raw in (event.event_datetime_utc, event.event_datetime_local):
        s = (raw or "").strip()
        if not s:
            continue
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(s[:19], fmt)
            except ValueError:
                continue
    return datetime.min


def recent_events_with_media(
    rows: Sequence[Mapping[str, Any]],
    *,
    limit: int = 10,
    enrich: bool = False,
    client: ChampDsClient | None = None,
) -> list[ChampDsEvent]:
    events: list[ChampDsEvent] = []
    for row in rows:
        ev = ChampDsEvent(
            customer_event_id=int(row.get("CustomerEventID") or 0),
            event_title=str(row.get("EventTitle") or "").strip(),
            event_datetime_utc=str(row.get("EventDateTimeUTC") or "").strip(),
            event_datetime_local=str(row.get("EventDateTimeLocal") or "").strip(),
            media_info=dict(row.get("MediaInfo") or {}),
            agenda_attachments=list((row.get("Agenda") or {}).get("Attachments") or [])
            if isinstance(row.get("Agenda"), dict)
            else [],
            minutes_attachments=list((row.get("Minutes") or {}).get("Attachments") or [])
            if isinstance(row.get("Minutes"), dict)
            else [],
            raw=dict(row),
        )
        if not ev.has_media:
            continue
        events.append(ev)
    events.sort(key=_parse_event_dt, reverse=True)
    if limit > 0:
        events = events[:limit]
    if enrich and client is not None:
        events = [client.enrich_event(ev) for ev in events]
    return events


def board_of_commissioners_group_id(archive: ChampDsArchiveConfig) -> int | None:
    for ag in archive.archive_groups:
        name = str(ag.get("GroupName") or "").lower()
        if "board of commissioners" in name and "planning" not in name:
            return int(ag.get("CustomerArchiveGroupID") or ag.get("ArchiveGroupID") or 0) or None
    if archive.archive_groups:
        first = archive.archive_groups[0]
        return int(first.get("CustomerArchiveGroupID") or first.get("ArchiveGroupID") or 0) or None
    return None
