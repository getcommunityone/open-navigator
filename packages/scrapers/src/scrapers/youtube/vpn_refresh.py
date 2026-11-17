"""Get a fresh VPN exit IP when YouTube starts blocking the current one.

YouTube throttles by IP address. Behind a full-tunnel VPN (Surfshark), a new exit
IP usually clears the block, while city websites are the opposite case: some refuse
VPN addresses, and ``scrapers.discovery.scrape_http`` retries those on the home
connection. This module handles the YouTube side.

When the caption backfill hits repeated blocks, :func:`refresh_exit_ip`:

1. runs ``VPN_REFRESH_COMMAND`` if it's set (any command that reconnects the VPN or
   switches its server; Surfshark on Windows has no command-line tool, so this is
   whatever the operator has set up, e.g. a scheduled task that restarts it);
2. waits until the public IP changes, polling every ``poll_seconds`` up to
   ``wait_seconds``. With Surfshark's *Rotating IP* setting on, the exit IP changes
   every few minutes without reconnecting, so waiting alone is enough.

It does nothing unless a VPN tunnel is up (``vpn_guard.read_routes()`` finds one),
because without a tunnel the public IP is the home connection's and won't change.
``scrapers.youtube.vpn_guard.vpn_status()`` reports the tunnel, home interface and
both public IPs; ``require_vpn()`` stops YouTube runs when the tunnel is down.

Environment:
  YOUTUBE_VPN_REFRESH — ``auto`` (default: on when a VPN tunnel is up), ``0`` off
  VPN_REFRESH_COMMAND — optional command run before waiting
  VPN_REFRESH_WAIT_SECONDS — longest wait for a new IP (default 720)
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from typing import Callable, Optional

import httpx
from loguru import logger

IP_ECHO_URLS = ("https://api.ipify.org", "https://ifconfig.me/ip")


@dataclass
class RefreshResult:
    old_ip: Optional[str]
    new_ip: Optional[str]
    command_ran: bool
    waited_seconds: float

    @property
    def changed(self) -> bool:
        return bool(self.old_ip) and bool(self.new_ip) and self.new_ip != self.old_ip


def refresh_enabled() -> bool:
    """On when ``YOUTUBE_VPN_REFRESH`` allows it and traffic leaves through a VPN tunnel."""
    mode = (os.getenv("YOUTUBE_VPN_REFRESH") or "auto").strip().lower()
    if mode in ("0", "false", "no", "off"):
        return False
    # Read the route table live (vpn_guard), not the per-process cached
    # direct_egress_interface(): the tunnel can come and go during a run (#488).
    from scrapers.youtube.vpn_guard import read_routes

    return read_routes().tunnel_interface is not None


def public_ip(timeout: float = 10.0) -> Optional[str]:
    """The current public IP over the default route (the VPN, when it's up)."""
    for url in IP_ECHO_URLS:
        try:
            resp = httpx.get(url, timeout=timeout, trust_env=False)
        except httpx.HTTPError:
            continue
        text = resp.text.strip()
        if resp.status_code == 200 and text and len(text) <= 45:
            return text
    return None


def refresh_exit_ip(
    old_ip: Optional[str] = None,
    *,
    wait_seconds: Optional[float] = None,
    poll_seconds: float = 20.0,
    command: Optional[str] = None,
    get_ip: Callable[[], Optional[str]] = public_ip,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> RefreshResult:
    """Run the refresh command (if any) and wait for the public IP to change."""
    if wait_seconds is None:
        wait_seconds = float(os.getenv("VPN_REFRESH_WAIT_SECONDS") or 720)
    command = (
        command
        if command is not None
        else (os.getenv("VPN_REFRESH_COMMAND") or "").strip()
    )
    old_ip = old_ip or get_ip()

    ran = False
    if command:
        logger.info("vpn_refresh running VPN_REFRESH_COMMAND")
        try:
            subprocess.run(command, shell=True, timeout=120, check=False)  # noqa: S602 - operator-set command
            ran = True
        except subprocess.TimeoutExpired:
            logger.warning("vpn_refresh: VPN_REFRESH_COMMAND timed out after 120s")

    start = clock()
    new_ip: Optional[str] = None
    while True:
        new_ip = get_ip()
        if new_ip and old_ip is None:
            # The IP lookup failed before; this reading is the baseline, not a change.
            old_ip = new_ip
        elif new_ip and new_ip != old_ip:
            break
        if clock() - start >= wait_seconds:
            break
        sleep(poll_seconds)
    result = RefreshResult(
        old_ip=old_ip, new_ip=new_ip, command_ran=ran, waited_seconds=clock() - start
    )
    if result.changed:
        logger.success("vpn_refresh: new exit IP after {:.0f}s", result.waited_seconds)
    else:
        logger.warning(
            "vpn_refresh: exit IP unchanged after {:.0f}s (turn on Surfshark's Rotating IP, "
            "or set VPN_REFRESH_COMMAND)",
            result.waited_seconds,
        )
    return result
