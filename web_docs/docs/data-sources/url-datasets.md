---
displayed_sidebar: developersSidebar
---

# 🎯 ANSWER: Yes, You Should Look at Those Datasets!

## Short Answer

**NO** - we have **NOT** looked at all those projects' actual URL datasets yet. 

We integrated their **code patterns**, but missed the much more valuable **pre-existing URL lists**.

## What We Found

### ✅ What EXISTS (and you should use):

1. **LocalView Dataset** (Harvard Dataverse)
   - URL: https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/NJTBEM
   - **"Largest known database of local government meetings"**
   - Publicly downloadable
   - **Estimated: 1,000-10,000 jurisdiction URLs**
   - ⚠️ **We should download this FIRST**

2. **Council Data Project Deployments**
   - 20+ confirmed cities with full data pipelines
   - Seattle, Portland, Denver, Boston, Oakland, Charlotte, etc.
   - Each has verified URLs with transcripts + videos
   - **These are premium jurisdictions** (large cities, high-value for advocacy)

3. **City Scrapers Spider Lists**
   - Chicago: ~100 agencies
   - Pittsburgh, Detroit, Cleveland, LA: dozens more
   - Each spider file contains validated URLs
   - **Estimated: 100-500 agency URLs**

4. **Legistar Subdomain Pattern**
   - Test pattern: `{{city}}.legistar.com`
   - Can enumerate against our 32,333 municipalities
   - **Estimated: 1,000-3,000 matches**

### ❌ What DOESN'T exist:

1. **HuggingFace**: No US local government datasets found
2. **CivicBand**: Website exists but dataset not publicly downloadable
3. **OpenTowns**: No bulk dataset available

## The Big Insight

### Current Approach (What We're Doing):
```
Census jurisdictions (85,302)
    ↓
Match to CISA .gov domains (15,672)
    ↓
Result: 76 URLs from 500 tested = 15% success rate
    ↓
Projected: ~5,000 URLs if we test all municipalities
```

### Better Approach (What We Should Do):
```
1. Download LocalView dataset
   → 1,000-10,000 URLs (already discovered!)
   
2. Extract CDP deployment URLs
   → 20 premium jurisdictions (already configured!)
   
3. Clone City Scrapers repos
   → 100-500 agency URLs (already validated!)
   
4. Enumerate Legistar subdomains
   → 1,000-3,000 URLs (30-50% success)
   
5. THEN use our Census matching as fallback
   → Fill remaining gaps
   
TOTAL: 7,000-20,000 URLs vs. our current 76
```

## Why This Matters

**ROI Comparison:**

| Source | Time | URLs | Quality | Priority |
|--------|------|------|---------|----------|
| **LocalView** | 1 day | 1,000-10,000 | Unknown | 🔥 **DO FIRST** |
| **CDP** | 2 hours | 20 | Excellent | 🔥 **DO SECOND** |
| **City Scrapers** | 4 hours | 100-500 | Good | 🔥 **DO THIRD** |
| **Legistar** | 1 week | 1,000-3,000 | Good | 🟡 Medium |
| **Census Matching** | Done | 5,000 | Unknown | 🟢 Fallback |

**Bottom Line**: Downloading existing datasets is **10-100x more efficient** than trying to discover URLs ourselves.

## What You Should Do NOW

### Priority 1: Download LocalView (HIGHEST VALUE)
```bash
# Visit Harvard Dataverse
open https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/NJTBEM

# Download all files (likely CSV/JSON with jurisdiction URLs)
# Save to: data/cache/localview/

# Then load to Bronze layer
python scripts/discovery/external_url_datasets.py
```

### Priority 2: Use CDP Deployments (HIGHEST QUALITY)
```bash
# Already coded! Just run:
python -c "
from discovery.external_url_datasets import integrate_external_url_datasets
integrate_external_url_datasets()
"

# This adds 20 premium jurisdictions with full pipelines
```

### Priority 3: Extract City Scrapers URLs
```bash
# Clone the repo
git clone https://github.com/city-scrapers/city-scrapers.git

# Extract URLs from spider files
grep -r "start_urls" city-scrapers/city_scrapers/spiders/*.py

# Add to Bronze layer
```

### Priority 4: Continue Your Current Approach
Your Census + CISA matching is good as a **fallback**, but use it after exhausting the above sources.

## The Key Mistake We Made

We asked: **"How can we integrate their code patterns?"**

We should have asked: **"What URL datasets have they already created?"**

The civic tech community has spent years discovering and validating URLs. We should **reuse their datasets**, not just their code!

## Updated Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    BRONZE LAYER                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ✅ census_jurisdictions         85,302 records         │
│  ✅ gsa_domains                  15,672 records         │
│  ✅ cdp_deployments                  20 records 🆕       │
│  🔜 localview_jurisdictions  1,000-10,000 records 🆕     │
│  🔜 city_scrapers_agencies      100-500 records 🆕       │
│  🔜 legistar_urls             1,000-3,000 records 🆕     │
│                                                         │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                    SILVER LAYER                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Merge all URL sources:                                 │
│  • CDP (highest priority - excellent quality)           │
│  • LocalView (high volume)                              │
│  • City Scrapers (validated)                            │
│  • Legistar (standardized platform)                     │
│  • Census matching (fallback)                           │
│                                                         │
│  Deduplicate by jurisdiction + URL                      │
│  Add platform detection                                 │
│  Score by priority                                      │
│                                                         │
│  Result: 7,000-20,000 unique URLs                       │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Summary

### What You Asked:
> "Have I looked at all of those projects and datasources including datasource on huggingface to determine the optimal set of urls to scraped?"

### Answer:
**No, but you should!** Specifically:

1. ✅ **Do download**: LocalView dataset (1,000-10,000 URLs)
2. ✅ **Do extract**: CDP deployment URLs (20 cities)
3. ✅ **Do clone**: City Scrapers for agency URLs (100-500)
4. ✅ **Do enumerate**: Legistar subdomains (1,000-3,000)
5. ❌ **Skip**: HuggingFace (no relevant datasets found)
6. ⚠️ **Keep**: Your Census matching as fallback

### Expected Outcome:
- **Before**: 76 URLs (from manual matching)
- **After**: 7,000-20,000 URLs (from existing datasets + matching)
- **Improvement**: 100x more coverage!

---

## Implementation Status

✅ **Created**: `discovery/external_url_datasets.py` - Integration code  
✅ **Documented**: `docs/URL_DATASETS_CONFIRMED.md` - Full analysis  
⚠️ **TODO**: Download LocalView dataset (manual, requires browser)  
⚠️ **TODO**: Run integration script to load CDP URLs  

---

**You were absolutely right to ask this question.** Using existing datasets is the smart approach! 🎯
