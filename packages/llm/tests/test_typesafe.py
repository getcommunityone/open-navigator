"""Jev client and transcript screen (llm.typesafe). No network: httpx.MockTransport."""

from __future__ import annotations

import json

import httpx
import pytest
from llm.typesafe import client as jev
from llm.typesafe import screen_transcripts as screen
from llm.usage import prices

OK_BODY = {
    "model": "jev-1.14.0",
    "answers": {
        "meeting_kind": {
            "type": "choice",
            "choice": "government_meeting",
            "confidence": 0.9,
            "probabilities": {
                "government_meeting": 0.9,
                "government_other": 0.08,
                "not_government": 0.02,
            },
        },
        "has_decisions": {"type": "noul", "noul": 0.97},
        "mentions_data_center": {"type": "noul", "noul": 0.04},
    },
    "usage": {"input_tokens": 1200, "output_tokens": 30},
}


@pytest.fixture(autouse=True)
def usage_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_USAGE_LOG_DIR", str(tmp_path))
    return tmp_path


def _client(handler, **kw) -> jev.JevClient:
    return jev.JevClient(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
        sleep=lambda s: None,
        **kw,
    )


def test_request_shape_and_answers():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["Authorization"]
        seen["long"] = request.headers.get(jev.LONG_CONTEXT_HEADER)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=OK_BODY)

    with _client(handler) as c:
        resp = c.system_one(state="Motion carried 5-0.", questions=screen.QUESTIONS)

    assert seen["url"] == "https://api.typesafe.ai/v1/systemone"
    assert seen["auth"] == "Bearer test-key"
    assert seen["long"] is None
    assert seen["body"]["model"] == "jev-latest"
    assert seen["body"]["questions"]["has_decisions"]["type"] == "noul"
    assert (
        seen["body"]["questions"]["meeting_kind"]["criteria"].keys()
        == screen.MEETING_KINDS.keys()
    )
    assert resp.model == "jev-1.14.0"
    assert resp.answers["meeting_kind"].choice == "government_meeting"
    assert resp.answers["has_decisions"].noul == pytest.approx(0.97)
    assert resp.answers["has_decisions"].choice is None
    assert resp.input_tokens == 1200


def test_long_context_header():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers[jev.LONG_CONTEXT_HEADER] == "true"
        return httpx.Response(200, json=OK_BODY)

    with _client(handler) as c:
        c.system_one(state="x", questions={"q": jev.noul("x")}, long_context=True)


def test_retries_429_and_529_then_succeeds(usage_dir):
    statuses = iter([429, 529, 200])

    def handler(request: httpx.Request) -> httpx.Response:
        code = next(statuses)
        return httpx.Response(
            code, json=OK_BODY if code == 200 else {"detail": "slow down"}
        )

    with _client(handler) as c:
        resp = c.system_one(state="x", questions={"q": jev.noul("x")})
    assert resp.model == "jev-1.14.0"
    rows = [
        json.loads(line)
        for f in usage_dir.rglob("*.jsonl")
        for line in f.read_text().splitlines()
    ]
    assert len(rows) == 1
    assert (
        rows[0]["provider"] == "typesafe"
        and rows[0]["attempt_count"] == 3
        and rows[0]["is_ok"]
    )
    assert rows[0]["input_token_count"] == 1200


def test_client_error_is_not_retried(usage_dir):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(422, json={"detail": "criteria: field required"})

    with _client(handler) as c, pytest.raises(jev.JevError) as err:
        c.system_one(state="x", questions={"q": jev.noul("x")})
    assert err.value.status_code == 422
    assert "field required" in str(err.value)
    assert len(calls) == 1
    rows = [
        json.loads(line)
        for f in usage_dir.rglob("*.jsonl")
        for line in f.read_text().splitlines()
    ]
    assert rows[0]["is_ok"] is False and rows[0]["error_type"] == "http_422"


def test_gives_up_after_max_attempts():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(529, json={"detail": "overloaded"})

    with _client(handler, max_attempts=2) as c, pytest.raises(jev.JevError) as err:
        c.system_one(state="x", questions={"q": jev.noul("x")})
    assert err.value.status_code == 529


def test_missing_key(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(jev.JevError, match="TYPESAFE_API_KEY"):
        jev.JevClient()


def test_question_builders_validate():
    with pytest.raises(ValueError):
        jev.score("x", ["only one"])
    with pytest.raises(ValueError):
        jev.choice("x", {})
    assert jev.score("x", ["low", "high"]) == {
        "type": "score",
        "instructions": "x",
        "criteria": ["low", "high"],
    }


def test_chunk_segments_breaks_between_segments():
    assert screen.chunk_segments(["aaaa", "bbbb", "cc"], max_chars=9) == [
        "aaaa bbbb",
        "cc",
    ]
    assert screen.chunk_segments(["  ", ""], max_chars=9) == []
    # One segment longer than the limit is split on its own.
    assert screen.chunk_segments(["x" * 10], max_chars=4) == ["xxxx", "xxxx", "xx"]
    assert all(
        len(c) <= 50 for c in screen.chunk_segments(["word"] * 100, max_chars=50)
    )


def test_pick_chunks_keeps_first_and_last():
    assert screen.pick_chunks(["a"] * 3, 4) == [0, 1, 2]
    picked = screen.pick_chunks(["a"] * 10, 4)
    assert picked[0] == 0 and picked[-1] == 9 and len(picked) == 4
    assert screen.pick_chunks([], 4) == []


def _resp(kind_probs, decisions, dc):
    return jev.JevResponse.from_json(
        {
            "model": "jev-1.14.0",
            "answers": {
                "meeting_kind": {"type": "choice", "probabilities": kind_probs},
                "has_decisions": {"type": "noul", "noul": decisions},
                "mentions_data_center": {"type": "noul", "noul": dc},
            },
            "usage": {"input_tokens": 10, "output_tokens": 1},
        }
    )


def test_aggregate_averages_choice_and_takes_noul_max():
    out = screen.aggregate(
        [
            _resp({"government_meeting": 0.6, "government_other": 0.4}, 0.1, 0.0),
            _resp({"government_meeting": 1.0, "government_other": 0.0}, 0.9, 0.3),
        ]
    )
    assert out["meeting_kind"] == "government_meeting"
    assert out["meeting_kind_probabilities"]["government_meeting"] == pytest.approx(0.8)
    assert out["has_decisions_p"] == pytest.approx(0.9)
    assert out["mentions_data_center_p"] == pytest.approx(0.3)


def test_screen_transcript_sends_each_picked_chunk():
    states = []

    def handler(request: httpx.Request) -> httpx.Response:
        states.append(json.loads(request.content)["state"])
        return httpx.Response(200, json=OK_BODY)

    with _client(handler) as c:
        result = screen.screen_transcript(
            c, "vid1", ["seg"] * 50, chunk_chars=20, max_chunks=3
        )
    assert result is not None
    assert result.chunks_screened == 3 == len(states)
    assert result.chunk_count > 3
    assert result.input_tokens == 3600
    assert result.has_decisions_p == pytest.approx(0.97)
    row = result.row()
    assert row["question_version"] == screen.QUESTION_VERSION
    assert json.loads(row["answers"])[0]["chunk"] == 0

    with _client(handler) as c:
        assert screen.screen_transcript(c, "empty", ["  "]) is None


def test_select_sql_filters():
    sql, params = screen.select_sql(
        states=["al", " ga "], jurisdiction_id="x_1", rescreen=False
    )
    assert "e.state_code = ANY(%s)" in sql and params[0] == ["AL", "GA"]
    assert params[1] == "x_1" and params[2] == screen.QUESTION_VERSION
    assert sql.rstrip().endswith("LIMIT %s")
    sql, params = screen.select_sql(states=[], jurisdiction_id="", rescreen=True)
    assert "NOT EXISTS" not in sql and params == []


def test_jev_price_on_file():
    rate = prices.model_price("jev-1.14.0", "interactive", prices.load_prices())
    assert rate is not None
    assert rate["input_usd_per_1m"] == pytest.approx(0.042)
    row = {
        "model": "jev-1.14.0",
        "api_mode": "interactive",
        "input_token_count": 1_000_000,
        "output_token_count": 50,
    }
    assert prices.call_cost_usd(row, prices.load_prices()) == pytest.approx(0.042)


def test_batch_backlog_flag_parses():
    from llm.gemini.batch_backlog import build_parser

    args = build_parser().parse_args(["submit", "--skip-jev-below", "0.2"])
    assert args.skip_jev_below == pytest.approx(0.2)
    assert build_parser().parse_args(["submit"]).skip_jev_below is None


def test_batch_backlog_meeting_flag_parses():
    from llm.gemini.batch_backlog import build_parser

    args = build_parser().parse_args(["submit", "--skip-jev-meeting-below", "0.6"])
    assert args.skip_jev_meeting_below == pytest.approx(0.6)
    assert build_parser().parse_args(["submit"]).skip_jev_meeting_below is None
    both = build_parser().parse_args(
        ["submit", "--skip-jev-below", "0.2", "--skip-jev-meeting-below", "0.7"]
    )
    assert both.skip_jev_below == pytest.approx(0.2)
    assert both.skip_jev_meeting_below == pytest.approx(0.7)


def test_calibrate_threshold_counts():
    # Already-analyzed sample: null gov_p must not count as a skip.
    rows = [
        ("a", 0.9),
        ("b", 0.55),
        ("c", 0.4),
        ("d", None),
    ]
    table = screen.calibrate_threshold_table(rows, thresholds=(0.5, 0.6, 0.7))
    assert [r["threshold"] for r in table] == [0.5, 0.6, 0.7]
    # T=0.5 skips only c (0.4); d null kept
    assert table[0] == {
        "threshold": 0.5,
        "n": 4,
        "keep": 3,
        "skip": 1,
        "false_skip_rate": pytest.approx(0.25),
    }
    # T=0.6 skips b+c
    assert table[1]["skip"] == 2 and table[1]["keep"] == 2
    # T=0.7 skips b+c (a=0.9 kept)
    assert table[2]["skip"] == 2 and table[2]["keep"] == 2


def test_gov_meeting_p_below():
    assert screen.gov_meeting_p_below(0.59, 0.6) is True
    assert screen.gov_meeting_p_below(0.6, 0.6) is False
    assert screen.gov_meeting_p_below(None, 0.6) is False


def test_screen_calibrate_flag_parses():
    args = screen.build_parser().parse_args(["--calibrate", "--state", "AL", "--limit", "50"])
    assert args.calibrate is True
    assert args.state == ["AL"] and args.limit == 50
    assert screen.build_parser().parse_args([]).calibrate is False


def test_screen_usage_rows_name_the_stage_and_video(usage_dir):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=OK_BODY)

    with _client(handler) as c:
        screen.screen_transcript(c, "vid9", ["seg"] * 10, chunk_chars=20, max_chunks=2)
    rows = [
        json.loads(line)
        for f in usage_dir.rglob("*.jsonl")
        for line in f.read_text().splitlines()
    ]
    assert rows and all(
        r["stage"] == "jev_screen" and r["video_id"] == "vid9" for r in rows
    )
