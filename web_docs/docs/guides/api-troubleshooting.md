---
sidebar_position: 5
---

# API Troubleshooting

Common issues when working with external APIs and their solutions.

## ProPublica Nonprofit Explorer API

### 500 Internal Server Error

**Symptom:**
```
ERROR | ProPublica API request failed: 500 Server Error: Internal Server Error
```

**Cause:**
The ProPublica API is experiencing server-side issues. This is not a problem with your code or configuration.

**Solution:**

The pipeline now includes **automatic retry logic** with exponential backoff:

1. **Automatic retries**: Up to 3 attempts per request
2. **Exponential backoff**: 2s, 4s, 8s delays between retries
3. **Graceful degradation**: Continues processing other states/NTEE codes if one fails

**What to do:**

1. **Wait and retry** - API issues are usually temporary:
   ```bash
   # Try again in 5-10 minutes
   python scripts/create_all_gold_tables.py --nonprofits-only --states AL MI
   ```

2. **Try different states** - Some states may work while others fail:
   ```bash
   # Try California and Texas instead
   python scripts/create_all_gold_tables.py --nonprofits-only --states CA TX
   ```

3. **Use cached data** - If you've successfully discovered data before:
   ```bash
   # Use existing bronze data
   python scripts/create_all_gold_tables.py --nonprofits-only --skip-discovery
   ```

4. **Check API status** - Visit the ProPublica website to check for known issues

5. **Reduce request volume** - Try fewer NTEE codes at once by modifying the script

:::tip Success Rate
The pipeline shows a **discovery summary** with success/failure counts:
```
DISCOVERY SUMMARY
Total requests: 12
Successful: 8 (66.7%)
No results: 2
Failed: 2
Total nonprofits discovered: 1,247
```

Even with some failures, you'll still get useful data!
:::

### Rate Limiting

**Symptom:**
```
Too many requests
```

**Solution:**
The pipeline includes automatic rate limiting (1 request/second). If you still encounter issues, the built-in retry logic will handle it.

### Timeout Errors

**Symptom:**
```
Request timeout
```

**Solution:**
- Automatic retry with exponential backoff
- Timeout increased to 30 seconds per request
- If all retries fail, continues to next request

## Alternative Data Sources

If ProPublica API is consistently unavailable, you can use these alternative sources:

### 1. IRS Tax Exempt Organization Search

Direct download of IRS data:
- https://www.irs.gov/charities-non-profits/tax-exempt-organization-search-bulk-data-downloads

### 2. Every.org API

Alternative nonprofit data source (requires registration):
- https://www.every.org/nonprofits

### 3. GuideStar/Candid

Comprehensive nonprofit database (some features require subscription):
- https://www.guidestar.org/

## Pipeline Best Practices

### Start Small

```bash
# Test with one state first
python scripts/create_all_gold_tables.py --nonprofits-only --states AL
```

### Check Cached Data

```bash
# See what's already been discovered
ls -lh data/cache/nonprofits/
ls -lh data/bronze/nonprofits/
```

### Monitor Progress

The pipeline provides detailed logging:
- ✅ Successful requests
- ⚠️  No results found
- ❌ Failed requests
- Progress counter (8/12)

### Use Skip Discovery

If you've already discovered data and just want to regenerate gold tables:

```bash
python scripts/create_all_gold_tables.py --nonprofits-only --skip-discovery
```

## Error Codes Reference

| Error Code | Meaning | Solution |
|------------|---------|----------|
| 500 | Server error | Retry later, API is down |
| 429 | Too many requests | Built-in rate limiting handles this |
| 404 | Not found | Check state/NTEE code validity |
| 403 | Forbidden | Check if API requires authentication |
| Timeout | Request took too long | Automatic retry with backoff |

## Getting Help

If issues persist:

1. **Check cache directory** - Data may have been partially downloaded:
   ```bash
   ls -lh data/cache/nonprofits/
   ```

2. **Review logs** - Detailed error messages help diagnose issues

3. **Try different parameters**:
   ```bash
   # Different states
   --states NY CA FL
   
   # Skip discovery (use cached)
   --skip-discovery
   ```

4. **File an issue** - Include:
   - Error messages
   - States/NTEE codes attempted
   - Timestamp
   - Discovery summary output

## Success Stories

**Expected behavior:**
- Some requests may fail (API issues)
- Pipeline continues processing
- You get partial results from successful requests
- Summary shows what worked vs. what failed

**Example successful run:**
```
DISCOVERY SUMMARY
Total requests: 24 (4 states × 6 NTEE codes)
Successful: 18 (75%)
No results: 4
Failed: 2
Total nonprofits discovered: 3,421

✅ Created gold tables with 3,421 nonprofit records!
```

Even with 2 failed requests, you got 3,400+ nonprofits!

---

## Quick Reference

```bash
# Standard run (handles failures gracefully)
python scripts/create_all_gold_tables.py --nonprofits-only --states AL MI

# Use cached data (skip API calls)
python scripts/create_all_gold_tables.py --nonprofits-only --skip-discovery

# Try different states if some fail
python scripts/create_all_gold_tables.py --nonprofits-only --states CA TX NY

# Run only meetings (no API calls)
python scripts/create_all_gold_tables.py --meetings-only
```
