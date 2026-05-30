---
sidebar_position: 13
---

# Dynamic Trending Causes Implementation Summary

## What Changed

This update implements **dynamic, geography-specific trending causes** that show what policy areas are being discussed in government meetings for the selected location (national, state, county, or city).

### Before
- Hardcoded list of trending topics (Animals, Arts, Education, etc.)
- Same topics shown to all users regardless of location
- Static data from `/api/trending` endpoint

### After
- **Dynamic causes** based on AI-analyzed meeting decisions from last 90 days
- **Location-specific**: Different causes for Mobile, AL vs Boston, MA vs National
- **Automatic updates**: Recomputed daily via dbt pipeline
- **Intelligent fallback**: Shows global trending if no local data exists

## Files Changed

### 1. Database Layer (dbt)
- **`dbt_project/models/marts/jurisdiction_state_aggregate.sql`**
  - Added CTEs to aggregate trending causes by jurisdiction
  - Joins `int_trending_causes_by_jurisdiction` data
  - Populates `trending_causes` JSONB column at all levels (national, state, county, city)

### 2. Frontend
- **`frontend/src/pages/Home.tsx`**
  - Updated `trendingTopics` to use `locationStats.trending_causes` when available
  - Added `getCauseIcon()` helper to map cause names to emoji icons
  - Falls back to `/api/trending` if no location-specific data

### 3. Scripts
- **`scripts/data/update_trending_causes.sh`** (NEW)
  - Bash script to run dbt models and populate trending causes
  - Can be added to cron for daily updates

### 4. Documentation
- **`web_docs/docs/dbt/trending-causes.md`**
  - Updated to reflect new implementation
  - Added examples for each aggregation level

- **`website/docs/development/trending-causes-by-geography.md`** (NEW)
  - Comprehensive guide on how trending causes work
  - Troubleshooting tips
  - Performance considerations

## Testing

### 1. Populate the Data

First, run the dbt models to compute trending causes:

```bash
./scripts/data/update_trending_causes.sh
```

This will:
1. Clean and filter decisions to last 90 days
2. Aggregate causes by jurisdiction
3. Update `jurisdiction_state_aggregate` table with trending_causes

### 2. Verify Database

Check that trending causes exist:

```sql
-- Connect to database
psql -h localhost -p 5433 -U postgres -d open_navigator

-- Check city-level causes
SELECT 
  city,
  state_code,
  jsonb_array_length(trending_causes) as num_causes
FROM jurisdiction_state_aggregate
WHERE level = 'city' 
  AND trending_causes IS NOT NULL
LIMIT 10;

-- View a sample
SELECT jsonb_pretty(trending_causes) 
FROM jurisdiction_state_aggregate 
WHERE city ILIKE '%Mobile%' 
  AND level = 'city'
LIMIT 1;
```

### 3. Test Frontend

Start the application:

```bash
./start-all.sh
```

Then:

1. Open http://localhost:5173
2. Observe the trending topics bar (should show national causes by default)
3. Search for a specific city (e.g., "Mobile, AL")
4. The trending topics should update to show Mobile-specific causes
5. Switch to another location and verify causes change

### 4. Test API Directly

```bash
# National level
curl "http://localhost:8000/api/stats" | jq '.trending_causes'

# State level
curl "http://localhost:8000/api/stats?state=AL" | jq '.trending_causes'

# City level
curl "http://localhost:8000/api/stats?state=AL&city=Mobile" | jq '.trending_causes'
```

## Expected Behavior

### With Data
When trending causes data exists:
- User selects "Mobile, AL"
- API returns `trending_causes` array with causes like:
  ```json
  [
    {
      "cause": "Education and Workforce",
      "decision_count": 12,
      "rank": 1
    },
    {
      "cause": "Health",
      "decision_count": 8,
      "rank": 2
    }
  ]
  ```
- Frontend displays: "📚 Education and Workforce" "🏥 Health" etc.

### Without Data (Fallback)
When no trending causes exist for a location:
- API returns `trending_causes: null`
- Frontend falls back to `/api/trending` (global popular causes)
- User sees standard causes: Climate, Education, Health, etc.

## Deployment

### Local Development
1. Run `./scripts/data/update_trending_causes.sh` once to populate data
2. Data persists in PostgreSQL database
3. No additional steps needed

### Production (Neon/HuggingFace)
1. Ensure dbt is installed in production environment
2. Add cron job to run daily:
   ```bash
   0 2 * * * cd /path/to/open-navigator && ./scripts/data/update_trending_causes.sh
   ```
3. Or run manually after data ingestion:
   ```bash
   python scripts/datasources/gemini/load_meeting_transcripts_bronze.py
   ./scripts/data/update_trending_causes.sh
   ```

## Troubleshooting

### Issue: No trending causes displayed
**Solution**: Check if `bronze_decisions` table has recent data (last 90 days)
```sql
SELECT COUNT(*) FROM bronze_decisions 
WHERE decision_date >= CURRENT_DATE - INTERVAL '90 days';
```

If count is 0, load meeting transcript data first.

### Issue: Frontend shows old causes
**Solution**: Clear cache or wait 5 minutes (cache TTL)
```bash
# Restart API to clear cache
pkill -f "python main.py serve"
python main.py serve
```

### Issue: dbt models fail
**Solution**: Check database connection
```bash
cd dbt_project
dbt debug
```

Ensure `profiles.yml` points to correct database.

## Performance

- **Database query**: ~10-50ms (indexed queries on jurisdiction_state_aggregate)
- **Frontend render**: Instant (uses React.useMemo)
- **Cache duration**: 5 minutes (both API and frontend)
- **Update frequency**: Daily (via cron) or on-demand

## Migration Notes

No migration needed! The implementation:
- ✅ Backward compatible (falls back to `/api/trending` if no data)
- ✅ No schema changes required (trending_causes column already exists)
- ✅ Works immediately after running dbt models
- ✅ No code changes needed in other parts of the app

## Next Steps

After implementing this change:

1. **Monitor usage**: Track which causes users click on
2. **A/B test**: Compare engagement with location-specific vs global causes
3. **Expand data sources**: Include more meeting transcripts (currently ~1,366 meetings)
4. **Add visualizations**: Show trending causes on a map
5. **Enable filtering**: Let users filter search results by trending cause

## Questions?

See the full documentation at:
- [Trending Causes by Geography](website/docs/development/trending-causes-by-geography.md)
- [dbt ETL Strategy](website/docs/development/dbt-etl-strategy.md)
- [Trending Causes](../dbt/trending-causes.md)
