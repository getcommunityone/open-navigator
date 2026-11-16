"""scrapers.youtube.vpn_refresh: wait for a new VPN exit IP when YouTube blocks."""

from __future__ import annotations

from scrapers.youtube import vpn_refresh as vr


class _Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.t += s


def test_waits_until_the_ip_changes():
    ips = iter(["1.1.1.1", "1.1.1.1", "2.2.2.2"])
    clock = _Clock()
    res = vr.refresh_exit_ip(
        "1.1.1.1",
        wait_seconds=600,
        poll_seconds=30,
        command="",
        get_ip=lambda: next(ips),
        sleep=clock.sleep,
        clock=clock,
    )
    assert (
        res.changed
        and res.new_ip == "2.2.2.2"
        and res.waited_seconds == 60
        and not res.command_ran
    )


def test_gives_up_after_the_wait():
    clock = _Clock()
    res = vr.refresh_exit_ip(
        "1.1.1.1",
        wait_seconds=90,
        poll_seconds=30,
        command="",
        get_ip=lambda: "1.1.1.1",
        sleep=clock.sleep,
        clock=clock,
    )
    assert not res.changed and res.waited_seconds >= 90


def test_runs_the_refresh_command(tmp_path):
    marker = tmp_path / "ran"
    res = vr.refresh_exit_ip(
        "1.1.1.1",
        wait_seconds=0,
        command=f"touch {marker}",
        get_ip=lambda: "3.3.3.3",
    )
    assert marker.exists() and res.command_ran and res.changed


def test_off_without_a_tunnel_or_when_disabled(monkeypatch):
    from scrapers.discovery import scrape_http

    monkeypatch.setattr(scrape_http, "direct_egress_interface", lambda: None)
    assert vr.refresh_enabled() is False
    monkeypatch.setattr(scrape_http, "direct_egress_interface", lambda: "eth3")
    assert vr.refresh_enabled() is True
    monkeypatch.setenv("YOUTUBE_VPN_REFRESH", "0")
    assert vr.refresh_enabled() is False


def test_unknown_starting_ip_is_not_a_change():
    """If the first IP lookup fails, the next reading is the baseline, not a new IP."""
    ips = iter([None, "1.1.1.1", "1.1.1.1", "1.1.1.1"])
    clock = _Clock()
    res = vr.refresh_exit_ip(
        wait_seconds=60,
        poll_seconds=30,
        command="",
        get_ip=lambda: next(ips),
        sleep=clock.sleep,
        clock=clock,
    )
    assert not res.changed and res.old_ip == "1.1.1.1"
