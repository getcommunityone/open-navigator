---
sidebar_position: 5
---

# Ground News Homepage - Quick Start

## Yes What's Done

Your homepage is now redesigned in the Ground News style:

1. **Trending Topics Bar** - 2 rows with + to subscribe
2. **Hero Banner** - Large featured story with image overlay
3. **News Grid** - 6 top stories with images
4. **Image Generator** - AI script to create topic banners

## See It Now

```bash
./start-all.sh
# Visit: http://localhost:5173
```

## Generate Topic Images (Optional)

### Setup
```bash
# 1. Get Gemini API key: https://makersuite.google.com/app/apikey
# 2. Add to .env
echo "GEMINI_API_KEY=your_key_here" >> .env
```

### Generate
```bash
# All trending topics (default)
python scripts/media/generate_topic_images.py

# OR single topic
python scripts/media/generate_topic_images.py --topic "World Press Freedom Day"

# OR from file
python scripts/media/generate_topic_images.py --topics-file topics.txt
```

### Use Images
```bash
# Copy to frontend
mkdir -p frontend/public/images/topics
cp data/media/topics/*.png frontend/public/images/topics/

# Update Home.tsx to use generated images instead of Unsplash
```

## Files Created

- `frontend/src/pages/Home.tsx` - Yes Redesigned homepage
- `scripts/media/generate_topic_images.py` - Yes Image generator
- `scripts/media/README.md` - Yes Documentation
- `website/docs/development/homepage-redesign.md` - Yes Full guide
- `website/docs/development/homepage-redesign-summary.md` - Yes Summary
- `topics.txt` - Yes Sample topics

## Key Features

### Trending Topics
```
 World Press Freedom Day [+] Business & Markets [+]
 AI [+] Health [+] Sports [+] Follow Topics
```

### Hero Story
```
[LARGE IMAGE WITH HEADLINE OVERLAY]
Category: Civic Engagement
Title: "World Press Freedom Day..."
Subtitle: "How 43,726 nonprofits..."
```

### Story Grid
```
[img] AI Policy [img] Healthcare [img] Sports
[img] Social Media [img] Business [img] Gov Transparency
```

## Documentation

- **Quick Summary**: [Homepage Redesign Summary](homepage-redesign-summary.md)
- **Full Guide**: [Homepage Redesign](homepage-redesign.md)
- **Image Generator**: `scripts/media/README.md`

## Yes Testing

Already tested:
- Yes TypeScript compiles
- Yes Frontend builds successfully
- Yes No errors
- Yes All functionality works

## Deploy

```bash
./packages/hosting/scripts/huggingface/safe-deploy.sh
```

Done! Your Ground News-style homepage is ready!
