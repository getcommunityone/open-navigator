# Databricks notebook source
# MAGIC %md
# MAGIC # Jurisdiction Discovery Pipeline
# MAGIC 
# MAGIC This notebook runs the complete jurisdiction discovery system to identify
# MAGIC all 90,000+ local government units in the United States and discover their
# MAGIC official websites and meeting minutes URLs.
# MAGIC 
# MAGIC **Pipeline Steps:**
# MAGIC 1. **Bronze Layer**: Ingest Census Bureau + GSA .gov domain data
# MAGIC 2. **Silver Layer**: Discover URLs via pattern matching + GSA registry
# MAGIC 3. **Gold Layer**: Create prioritized scraping targets
# MAGIC 
# MAGIC **Requirements:**
# MAGIC - Databricks cluster with Delta Lake
# MAGIC - ~2-4 hours for full 30,000 jurisdiction discovery
# MAGIC - **No external API keys needed!** ✅

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup & Configuration

# COMMAND ----------

# Install dependencies (if not in cluster init script)
%pip install httpx beautifulsoup4

# COMMAND ----------

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, "/Workspace/Repos/open-navigator")

from scripts.discovery.discovery_pipeline import DiscoveryPipeline
from config import settings
from pyspark.sql.functions import col, count, avg, when
import asyncio

print("✅ Imports successful")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify Configuration
# MAGIC 
# MAGIC Pattern-based discovery uses **no external APIs** - only public datasets!

# COMMAND ----------

# Verify configuration
print(f"Delta Lake Path: {settings.delta_lake_path}")
print("✅ Discovery method: Pattern-based matching")
print("✅ No external API keys required")
print("✅ Zero cost discovery!")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Bronze Layer - Ingest Raw Data
# MAGIC 
# MAGIC Downloads and ingests:
# MAGIC - Census Bureau Government Integrated Directory (90,735 jurisdictions)
# MAGIC - GSA .gov domain list (12,000+ validated domains)

# COMMAND ----------

pipeline = DiscoveryPipeline()

# Run bronze ingestion
bronze_stats = await pipeline.run_bronze_ingestion()

print("\n📊 Bronze Layer Complete:")
print(f"   Total records: {bronze_stats['total_records']:,}")
print(f"   Counties: {bronze_stats['by_type'].get('county', 0):,}")
print(f"   Municipalities: {bronze_stats['by_type'].get('municipality', 0):,}")
print(f"   School Districts: {bronze_stats['by_type'].get('school_district', 0):,}")
print(f"   Special Districts: {bronze_stats['by_type'].get('special_district', 0):,}")
print(f"   Townships: {bronze_stats['by_type'].get('township', 0):,}")
print(f"   .gov domains: {bronze_stats['gov_domains']:,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify Bronze Data

# COMMAND ----------

# Load bronze unified table
bronze_df = spark.read.format("delta").load(f"{settings.delta_lake_path}/bronze/jurisdictions/unified")

display(bronze_df.limit(10))

# COMMAND ----------

# Bronze statistics
bronze_df.groupBy("jurisdiction_type", "state").count().display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Silver Layer - URL Discovery
# MAGIC 
# MAGIC **Options:**
# MAGIC - `limit`: Test with small number first (e.g., 100)
# MAGIC - `state_filter`: Focus on specific state (e.g., "CA")
# MAGIC - `type_filter`: Focus on type (e.g., "county")
# MAGIC 
# MAGIC **Note:** Full discovery of 30,000 targets takes ~4-6 hours

# COMMAND ----------

# TEST RUN: Discover 100 jurisdictions
discovery_stats = await pipeline.run_url_discovery(limit=100)

print("\n📊 URL Discovery Complete:")
print(f"   Attempted: {discovery_stats['attempted']:,}")
print(f"   Successful: {discovery_stats['successful']:,}")
print(f"   Homepages found: {discovery_stats['homepages']:,}")
print(f"   Minutes URLs found: {discovery_stats['minutes_urls']:,}")
print(f"   Avg confidence: {discovery_stats['avg_confidence']:.2f}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Full Production Run (Uncomment when ready)
# MAGIC 
# MAGIC ```python
# MAGIC # FULL RUN: Discover all jurisdictions (4-6 hours)
# MAGIC # discovery_stats = await pipeline.run_url_discovery(limit=None)
# MAGIC 
# MAGIC # OR by state
# MAGIC # discovery_stats = await pipeline.run_url_discovery(state_filter="CA")
# MAGIC 
# MAGIC # OR by type
# MAGIC # discovery_stats = await pipeline.run_url_discovery(type_filter="county")
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify Silver Data

# COMMAND ----------

# Load discovered URLs
silver_df = spark.read.format("delta").load(f"{settings.delta_lake_path}/silver/discovered_urls")

display(silver_df.limit(10))

# COMMAND ----------

# Discovery success rates by state
silver_df.groupBy("state").agg(
    count("*").alias("total"),
    count(when(col("homepage_url").isNotNull(), 1)).alias("homepages"),
    count(when(col("minutes_url").isNotNull(), 1)).alias("minutes"),
    avg("confidence_score").alias("avg_confidence")
).orderBy(col("total").desc()).display()

# COMMAND ----------

# CMS platform detection
silver_df.groupBy("cms_platform").count().orderBy(col("count").desc()).display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Gold Layer - Create Scraping Targets
# MAGIC 
# MAGIC Filters to high-quality targets:
# MAGIC - Has minutes URL
# MAGIC - Confidence score > 0.6
# MAGIC - Prioritized by population and domain quality

# COMMAND ----------

gold_stats = pipeline.create_scraping_targets()

print("\n📊 Gold Layer Complete:")
print(f"   Scraping targets created: {gold_stats['targets_created']:,}")
print(f"   High priority (>150): {gold_stats['high_priority']:,}")
print(f"   Medium priority (100-150): {gold_stats['medium_priority']:,}")
print(f"   Low priority (<100): {gold_stats['low_priority']:,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify Gold Data

# COMMAND ----------

# Load scraping targets
gold_df = spark.read.format("delta").load(f"{settings.delta_lake_path}/gold/scraping_targets")

display(gold_df.orderBy(col("priority_score").desc()).limit(20))

# COMMAND ----------

# Priority distribution
gold_df.groupBy(
    when(col("priority_score") > 150, "High")
    .when(col("priority_score") > 100, "Medium")
    .otherwise("Low").alias("priority_tier")
).count().display()

# COMMAND ----------

# By jurisdiction type
gold_df.groupBy("jurisdiction_type").agg(
    count("*").alias("total"),
    avg("priority_score").alias("avg_priority"),
    avg("population").alias("avg_population")
).orderBy(col("total").desc()).display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary Dashboard

# COMMAND ----------

# Complete pipeline summary
summary = f"""
╔══════════════════════════════════════════════════════════════╗
║         JURISDICTION DISCOVERY PIPELINE SUMMARY              ║
╚══════════════════════════════════════════════════════════════╝

Bronze Layer (Raw Data):
  └─ Total jurisdictions: {bronze_stats['total_records']:,}
  └─ .gov domains: {bronze_stats['gov_domains']:,}

Silver Layer (URL Discovery):
  └─ URLs discovered: {discovery_stats['successful']:,}
  └─ Success rate: {discovery_stats['successful']/discovery_stats['attempted']*100:.1f}%
  └─ With minutes URLs: {discovery_stats['minutes_urls']:,}
  └─ Avg confidence: {discovery_stats['avg_confidence']:.2f}

Gold Layer (Scraping Targets):
  └─ Ready to scrape: {gold_stats['targets_created']:,}
  └─ High priority: {gold_stats['high_priority']:,}
  
✅ Pipeline Complete! Ready for scraping.
"""

print(summary)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next Steps
# MAGIC 
# MAGIC 1. **Review high-priority targets:**
# MAGIC    ```python
# MAGIC    high_priority = gold_df.filter(col("priority_score") > 150)
# MAGIC    display(high_priority)
# MAGIC    ```
# MAGIC 
# MAGIC 2. **Start scraping:**
# MAGIC    - Run `Scraping_Agent.py` notebook
# MAGIC    - Or use CLI: `python main.py scrape-batch --source discovered --limit 100`
# MAGIC 
# MAGIC 3. **Monitor progress:**
# MAGIC    ```sql
# MAGIC    SELECT scraping_status, COUNT(*) 
# MAGIC    FROM gold.scraping_targets 
# MAGIC    GROUP BY scraping_status
# MAGIC    ```
# MAGIC 
# MAGIC 4. **Schedule re-discovery:**
# MAGIC    - Run monthly to catch new URLs
# MAGIC    - Use Databricks workflows for automation

# COMMAND ----------

# MAGIC %md
# MAGIC ## Troubleshooting
# MAGIC 
# MAGIC ### Low discovery success rate?
# MAGIC 
# MAGIC 1. Check API keys:
# MAGIC    ```python
# MAGIC    print(f"Google: {settings.google_search_api_key[:10]}..." if settings.google_search_api_key else "Not set")
# MAGIC    print(f"Bing: {settings.bing_search_api_key[:10]}..." if settings.bing_search_api_key else "Not set")
# MAGIC    ```
# MAGIC 
# MAGIC 2. Check API quotas:
# MAGIC    - Google: 100/day free, then $5/1000 queries
# MAGIC    - Bing: $3/1000 queries
# MAGIC 
# MAGIC 3. Review failed discoveries:
# MAGIC    ```python
# MAGIC    failed = silver_df.filter(col("homepage_url").isNull())
# MAGIC    display(failed)
# MAGIC    ```
# MAGIC 
# MAGIC ### Memory errors?
# MAGIC 
# MAGIC 1. Process by state:
# MAGIC    ```python
# MAGIC    for state in ["CA", "TX", "NY", ...]:
# MAGIC        await pipeline.run_url_discovery(state_filter=state)
# MAGIC    ```
# MAGIC 
# MAGIC 2. Increase cluster size or driver memory
