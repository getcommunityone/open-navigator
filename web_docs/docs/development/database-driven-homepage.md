# Database-Driven Homepage - Complete Setup Guide

## 🎉 What You Now Have

**✅ Fully database-driven homepage with automated cause/topic management:**

1. **API Endpoint** - `/api/trending` serves causes from database
2. **Frontend Integration** - Homepage fetches causes dynamically
3. **Image Generator** - Creates images for ALL 235 causes automatically
4. **Three Data Sources:**
   - **EveryOrg** (39 popular causes like "Climate", "Education", "Health")
   - **NTEE Codes** (196 IRS nonprofit categories like "E32: School-Based Health Care")
   - **Mixed** (automatically combines both)

---

## 🚀 Quick Start

### Step 1: Generate Images for ALL Causes

```bash
cd /home/developer/projects/open-navigator
source .venv/bin/activate

# First, add Gemini API key to .env:
# echo "GEMINI_API_KEY=your_key_here" >> .env
# Get key from: https://makersuite.google.com/app/apikey

# Generate ALL 235 cause images (takes ~10-15 minutes)
python scripts/media/generate_all_cause_images.py

# OR test with just 10 causes first
python scripts/media/generate_all_cause_images.py --limit 10

# OR generate only EveryOrg causes (39 causes)
python scripts/media/generate_all_cause_images.py --type everyorg

# OR generate only NTEE codes (196 causes)
python scripts/media/generate_all_cause_images.py --type ntee
```

**Output:**
```
data/media/causes/
├── everyorg_animals_banner.png (1200x600)
├── everyorg_animals_square.png (400x400)
├── everyorg_climate_banner.png
├── everyorg_climate_square.png
├── ntee_E_banner.png
├── ntee_E_square.png
├── ntee_E32_banner.png
├── ntee_E32_square.png
└── all_causes_metadata.json
```

### Step 2: Copy Images to Frontend

```bash
# Make images accessible to frontend
mkdir -p frontend/public/images/causes
cp data/media/causes/*.png frontend/public/images/causes/

# OR use symlink
ln -s ../../../data/media/causes frontend/public/images/causes
```

### Step 3: Test the API

```bash
# Start the API
./start-all.sh

# Or just API:
cd /home/developer/projects/open-navigator
source .venv/bin/activate
uvicorn api.main:app --reload --port 8000

# Test endpoints:
curl http://localhost:8000/api/trending?source=everyorg&limit=12
curl http://localhost:8000/api/trending?source=ntee&level=1
curl http://localhost:8000/api/trending?source=mixed&limit=12
curl http://localhost:8000/api/trending/stats
```

### Step 4: See It Live

```bash
# Visit homepage
http://localhost:5173

# You should see:
# - Trending causes loaded from database (not hardcoded!)
# - Count showing: "(12 from database)"
# - Causes change based on what's in parquet files
```

---

## 📚 How It Works

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. CAUSES DATA (Parquet Files)                             │
├─────────────────────────────────────────────────────────────┤
│ data/gold/causes_everyorg_causes.parquet (39 rows)         │
│ data/gold/causes_ntee_codes (196 rows)             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. IMAGE GENERATOR (Python Script)                         │
├─────────────────────────────────────────────────────────────┤
│ scripts/media/generate_all_cause_images.py                 │
│ - Reads parquet files                                       │
│ - Uses Gemini AI for color schemes                         │
│ - Generates banner (1200x600) + square (400x400)           │
│ - Saves to data/media/causes/                              │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. API ENDPOINT (FastAPI)                                  │
├─────────────────────────────────────────────────────────────┤
│ GET /api/trending?source=mixed&limit=12                    │
│ - Reads parquet files                                       │
│ - Returns causes with metadata                              │
│ - Includes image URLs                                       │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. FRONTEND (React)                                        │
├─────────────────────────────────────────────────────────────┤
│ Home.tsx - useQuery('trending-causes')                     │
│ - Fetches from API on page load                            │
│ - Renders trending topics bar                              │
│ - Shows cause icons, names, + buttons                      │
│ - Clickable → search that cause                            │
└─────────────────────────────────────────────────────────────┘
```

### API Endpoints

#### `GET /api/trending`

**Parameters:**
- `source`: "everyorg" | "ntee" | "mixed" (default: "everyorg")
- `limit`: Number of causes to return (default: 12, max: 100)
- `level`: NTEE level filter (1=major groups, 2=subcategories) - only for ntee source

**Response:**
```json
{
  "causes": [
    {
      "name": "Climate",
      "icon": "🌍",
      "category": "primary",
      "description": "Climate change mitigation...",
      "image_url": "/images/causes/everyorg_climate_square.png",
      "popularity_rank": 4
    },
    {
      "name": "Health",
      "icon": "⚕️",
      "category": "major_group",
      "description": "NTEE Code E",
      "image_url": "/images/causes/ntee_E_square.png",
      "popularity_rank": null
    }
  ],
  "total": 12
}
```

#### `GET /api/trending/stats`

**Response:**
```json
{
  "everyorg_causes": 39,
  "ntee_causes": 196,
  "total_causes": 235,
  "generated_images": 470
}
```

---

## 🎨 Image Generation Details

### What Gets Generated

**For each cause** (e.g., "Climate"):
1. **Banner image** (1200x600px)
   - Filename: `everyorg_climate_banner.png`
   - Use: Hero banners, featured stories
   - Has: Gradient background, large text overlay

2. **Square thumbnail** (400x400px)
   - Filename: `everyorg_climate_square.png`
   - Use: Topic cards, trending bar
   - Has: Circular gradient, compact text

3. **Color scheme** (in metadata.json)
   - AI-generated thematic colors
   - Example: Climate → greens and blues
   - Example: Health → calming medical blues

### Filename Patterns

- **EveryOrg**: `everyorg_{cause_id}_{type}.png`
  - `everyorg_climate_banner.png`
  - `everyorg_education_square.png`

- **NTEE**: `ntee_{code}_{type}.png`
  - `ntee_E_banner.png` (Health - major group)
  - `ntee_E32_square.png` (School-Based Health Care - specific)

### Generation Progress

The script shows:
```
[1/235] Processing: Climate
   Category: everyorg | ID: climate
────────────────────────────────────────────────────────────
🎨 Generated color scheme: Calming greens and blues for environmental focus
🖼️  Creating banner image (1200x600)...
✅ Saved: data/media/causes/everyorg_climate_banner.png
🔲 Creating square image (400x400)...
✅ Saved: data/media/causes/everyorg_climate_square.png
   ✅ Success! (1/235 = 0.4% complete)
```

---

## 🔧 Customization

### Change Source Mix

**Homepage** (`frontend/src/pages/Home.tsx`):
```typescript
// Current: Mixed (6 everyorg + 6 ntee)
source: 'mixed',
limit: 12

// Only popular causes:
source: 'everyorg',
limit: 12

// Only IRS categories:
source: 'ntee',
limit: 12,
level: 1  // Only major groups (Arts, Health, Education, etc.)
```

### Add Custom Causes

**Option 1: Add to EveryOrg causes**
```python
import polars as pl

# Load existing
df = pl.read_parquet('data/gold/causes_everyorg_causes.parquet')

# Add new cause
new_cause = pl.DataFrame({
    'cause_id': ['oral-health'],
    'cause_name': ['Oral Health'],
    'description': ['Dental care access and fluoride policy'],
    'category': ['primary'],
    'parent_id': [None],
    'icon': ['🦷'],
    'popularity_rank': [40],
    'data_source': ['Manual'],
    'download_date': [pl.datetime('now')],
    'version': ['2026.1']
})

# Combine
df = pl.concat([df, new_cause])

# Save
df.write_parquet('data/gold/causes_everyorg_causes.parquet')
```

**Option 2: Add to NTEE codes**
(Similar process with causes_ntee_codes)

### Skip Existing Images

If you've already generated some images:
```bash
python scripts/media/generate_all_cause_images.py --skip-existing
```

This will only generate images for causes that don't have them yet.

---

## 📊 What Changed

### Files Modified

1. **API:**
   - ✅ `api/routes/trending.py` - New trending causes endpoint
   - ✅ `api/main.py` - Registered trending router

2. **Frontend:**
   - ✅ `frontend/src/pages/Home.tsx` - Database-driven causes
   - Added `useQuery` to fetch from `/api/trending`
   - Shows count "(X from database)"

3. **Scripts:**
   - ✅ `scripts/media/generate_all_cause_images.py` - Batch generator
   - ✅ `scripts/media/generate_topic_images.py` - Base generator (already existed)

### Before vs After

**Before (Hardcoded):**
```typescript
const TRENDING_TOPICS = [
  { name: 'World Press Freedom Day', icon: '📰', category: 'Global' },
  { name: 'Business & Markets', icon: '💼', category: 'Economics' },
  // ... hardcoded list
]
```

**After (Database-Driven):**
```typescript
const { data: trendingData } = useQuery({
  queryKey: ['trending-causes'],
  queryFn: async () => {
    const response = await api.get('/trending', {
      params: { source: 'mixed', limit: 12 }
    })
    return response.data
  }
})

const trendingTopics = trendingData?.causes || []
```

---

## 🎯 Next Steps

### Phase 1: Generate All Images (Do This First!)

```bash
# Get Gemini API key
https://makersuite.google.com/app/apikey

# Add to .env
echo "GEMINI_API_KEY=your_key" >> .env

# Generate all 235 cause images (~10-15 minutes)
python scripts/media/generate_all_cause_images.py

# Copy to frontend
cp data/media/causes/*.png frontend/public/images/causes/
```

### Phase 2: Test Locally

```bash
./start-all.sh

# Visit http://localhost:5173
# Check that trending causes load from database
# Inspect network tab: should see /api/trending request
```

### Phase 3: Deploy

```bash
# Standard deployment
./packages/hosting/scripts/huggingface/safe-deploy.sh

# Make sure to include generated images!
# Either:
# 1. Copy to frontend/public/images/causes before deploy
# 2. Or upload to CDN and update image_url in API
```

### Phase 4: Track Popularity (Future)

Add analytics to track which causes users click:
```sql
CREATE TABLE cause_interactions (
  cause_id VARCHAR,
  interaction_type VARCHAR,  -- click, follow, search
  user_id VARCHAR,
  timestamp TIMESTAMP
);
```

Then use this data to dynamically rank causes by popularity!

---

## 🐛 Troubleshooting

### "GEMINI_API_KEY not found"

```bash
# Get key from Google
https://makersuite.google.com/app/apikey

# Add to .env
echo "GEMINI_API_KEY=your_actual_key_here" >> .env

# Verify
grep GEMINI_API_KEY .env
```

### Images Don't Show on Homepage

1. **Check API response:**
   ```bash
   curl http://localhost:8000/api/trending?source=mixed&limit=1
   # Look for "image_url" field
   ```

2. **Check images exist:**
   ```bash
   ls frontend/public/images/causes/ | head -10
   ```

3. **Check browser console:**
   - Should see no 404 errors for images
   - Network tab shows images loading

### "No causes found" Error

Verify parquet files exist:
```bash
ls -lh data/gold/causes*.parquet
# Should show:
# causes_everyorg_causes.parquet (39 rows)
# causes_ntee_codes (196 rows)
```

### Frontend Shows "(0 from database)"

1. Check API is running:
   ```bash
   curl http://localhost:8000/api/trending
   ```

2. Check for CORS errors in browser console

3. Verify .env has correct API URL

---

## 📝 Summary

**You now have:**

✅ **235 causes** ready to generate images for
- 39 EveryOrg popular causes (Climate, Education, etc.)
- 196 NTEE codes (official IRS categories)

✅ **Automated image generation** script
- Reads causes from parquet files
- Uses Gemini AI for color schemes
- Generates banner + square for each

✅ **Database-driven API** endpoint
- `/api/trending` serves causes dynamically
- Supports filtering by source, limit, level
- Includes image URLs and metadata

✅ **Frontend integration**
- Homepage fetches causes from API
- Shows "(X from database)" count
- Automatically updates when data changes

**Your homepage is now 100% database-driven! 🎉**

No more hardcoded causes - everything comes from your parquet files!
