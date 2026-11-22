"""Operator-actions file feed + dismiss (#712)."""

from __future__ import annotations

import json
from pathlib import Path

from api.batch_jobs.operator_actions import dismiss_action, list_open_actions


def _write_actions(path: Path, *, count: int = 36, stamp: str = "20261122_071559") -> None:
    path.write_text(
        json.dumps(
            {
                "generated_at": "2026-11-22T14:00:00+00:00",
                "stamp": stamp,
                "states": ["VA"],
                "actions": [
                    {
                        "code": "youtube_api_quota",
                        "title": "YouTube Data API quota exhausted",
                        "count": count,
                        "examples": ["accomack_51001"],
                        "states": ["VA"],
                        "fingerprint": f"youtube_api_quota:{count}:{stamp}",
                        "template_id": "youtube_api_quota",
                        "detail": "quota",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_list_open_actions_and_dismiss(tmp_path: Path):
    actions = tmp_path / "action_required.json"
    dismissals = tmp_path / "action_dismissals.json"
    _write_actions(actions)
    payload = list_open_actions(action_path=actions, dismissals_path=dismissals)
    assert len(payload["open"]) == 1
    assert payload["open"][0]["code"] == "youtube_api_quota"
    assert payload["templates"]
    fp = payload["open"][0]["fingerprint"]
    dismiss_action(
        "youtube_api_quota",
        fingerprint=fp,
        action_path=actions,
        dismissals_path=dismissals,
    )
    after = list_open_actions(action_path=actions, dismissals_path=dismissals)
    assert after["open"] == []


def test_dismiss_reopens_on_new_fingerprint(tmp_path: Path):
    actions = tmp_path / "action_required.json"
    dismissals = tmp_path / "action_dismissals.json"
    _write_actions(actions, count=36, stamp="a")
    dismiss_action(
        "youtube_api_quota",
        action_path=actions,
        dismissals_path=dismissals,
    )
    assert list_open_actions(action_path=actions, dismissals_path=dismissals)["open"] == []
    _write_actions(actions, count=40, stamp="b")
    reopened = list_open_actions(action_path=actions, dismissals_path=dismissals)
    assert len(reopened["open"]) == 1
    assert reopened["open"][0]["fingerprint"] == "youtube_api_quota:40:b"
