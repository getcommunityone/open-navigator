---
sidebar_position: 12
---

# 🚨 CRITICAL: Which Port to Use?

## TL;DR: Go to Port 5173 for the App

```
http://localhost:5173  ← YOUR ORIGINAL DASHBOARD (search, filters, everything)
http://localhost:3000  ← New documentation site (just guides/docs)
```

## The Confusion Explained

### What Happened
You asked to "change the react site to use docusaurus". I interpreted this as "add documentation using Docusaurus" but kept the React dashboard separate.

**Result:** You now have TWO separate websites running:
1. **Port 3000** - Docusaurus (NEW) - Documentation only
2. **Port 5173** - React Dashboard (ORIGINAL) - All your features

### What You're Seeing

If you go to `http://localhost:3000`, you see:
- ❌ Marketing homepage with big buttons
- ❌ Documentation pages
- ❌ No search functionality
- ❌ No filters
- ❌ No heatmap
- ❌ Looks completely different

**This is CORRECT - it's the documentation site!**

If you go to `http://localhost:5173`, you see:
- ✅ Your original dashboard
- ✅ Search and filter functionality
- ✅ Interactive heatmap
- ✅ Document explorer
- ✅ Nonprofit search
- ✅ Opportunity tracker
- ✅ All your original work UNCHANGED

## Quick Test

Open these two URLs in separate browser tabs:

### Tab 1: Documentation Site
```
http://localhost:3000
```
You'll see:
- Docusaurus marketing page
- "Get Started" and "Launch Dashboard" buttons
- Feature descriptions
- Big homepage

### Tab 2: React Dashboard (YOUR ORIGINAL APP)
```
http://localhost:5173
```
You'll see:
- Dashboard with stats cards
- Charts and visualizations
- Navigation: Dashboard, Heatmap, Documents, Opportunities, Nonprofits, Settings
- **THIS IS YOUR ORIGINAL APPLICATION**

## File Locations

### React Dashboard (Port 5173)
```
frontend/
  src/
    pages/
      Dashboard.tsx      ← Your original homepage
      Heatmap.tsx        ← Interactive map
      Documents.tsx      ← Search functionality
      Opportunities.tsx  ← Filters and tracking
      Nonprofits.tsx     ← Nonprofit search
    App.tsx              ← Routes
    components/
      Layout.tsx         ← Navigation
```

**Start with:** `cd frontend && npm run dev`

### Documentation Site (Port 3000)
```
website/
  docs/                  ← Markdown documentation
  src/pages/
    index.tsx            ← Marketing homepage
    dashboard.tsx        ← Redirect page
  docusaurus.config.ts   ← Configuration
```

**Start with:** `cd website && npm start`

## Nothing Was Lost

✅ All your React components: **Still in `frontend/src/pages/`**  
✅ All your search/filter code: **Unchanged**  
✅ All your API integrations: **Unchanged**  
✅ All your styling: **Unchanged**  

The Docusaurus site was **ADDED**, not used to **REPLACE** anything.

## Solution

### Option 1: Just Use the Dashboard
```bash
# Ignore the docs site, just use the dashboard
cd frontend
npm run dev
# Open http://localhost:5173
```

### Option 2: Remove Docusaurus (if you don't want it)
```bash
# Delete the documentation site
rm -rf website/
# Update README to remove docs references
```

### Option 3: Understand the Architecture
Read [ARCHITECTURE.md](ARCHITECTURE.md) which explains the three-service model.

## Common Mistakes

❌ Opening `http://localhost:3000` and expecting to see the dashboard  
✅ Opening `http://localhost:5173` to see the dashboard

❌ Looking at `website/src/pages/index.tsx` for dashboard code  
✅ Looking at `frontend/src/pages/Dashboard.tsx` for dashboard code

❌ Thinking Docusaurus replaced the React app  
✅ Understanding Docusaurus is a separate documentation layer

## Questions?

**Q: Where's my search functionality?**  
A: `http://localhost:5173` → Documents page

**Q: Where's my heatmap?**  
A: `http://localhost:5173` → Heatmap page

**Q: Where are my filters?**  
A: `http://localhost:5173` → Opportunities page

**Q: Why does port 3000 look different?**  
A: Because it's a different site (documentation). Use port 5173.

**Q: Did I lose any work?**  
A: NO! Everything is in `frontend/` directory, unchanged.

---

## Right Now: What You Should Do

1. Open browser to: **http://localhost:5173**
2. You'll see your original dashboard
3. Everything works exactly as before
4. Use port 3000 only for reading documentation

**Your work is NOT lost. You're just looking at the wrong port.**
