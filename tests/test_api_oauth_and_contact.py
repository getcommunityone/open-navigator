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


class _FakeSubmissionStore:
    """In-memory stand-in for the contact_submission table."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.rows: dict[int, Any] = {}
        self._next_id = 1

    def session(self) -> "_FakeSubmissionSession":
        if self.fail:
            raise RuntimeError("database unavailable")
        return _FakeSubmissionSession(self)


class _FakeSubmissionSession:
    def __init__(self, store: _FakeSubmissionStore) -> None:
        self._store = store
        self._pending: list[Any] = []

    def add(self, row: Any) -> None:
        self._pending.append(row)

    def commit(self) -> None:
        for row in self._pending:
            if row.contact_submission_id is None:
                row.contact_submission_id = self._store._next_id
                self._store._next_id += 1
            self._store.rows[row.contact_submission_id] = row
        self._pending.clear()

    def refresh(self, row: Any) -> None:
        return None

    def get(self, model: Any, ident: int) -> Any:
        return self._store.rows.get(ident)

    def delete(self, row: Any) -> None:
        self._store.rows.pop(row.contact_submission_id, None)

    def rollback(self) -> None:
        self._pending.clear()

    def close(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    contact.clear_contact_rate_limits()
    yield
    contact.clear_contact_rate_limits()


@pytest.fixture(autouse=True)
def submission_store(monkeypatch: pytest.MonkeyPatch) -> _FakeSubmissionStore:
    """Keep every test off the real database; tests can inspect the stored rows."""
    store = _FakeSubmissionStore()
    monkeypatch.setattr(contact, "_open_session", store.session)
    return store


def _capturing_client(captured: dict[str, Any], status_code: int = 201, issue_number: int = 451):
    class _FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url: str, json: dict[str, Any], headers: dict[str, str], timeout: float):
            captured["json"] = json
            req = httpx.Request("POST", url)
            if status_code != 201:
                return httpx.Response(status_code, text="upstream error", request=req)
            return httpx.Response(
                201,
                json={
                    "number": issue_number,
                    "html_url": f"https://github.com/getcommunityone/open-navigator/issues/{issue_number}",
                },
                request=req,
            )

    return _FakeAsyncClient


def _private_request() -> "contact.ContactRequest":
    return contact.ContactRequest(
        name="Dana",
        email="Dana.Private@Example.org",
        subject="Budget page question",
        message="Where does the county budget data on the money page come from?",
        category="question",
    )


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


def test_parse_signed_request_rejects_missing_algorithm():
    secret = "test_fb_app_secret_123"
    no_alg = _make_signed_request({"user_id": "12345"}, secret)
    with pytest.raises(HTTPException) as exc:
        data_deletion.parse_signed_request(no_alg, secret)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "server_error"])
async def test_contact_submit_failed_upstream_can_be_retried_immediately(
    monkeypatch: pytest.MonkeyPatch, failure: str
):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token_123")
    calls = {"n": 0}

    class _FlakyAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url: str, json: dict[str, Any], headers: dict[str, str], timeout: float):
            calls["n"] += 1
            req = httpx.Request("POST", url)
            if calls["n"] == 1:
                if failure == "timeout":
                    raise httpx.TimeoutException("timed out", request=req)
                return httpx.Response(502, text="bad gateway", request=req)
            return httpx.Response(201, json={"html_url": "https://github.com/example/issues/2"}, request=req)

    monkeypatch.setattr(contact.httpx, "AsyncClient", _FlakyAsyncClient)

    req_model = contact.ContactRequest(
        name="Carol",
        email="carol@example.com",
        subject="Retry after failure",
        message="This message failed upstream the first time and is retried.",
        category="feedback",
    )

    with pytest.raises(HTTPException) as exc_first:
        await contact.submit_contact(req_model)
    assert exc_first.value.status_code in (500, 504)

    # The identical retry must reach GitHub, not be rejected as a duplicate.
    resp = await contact.submit_contact(req_model)
    assert resp.success is True
    assert calls["n"] == 2

    # Once it has succeeded, the same message is a duplicate again.
    with pytest.raises(HTTPException) as exc_dup:
        await contact.submit_contact(req_model)
    assert exc_dup.value.status_code == 429


@pytest.mark.asyncio
async def test_contact_issue_body_has_no_email_and_row_keeps_it(
    monkeypatch: pytest.MonkeyPatch, submission_store: _FakeSubmissionStore
):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token_123")
    captured: dict[str, Any] = {}
    monkeypatch.setattr(contact.httpx, "AsyncClient", _capturing_client(captured, issue_number=451))

    req_model = _private_request()
    resp = await contact.submit_contact(req_model)

    assert resp.success is True
    body = captured["json"]["body"]
    title = captured["json"]["title"]
    for text in (body, title):
        assert str(req_model.email).lower() not in text.lower()
        assert "@" not in text
    assert "Reply address kept privately (submission `#1`)" in body

    row = submission_store.rows[1]
    assert row.sender_email == str(req_model.email)
    assert row.sender_name == "Dana"
    assert row.subject == "Budget page question"
    assert row.github_issue_number == 451
    assert row.github_issue_url == "https://github.com/getcommunityone/open-navigator/issues/451"


@pytest.mark.asyncio
async def test_contact_db_failure_still_creates_email_free_issue(
    monkeypatch: pytest.MonkeyPatch, submission_store: _FakeSubmissionStore
):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token_123")
    submission_store.fail = True
    captured: dict[str, Any] = {}
    monkeypatch.setattr(contact.httpx, "AsyncClient", _capturing_client(captured))

    messages: list[str] = []
    sink_id = contact.logger.add(lambda m: messages.append(str(m)), level="DEBUG")
    try:
        req_model = _private_request()
        resp = await contact.submit_contact(req_model)
    finally:
        contact.logger.remove(sink_id)

    assert resp.success is True
    body = captured["json"]["body"]
    assert str(req_model.email).lower() not in body.lower()
    assert "@" not in body
    assert "Reply address not kept" in body
    assert messages, "expected a warning about the unavailable store"
    assert all(str(req_model.email).lower() not in m.lower() for m in messages)


@pytest.mark.asyncio
async def test_contact_failed_issue_discards_stored_email(
    monkeypatch: pytest.MonkeyPatch, submission_store: _FakeSubmissionStore
):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token_123")
    captured: dict[str, Any] = {}
    monkeypatch.setattr(contact.httpx, "AsyncClient", _capturing_client(captured, status_code=502))

    with pytest.raises(HTTPException):
        await contact.submit_contact(_private_request())
    assert submission_store.rows == {}


@pytest.mark.asyncio
async def test_facebook_data_deletion_log_has_no_email(monkeypatch: pytest.MonkeyPatch):
    secret = "fb_secret_key"
    monkeypatch.setenv("FACEBOOK_APP_SECRET", secret)
    sr = _make_signed_request({"algorithm": "HMAC-SHA256", "user_id": "fb_user_77"}, secret)

    email = "erase.me@example.com"
    messages: list[str] = []
    sink_id = data_deletion.logger.add(lambda m: messages.append(str(m)), level="DEBUG")
    try:
        for db in (
            _FakeSession(user=SimpleNamespace(user_id=7, email=email, oauth_provider="facebook")),
            _FakeSession(
                user=SimpleNamespace(user_id=7, email=email, oauth_provider="facebook"),
                fail_commit=True,
            ),
        ):
            try:
                await data_deletion.facebook_data_deletion_callback(
                    _build_json_request({"signed_request": sr}), db=db
                )
            except HTTPException:
                pass
    finally:
        data_deletion.logger.remove(sink_id)

    joined = "\n".join(messages)
    assert "Deleting user account: user_id=7 (Facebook ID: fb_user_77)" in joined
    assert email not in joined
    assert "@" not in joined
