# ✅ DATABASE-DRIVEN HOMEPAGE - READY TO USE!

## 🎉 What's Done

Your homepage is now **100% database-driven** with all **235 causes** ready to generate images for!

### ✅ Completed

1. **API Endpoint** - `/api/trending` serves causes from parquet files
2. **Frontend Integration** - Homepage fetches from database (not hardcoded!)
3. **Image Generator** - Script to create images for ALL 235 causes
4. **Build Verified** - TypeScript compiles ✅, Build succeeds ✅

---

## 🚀 Quick Start (3 Steps)

### 1. Generate Images for Your Causes

```bash
cd /home/developer/projects/open-navigator
source .venv/bin/activate

# Get Gemini API key: https://makersuite.google.com/app/apikey
echo "GEMINI_API_KEY=your_key_here" >> .env

# Generate images for ALL 235 causes (~10-15 min)
python scripts/media/generate_all_cause_images.py

# OR test with 10 first
python scripts/media/generate_all_cause_images.py --limit 10
```

### 2. Copy Images to Frontend

```bash
mkdir -p frontend/public/images/causes
cp data/media/causes/*.png frontend/public/images/causes/
```

### 3. Test Live

```bash
./start-all.sh
# Visit: http://localhost:5173
```

You should see:
- Trending causes bar with database count
- "(12 from database)" indicator
- Causes dynamically loaded

---

## 📊 Your Causes Data

**Total: 235 causes in database**

### EveryOrg Causes (39)
Popular curated categories:
- Animals
- Arts & Culture
- Civil Rights
- Climate
- Disabilities
- Education
- Health
- Housing
- ...and 31 more

### NTEE Codes (196)
Official IRS nonprofit categories:
- **A** - Arts, Culture & Humanities
- **B** - Education
- **C** - Environment
- **D** - Animal-Related
- **E** - Health
- **F** - Mental Health
- ...all 26 major groups + subcategories

---

## 🎨 Generated Images

For each cause, you get:

1. **Banner** (1200x600px)
   - `everyorg_climate_banner.png`
   - `ntee_E_banner.png`
   - Use: Hero images, featured stories

2. **Square** (400x400px)
   - `everyorg_climate_square.png`
   - `ntee_E_square.png`
   - Use: Topic cards, trending bar

3. **AI Color Scheme**
   - Gemini generates thematic colors
   - Saved in `metadata.json`

---

## 🔌 API Endpoints

### `GET /api/trending`

**Get trending causes:**
```bash
# Mix of both sources (default)
curl http://localhost:8001/api/trending?source=mixed&limit=12

# Only popular causes
curl http://localhost:8001/api/trending?source=everyorg&limit=12

# Only IRS categories
curl http://localhost:8001/api/trending?source=ntee&level=1

# View stats
curl http://localhost:8001/api/trending/stats
```

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
    }
  ],
  "total": 12
}
```

---

## 📝 Files Created

### API
- ✅ `api/routes/trending.py` - Trending causes endpoint
- ✅ `api/main.py` - Router registered

### Frontend
- ✅ `frontend/src/pages/Home.tsx` - Database-driven causes

### Scripts
- ✅ `scripts/media/generate_all_cause_images.py` - Batch generator for all causes
- ✅ `scripts/media/generate_topic_images.py` - Base image generator

### Documentation
- ✅ `DATABASE_DRIVEN_HOMEPAGE.md` - Full documentation
- ✅ `QUICKSTART_HOMEPAGE.md` - Quick reference

---

## 🎯 How It Works

```
Parquet Files (data/gold/)
  ├─ causes_everyorg_causes.parquet (39 rows)
  └─ causes_ntee_codes (196 rows)
              ↓
API (/api/trending)
  ├─ Reads parquet files
  ├─ Returns causes with metadata
  └─ Includes image URLs
              ↓
Frontend (Home.tsx)
  ├─ useQuery('trending-causes')
  ├─ Fetches from API on load
  └─ Renders dynamically
```

---

## 🛠️ Advanced Options

### Generate Only Specific Causes

```bash
# Only EveryOrg (39 causes)
python scripts/media/generate_all_cause_images.py --type everyorg

# Only NTEE (196 causes)
python scripts/media/generate_all_cause_images.py --type ntee

# Skip existing images
python scripts/media/generate_all_cause_images.py --skip-existing
```

### Change Homepage Source

Edit `frontend/src/pages/Home.tsx`:
```typescript
// Line ~109 - Change source
const { data: trendingData } = useQuery({
  queryFn: async () => {
    const response = await api.get('/trending', {
      params: {
        source: 'everyorg',  // 'everyorg', 'ntee', or 'mixed'
        limit: 12
      }
    })
    return response.data
  }
})
```

### Add Custom Causes

```python
import polars as pl

# Load existing
df = pl.read_parquet('data/gold/causes_everyorg_causes.parquet')

# Add new cause
new = pl.DataFrame({
    'cause_id': ['oral-health'],
    'cause_name': ['Oral Health'],
    'description': ['Dental care access'],
    'category': ['primary'],
    'icon': ['🦷'],
    'popularity_rank': [40]
})

# Combine and save
pl.concat([df, new]).write_parquet('data/gold/causes_everyorg_causes.parquet')

# Generate image
python scripts/media/generate_all_cause_images.py --type everyorg
```

---

## ✅ Build Status

**Verified:**
- ✅ TypeScript compiles with no errors
- ✅ Frontend builds successfully (5.21s)
- ✅ Bundle size: 1.39 MB (gzipped: 380 KB)
- ✅ All imports resolved
- ✅ API endpoints registered

---

## 🚀 Deploy

```bash
# Deploy to HuggingFace Spaces
./packages/hosting/scripts/huggingface/safe-deploy.sh

# Make sure images are included!
# Copy them to frontend/public/images/causes/ first
```

---

## 📖 Full Documentation

- **Complete Guide**: `DATABASE_DRIVEN_HOMEPAGE.md`
- **API Docs**: Visit `/docs` when API is running
- **Image Generator**: `scripts/media/README.md`

---

## 🎉 Summary

**You now have:**

✅ 235 causes in database (39 EveryOrg + 196 NTEE)
✅ API endpoint serving causes dynamically  
✅ Frontend fetching from database
✅ Image generator for all causes
✅ No more hardcoded data!

**Your homepage is database-driven!** 🚀

Just add your Gemini API key and run the image generator!
