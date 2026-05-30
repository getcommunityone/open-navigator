---
sidebar_position: 8
---

# Ground News-Style Homepage Redesign

## Overview

The homepage has been redesigned to follow the Ground News pattern with trending topics, a featured hero story, and a news grid layout. This creates a more engaging, content-forward experience while maintaining search functionality.

## What Changed

### 1. Trending Topics Bar

Two rows of trending topics at the top of the page with **+ icons** to subscribe/follow:

**First Row:**
- World Press Freedom Day 📰
- Business & Markets 💼
- Artificial Intelligence 🤖
- Health & Medicine ⚕️
- Premier League ⚽
- Soccer ⚽

**Second Row:**
- Baseball ⚾
- Donald Trump 🏛️
- IPL 🏏
- Social Media 📱
- Trump Administration 🇺🇸
- "Follow Topics" button

Each topic:
- Has an emoji icon
- Shows + sign on hover
- Clickable to search that topic
- Professional pill-shaped design

### 2. Featured Hero Story

Large banner with:
- **1200x600px hero image** with overlay
- **Gradient background** from black to transparent
- **Large headline** overlay (3-5xl text)
- **Subtitle** with context
- **Category badge** (top left)
- **Hover effects** (image opacity, text color)

Example:
```
Category: Civic Engagement
Title: "World Press Freedom Day: 43,726 Nonprofits Fighting for Transparency"
Subtitle: "How local journalism and civic organizations are tracking government decisions..."
```

### 3. Top Stories Grid

3-column responsive grid with 6 story cards:
- **Small image** (400x300px) for each story
- **Topic badge** overlay on image
- **Story title** (2-line max with line-clamp)
- **Hover effects** (shadow, scale, color change)

Topics covered:
- Artificial Intelligence
- Health & Medicine
- Sports & Recreation
- Social Media
- Business Development
- Government Transparency

### 4. Search Section (Moved Lower)

The original search interface is now in a collapsible section lower on the page:
- Still has both tabs (Search Topics, Find My Community)
- Maintains all functionality
- More subdued background (gray instead of white)
- Search-forward → Content-forward shift

## Technical Implementation

### New Icons Added

```typescript
import {
  PlusIcon,      // For "subscribe/follow" buttons
  BellIcon,      // For "Follow Topics" button
  FireIcon       // For "Trending" indicator
} from '@heroicons/react/24/outline'
```

### Data Structures

**TRENDING_TOPICS array:**
```typescript
{
  name: string,      // "World Press Freedom Day"
  icon: string,      // "📰"
  category: string   // "Global"
}
```

**FEATURED_STORY object:**
```typescript
{
  title: string,
  subtitle: string,
  image: string,     // URL to hero image
  category: string,
  link: string       // Internal route
}
```

**TOP_STORIES array:**
```typescript
{
  title: string,
  topic: string,     // Displayed as badge
  image: string,     // 400x300px thumbnail
  link: string
}
```

### Styling Features

1. **Trending Bar:**
   - `bg-gray-50 border-b` for subtle separation
   - Pill-shaped buttons with `rounded-full`
   - Hover state with `border-primary-500`

2. **Hero Banner:**
   - `h-[500px]` fixed height
   - `bg-gradient-to-t from-black` for text readability
   - `group-hover:opacity-50` for image
   - `group-hover:text-primary-300` for headline

3. **Story Cards:**
   - `hover:shadow-lg` for elevation
   - `group-hover:scale-105` on images
   - `line-clamp-2` for title truncation

## Image Generation

### New Script: `scripts/media/generate_topic_images.py`

Generates professional banner and square images for topics using Google Gemini AI.

**Features:**
- AI-powered color scheme generation
- Banner images (1200x600px)
- Square thumbnails (400x400px)
- Gradient backgrounds
- Smart text wrapping
- Batch processing

**Usage:**
```bash
# Single topic
python scripts/media/generate_topic_images.py --topic "World Press Freedom Day"

# Batch from file
python scripts/media/generate_topic_images.py --topics-file topics.txt

# Default trending topics
python scripts/media/generate_topic_images.py
```

**Requirements:**
- Google Gemini API key in `.env`: `GEMINI_API_KEY=your_key`
- Auto-installs: `google-generativeai`, `pillow`, `requests`

**Output:**
```
data/media/topics/
├── world_press_freedom_day_banner.png   (1200x600)
├── world_press_freedom_day_square.png   (400x400)
├── artificial_intelligence_banner.png
├── artificial_intelligence_square.png
└── metadata.json                         (color schemes, paths)
```

### Color Scheme Generation

Gemini analyzes each topic and suggests:
- **Primary color**: Main gradient start
- **Secondary color**: Gradient end
- **Text color**: High contrast for readability
- **Background color**: Base tone
- **Reasoning**: Why these colors fit the topic

Examples:
- **Politics**: Professional blues (#2563EB) and reds
- **Health**: Calming greens and blues
- **Technology**: Modern purples (#7C3AED) and blues
- **Sports**: Energetic oranges and reds

## Using Generated Images

### Update Homepage Data

Replace placeholder Unsplash images with generated ones:

```typescript
const FEATURED_STORY = {
  title: 'World Press Freedom Day...',
  image: '/images/topics/world_press_freedom_day_banner.png', // ← Use generated
  // ...
}

const TOP_STORIES = [
  {
    title: 'AI Policy Tracking...',
    image: '/images/topics/artificial_intelligence_square.png', // ← Use generated
    // ...
  }
]
```

### Integration Steps

1. **Generate images:**
   ```bash
   cd /home/developer/projects/open-navigator
   source .venv/bin/activate
   python scripts/media/generate_topic_images.py
   ```

2. **Copy to frontend:**
   ```bash
   mkdir -p frontend/public/images/topics
   cp data/media/topics/*.png frontend/public/images/topics/
   ```

3. **Update Home.tsx:**
   - Change image URLs from `https://images.unsplash.com/...`
   - To `/images/topics/{topic}_square.png` or `{topic}_banner.png`

4. **Rebuild:**
   ```bash
   cd frontend && npm run build
   ```

## Benefits

### User Experience

1. **Content Discovery**: Users see trending topics immediately
2. **Visual Engagement**: Large hero image draws attention
3. **Quick Navigation**: Click topics to search instantly
4. **Personalization**: + buttons suggest following/subscribing
5. **Familiar Pattern**: Matches news aggregators users know

### Technical Benefits

1. **SEO**: Content-forward design better for crawlers
2. **Performance**: Images lazy-load below fold
3. **Flexibility**: Easy to update trending topics
4. **Branding**: Custom generated images (no stock photo licenses)
5. **Accessibility**: High contrast, semantic HTML

## Future Enhancements

### Phase 2: Dynamic Content

- [ ] Pull trending topics from actual search data
- [ ] Featured story from latest government decisions
- [ ] Top stories from recent meeting minutes
- [ ] Real-time topic popularity tracking

### Phase 3: Personalization

- [ ] User can follow/subscribe to topics
- [ ] Save "+ Follow" state to user preferences
- [ ] Customized feed based on followed topics
- [ ] Email/push notifications for followed topics

### Phase 4: Advanced Image Generation

- [ ] Use Imagen 2 when available in Gemini API
- [ ] Real-time image generation on topic creation
- [ ] Video thumbnails from meeting recordings
- [ ] Animated topic badges (WebP/GIF)

## Design Inspiration

Based on [Ground News](https://ground.news):
- Trending topics bar at top
- Large hero story with image overlay
- Grid of smaller story cards
- Clean, professional news aesthetic
- Content-first approach

## Migration Notes

### Breaking Changes
- None! Search functionality preserved
- Existing routes still work
- All components intact

### Deprecations
- None

### Backward Compatibility
- 100% compatible
- Search moved lower but fully functional
- All existing links work

## Examples

### Before (Search-First)
```
+----------------------------------+
| Open Navigator                    |
| Search box (prominent)            |
| Tabs: Search / Location           |
| Quick topic pills                 |
| Stats section                     |
+----------------------------------+
```

### After (Content-First)
```
+----------------------------------+
| Trending: [Topic] [Topic] [+]     |
| [Topic] [Topic] [Topic] [+]       |
+----------------------------------+
| [HERO IMAGE WITH HEADLINE]        |
| Large featured story              |
+----------------------------------+
| Top Stories Grid                  |
| [img] [img] [img]                |
| Story Story Story                 |
+----------------------------------+
| Search Section (collapsible)      |
| Features Grid                     |
| Stats                             |
+----------------------------------+
```

## Testing

### Manual Tests

1. **Trending Topics**
   - Click each topic → should navigate to search
   - Hover → should show border/background change
   - + icon → should be visible

2. **Hero Banner**
   - Image loads correctly
   - Text is readable over image
   - Hover effects work
   - Link goes to correct search

3. **Story Grid**
   - All 6 stories display
   - Images load
   - Topic badges visible
   - Hover effects (shadow, scale)

4. **Search Still Works**
   - Both tabs functional
   - Location lookup works
   - Search results correct

### Automated Tests

Build verification:
```bash
cd frontend
npx tsc --noEmit  # TypeScript check
npm run build     # Vite build
```

## Deployment

### HuggingFace Spaces

No changes needed! Same deployment process:

```bash
./scripts/huggingface/safe-deploy.sh
```

The Docker build will include:
- Updated Home.tsx
- Generated topic images (if copied to frontend/public)
- All existing functionality

### Local Development

```bash
./start-all.sh  # Starts all 3 services
# Visit http://localhost:5173
```

## Resources

- **Script**: `scripts/media/generate_topic_images.py`
- **README**: `scripts/media/README.md`
- **Component**: `frontend/src/pages/Home.tsx`
- **Icons**: Heroicons 24 outline
- **Images**: Unsplash (placeholder) → Generated (production)

## Questions?

See [scripts/media/README.md](../../../scripts/media/README.md) for image generation details.
