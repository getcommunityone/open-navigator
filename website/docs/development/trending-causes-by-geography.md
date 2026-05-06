---
sidebar_position: 12
---

# Dynamic Trending Causes by Geography

This guide explains how trending causes are computed and displayed based on the selected geography.

## Overview

The Open Navigator homepage displays **trending causes** - policy areas that have received the most attention in recent government meetings. These causes are dynamically computed based on:

- **Geography**: National, State, County, or City level
- **Time window**: Last 90 days of decisions
- **Data source**: AI-analyzed meeting transcripts from `bronze_decisions` table

## How It Works

### Data Flow

```
bronze_decisions (meetings)
    ↓ (dbt staging)
stg_bronze_decisions (cleaned, filtered to last 90 days)
    ↓ (dbt intermediate)
int_trending_causes_by_jurisdiction (aggregated by cause & jurisdiction)
    ↓ (dbt marts)
stats_aggregates.trending_causes (JSONB column)
    ↓ (API)
GET /api/stats?state=AL&city=Mobile
    ↓ (Frontend)
Home.tsx displays location-specific trending causes
```

### Example User Flow

1. **User lands on homepage** → Shows national trending causes
2. **User searches for "Mobile, AL"** → Shows Mobile's trending causes (last 90 days)
3. **User searches for "Alabama"** → Shows Alabama's trending causes (aggregated from all AL cities)
4. **No data?** → Falls back to global trending causes from `/api/trending`

## Technical Implementation

### Database Schema

The `stats_aggregates` table contains pre-computed statistics at multiple levels:

```sql
CREATE TABLE stats_aggregates (
    level VARCHAR(20),              -- 'national', 'state', 'county', 'city'
    state_code VARCHAR(2),
    county VARCHAR(100),
    city VARCHAR(100),
    jurisdictions_count INTEGER,
    nonprofits_count INTEGER,
    events_count INTEGER,
    contacts_count INTEGER,
    trending_causes JSONB,          -- ← Dynamic trending causes
    last_updated TIMESTAMP
);
```

### Trending Causes JSON

The structure varies by aggregation level:

**City Level** (most detailed):
```json
[
  {
    "cause": "Education and Workforce",
    "code": "COFOG-09",
    "decision_count": 5,
    "topics": 3,
    "most_recent": "2024-05-22",
    "rank": 1,
    "sample_headlines": [
      "MPS highlights literacy strategies",
      "Board approves new curriculum"
    ]
  }
]
```

**State Level** (aggregated):
```json
[
  {
    "cause": "Education and Workforce",
    "decision_count": 127,
    "jurisdictions": 15
  }
]
```

**National Level**:
```json
[
  {
    "cause": "Education and Workforce",
    "decision_count": 1543,
    "states": 42
  }
]
```

### Frontend Component

The `Home.tsx` component fetches trending causes from the stats endpoint:

```typescript
// Fetch location stats (includes trending_causes)
const { data: locationStats } = useQuery({
  queryKey: ['location-stats', location],
  queryFn: async () => {
    const response = await api.get('/stats', { 
      params: { state: 'AL', city: 'Mobile' }
    });
    return response.data;
  }
});

// Use location-specific causes if available
const trendingTopics = React.useMemo(() => {
  if (locationStats?.trending_causes) {
    // Transform database format to UI format
    return locationStats.trending_causes.map(cause => ({
      name: cause.cause,
      icon: getCauseIcon(cause.cause),
      description: `${cause.decision_count} recent decisions`
    }));
  }
  
  // Fallback to global trending
  return trendingData?.causes || [];
}, [locationStats, trendingData]);
```

## Updating Trending Causes

### Automated Updates (Recommended)

Set up a daily cron job to refresh trending causes:

```bash
# Add to crontab
0 2 * * * cd /path/to/open-navigator && ./scripts/data/update_trending_causes.sh
```

### Manual Updates

Run the dbt models to recompute trending causes:

```bash
# Quick update
./scripts/data/update_trending_causes.sh

# Or step-by-step
cd dbt_project
dbt run --select stg_bronze_decisions
dbt run --select int_trending_causes_by_jurisdiction
dbt run --select stats_aggregates
```

### Verification

Check that trending causes are populated:

```sql
-- Count jurisdictions with trending causes
SELECT 
  level,
  COUNT(*) as total,
  COUNT(CASE WHEN trending_causes IS NOT NULL THEN 1 END) as with_causes
FROM stats_aggregates
GROUP BY level;

-- View sample trending causes
SELECT 
  city,
  state_code,
  jsonb_pretty(trending_causes) as causes
FROM stats_aggregates
WHERE level = 'city' 
  AND trending_causes IS NOT NULL
LIMIT 5;
```

## Cause Categories

Trending causes are mapped to **COFOG** (Classification of Functions of Government) categories:

| Code | Category | Icon | Example Topics |
|------|----------|------|----------------|
| COFOG-01 | General Public Services | 🏛️ | Council procedures, budgets |
| COFOG-04 | Economic Affairs | 💼 | Business incentives, development |
| COFOG-05 | Environmental Protection | 🌍 | Parks, recycling, climate |
| COFOG-06 | Housing and Community Amenities | 🏠 | Zoning, affordable housing |
| COFOG-07 | Health | 🏥 | Public health, hospitals |
| COFOG-08 | Recreation, Culture, Religion | 🎨 | Libraries, museums, sports |
| COFOG-09 | Education and Workforce | 📚 | Schools, training programs |
| COFOG-10 | Social Protection | 🤝 | Social services, elderly care |

## Performance Considerations

### Why Pre-compute in dbt?

Instead of computing trending causes on-demand in the API, we use dbt to:

- ✅ **Speed**: Query takes ~10ms vs 3-5 seconds for on-the-fly aggregation
- ✅ **Consistency**: All users see the same data (updated daily)
- ✅ **Scalability**: No expensive computations at request time
- ✅ **Testing**: dbt tests ensure data quality

### Cache Strategy

The API caches stats for 5 minutes:

```python
# In api/routes/stats_neon.py
CACHE_DURATION = timedelta(minutes=5)
```

The frontend also caches for 5 minutes:

```typescript
staleTime: 5 * 60 * 1000  // 5 minutes
```

## Troubleshooting

### No trending causes shown?

Check if data exists:

```sql
SELECT COUNT(*) 
FROM stats_aggregates 
WHERE trending_causes IS NOT NULL;
```

If count is 0, run the dbt models:

```bash
./scripts/data/update_trending_causes.sh
```

### Causes not updating?

Clear the cache:

```bash
# Restart API to clear server-side cache
pkill -f "python main.py serve"
python main.py serve

# Frontend cache clears automatically after 5 minutes
```

### Wrong causes displayed?

Verify the bronze_decisions table has recent data:

```sql
SELECT 
  COUNT(*) as total,
  MIN(decision_date) as oldest,
  MAX(decision_date) as newest
FROM bronze_decisions
WHERE decision_date >= CURRENT_DATE - INTERVAL '90 days';
```

If no recent decisions exist, run the data ingestion pipeline:

```bash
# Load meeting transcripts
python scripts/datasources/gemini/load_meeting_transcripts_bronze.py

# Then update trending causes
./scripts/data/update_trending_causes.sh
```

## Related Documentation

- [dbt ETL Strategy](./dbt-etl-strategy.md) - Overall data pipeline architecture
- [Bronze to Production Merge](./bronze-to-production-merge.md) - Entity resolution strategy
- [dbt Project README](../../dbt_project/README.md) - dbt models and configuration
- [API Stats Endpoint](../api-reference/stats-endpoint.md) - Stats API documentation

## Future Enhancements

Potential improvements to trending causes:

1. **Real-time updates**: Use CDC (Change Data Capture) instead of daily batch
2. **Personalization**: Show causes relevant to user's interests
3. **Trend arrows**: Show if a cause is rising or falling
4. **Time comparison**: "Education up 23% vs last month"
5. **Geographic clustering**: Show regional trends (e.g., "Southern states")
