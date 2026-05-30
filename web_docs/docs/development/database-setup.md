---
sidebar_position: 1
---

# Database Setup & Stats Verification

## Quick Setup

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your Neon database URL
# NEON_DATABASE_URL=postgresql://user:password@host/database
```

### 3. Run End-to-End Setup

```bash
# Automated setup script
./scripts/setup-database.sh
```

This script will:
- ✅ Verify environment is configured
- 📤 Sync data from `data/gold/` to Neon database
- 🔍 Verify all required tables exist
- 📊 Display current stats (nonprofits, events, contacts, jurisdictions)
- 🌐 Test API endpoint if server is running

## Manual Setup Steps

If you prefer manual control:

### Sync Data to Neon

```bash
# Smart sync - detects schema changes and syncs efficiently
./scripts/data/sync-smart.sh

# Or full sync (slower but comprehensive)
./scripts/data/sync_to_neon_smart.py --force
```

### Verify Database

```python
# Check stats via Python
python -c "
import psycopg2
conn = psycopg2.connect('your_neon_database_url')
cur = conn.cursor()

# Check table counts
cur.execute('SELECT COUNT(*) FROM nonprofits_organizations')
print(f'Nonprofits: {cur.fetchone()[0]:,}')

cur.execute('SELECT COUNT(*) FROM events_meetings')
print(f'Events: {cur.fetchone()[0]:,}')

cur.execute('SELECT COUNT(*) FROM contacts_local_officials')
print(f'Contacts: {cur.fetchone()[0]:,}')
"
```

### Test API

```bash
# Start the API server
cd /home/developer/projects/open-navigator
NEON_DATABASE_URL_DEV="postgresql://user:password@host/db" \
  .venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# In another terminal, test stats endpoint
curl "http://localhost:8000/api/stats?state=MA" | python3 -m json.tool
```

## Common Issues

### Stats Show as `undefined` in UI

**Symptom**: Console shows `Stats data: undefined`

**Causes**:
1. **Wrong response path**: Frontend accessing `res.data.data` instead of `res.data`
2. **Database not synced**: Tables are empty or don't exist
3. **API error**: Check backend logs for database connection errors

**Fix**:
```bash
# 1. Check if data is in Neon
./scripts/setup-database.sh

# 2. Check API logs
tail -f logs/api.log

# 3. Test API directly
curl "http://localhost:8000/api/stats?state=MA"
```

### Database Connection Errors

**Error**: `Database error: could not connect to server`

**Fix**:
```bash
# Verify NEON_DATABASE_URL in .env
cat .env | grep NEON_DATABASE_URL

# Test connection
.venv/bin/python -c "
import psycopg2
import os
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(os.getenv('NEON_DATABASE_URL'))
print('✅ Connection successful')
"
```

### Empty Stats

**Error**: All stats show 0

**Fix**:
```bash
# Sync data from parquet files to database
./scripts/data/sync-smart.sh

# Or use full sync
.venv/bin/python scripts/data/sync_local_to_neon_simple.py
```

## Stats API Reference

### Endpoints

#### National Stats
```bash
GET /api/stats
```

Response:
```json
{
  "location": "United States",
  "level": "national",
  "jurisdictions": 32000,
  "nonprofits": 43726,
  "events": 50000,
  "contacts": 10000,
  "total_revenue": 1500000000,
  "total_assets": 3000000000
}
```

#### State Stats
```bash
GET /api/stats?state=MA
```

#### County Stats
```bash
GET /api/stats?state=MA&county=Suffolk%20County
```

#### City Stats
```bash
GET /api/stats?state=MA&city=Boston
```

### Error Responses

#### Database Error
```json
{
  "detail": "Database error: connection timeout"
}
```

**Status Code**: 500

#### No Data Available
```json
{
  "location": "Test City, XX",
  "level": "city",
  "jurisdictions": 0,
  "nonprofits": 0,
  "note": "No data available for this location"
}
```

**Status Code**: 200 (with empty stats)

## Frontend Integration

### Accessing Stats

```typescript
// Correct - stats are at res.data
const response = await api.get('/stats', { 
  params: { state: 'MA' } 
})
const stats = response.data  // ✅ Correct

// Wrong - don't use res.data.data
const stats = response.data.data  // ❌ Will be undefined
```

### Error Handling

```typescript
const { data: stats, isLoading, error } = useQuery({
  queryKey: ['stats', state],
  queryFn: async () => {
    const response = await api.get('/stats', { 
      params: { state } 
    })
    return response.data
  },
  onError: (error: any) => {
    console.error('Stats error:', error.response?.data?.detail || error.message)
    // Show user-friendly error message
  }
})

// Check for errors in the data
if (stats?.error) {
  return <div>⚠️ Stats unavailable: {stats.error}</div>
}
```

## Maintenance

### Update Data

```bash
# Quick update - only changed data
./scripts/data/sync-smart.sh

# Full refresh - all data
./scripts/data/sync-smart.sh --force
```

### Monitor Database Size

```sql
-- Check database size
SELECT 
  pg_size_pretty(pg_database_size(current_database())) as size;

-- Check table sizes
SELECT 
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Vacuum Database

```bash
# Connect to Neon database
.venv/bin/python -c "
import psycopg2
import os
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(os.getenv('NEON_DATABASE_URL'))
conn.autocommit = True
cur = conn.cursor()
cur.execute('VACUUM ANALYZE')
print('✅ Vacuum complete')
"
```

## Monitoring

### Health Check

```bash
# Check API health
curl http://localhost:8000/health

# Check stats availability
curl "http://localhost:8000/api/stats?state=MA" | jq '.nonprofits'
```

### Logs

```bash
# API logs
tail -f logs/api.log

# Frontend logs (browser console)
# Look for: 📊 [HomeModern] Stats data: ...
```

## See Also

- [Deployment Guide](../deployment/huggingface-spaces.md)
- [Data Sources](../data-sources/overview.md)
- [API Documentation](../development/api-reference.md)
