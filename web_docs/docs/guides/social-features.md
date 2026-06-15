---
title: Social Features
---

# Social Features - LinkedIn/Facebook Style Following

## Overview

The platform now includes comprehensive social networking features inspired by LinkedIn and Facebook, allowing users to follow and engage with:

1. **Leaders** - Elected officials, decision makers, community advocates
2. **Organizations** - Nonprofits, charities, government agencies
3. **Causes** - Policy topics and issues (oral health, housing, education, etc.)
4. **Other Users** - Fellow community members and advocates

---

## 🎯 Features

### Follow System
- ✅ One-click follow/unfollow buttons (LinkedIn/Facebook style)
- ✅ Hover effects ("Following" → "Unfollow")
- ✅ Real-time follower counts
- ✅ Optimistic UI updates
- ✅ Persistent follow state across sessions

### Profile Page
- ✅ User profile with avatar, bio, location
- ✅ Follower/following statistics
- ✅ Tabbed interface showing:
  - Leaders you're following
  - Charities you're following
  - Causes you care about
- ✅ Breakdown by category (e.g., "Following 5 leaders, 3 charities, 2 causes")

### Social Stats Component
- ✅ Displays follower/following counts
- ✅ Shows breakdown of what user follows
- ✅ Clickable to view full lists
- ✅ LinkedIn-style presentation

---

## 📊 Database Schema

### New Tables

#### `leaders`
Public officials and decision makers
- `id` - Primary key
- `name`, `slug` - Identity
- `title`, `office` - Position details
- `city`, `state`, `jurisdiction` - Location
- `email`, `phone`, `website` - Contact
- `twitter`, `linkedin`, `facebook` - Social media
- `follower_count` - Denormalized count
- `is_verified` - Verification badge

#### `organizations`
Nonprofits, charities, advocacy groups
- `id` - Primary key
- `name`, `slug` - Identity
- `description`, `logo_url` - Branding
- `org_type` - 'nonprofit', 'government', 'advocacy', 'charity'
- `city`, `state`, `address` - Location
- `ein`, `ntee_code`, `revenue` - IRS data
- `follower_count` - Denormalized count
- `is_verified` - Verification badge

#### `causes`
Policy topics and issues
- `id` - Primary key
- `name`, `slug` - Identity
- `description`, `icon_url`, `color` - Visual identity
- `category` - 'health', 'education', 'housing', 'environment', etc.
- `follower_count` - Denormalized count

#### Follow Relationship Tables
All use composite unique constraints to prevent duplicate follows:

- `user_follows` - User → User relationships
- `leader_follows` - User → Leader relationships
- `organization_follows` - User → Organization relationships
- `cause_follows` - User → Cause relationships

Each contains:
- `user_id` - Foreign key to users
- `{entity}_id` - Foreign key to entity
- `created_at` - Timestamp

---

## 🔌 API Endpoints

### Follow Actions

```http
POST   /api/social/follow/user/{user_id}         # Follow a user
DELETE /api/social/follow/user/{user_id}         # Unfollow a user

POST   /api/social/follow/leader/{leader_id}     # Follow a leader
DELETE /api/social/follow/leader/{leader_id}     # Unfollow a leader

POST   /api/social/follow/organization/{org_id}  # Follow an organization
DELETE /api/social/follow/organization/{org_id}  # Unfollow an organization

POST   /api/social/follow/cause/{cause_id}       # Follow a cause
DELETE /api/social/follow/cause/{cause_id}       # Unfollow a cause
```

**Response:**
```json
{
  "success": true,
  "following": true,
  "follower_count": 1234,
  "message": "Successfully followed leader"
}
```

### Check Following Status

```http
GET /api/social/following/status?user_id=1&leader_id=2&org_id=3&cause_id=4
```

**Response:**
```json
{
  "user": false,
  "leader": true,
  "organization": true,
  "cause": false
}
```

### Get Statistics

```http
GET /api/social/stats              # Current user's stats
GET /api/social/stats?user_id=123  # Another user's stats
```

**Response:**
```json
{
  "followers": 150,
  "following": 42,
  "following_users": 10,
  "following_leaders": 15,
  "following_organizations": 12,
  "following_causes": 5
}
```

### Get Following Lists

```http
GET /api/social/following/leaders       # Leaders you follow
GET /api/social/following/organizations # Organizations you follow
GET /api/social/following/causes        # Causes you follow
```

**Response (Leaders):**
```json
[
  {
    "id": 1,
    "name": "Jane Smith",
    "slug": "jane-smith",
    "title": "Mayor",
    "office": "Office of the Mayor",
    "city": "Tuscaloosa",
    "state": "AL",
    "photo_url": "https://...",
    "follower_count": 1542,
    "is_verified": true
  }
]
```

---

## 🎨 UI Components

### FollowButton Component

**Location:** `frontend/src/components/FollowButton.tsx`

**Props:**
```typescript
interface FollowButtonProps {
  type: 'user' | 'leader' | 'organization' | 'cause'
  id: number
  initialFollowing?: boolean
  initialCount?: number
  showCount?: boolean
  compact?: boolean
  onFollowChange?: (following: boolean, count: number) => void
}
```

**Usage:**
```tsx
// Compact button (for cards)
<FollowButton 
  type="leader" 
  id={leader.id}
  initialFollowing={false}
  compact={true}
/>

// Full button with count
<FollowButton 
  type="organization" 
  id={org.id}
  initialFollowing={true}
  initialCount={1234}
  showCount={true}
/>
```

**Features:**
- LinkedIn-style hover effect: "Following" → "Unfollow" (red)
- Blue button when not following
- White button with check mark when following
- Loading spinner during API calls
- Optimistic UI updates

### SocialStats Component

**Location:** `frontend/src/components/SocialStats.tsx`

**Props:**
```typescript
interface SocialStatsProps {
  userId?: number          // Optional, defaults to current user
  showBreakdown?: boolean  // Show category breakdown
  clickable?: boolean      // Link to profile page
}
```

**Usage:**
```tsx
// Show current user's stats
<SocialStats showBreakdown={true} />

// Show another user's stats
<SocialStats userId={123} showBreakdown={false} />
```

**Features:**
- Displays follower/following counts
- Shows breakdown by category (leaders, charities, causes, people)
- Colored category badges
- Links to profile page (optional)

---

## 📱 Pages

### Profile Page

**Route:** `/profile`
**Location:** `frontend/src/pages/Profile.tsx`

**Features:**
- User avatar and basic info
- Social statistics with breakdown
- Tabbed interface:
  - **Leaders** - Grid of leader cards with follow buttons
  - **Charities** - Grid of organization cards with follow buttons
  - **Causes** - Grid of cause cards with follow buttons
- Empty states with CTAs ("Find leaders to follow →")
- Verification badges for verified entities

### Find Leaders Page (Updated)

**Route:** `/people`
**Location:** `frontend/src/pages/PeopleFinder.tsx`

**Changes:**
- Added follow button to each person card
- Shows follower count
- LinkedIn-style card layout with separator
- Follow button at bottom of each card

---

## 🚀 Migration

### Run Database Migration

```bash
cd /home/developer/projects/open-navigator
source .venv/bin/activate
python scripts/migrate_social_features.py
```

**Output:**
```
✅ Social features tables created successfully!

📊 New tables:
  ✓ leaders - Public officials and decision makers
  ✓ organizations - Nonprofits and charities
  ✓ causes - Policy topics and issues
  ✓ user_follows - User→User follows
  ✓ leader_follows - User→Leader follows
  ✓ organization_follows - User→Organization follows
  ✓ cause_follows - User→Cause follows

🎉 Migration complete! Social features are ready to use.
```

---

## 📝 Next Steps

### 1. Seed Data
Create seed data for leaders, organizations, and causes:

```python
# scripts/seed_social_data.py
from api.models import Leader, Organization, Cause
from api.database import SessionLocal

db = SessionLocal()

# Add Tuscaloosa Mayor
leader = Leader(
    name="Walter Maddox",
    slug="walter-maddox",
    title="Mayor",
    office="Office of the Mayor",
    city="Tuscaloosa",
    state="Alabama",
    jurisdiction="City of Tuscaloosa",
    email="mayor@tuscaloosa.com",
    follower_count=0,
    is_verified=True
)
db.add(leader)

# Add causes
causes = [
    Cause(
        name="Oral Health",
        slug="oral-health",
        description="Access to dental care and oral health education",
        category="health",
        color="#354F52",
        follower_count=0
    ),
    Cause(
        name="Affordable Housing",
        slug="affordable-housing",
        description="Creating affordable housing opportunities",
        category="housing",
        color="#52796F",
        follower_count=0
    ),
    # Add more...
]

db.add_all(causes)
db.commit()
```

### 2. Activity Feed
Create a feed showing updates from followed entities:
- New meeting minutes from followed leaders
- Updates from followed organizations
- News about followed causes

### 3. Notifications
Notify users when:
- Someone follows them
- A followed leader posts something
- A followed organization has an update
- Activity on a followed cause

### 4. Recommendations
Suggest who to follow based on:
- Location (follow local leaders)
- Interests (follow related causes)
- Network (follow people in your network)

### 5. Analytics
Track engagement metrics:
- Most followed leaders
- Most popular causes
- Follow growth over time
- Engagement rates

---

## 🎨 Design Principles

### LinkedIn/Facebook Patterns Used

1. **Follow Button States:**
   - Not following: Blue "Follow" button
   - Following: White "Following" button with check
   - Hover on following: Red "Unfollow" button

2. **Profile Layout:**
   - Large avatar at top
   - Stats prominently displayed
   - Tabbed content for different categories

3. **Social Proof:**
   - Follower counts visible everywhere
   - Verification badges for trusted entities
   - "X people follow this" messaging

4. **Discovery:**
   - Follow buttons on all entity cards
   - Empty states with clear CTAs
   - Category-based browsing

### Plain Language

- ✅ "Charities" instead of "Nonprofits"
- ✅ "Leaders" instead of "Officials"
- ✅ "Following" instead of "Subscribed"
- ✅ "Followers" instead of "Subscribers"

---

## 🔐 Authentication

All follow endpoints require authentication:
- User must be logged in via OAuth (HuggingFace, Google, Facebook, GitHub)
- JWT token passed in Authorization header
- `get_current_user` dependency validates token

**Error Responses:**
```json
{
  "detail": "Not authenticated"
}
```

---

## 📚 Resources

### API Documentation
- Swagger UI: http://localhost:8001/docs
- ReDoc: http://localhost:8001/redoc

### Code Files
- **Backend:**
  - `api/models.py` - Database models
  - `api/routes/social.py` - API endpoints
  - `scripts/migrate_social_features.py` - Migration script

- **Frontend:**
  - `frontend/src/components/FollowButton.tsx` - Follow button component
  - `frontend/src/components/SocialStats.tsx` - Stats display component
  - `frontend/src/pages/Profile.tsx` - Profile page
  - `frontend/src/pages/PeopleFinder.tsx` - Updated with follow buttons

---

## 🎉 Summary

You now have a complete social networking system for civic engagement! Users can:

1. **Follow leaders** they care about
2. **Follow charities** doing important work
3. **Follow causes** they're passionate about
4. **Follow other users** in their network
5. **View their profile** with social stats
6. **See who they follow** in organized tabs

This transforms the platform from a read-only information source into an **engaging social network for civic participation**! 🚀
