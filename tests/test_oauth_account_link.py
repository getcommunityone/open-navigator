"""Tests for the OAuth account-linking safety gate (get_or_create_user).

Guards against email-confusion account takeover: an OAuth login must not merge
into a pre-existing account (matched only by email) unless the provider attests
the email is verified. The (provider, oauth_id) match path is always safe.
"""
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.models import Base
from api.routes.auth import get_or_create_user


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def test_new_user_created_even_if_unverified(db):
    # No existing account with this email → creation is fine regardless of
    # verification (there is nothing to take over).
    user = get_or_create_user(
        db, email="new@x.com", provider="google", oauth_id="g1", email_verified=False
    )
    assert user.user_id is not None
    assert user.email == "new@x.com"


def test_same_identity_relogin_needs_no_verification(db):
    get_or_create_user(
        db, email="a@x.com", provider="google", oauth_id="g1", email_verified=True
    )
    # Same (provider, oauth_id) → matched by stable provider id, not email.
    again = get_or_create_user(
        db, email="a@x.com", provider="google", oauth_id="g1", email_verified=False
    )
    assert again.oauth_id == "g1"


def test_unverified_cross_provider_link_refused(db):
    get_or_create_user(
        db, email="v@x.com", provider="google", oauth_id="g1", email_verified=True
    )
    # Different provider claims the same email without verification → refuse.
    with pytest.raises(HTTPException) as excinfo:
        get_or_create_user(
            db,
            email="v@x.com",
            provider="facebook",
            oauth_id="f9",
            email_verified=False,
        )
    assert excinfo.value.status_code == 409


def test_verified_cross_provider_link_allowed(db):
    get_or_create_user(
        db, email="v@x.com", provider="google", oauth_id="g1", email_verified=True
    )
    linked = get_or_create_user(
        db, email="v@x.com", provider="github", oauth_id="h2", email_verified=True
    )
    assert linked.oauth_provider == "github"
    assert linked.oauth_id == "h2"
