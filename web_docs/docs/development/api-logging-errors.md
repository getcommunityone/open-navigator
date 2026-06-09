---
sidebar_position: 5
---

# API Logging & Error Handling Implementation

## Summary of Changes

### 1. **Comprehensive Logging Configuration** ([api/main.py](https://github.com/getcommunityone/open-navigator/blob/main/api/main.py))

Added dual-output logging that appears in both files and container logs:

```python
# Console output (shows in HuggingFace container logs)
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | ...",
    level=settings.log_level
)

# File output with rotation and retention
logger.add(
    settings.log_file,
    rotation="500 MB",      # New file when size exceeds 500MB
    retention="10 days",    # Auto-delete logs older than 10 days
    level=settings.log_level
)
```

**Benefits:**
- ✅ Logs visible in HuggingFace Spaces container logs
- ✅ Automatic rotation prevents disk space issues
- ✅ 10-day retention for compliance and debugging

---

### 2. **Automatic Request Logging Middleware** ([api/main.py](https://github.com/getcommunityone/open-navigator/blob/main/api/main.py))

Every API request is automatically logged with:
- Request method & path
- Client IP address
- Response status code
- Request duration (milliseconds)
- Response size (bytes)

**Example Log Output:**
```
➡️  GET /api/bills?state=ma - Client: 192.168.1.1
✅ GET /api/bills?state=ma - Status: 200 - Duration: 45.32ms - Size: 12834 bytes
```

```
➡️  POST /api/search/ - Client: 10.0.0.5
⚠️  POST /api/search/ - Status: 404 - Duration: 12.45ms
```

```
➡️  GET /api/stats - Client: 172.16.0.1
❌ GET /api/stats - Status: 500 - Duration: 234.12ms
```

---

### 3. **Startup Data Validation** ([api/main.py](https://github.com/getcommunityone/open-navigator/blob/main/api/main.py))

API now validates data availability on startup:

```
================================================================================
🚀 STARTING Open Navigator API
================================================================================
Configuration: oral_health.policy_analysis
Log Level: INFO
Log File: logs/oral-health-policy-pulse.log

📊 VALIDATING DATA AVAILABILITY...
--------------------------------------------------------------------------------
  ✅ reference/jurisdictions_cities.parquet: 19,502 records (2.45 MB)
  ✅ reference/jurisdictions_counties.parquet: 3,143 records (0.34 MB)
  ✅ reference/causes_ntee_codes: 645 records (0.02 MB)

📍 STATE DATA AVAILABILITY:
  ✅ AL: nonprofits, officials, events
  ✅ AK: nonprofits, officials
  ... and 42 more states

  📊 Total states with data: 50

================================================================================
✅ API READY - 3/3 critical files available
================================================================================
```

**Benefits:**
- Catch missing data files before users encounter errors
- Clear visibility into what data is available
- Early warning for data pipeline issues

---

### 4. **Structured Error Responses** ([api/errors.py](https://github.com/getcommunityone/open-navigator/blob/main/api/errors.py))

Instead of raw error dumps, users now receive helpful, structured errors:

**Old Response (Bad):**
```json
{
  "detail": "HTTP Error: HTTP GET error on 'https://huggingface.co/datasets/...' (HTTP 404 Not Found)..."
}
```

**New Response (Good):**
```json
{
  "message": "No bills data available for MA",
  "error_type": "data_not_found",
  "technical_details": "Dataset 'CommunityOne/states-ma-bills-bills' not found on HuggingFace.\n\nFull error: HTTP GET error...",
  "suggestions": [
    "Try a different state - we have data for 50+ states",
    "Check /api/bills/map to see which states have bills data",
    "Contact support if you believe this data should be available"
  ],
  "metadata": {
    "dataset": "CommunityOne/states-ma-bills-bills",
    "state": "MA",
    "data_type": "bills"
  }
}
```

**Error Types Handled:**
- `data_not_found` - Missing datasets or files
- `network_error` - Timeouts and connection issues
- `query_error` - Invalid SQL/DuckDB queries
- `validation_error` - Invalid parameters
- `server_error` - Unexpected errors

**Updated Endpoints:**
- `/api/bills` - Bill search
- `/api/bills/sessions` - Session list
- `/api/bills/map` - Map data
- `/api/search` - Unified search
- `/api/search/suggest` - Suggestions

---

## Frontend Integration

The frontend can now show errors like this:

```typescript
// Error response structure
interface ErrorDetail {
  message: string;              // User-friendly message (always show)
  error_type: string;          // Error category
  technical_details?: string;  // Full error (show in expandable section)
  suggestions?: string[];      // Helpful tips
  metadata?: Record<string, any>;
}

// Example usage in React
try {
  const response = await api.get('/api/bills?state=MA');
} catch (error) {
  if (error.response?.data?.message) {
    // Show user-friendly message
    showError(error.response.data.message);
    
    // Option to expand technical details
    if (error.response.data.technical_details) {
      showExpandableDetails(error.response.data.technical_details);
    }
    
    // Show suggestions
    if (error.response.data.suggestions) {
      showSuggestions(error.response.data.suggestions);
    }
  }
}
```

**UI Example:**
```
❌ No bills data available for MA

💡 Suggestions:
  • Try a different state - we have data for 50+ states
  • Check /api/bills/map to see which states have bills data

[Show Technical Details ▼]
```

Expanded:
```
❌ No bills data available for MA

💡 Suggestions:
  • Try a different state - we have data for 50+ states
  • Check /api/bills/map to see which states have bills data

[Hide Technical Details ▲]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Dataset 'CommunityOne/states-ma-bills-bills' not found on HuggingFace.

Full error: HTTP GET error on 'https://huggingface.co/datasets/...'
```

---

## HuggingFace Container Logs

**Yes, logs will appear in HuggingFace Spaces container logs!**

The `logger.add(sys.stderr, ...)` configuration ensures all logs are written to stderr, which Docker/HuggingFace captures and displays in the container log console.

You'll see:
1. ✅ Startup validation logs
2. ✅ Request/response logs for every API call
3. ✅ Detailed error logs with context

---

## Configuration

Logging is controlled by environment variables in `.env`:

```bash
# Logging Configuration
LOG_LEVEL=INFO        # DEBUG, INFO, WARNING, ERROR
LOG_FILE=logs/oral-health-policy-pulse.log
```

**Log Rotation:**
- New file created when size exceeds 500 MB
- Format: `oral-health-policy-pulse.log`, `oral-health-policy-pulse.log.1`, etc.

**Log Retention:**
- Files older than 10 days are automatically deleted
- Prevents disk space issues in production

---

## Testing

Test the new error responses:

```bash
# Test missing data error
curl https://www.communityone.com/api/bills?state=ZZ

# Expected response:
{
  "message": "No bills data available for ZZ",
  "error_type": "data_not_found",
  "suggestions": ["Try a different state - we have data for 50+ states", ...],
  "metadata": {"state": "ZZ", "data_type": "bills"}
}
```

```bash
# View container logs (HuggingFace Spaces)
# Look for:
# - 🚀 STARTING... header
# - ➡️ Request logs
# - ✅/❌ Response logs
# - 📊 Data validation results
```

---

## Benefits

1. **Better User Experience**
   - Clear, actionable error messages
   - Suggestions for next steps
   - Option to see technical details

2. **Easier Debugging**
   - All requests logged with timing
   - Structured error context
   - Full stack traces in logs

3. **Production Ready**
   - Automatic log rotation
   - Configurable retention
   - Visible in container logs

4. **Compliance**
   - Complete audit trail of API usage
   - Automatic cleanup of old logs
   - Configurable log levels
