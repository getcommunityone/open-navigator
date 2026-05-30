# Jurisdiction Discovery - Quick Start Guide

## No External APIs Required! 🎉

This discovery system uses **pattern-based matching** and **public datasets** only. No search API keys needed!

## Quick Start

### 1. Install Dependencies

All required packages are in `requirements.txt`:

```bash
pip install -r requirements.txt
```

Key packages:
- `httpx` - HTTP client for URL verification
- `beautifulsoup4` - HTML parsing for web crawling
- `pyspark` - Data processing
- `delta-spark` - Delta Lake storage

### 2. Initialize Delta Lake

```bash
python main.py init
```

### 3. Run Discovery

```bash
# Test with 100 jurisdictions
python main.py discover-jurisdictions --limit 100

# Single state
python main.py discover-jurisdictions --state CA

# Full discovery (~30k jurisdictions, 12-18 hours)
python main.py discover-jurisdictions
```

### 4. View Results

```bash
python main.py discovery-stats
```

Expected output:
```
📊 Jurisdiction Discovery Statistics

Bronze Layer (Raw Data):
  Total jurisdictions: 90,735
    - county: 3,143
    - municipality: 19,495
    - school_district: 13,051

Silver Layer (Discovered URLs):
  Total discoveries: 87
  Homepages found: 78 (89.7%)
  Minutes URLs found: 65 (74.7%)
  Avg confidence: 0.82

Gold Layer (Scraping Targets):
  Total targets: 65
  High priority: 42
```

### 5. Start Scraping

```bash
python main.py scrape-batch --source discovered --limit 50
```

## How It Works

### Strategy 1: GSA Domain Matching

The system directly matches jurisdiction names to the GSA .gov registry:

```python
"Sacramento County" → normalized: "sacramento"
GSA lookup → "sacramento.gov" ✓
Confidence: 1.0
```

### Strategy 2: URL Pattern Generation

Common government URL patterns are tested:

**Counties:**
- `co.{name}.{state}.us`
- `{name}county.gov`

**Cities:**
- `www.{name}.gov`
- `cityof{name}.gov`

**School Districts:**
- `{name}.k12.{state}.us`
- `{name}schools.org`

**Example:**
```python
"Fresno" (municipality, CA)
Test: https://www.fresno.gov → ✓ Found
Confidence: 0.9
```

### Strategy 3: Web Crawling

Once a homepage is found:
1. Crawl for "minutes", "agendas" links
2. Detect CMS platforms (Granicus, CivicClerk, etc.)
3. Boost confidence for .gov domains

## Performance

### Expected Results

- **Counties**: 85-95% discovery rate
- **Cities > 10k**: 75-90% discovery rate
- **School Districts**: 70-85% discovery rate
- **Processing Time**: ~3-5 min per 100 jurisdictions
- **Total Cost**: $0 (no API fees!)

### Optimization

**Parallel Processing:**
```bash
# Process multiple states in parallel
for state in CA TX NY FL PA; do
  python main.py discover-jurisdictions --state $state &
done
wait
```

**Databricks Notebook:**
For production runs, use the Databricks notebook:
1. Upload `notebooks/Jurisdiction_Discovery.py`
2. Create cluster (2-4 workers)
3. Run with Spark parallel processing

## Troubleshooting

### Low Discovery Rate

Check if URL patterns need adjustment for specific regions:

```python
# In discovery/url_discovery_agent.py
# Add regional patterns, e.g.:
if state == "MA":  # Massachusetts has unique patterns
    patterns.extend([
        (f"https://www.{name_slug}.ma.us", 0.85),
    ])
```

### Memory Errors

Process in smaller batches:

```bash
# By state
python main.py discover-jurisdictions --state CA

# Or by type
python main.py discover-jurisdictions --type county
```

### Census Download Fails

Cached for 7 days by default. For manual download:

1. Download from: https://www.census.gov/programs-surveys/gus.html
2. Place in `data/cache/census/`
3. Rerun discovery

## Next Steps

1. **Test Discovery**: Run with `--limit 100`
2. **Review Results**: Check `discovery-stats`
3. **Full Run**: Remove limit for production
4. **Start Scraping**: Use discovered URLs
5. **Schedule Re-Discovery**: Monthly updates

## Cost

**Total: $0** 🎉

- No API fees
- Uses free public datasets
- Only local/cloud compute costs

Compare to legacy approach:
- ~~Google Search API: $150~~
- ~~Bing Search API: $90~~
- **Pattern Matching: $0**

---

**Ready to discover 90,000+ government websites with zero external dependencies!** 🚀
# Jurisdiction Discovery System - Setup Guide

## Quick Start

### 1. Configure Search APIs

The discovery system requires search API keys to find government websites. You can use either Google Custom Search or Bing Search (or both for redundancy).

#### Option A: Google Custom Search API

1. **Enable the API**
   - Visit [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing
   - Enable "Custom Search API"

2. **Create API Key**
   - Go to "Credentials" → "Create Credentials" → "API Key"
   - Copy your API key

3. **Create Search Engine**
   - Visit [Google Custom Search](https://cse.google.com/cse/all)
   - Click "Add" to create new search engine
   - Set "Sites to search" to: `*.gov` (to focus on government sites)
   - Copy your "Search Engine ID"

4. **Add to .env**
   ```bash
   GOOGLE_SEARCH_API_KEY=your_google_api_key
   GOOGLE_SEARCH_ENGINE_ID=your_search_engine_id
   ```

**Pricing:** First 100 queries/day free, then $5 per 1,000 queries

#### Option B: Bing Search API

1. **Create Azure Account**
   - Visit [Azure Portal](https://portal.azure.com/)
   - Create account (free tier available)

2. **Create Bing Search Resource**
   - Click "Create a resource" → Search for "Bing Search v7"
   - Select pricing tier (F1 free tier: 1k queries/month)
   - Create resource

3. **Get API Key**
   - Go to your Bing Search resource
   - Click "Keys and Endpoint"
   - Copy one of the keys

4. **Add to .env**
   ```bash
   BING_SEARCH_API_KEY=your_bing_api_key
   ```

**Pricing:** Free tier: 1,000 queries/month; Paid: $3 per 1,000 queries

### 2. Install Dependencies

All required packages are already in `requirements.txt`:

```bash
pip install -r requirements.txt
```

Key packages for discovery:
- `httpx==0.27.0` - Async HTTP client
- `beautifulsoup4==4.12.2` - HTML parsing
- `pyspark==3.5.0` - Data processing
- `delta-spark==3.0.0` - Delta Lake

### 3. Initialize Delta Lake

```bash
python main.py init
```

This creates the necessary Delta Lake tables.

### 4. Run Discovery Pipeline

#### Test Run (100 jurisdictions)

```bash
python main.py discover-jurisdictions --limit 100
```

Expected output:
```
📊 Bronze Layer Complete:
   Total records: 90,735
   Counties: 3,143
   Municipalities: 19,495
   ...

📊 URL Discovery Complete:
   Attempted: 100
   Successful: 87
   Homepages found: 87
   Minutes URLs found: 65
   Avg confidence: 0.72

📊 Gold Layer Complete:
   Scraping targets created: 65
   High priority (>150): 42
   ...

✅ Discovery Complete!
```

#### State-Specific Discovery

```bash
python main.py discover-jurisdictions --state CA
```

#### Full Production Run

```bash
# Discovers all ~30,000 high-priority jurisdictions
# Takes 4-6 hours with parallel processing
python main.py discover-jurisdictions
```

### 5. View Statistics

```bash
python main.py discovery-stats
```

Output:
```
📊 Jurisdiction Discovery Statistics

Bronze Layer (Raw Data):
  Total jurisdictions: 90,735
    - county: 3,143
    - municipality: 19,495
    - school_district: 13,051
    - special_district: 38,542
    - township: 16,504

Silver Layer (Discovered URLs):
  Total discoveries: 27,483
  Homepages found: 24,125 (87.8%)
  Minutes URLs found: 18,562 (67.5%)
  Avg confidence: 0.74

Gold Layer (Scraping Targets):
  Total targets: 18,562
  High priority: 12,340
    - pending: 18,562
```

### 6. Start Scraping

```bash
# Scrape high-priority targets
python main.py scrape-batch --source discovered --limit 50 --priority 150

# Or scrape all pending targets (use with caution!)
python main.py scrape-batch --source discovered --limit 1000
```

## Using Databricks Notebook

For production deployment on Databricks:

1. **Upload Notebook**
   ```bash
   databricks workspace import notebooks/Jurisdiction_Discovery.py \
     -l PYTHON \
     -f SOURCE \
     /Users/your-email@company.com/Jurisdiction_Discovery
   ```

2. **Configure Secrets**
   ```bash
   # Create secret scope
   databricks secrets create-scope oral-health-app
   
   # Add API keys
   databricks secrets put-secret oral-health-app google-search-api-key
   databricks secrets put-secret oral-health-app google-search-engine-id
   databricks secrets put-secret oral-health-app bing-search-api-key
   ```

3. **Create Cluster**
   - Runtime: 14.3 LTS or higher
   - Node type: Standard_DS3_v2 (or similar)
   - Workers: 2-4 (for parallel processing)
   - Libraries: All from `requirements.txt`

4. **Run Notebook**
   - Open notebook in Databricks workspace
   - Attach to cluster
   - Run all cells

## Cost Estimation

### API Costs

For discovering 30,000 jurisdictions:

| Provider | Free Tier | Paid Cost | Total Cost |
|----------|-----------|-----------|------------|
| Google | 100/day (3,000/month) | $5/1k | ~$135 |
| Bing | 1,000/month | $3/1k | ~$87 |
| **Both** | 4,000 free | Rest on Bing | ~$78 |

**Recommendation:** Use both APIs to maximize free tier usage.

### Compute Costs

**Local Development:**
- Free (uses local resources)
- ~4-6 hours for full discovery

**Databricks:**
- Cluster: ~$2-4/hour
- Total: ~$8-24 for full discovery
- Can use spot instances to reduce cost

### Re-discovery Schedule

- **Monthly**: Catch URL changes and new jurisdictions
- **Cost**: ~$10-20/month (many URLs cached)

## Troubleshooting

### Low Discovery Rate

**Problem:** Only finding 30-40% of URLs

**Solutions:**
1. Check API keys are correct
2. Verify API quotas not exceeded
3. Review failed discoveries:
   ```python
   from pyspark.sql.functions import col
   silver_df = spark.read.format("delta").load("silver/discovered_urls")
   failed = silver_df.filter(col("homepage_url").isNull())
   failed.show(20, truncate=False)
   ```

### Memory Errors

**Problem:** Out of memory during discovery

**Solutions:**
1. Process by state:
   ```bash
   for state in CA TX NY FL PA OH IL MI NC GA; do
     python main.py discover-jurisdictions --state $state
   done
   ```

2. Increase Spark memory:
   ```python
   spark = SparkSession.builder \
     .config("spark.driver.memory", "8g") \
     .config("spark.executor.memory", "8g") \
     .getOrCreate()
   ```

3. Use Databricks cluster (more memory available)

### API Rate Limits

**Problem:** Hitting rate limits too quickly

**Solutions:**
1. Reduce batch size in `url_discovery_agent.py`:
   ```python
   batch_size = 5  # Instead of 10
   ```

2. Add delays between batches:
   ```python
   await asyncio.sleep(1)  # After each batch
   ```

3. Use both Google and Bing to distribute load

### Census Data Download Fails

**Problem:** Census Bureau site unreachable

**Solutions:**
1. Use cached data (automatically cached for 7 days)
2. Manual download:
   ```bash
   # Download files manually from Census Bureau
   # Place in data/cache/census/
   ```

3. Check Census Bureau site status: https://www.census.gov/programs-surveys/gus.html

## Monitoring Progress

### Check Discovery Status

```sql
-- In Databricks SQL or Spark
SELECT 
    state,
    COUNT(*) as total,
    COUNT(homepage_url) as found,
    ROUND(COUNT(homepage_url) * 100.0 / COUNT(*), 1) as success_rate
FROM silver.discovered_urls
GROUP BY state
ORDER BY success_rate DESC;
```

### Track Scraping Progress

```sql
SELECT 
    scraping_status,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM gold.scraping_targets), 1) as pct
FROM gold.scraping_targets
GROUP BY scraping_status;
```

## Next Steps

Once discovery is complete:

1. **Review High-Priority Targets**
   - Check for false positives
   - Validate CMS platform detection

2. **Start Scraping**
   - Begin with top 100 high-priority sites
   - Monitor document quality
   - Adjust priority scores as needed

3. **Schedule Automation**
   - Set up monthly re-discovery job
   - Monitor for new jurisdictions
   - Track URL changes

4. **Integration**
   - Connect to existing scraper agents
   - Feed documents to classification pipeline
   - Generate advocacy opportunities

## Support

For issues or questions:
- GitHub Issues: [github.com/getcommunityone/open-navigator-for-engagement/issues](https://github.com/getcommunityone/open-navigator-for-engagement/issues)
- Documentation: [JURISDICTION_DISCOVERY.md](JURISDICTION_DISCOVERY.md)

---

**Ready to discover 90,000+ government websites!** 🦷✨
