"""Unit tests for api/routes/data_deletion.py and api/routes/contact.py security hardening."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from api.routes import contact, data_deletion


def _make_signed_request(payload_dict: dict[str, Any], secret: str) -> str:
    raw_json = json.dumps(payload_dict, separators=(",", ":")).encode("utf-8")
    b64_payload = base64.urlsafe_b64encode(raw_json).decode("ascii").rstrip("=")
    sig = hmac.new(secret.encode("utf-8"), msg=b64_payload.encode("utf-8"), digestmod=hashlib.sha256).digest()
    b64_sig = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    return f"{b64_sig}.{b64_payload}"


def _build_json_request(body: dict[str, Any]) -> Request:
    raw = json.dumps(body).encode("utf-8")

    async def receive():
        return {"type": "http.request", "body": raw, "more_body": False}

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/data-deletion/facebook",
        "headers": [(b"content-type", b"application/json")],
    }
    return Request(scope, receive)


class _FakeQuery:
    def __init__(self, user: Any) -> None:
        self._user = user

    def filter(self, *args: Any, **kwargs: Any) -> "_FakeQuery":
        return self

    def first(self) -> Any:
        return self._user


class _FakeSession:
    def __init__(self, user: Any = None, fail_commit: bool = False) -> None:
        self._user = user
        self._fail_commit = fail_commit
        self.deleted: list[Any] = []
        self.committed = False
        self.rolled_back = False

    def query(self, model: Any) -> _FakeQuery:
        return _FakeQuery(self._user)

    def delete(self, obj: Any) -> None:
        self.deleted.append(obj)

    def commit(self) -> None:
        if self._fail_commit:
            raise RuntimeError("DB commit failed")
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    contact.clear_contact_rate_limits()
    yield
    contact.clear_contact_rate_limits()


def test_parse_signed_request_handles_all_base64_paddings_and_verifies_hmac():
    secret = "test_fb_app_secret_123"
    for uid in ("1", "12", "123", "1234", "9876543210"):
        sr = _make_signed_request({"algorithm": "HMAC-SHA256", "user_id": uid}, secret)
        parsed = data_deletion.parse_signed_request(sr, secret)
        assert parsed["user_id"] == uid


def test_parse_signed_request_rejects_wrong_algorithm_or_bad_signature():
    secret = "test_fb_app_secret_123"
    bad_alg = _make_signed_request({"algorithm": "NONE", "user_id": "12345"}, secret)
    with pytest.raises(HTTPException) as exc_alg:
        data_deletion.parse_signed_request(bad_alg, secret)
    assert exc_alg.value.status_code == 400

    valid_sr = _make_signed_request({"algorithm": "HMAC-SHA256", "user_id": "12345"}, secret)
    with pytest.raises(HTTPException) as exc_sig:
        data_deletion.parse_signed_request(valid_sr, "wrong_secret")
    assert exc_sig.value.status_code == 400


@pytest.mark.asyncio
async def test_facebook_data_deletion_json_payload_and_rollback_on_db_error(
    monkeypatch: pytest.MonkeyPatch,
):
    secret = "fb_secret_key"
    monkeypatch.setenv("FACEBOOK_APP_SECRET", secret)
    monkeypatch.setenv("FRONTEND_URL", "https://www.communityone.com/")

    sr = _make_signed_request({"algorithm": "HMAC-SHA256", "user_id": "fb_user_42"}, secret)
    fake_user = SimpleNamespace(email="user@example.com", oauth_provider="facebook", oauth_id="fb_user_42")
    db = _FakeSession(user=fake_user)

    res = await data_deletion.facebook_data_deletion_callback(_build_json_request({"signed_request": sr}), db=db)
    assert db.committed is True
    assert len(db.deleted) == 1
    assert res.confirmation_code.startswith("DEL-fb_user_42-")
    assert "status=deleted" in res.url
    assert "//data-deletion-status" not in res.url

    # Verify unsafe user_id with query injection is rejected
    bad_uid_sr = _make_signed_request({"algorithm": "HMAC-SHA256", "user_id": "42&status=deleted"}, secret)
    with pytest.raises(HTTPException) as exc_uid:
        await data_deletion.facebook_data_deletion_callback(
            _build_json_request({"signed_request": bad_uid_sr}), db=_FakeSession()
        )
    assert exc_uid.value.status_code == 400

    # Verify DB rollback when commit fails
    failing_db = _FakeSession(user=fake_user, fail_commit=True)
    with pytest.raises(HTTPException) as exc_db:
        await data_deletion.facebook_data_deletion_callback(
            _build_json_request({"signed_request": sr}), db=failing_db
        )
    assert exc_db.value.status_code == 500
    assert failing_db.rolled_back is True


@pytest.mark.asyncio
async def test_contact_submit_sanitizes_control_chars_and_uses_bearer_auth(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token_123")
    monkeypatch.setenv("GITHUB_REPO", "getcommunityone/open-navigator")

    captured: dict[str, Any] = {}

    class _FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url: str, json: dict[str, Any], headers: dict[str, str], timeout: float):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            req = httpx.Request("POST", url)
            return httpx.Response(201, json={"html_url": "https://github.com/getcommunityone/open-navigator/issues/999"}, request=req)

    monkeypatch.setattr(contact.httpx, "AsyncClient", _FakeAsyncClient)

    req_model = contact.ContactRequest(
        name="Alice\r\nInjected",
        email="Alice@Example.com",
        subject="Broken link\r\n## Fake Heading",
        message="The municipal budget page fails to load for our county.",
        category=" FEATURE ",
    )

    resp = await contact.submit_contact(req_model)
    assert resp.success is True
    assert resp.issue_url == "https://github.com/getcommunityone/open-navigator/issues/999"
    assert captured["headers"]["Authorization"] == "Bearer ghp_test_token_123"
    assert "\r" not in captured["json"]["title"]
    assert "\n" not in captured["json"]["title"]
    assert captured["json"]["labels"] == ["enhancement", "contact-form"]


@pytest.mark.asyncio
async def test_contact_submit_enforces_duplicate_and_sender_rate_limits(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token_123")

    class _FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url: str, json: dict[str, Any], headers: dict[str, str], timeout: float):
            req = httpx.Request("POST", url)
            return httpx.Response(201, json={"html_url": "https://github.com/example/issues/1"}, request=req)

    monkeypatch.setattr(contact.httpx, "AsyncClient", _FakeAsyncClient)

    base_req = contact.ContactRequest(
        name="Bob",
        email="bob@example.com",
        subject="Question about meetings",
        message="How often are city council transcripts updated?",
        category="question",
    )

    await contact.submit_contact(base_req)

    # Immediate duplicate submission must be rejected with 429
    with pytest.raises(HTTPException) as exc_dup:
        await contact.submit_contact(base_req)
    assert exc_dup.value.status_code == 429

    # Distinct messages from same sender up to _MAX_SUBMISSIONS_PER_SENDER (5 total)
    for i in range(2, contact._MAX_SUBMISSIONS_PER_SENDER + 1):
        await contact.submit_contact(
            contact.ContactRequest(
                name="Bob",
                email="bob@example.com",
                subject=f"Question {i}",
                message=f"Distinct question body number {i} for testing rate limit.",
                category="question",
            )
        )

    with pytest.raises(HTTPException) as exc_rate:
        await contact.submit_contact(
            contact.ContactRequest(
                name="Bob",
                email="bob@example.com",
                subject="Question overflow",
                message="This sixth submission within the window must be rate limited.",
                category="question",
            )
        )
    assert exc_rate.value.status_code == 429
