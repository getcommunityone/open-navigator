"""
Social features API routes - following, followers, feeds
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from api.database import get_db
from api.auth import get_current_user
from api.models import (
    User, Official, Organization, Cause,
    UserFollow, OfficialFollow, OrganizationFollow, CauseFollow
)

router = APIRouter(prefix="/social", tags=["social"])


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
    """Brief organization info for lists"""
    id: int
    name: str
    slug: str
    description: Optional[str]
    logo_url: Optional[str]
    org_type: Optional[str]
    city: Optional[str]
    state: Optional[str]
    follower_count: int
    is_verified: bool
    
    class Config:
        from_attributes = True


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
    existing = db.query(UserFollow).filter(
        UserFollow.follower_id == current_user.user_id,
        UserFollow.following_id == user_id
    ).first()
    
    if existing:
        return FollowResponse(
            success=True,
            following=True,
            follower_count=db.query(UserFollow).filter(UserFollow.following_id == user_id).count(),
            message="Already following this user"
        )
    
    # Create follow
    follow = UserFollow(follower_id=current_user.user_id, following_id=user_id)
    db.add(follow)
    db.commit()
    
    follower_count = db.query(UserFollow).filter(UserFollow.following_id == user_id).count()
    
    return FollowResponse(
        success=True,
        following=True,
        follower_count=follower_count,
        message="Successfully followed user"
    )


@router.delete("/follow/user/{user_id}")
async def unfollow_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> FollowResponse:
    """Unfollow a user"""
    
    follow = db.query(UserFollow).filter(
        UserFollow.follower_id == current_user.user_id,
        UserFollow.following_id == user_id
    ).first()
    
    if not follow:
        return FollowResponse(
            success=True,
            following=False,
            follower_count=db.query(UserFollow).filter(UserFollow.following_id == user_id).count(),
            message="Not following this user"
        )
    
    db.delete(follow)
    db.commit()
    
    follower_count = db.query(UserFollow).filter(UserFollow.following_id == user_id).count()
    
    return FollowResponse(
        success=True,
        following=False,
        follower_count=follower_count,
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
    existing = db.query(OfficialFollow).filter(
        OfficialFollow.user_id == current_user.user_id,
        OfficialFollow.official_id == official_id
    ).first()
    
    if existing:
        return FollowResponse(
            success=True,
            following=True,
            follower_count=official.follower_count,
            message="Already following this official"
        )
    
    # Create follow
    follow = OfficialFollow(user_id=current_user.user_id, official_id=official_id)
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
    
    follow = db.query(OfficialFollow).filter(
        OfficialFollow.user_id == current_user.user_id,
        OfficialFollow.official_id == official_id
    ).first()
    
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
    org_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> FollowResponse:
    """Follow an organization"""
    
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    existing = db.query(OrganizationFollow).filter(
        OrganizationFollow.user_id == current_user.user_id,
        OrganizationFollow.organization_id == org_id
    ).first()
    
    if existing:
        return FollowResponse(
            success=True,
            following=True,
            follower_count=org.follower_count,
            message="Already following this organization"
        )
    
    follow = OrganizationFollow(user_id=current_user.user_id, organization_id=org_id)
    db.add(follow)
    org.follower_count += 1
    db.commit()
    
    return FollowResponse(
        success=True,
        following=True,
        follower_count=org.follower_count,
        message="Successfully followed organization"
    )


@router.delete("/follow/organization/{org_id}")
async def unfollow_organization(
    org_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> FollowResponse:
    """Unfollow an organization"""
    
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    follow = db.query(OrganizationFollow).filter(
        OrganizationFollow.user_id == current_user.user_id,
        OrganizationFollow.organization_id == org_id
    ).first()
    
    if not follow:
        return FollowResponse(
            success=True,
            following=False,
            follower_count=org.follower_count,
            message="Not following this organization"
        )
    
    db.delete(follow)
    org.follower_count = max(0, org.follower_count - 1)
    db.commit()
    
    return FollowResponse(
        success=True,
        following=False,
        follower_count=org.follower_count,
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
    
    existing = db.query(CauseFollow).filter(
        CauseFollow.user_id == current_user.user_id,
        CauseFollow.cause_id == cause_id
    ).first()
    
    if existing:
        return FollowResponse(
            success=True,
            following=True,
            follower_count=cause.follower_count,
            message="Already following this cause"
        )
    
    follow = CauseFollow(user_id=current_user.user_id, cause_id=cause_id)
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
    
    follow = db.query(CauseFollow).filter(
        CauseFollow.user_id == current_user.user_id,
        CauseFollow.cause_id == cause_id
    ).first()
    
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
    org_id: Optional[int] = None,
    cause_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict:
    """Check if current user is following various entities"""
    
    result = {}
    
    if user_id:
        result['user'] = db.query(UserFollow).filter(
            UserFollow.follower_id == current_user.user_id,
            UserFollow.following_id == user_id
        ).first() is not None
    
    if leader_id:
        result['official'] = db.query(OfficialFollow).filter(
            OfficialFollow.user_id == current_user.user_id,
            OfficialFollow.official_id == leader_id
        ).first() is not None
    
    if org_id:
        result['organization'] = db.query(OrganizationFollow).filter(
            OrganizationFollow.user_id == current_user.user_id,
            OrganizationFollow.organization_id == org_id
        ).first() is not None
    
    if cause_id:
        result['cause'] = db.query(CauseFollow).filter(
            CauseFollow.user_id == current_user.user_id,
            CauseFollow.cause_id == cause_id
        ).first() is not None
    
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
    followers = db.query(UserFollow).filter(UserFollow.following_id == target_id).count()
    
    # Count following (users this person follows)
    following_users = db.query(UserFollow).filter(UserFollow.follower_id == target_id).count()
    following_officials = db.query(OfficialFollow).filter(OfficialFollow.user_id == target_id).count()
    following_orgs = db.query(OrganizationFollow).filter(OrganizationFollow.user_id == target_id).count()
    following_causes = db.query(CauseFollow).filter(CauseFollow.user_id == target_id).count()
    
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
        OfficialFollow,
        OfficialFollow.official_id == Official.id
    ).filter(
        OfficialFollow.user_id == current_user.user_id
    ).all()
    
    return [OfficialSummary.from_orm(official) for official in officials]


@router.get("/following/organizations")
async def get_following_organizations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[OrganizationSummary]:
    """Get list of organizations the current user is following"""
    
    orgs = db.query(Organization).join(
        OrganizationFollow,
        OrganizationFollow.organization_id == Organization.id
    ).filter(
        OrganizationFollow.user_id == current_user.user_id
    ).all()
    
    return [OrganizationSummary.from_orm(org) for org in orgs]


@router.get("/following/causes")
async def get_following_causes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[CauseSummary]:
    """Get list of causes the current user is following"""
    
    causes = db.query(Cause).join(
        CauseFollow,
        CauseFollow.cause_id == Cause.id
    ).filter(
        CauseFollow.user_id == current_user.user_id
    ).all()
    
    return [CauseSummary.from_orm(cause) for cause in causes]
