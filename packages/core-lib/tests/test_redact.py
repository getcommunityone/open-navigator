"""#878: credentials never reach a log line."""

from __future__ import annotations

from loguru import logger

from core_lib.redact import MASK, env_secret_values, install_log_redaction, redact_secrets

# Shaped like a Google API key, and not one.
FAKE_GOOGLE_KEY = "AIza" + "Xx0" * 11 + "Zz"

YOUTUBE_ERROR = (
    "YouTube API error for channel UCabc: <HttpError 404 when requesting "
    f"https://youtube.googleapis.com/youtube/v3/playlistItems?playlistId=UUabc&part=snippet&maxResults=10&key={FAKE_GOOGLE_KEY}"
    '&alt=json returned "The playlist identified with the request\'s playlistId parameter cannot be found.">'
)


def test_the_youtube_error_line_loses_its_key_and_keeps_the_rest():
    out = redact_secrets(YOUTUBE_ERROR, known_values=[])
    assert FAKE_GOOGLE_KEY not in out
    assert f"&key={MASK}&alt=json" in out
    assert "playlistId=UUabc" in out and "HttpError 404" in out and "cannot be found" in out


def test_other_credential_parameters_and_headers():
    cases = {
        "GET /v1?api_key=abcdef0123456789&x=1": "GET /v1?api_key=***&x=1",
        "https://h/p?access_token=ya29.a0AfH6SMBx&u=2": "https://h/p?access_token=***&u=2",
        "Authorization: Bearer abcdefghijklmnop.qrstuv": "Authorization: Bearer ***",
        "x-api-key: 9f8e7d6c5b4a39281706": "x-api-key: ***",
        "password=hunter2hunter2 host=db": "password=*** host=db",
    }
    for raw, want in cases.items():
        assert redact_secrets(raw, known_values=[]) == want


def test_recognisable_key_shapes_anywhere_in_the_text():
    text = f"using {FAKE_GOOGLE_KEY} and sk-" + "a1B2" * 6 + " and hf_" + "Zz9" * 8
    out = redact_secrets(text, known_values=[])
    assert out == f"using {MASK} and {MASK} and {MASK}"


def test_ordinary_text_is_left_alone():
    for text in (
        "Loaded 1,234 rows for jurisdiction c-AL-01125",
        "key metrics: 12 of 52",
        "The token count was 4096",
        "https://www.youtube.com/watch?v=ajsME66iXbY&t=120s",
        "",
    ):
        assert redact_secrets(text, known_values=[]) == text


def test_values_of_credential_named_environment_variables():
    env = {
        "YOUTUBE_API_KEY": "plain-looking-value-12345",
        "GEMINI_API_KEY_2": "another-long-secret-value",
        "HF_TOKEN": "tok-abcdefghijkl",
        "POSTGRES_PASSWORD": "short",  # too short to blank safely
        "HOME": "/home/someone/projects",
        "EMPTY_KEY": "",
    }
    values = env_secret_values(env)
    assert values == sorted(values, key=len, reverse=True)
    assert set(values) == {"plain-looking-value-12345", "another-long-secret-value", "tok-abcdefghijkl"}
    out = redact_secrets("auth with plain-looking-value-12345 from /home/someone/projects", known_values=values)
    assert out == "auth with *** from /home/someone/projects"


def test_installed_redaction_covers_every_loguru_message():
    lines: list[str] = []
    install_log_redaction()
    sink_id = logger.add(lines.append, format="{message}")
    try:
        logger.error(YOUTUBE_ERROR)
        logger.info("key={}", FAKE_GOOGLE_KEY)
    finally:
        logger.remove(sink_id)
        logger.configure(patcher=lambda record: None)
    joined = "".join(lines)
    assert FAKE_GOOGLE_KEY not in joined and joined.count(MASK) >= 2
