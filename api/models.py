"""
Database models for authentication, user management, and social features
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, ForeignKey, Index, text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class User(Base):
    """User account model"""
    __tablename__ = "user"

    user_id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=True)
    full_name = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    
    # OAuth provider info
    oauth_provider = Column(String(50), nullable=True)  # 'huggingface', 'google', 'facebook', 'github'
    oauth_id = Column(String(255), nullable=True)  # Provider-specific user ID
    
    # Authentication
    hashed_password = Column(String(255), nullable=True)  # For email/password (optional)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # Location preferences
    state = Column(String(100), nullable=True)  # US State
    county = Column(String(100), nullable=True)  # County
    city = Column(String(100), nullable=True)  # City
    school_board = Column(String(255), nullable=True)  # School board/district
    
    # Profile completion
    profile_completed = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # User preferences (JSON stored as text)
    preferences = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<User {self.email}>"


class OAuthState(Base):
    """Temporary storage for OAuth state tokens (CSRF protection)"""
    __tablename__ = "contact_oauth_state"
    
    id = Column(Integer, primary_key=True, index=True)
    state_token = Column(String(255), unique=True, index=True, nullable=False)
    provider = Column(String(50), nullable=False)
    redirect_uri = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    
    def __repr__(self):
        return f"<OAuthState {self.provider} - {self.state_token[:8]}...>"


# ============================================================================
# SOCIAL FEATURES MODELS
# ============================================================================

# NOTE: the integer-keyed `organization` ORM entity was folded into the MDM
# golden record `mdm_organization` (a dbt mart, PK master_org_id — not an ORM
# table). Organizations are now followed by their text master_org_id via
# SocialFollow.target_uid; see api/routes/social.py and migration 093.


# NOTE: the integer-keyed `cause` ORM entity was retired in favour of the dbt tag
# taxonomy (a mart, PK tag_id text -- not an ORM table). Causes/topics are now
# followed by their text tag_id via SocialFollow.target_uid, exactly like
# organizations; see api/routes/social.py and migration 099.


# NOTE: the `Official` ORM entity (table contact_official) was retired by
# migration 052, which dropped the empty table. Officials data lives in per-state
# parquet gold files (data/gold/states/<ST>/contact_official.parquet), read directly
# by api/routes/search.py — never as a queryable table. The follow-an-official
# feature that depended on this model was orphaned (the frontend never called its
# routes) and was removed alongside it; see api/routes/social.py.


# ============================================================================
# FOLLOW RELATIONSHIPS (Many-to-Many)
# ============================================================================

class SocialFollow(Base):
    """A user following another entity (user, organization, or tag).

    Consolidates the former user_follows / contact_official_follows /
    organization_follows / cause_follows tables into one polymorphic table.
    ``follower_id`` is always the acting user; ``target_type`` + the matching
    target key identify what is being followed.

    Two target-key columns coexist because targets are keyed differently:
      - integer-keyed targets ('user') use ``target_id``.
      - text-keyed targets use ``target_uid``: 'organization' =
        mdm_organization.master_org_id, 'tag' = tag.tag_id.
    Exactly one of the two is set per row; uniqueness is enforced by the two
    partial indexes below.
    """
    __tablename__ = "social_follows"
    __table_args__ = (
        Index('uq_social_follow_intid', 'follower_id', 'target_type', 'target_id',
              unique=True, postgresql_where=text('target_uid IS NULL')),
        Index('uq_social_follow_uid', 'follower_id', 'target_type', 'target_uid',
              unique=True, postgresql_where=text('target_uid IS NOT NULL')),
    )

    # Allowed target_type values. target_id keys user; target_uid keys
    # organization (mdm_organization.master_org_id) and tag (tag.tag_id).
    TARGET_TYPES = ("user", "organization", "tag")
    UID_TARGET_TYPES = ("organization", "tag")

    id = Column(Integer, primary_key=True, index=True)
    follower_id = Column(Integer, ForeignKey('user.user_id', ondelete='CASCADE'), nullable=False, index=True)
    target_type = Column(String, nullable=False, index=True)
    target_id = Column(Integer, nullable=True, index=True)
    target_uid = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        key = self.target_uid if self.target_uid is not None else self.target_id
        return f"<SocialFollow user:{self.follower_id} -> {self.target_type}:{key}>"


# ============================================================================
# FEED PERSONALIZATION MODELS
# ============================================================================
# Operational user-preference tables for the feed-setup screen. Like User /
# SocialFollow these are ORM-managed public-schema tables (NOT dbt marts),
# auto-created by Base.metadata.create_all in api/database.py at startup. All
# three cascade-delete with their owning user.


class UserLocation(Base):
    """A location a user follows in their feed, at a chosen `shared_level`.

    `name` is the human label (e.g. "Tuscaloosa, AL"); the resolved geo columns
    are filled in from the place typeahead selection (all nullable). One row per
    location; `is_primary` marks the one synced into User.city/county/state.
    """
    __tablename__ = "user_locations"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id = Column(Integer, ForeignKey('user.user_id', ondelete='CASCADE'), nullable=False, index=True)
    name = Column(String(255), nullable=False)  # e.g. "Tuscaloosa, AL"
    # One of street | district | city | county | state
    shared_level = Column(String(20), nullable=False, default='city')
    is_primary = Column(Boolean, default=False)

    # Resolved geo (all nullable — filled from the typeahead selection)
    state_code = Column(String(2), nullable=True)
    state = Column(String(100), nullable=True)
    county = Column(String(100), nullable=True)
    place_fips = Column(String(10), nullable=True)
    county_fips = Column(String(10), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    jurisdiction_id = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<UserLocation user:{self.user_id} {self.name} ({self.shared_level})>"


class UserLensPref(Base):
    """A topical lens a user has enabled for their feed (composite PK)."""
    __tablename__ = "user_lens_prefs"

    user_id = Column(Integer, ForeignKey('user.user_id', ondelete='CASCADE'), primary_key=True)
    lens_slug = Column(String(50), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<UserLensPref user:{self.user_id} {self.lens_slug}>"


class UserSignalPref(Base):
    """A story signal a user has enabled for their feed (composite PK)."""
    __tablename__ = "user_signal_prefs"

    user_id = Column(Integer, ForeignKey('user.user_id', ondelete='CASCADE'), primary_key=True)
    signal_slug = Column(String(50), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<UserSignalPref user:{self.user_id} {self.signal_slug}>"

