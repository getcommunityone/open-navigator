"""
Social features API routes - following, followers, feeds
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, text
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from api.database import get_db
from api.auth import get_current_user
from api.models import (
    User, Official, Cause, SocialFollow
)

router = APIRouter(prefix="/social", tags=["social"])


def _follower_count(db: Session, target_type: str, target_id: int) -> int:
    """Count followers of an integer-keyed entity (user / official / cause)."""
    return db.query(SocialFollow).filter(
        SocialFollow.target_type == target_type,
        SocialFollow.target_id == target_id,
    ).count()


def _get_follow(db: Session, follower_id: int, target_type: str, target_id: int):
    """Return the existing follow row for an integer-keyed (follower, target)."""
    return db.query(SocialFollow).filter(
        SocialFollow.follower_id == follower_id,
        SocialFollow.target_type == target_type,
        SocialFollow.target_id == target_id,
    ).first()


def _follower_count_uid(db: Session, target_type: str, target_uid: str) -> int:
    """Count followers of a text-keyed entity (organization -> master_org_id)."""
    return db.query(SocialFollow).filter(
        SocialFollow.target_type == target_type,
        SocialFollow.target_uid == target_uid,
    ).count()


def _get_follow_uid(db: Session, follower_id: int, target_type: str, target_uid: str):
    """Return the existing follow row for a text-keyed (follower, target)."""
    return db.query(SocialFollow).filter(
        SocialFollow.follower_id == follower_id,
        SocialFollow.target_type == target_type,
        SocialFollow.target_uid == target_uid,
    ).first()


def _mdm_org(db: Session, master_org_id: str):
    """Look up a golden org in the mdm_organization mart (not an ORM table)."""
    return db.execute(
        text("""
            SELECT master_org_id, org_name, org_type, city_norm, state_code
            FROM mdm_organization
            WHERE master_org_id = :mid
        """),
        {"mid": master_org_id},
    ).mappings().first()


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class FollowResponse(BaseModel):
    """Response after follow/unfollow action"""
    success: bool
    following: bool
    follower_count: int
    message: str


class FollowerStats(BaseModel):
    """Follower/following statistics"""
    followers: int
    following: int
    following_users: int
    following_officials: int
    following_organizations: int
    following_causes: int


class UserSummary(BaseModel):
    """Brief user info for lists"""
    user_id: int
    username: Optional[str]
    full_name: Optional[str]
    avatar_url: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class OfficialSummary(BaseModel):
    """Brief official info for lists"""
    id: int
    name: str
    slug: str
    title: Optional[str]
    photo_url: Optional[str]
    office: Optional[str]
    city: Optional[str]
    state: Optional[str]
    follower_count: int
    is_verified: bool
    
    class Config:
        from_attributes = True


class OrganizationSummary(BaseModel):
    """Brief organization info for lists (served from mdm_organization).

    Identity is the text master_org_id. Fields not carried by the golden record
    (logo_url, description, is_verified) degrade to None/False; follower_count is
    derived from social_follows.
    """
    master_org_id: str
    name: Optional[str]
    org_type: Optional[str]
    city: Optional[str]
    state: Optional[str]
    follower_count: int
    logo_url: Optional[str] = None
    description: Optional[str] = None
    is_verified: bool = False


class CauseSummary(BaseModel):
    """Brief cause info for lists"""
    id: int
    name: str
    slug: str
    description: Optional[str]
    icon_url: Optional[str]
    color: Optional[str]
    category: Optional[str]
    follower_count: int
    
    class Config:
        from_attributes = True


# ============================================================================
# FOLLOW/UNFOLLOW ACTIONS
# ============================================================================

@router.post("/follow/user/{user_id}")
async def follow_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> FollowResponse:
    """Follow another user"""
    
    if current_user.user_id == user_id:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")
    
    # Check if target user exists
    target_user = db.query(User).filter(User.user_id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if already following
    existing = _get_follow(db, current_user.user_id, "user", user_id)

    if existing:
        return FollowResponse(
            success=True,
            following=True,
            follower_count=_follower_count(db, "user", user_id),
            message="Already following this user"
        )

    # Create follow
    follow = SocialFollow(follower_id=current_user.user_id, target_type="user", target_id=user_id)
    db.add(follow)
    db.commit()

    return FollowResponse(
        success=True,
        following=True,
        follower_count=_follower_count(db, "user", user_id),
        message="Successfully followed user"
    )


@router.delete("/follow/user/{user_id}")
async def unfollow_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> FollowResponse:
    """Unfollow a user"""
    
    follow = _get_follow(db, current_user.user_id, "user", user_id)

    if not follow:
        return FollowResponse(
            success=True,
            following=False,
            follower_count=_follower_count(db, "user", user_id),
            message="Not following this user"
        )

    db.delete(follow)
    db.commit()

    return FollowResponse(
        success=True,
        following=False,
        follower_count=_follower_count(db, "user", user_id),
        message="Successfully unfollowed user"
    )


@router.post("/follow/official/{official_id}")
async def follow_official(
    official_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> FollowResponse:
    """Follow an official"""
    
    # Check if official exists
    official = db.query(Official).filter(Official.id == official_id).first()
    if not official:
        raise HTTPException(status_code=404, detail="Official not found")
    
    # Check if already following
    existing = _get_follow(db, current_user.user_id, "official", official_id)

    if existing:
        return FollowResponse(
            success=True,
            following=True,
            follower_count=official.follower_count,
            message="Already following this official"
        )

    # Create follow
    follow = SocialFollow(follower_id=current_user.user_id, target_type="official", target_id=official_id)
    db.add(follow)
    
    # Update follower count
    official.follower_count += 1
    db.commit()
    
    return FollowResponse(
        success=True,
        following=True,
        follower_count=official.follower_count,
        message="Successfully followed official"
    )


@router.delete("/follow/official/{official_id}")
async def unfollow_official(
    official_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> FollowResponse:
    """Unfollow an official"""
    
    official = db.query(Official).filter(Official.id == official_id).first()
    if not official:
        raise HTTPException(status_code=404, detail="Official not found")
    
    follow = _get_follow(db, current_user.user_id, "official", official_id)

    if not follow:
        return FollowResponse(
            success=True,
            following=False,
            follower_count=official.follower_count,
            message="Not following this official"
        )
    
    db.delete(follow)
    official.follower_count = max(0, official.follower_count - 1)
    db.commit()
    
    return FollowResponse(
        success=True,
        following=False,
        follower_count=official.follower_count,
        message="Successfully unfollowed official"
    )


@router.post("/follow/organization/{org_id}")
async def follow_organization(
    org_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> FollowResponse:
    """Follow an organization (keyed by mdm_organization.master_org_id)."""

    org = _mdm_org(db, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    existing = _get_follow_uid(db, current_user.user_id, "organization", org_id)
    if existing:
        return FollowResponse(
            success=True,
            following=True,
            follower_count=_follower_count_uid(db, "organization", org_id),
            message="Already following this organization"
        )

    db.add(SocialFollow(follower_id=current_user.user_id, target_type="organization", target_uid=org_id))
    db.commit()

    return FollowResponse(
        success=True,
        following=True,
        follower_count=_follower_count_uid(db, "organization", org_id),
        message="Successfully followed organization"
    )


@router.delete("/follow/organization/{org_id}")
async def unfollow_organization(
    org_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> FollowResponse:
    """Unfollow an organization (keyed by mdm_organization.master_org_id)."""

    org = _mdm_org(db, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    follow = _get_follow_uid(db, current_user.user_id, "organization", org_id)
    if not follow:
        return FollowResponse(
            success=True,
            following=False,
            follower_count=_follower_count_uid(db, "organization", org_id),
            message="Not following this organization"
        )

    db.delete(follow)
    db.commit()

    return FollowResponse(
        success=True,
        following=False,
        follower_count=_follower_count_uid(db, "organization", org_id),
        message="Successfully unfollowed organization"
    )


@router.post("/follow/cause/{cause_id}")
async def follow_cause(
    cause_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> FollowResponse:
    """Follow a cause/topic"""
    
    cause = db.query(Cause).filter(Cause.id == cause_id).first()
    if not cause:
        raise HTTPException(status_code=404, detail="Cause not found")
    
    existing = _get_follow(db, current_user.user_id, "cause", cause_id)

    if existing:
        return FollowResponse(
            success=True,
            following=True,
            follower_count=cause.follower_count,
            message="Already following this cause"
        )

    follow = SocialFollow(follower_id=current_user.user_id, target_type="cause", target_id=cause_id)
    db.add(follow)
    cause.follower_count += 1
    db.commit()
    
    return FollowResponse(
        success=True,
        following=True,
        follower_count=cause.follower_count,
        message="Successfully followed cause"
    )


@router.delete("/follow/cause/{cause_id}")
async def unfollow_cause(
    cause_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> FollowResponse:
    """Unfollow a cause/topic"""
    
    cause = db.query(Cause).filter(Cause.id == cause_id).first()
    if not cause:
        raise HTTPException(status_code=404, detail="Cause not found")
    
    follow = _get_follow(db, current_user.user_id, "cause", cause_id)

    if not follow:
        return FollowResponse(
            success=True,
            following=False,
            follower_count=cause.follower_count,
            message="Not following this cause"
        )
    
    db.delete(follow)
    cause.follower_count = max(0, cause.follower_count - 1)
    db.commit()
    
    return FollowResponse(
        success=True,
        following=False,
        follower_count=cause.follower_count,
        message="Successfully unfollowed cause"
    )


# ============================================================================
# CHECK FOLLOW STATUS
# ============================================================================

@router.get("/following/status")
async def check_following_status(
    user_id: Optional[int] = None,
    leader_id: Optional[int] = None,
    org_id: Optional[str] = None,
    cause_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict:
    """Check if current user is following various entities"""

    result = {}

    if user_id:
        result['user'] = _get_follow(db, current_user.user_id, "user", user_id) is not None

    if leader_id:
        result['official'] = _get_follow(db, current_user.user_id, "official", leader_id) is not None

    if org_id:
        # Organizations are keyed by mdm_organization.master_org_id (text).
        result['organization'] = _get_follow_uid(db, current_user.user_id, "organization", org_id) is not None

    if cause_id:
        result['cause'] = _get_follow(db, current_user.user_id, "cause", cause_id) is not None

    return result


# ============================================================================
# FOLLOWER/FOLLOWING LISTS
# ============================================================================

@router.get("/stats")
async def get_follower_stats(
    user_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> FollowerStats:
    """Get follower/following statistics for a user"""
    
    target_id = user_id if user_id else current_user.user_id
    
    # Count followers (people following this user)
    followers = _follower_count(db, "user", target_id)

    # Count following (entities this person follows), grouped by target_type
    def _following(target_type: str) -> int:
        return db.query(SocialFollow).filter(
            SocialFollow.follower_id == target_id,
            SocialFollow.target_type == target_type,
        ).count()

    following_users = _following("user")
    following_officials = _following("official")
    following_orgs = _following("organization")
    following_causes = _following("cause")
    
    total_following = following_users + following_officials + following_orgs + following_causes
    
    return FollowerStats(
        followers=followers,
        following=total_following,
        following_users=following_users,
        following_officials=following_officials,
        following_organizations=following_orgs,
        following_causes=following_causes
    )


@router.get("/following/officials")
async def get_following_officials(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[OfficialSummary]:
    """Get list of officials the current user is following"""
    
    officials = db.query(Official).join(
        SocialFollow,
        and_(
            SocialFollow.target_type == "official",
            SocialFollow.target_id == Official.id,
        )
    ).filter(
        SocialFollow.follower_id == current_user.user_id
    ).all()
    
    return [OfficialSummary.from_orm(official) for official in officials]


@router.get("/following/organizations")
async def get_following_organizations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[OrganizationSummary]:
    """Get list of organizations the current user is following.

    Orgs live in the mdm_organization mart (not the ORM); join via the follow's
    text target_uid. follower_count is derived per org from social_follows.
    """
    rows = db.execute(
        text("""
            SELECT
                m.master_org_id,
                m.org_name,
                m.org_type,
                m.city_norm,
                m.state_code,
                (
                    SELECT count(*) FROM social_follows f2
                    WHERE f2.target_type = 'organization'
                      AND f2.target_uid = m.master_org_id
                ) AS follower_count
            FROM social_follows f
            JOIN mdm_organization m ON m.master_org_id = f.target_uid
            WHERE f.follower_id = :uid AND f.target_type = 'organization'
            ORDER BY m.org_name
        """),
        {"uid": current_user.user_id},
    ).mappings().all()

    return [
        OrganizationSummary(
            master_org_id=r["master_org_id"],
            name=r["org_name"],
            org_type=r["org_type"],
            city=r["city_norm"],
            state=r["state_code"],
            follower_count=r["follower_count"],
        )
        for r in rows
    ]


@router.get("/following/causes")
async def get_following_causes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[CauseSummary]:
    """Get list of causes the current user is following"""
    
    causes = db.query(Cause).join(
        SocialFollow,
        and_(
            SocialFollow.target_type == "cause",
            SocialFollow.target_id == Cause.id,
        )
    ).filter(
        SocialFollow.follower_id == current_user.user_id
    ).all()
    
    return [CauseSummary.from_orm(cause) for cause in causes]
