"""
Database models for authentication, user management, and social features
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Index, text
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


class Official(Base):
    """Public officials (elected, appointed) - renamed from Leader to match OpenStates"""
    __tablename__ = "contact_official"
    
    id = Column(Integer, primary_key=True, index=True)
    ocd_person_id = Column(String(255), unique=True, index=True, nullable=True)  # OpenCivicData ID
    name = Column(String(255), nullable=False, index=True)
    slug = Column(String(255), unique=True, index=True, nullable=False)
    family_name = Column(String(100), nullable=True)
    given_name = Column(String(100), nullable=True)
    sort_name = Column(String(255), nullable=True)
    
    # Bio and presentation
    title = Column(String(255), nullable=True)  # 'Mayor', 'State Senator', 'City Council Member'
    bio = Column(Text, nullable=True)
    photo_url = Column(String(500), nullable=True)
    gender = Column(String(20), nullable=True)
    birth_date = Column(DateTime, nullable=True)
    
    # Current role (primary position)
    position_type = Column(String(100), nullable=True)  # 'elected', 'appointed'
    office = Column(String(255), nullable=True)  # 'Office of the Mayor', 'State Senate District 12'
    party = Column(String(100), nullable=True)  # 'Democratic', 'Republican', 'Independent'
    chamber = Column(String(50), nullable=True)  # 'upper', 'lower', 'executive'
    district = Column(String(50), nullable=True)  # District number or name
    
    # Location/Jurisdiction
    state = Column(String(100), nullable=True)
    county = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    jurisdiction = Column(String(255), nullable=True)
    
    # Contact
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    website = Column(String(500), nullable=True)
    
    # Social media
    twitter = Column(String(255), nullable=True)
    linkedin = Column(String(255), nullable=True)
    facebook = Column(String(255), nullable=True)
    
    # Social stats
    follower_count = Column(Integer, default=0)
    
    # Verification
    is_verified = Column(Boolean, default=False)
    verified_at = Column(DateTime, nullable=True)
    
    # Term dates
    term_start_date = Column(DateTime, nullable=True)
    term_end_date = Column(DateTime, nullable=True)
    is_current = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Official {self.name}>"


# ============================================================================
# FOLLOW RELATIONSHIPS (Many-to-Many)
# ============================================================================

class SocialFollow(Base):
    """A user following another entity (user, official, organization, or tag).

    Consolidates the former user_follows / contact_official_follows /
    organization_follows / cause_follows tables into one polymorphic table.
    ``follower_id`` is always the acting user; ``target_type`` + the matching
    target key identify what is being followed.

    Two target-key columns coexist because targets are keyed differently:
      - integer-keyed targets ('user', 'official') use ``target_id``.
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

    # Allowed target_type values. target_id keys user/official; target_uid keys
    # organization (mdm_organization.master_org_id) and tag (tag.tag_id).
    TARGET_TYPES = ("user", "official", "organization", "tag")
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

