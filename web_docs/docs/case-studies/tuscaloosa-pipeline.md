---
sidebar_position: 3
---

# Tuscaloosa Policy Pulse Pipeline Guide

This guide shows how to run the complete 4-step pipeline for Tuscaloosa, AL.

## Prerequisites

```bash
source .venv/bin/activate
cd /home/developer/projects/open-navigator
```

---

## Step 1: GATHER - Collect Meeting Data

### 1.1 Tuscaloosa City Government (✅ Working)

```bash
python main.py scrape \
  --state AL \
  --municipality "Tuscaloosa" \
  --url https://tuscaloosaal.suiteonemedia.com \
  --platform suiteonemedia \
  --max-events 0 \
  --start-year 0 \
  --include-social
```

**Output:** `output/tuscaloosa/suiteonemedia_*.json`

### 1.2 Tuscaloosa City Schools (⚠️ Requires Manual Cookies)

The eBoard platform requires browser cookies to bypass Incapsula protection:

1. Visit https://simbli.eboardsolutions.com/SB_Meetings/SB_MeetingListing.aspx?S=2088
2. Complete any verification
3. Export cookies with [EditThisCookie](https://chrome.google.com/webstore/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg)
4. Save to `eboard_cookies.json`

Then run:

```bash
python main.py scrape \
  --state AL \
  --municipality "Tuscaloosa City Schools" \
  --url http://simbli.eboardsolutions.com/index.aspx?s=2088 \
  --platform eboard \
  --max-events 0 \
  --start-year 0 \
  --no-include-social
```

**Output:** `output/tuscaloosa_city_schools/eboard_*.json`

### 1.3 Consolidate Data

Combine all Tuscaloosa sources:

```bash
python -c "
import json
from pathlib import Path

# Load all Tuscaloosa documents
all_docs = []
for json_file in Path('output/tuscaloosa').glob('*.json'):
    with open(json_file) as f:
        docs = json.load(f)
        all_docs.extend(docs)

for json_file in Path('output/tuscaloosa_city_schools').glob('*.json'):
    with open(json_file) as f:
        docs = json.load(f)
        all_docs.extend(docs)

print(f'✓ Gathered {len(all_docs)} documents from Tuscaloosa')

# Save consolidated data
with open('output/tuscaloosa_all.json', 'w') as f:
    json.dump(all_docs, f, indent=2)
"
```

---

## Step 2: STRUCTURE - Process with AI

### 2.1 Load Data into Delta Lake (Bronze Layer)

```python
from pipeline.delta_lake import DeltaLakePipeline
import json

pipeline = DeltaLakePipeline()

# Load raw documents
with open('output/tuscaloosa_all.json') as f:
    documents = json.load(f)

# Write to Bronze layer (raw data)
pipeline.write_raw_documents(documents)

print(f"✓ Loaded {len(documents)} documents to Bronze layer")
```

### 2.2 Classify Documents (Silver Layer)

Run the classifier agent to tag documents by topic:

```bash
python -c "
import asyncio
from agents.classifier import ClassifierAgent
from pipeline.delta_lake import DeltaLakePipeline

async def classify_tuscaloosa():
    pipeline = DeltaLakePipeline()
    classifier = ClassifierAgent()
    
    # Get documents from Bronze
    spark = pipeline.get_spark_session()
    df = spark.read.format('delta').load('data/delta/bronze/documents')
    
    # Filter to Tuscaloosa only
    tuscaloosa_df = df.filter(
        (df.municipality.like('%Tuscaloosa%')) | 
        (df.state == 'AL')
    )
    
    documents = tuscaloosa_df.collect()
    print(f'Classifying {len(documents)} Tuscaloosa documents...')
    
    classified = []
    for doc in documents:
        result = await classifier.classify(
            content=doc.content,
            municipality=doc.municipality
        )
        classified.append({**doc.asDict(), **result})
    
    # Write to Silver layer
    pipeline.write_classified_documents(classified)
    print(f'✓ Classified {len(classified)} documents')

asyncio.run(classify_tuscaloosa())
"
```

**Classifications include:**
- Health policy topics (dental health, vaccination, nutrition, etc.)
- Education topics
- Budget/finance
- Infrastructure
- Public safety

### 2.3 Sentiment Analysis (Silver Layer)

```bash
python -c "
import asyncio
from agents.sentiment import SentimentAgent
from pipeline.delta_lake import DeltaLakePipeline

async def analyze_sentiment():
    pipeline = DeltaLakePipeline()
    sentiment_agent = SentimentAgent()
    
    # Get classified documents
    spark = pipeline.get_spark_session()
    df = spark.read.format('delta').load('data/delta/silver/classified_documents')
    
    tuscaloosa_df = df.filter(df.municipality.like('%Tuscaloosa%'))
    documents = tuscaloosa_df.collect()
    
    print(f'Analyzing sentiment for {len(documents)} documents...')
    
    enriched = []
    for doc in documents:
        sentiment = await sentiment_agent.analyze(doc.content)
        enriched.append({**doc.asDict(), 'sentiment': sentiment})
    
    pipeline.write_enriched_documents(enriched)
    print(f'✓ Sentiment analysis complete')

asyncio.run(analyze_sentiment())
"
```

---

## Step 3: ANALYZE - Extract Insights

### 3.1 Health Policy Analysis

Find all health-related policies in Tuscaloosa:

```python
from pipeline.delta_lake import DeltaLakePipeline

pipeline = DeltaLakePipeline()
spark = pipeline.get_spark_session()

# Query Gold layer
df = spark.read.format('delta').load('data/delta/gold/policy_insights')

# Filter to health topics in Tuscaloosa
health_df = df.filter(
    (df.municipality.like('%Tuscaloosa%')) &
    (df.topic.isin(['dental_health', 'health', 'vaccination', 'nutrition']))
)

# Aggregate by topic
summary = health_df.groupBy('topic').agg(
    {'document_id': 'count', 'sentiment_score': 'avg'}
).collect()

print("\n=== Tuscaloosa Health Policy Summary ===")
for row in summary:
    print(f"{row.topic}: {row['count(document_id)']} documents, "
          f"avg sentiment: {row['avg(sentiment_score)']:.2f}")
```

### 3.2 Time Series Analysis

Track policy trends over time:

```python
from pyspark.sql.functions import year, month, count

df = spark.read.format('delta').load('data/delta/gold/policy_insights')

tuscaloosa_df = df.filter(df.municipality.like('%Tuscaloosa%'))

# Group by year and topic
trends = tuscaloosa_df.groupBy(
    year('meeting_date').alias('year'),
    month('meeting_date').alias('month'),
    'topic'
).agg(count('*').alias('count')).orderBy('year', 'month')

trends.show(50)
```

### 3.3 Cross-Jurisdiction Comparison

Compare Tuscaloosa to similar cities:

```python
# Find cities with similar population
similar_cities_df = df.filter(
    (df.state == 'AL') |  # Other Alabama cities
    (df.municipality.like('%Mobile%')) |
    (df.municipality.like('%Montgomery%'))
)

# Compare health policy volume
comparison = similar_cities_df.groupBy('municipality').agg(
    count('*').alias('total_policies'),
    countDistinct('topic').alias('unique_topics')
).orderBy('total_policies', ascending=False)

comparison.show()
```

---

## Step 4: DELIVER - Create Insights Products

### 4.1 Executive Briefing

Generate a policy briefing for Tuscaloosa leaders:

```bash
python -c "
from datetime import datetime, timedelta
from pipeline.delta_lake import DeltaLakePipeline

pipeline = DeltaLakePipeline()
spark = pipeline.get_spark_session()

df = spark.read.format('delta').load('data/delta/gold/policy_insights')

# Last 90 days
recent_date = datetime.now() - timedelta(days=90)
recent_df = df.filter(
    (df.municipality.like('%Tuscaloosa%')) &
    (df.meeting_date >= recent_date)
)

print('\\n' + '='*60)
print('TUSCALOOSA POLICY BRIEFING - Last 90 Days')
print('='*60)

# Top topics
topics = recent_df.groupBy('topic').count().orderBy('count', ascending=False).take(10)
print('\\nTop Policy Topics:')
for i, row in enumerate(topics, 1):
    print(f'{i}. {row.topic}: {row.count} items')

# Recent highlights
highlights = recent_df.orderBy('meeting_date', ascending=False).take(5)
print('\\nRecent Highlights:')
for doc in highlights:
    print(f'\\n- {doc.meeting_date.strftime(\"%Y-%m-%d\")}: {doc.title[:80]}')
    print(f'  Topic: {doc.topic}, Sentiment: {doc.sentiment}')
"
```

### 4.2 Searchable Dashboard Data

Export data for a web dashboard:

```bash
python -c "
import json
from pipeline.delta_lake import DeltaLakePipeline

pipeline = DeltaLakePipeline()
spark = pipeline.get_spark_session()

df = spark.read.format('delta').load('data/delta/gold/policy_insights')
tuscaloosa_df = df.filter(df.municipality.like('%Tuscaloosa%'))

# Convert to JSON for web dashboard
dashboard_data = []
for row in tuscaloosa_df.collect():
    dashboard_data.append({
        'id': row.document_id,
        'date': row.meeting_date.isoformat(),
        'title': row.title,
        'topic': row.topic,
        'sentiment': row.sentiment,
        'url': row.source_url,
        'municipality': row.municipality
    })

# Save for frontend
with open('frontend/src/data/tuscaloosa_policies.json', 'w') as f:
    json.dump(dashboard_data, f, indent=2)

print(f'✓ Exported {len(dashboard_data)} policies for dashboard')
"
```

### 4.3 Monitoring Alerts

Set up keyword monitoring for specific topics:

```bash
python -c "
from alerts.keyword_monitor import KeywordMonitor

monitor = KeywordMonitor()

# Monitor health-related keywords
health_keywords = [
    'dental', 'dentist', 'tooth', 'teeth', 'fluoride',
    'oral health', 'school nurse', 'vaccination', 'immunization'
]

monitor.watch_jurisdiction(
    municipality='Tuscaloosa',
    state='AL',
    keywords=health_keywords,
    alert_email='your-email@example.com'
)

print('✓ Monitoring alerts configured for Tuscaloosa health policies')
"
```

### 4.4 Publish to HuggingFace

Share Tuscaloosa data with researchers:

```bash
python main.py publish-to-hf --dataset tuscaloosa
```

This creates a public dataset at: `huggingface.co/datasets/your-org/tuscaloosa-policy-pulse`

---

## Quick Start: Run Complete Pipeline

```bash
#!/bin/bash
# complete_tuscaloosa_pipeline.sh

set -e

echo "=== TUSCALOOSA POLICY PULSE PIPELINE ==="

# Step 1: Gather
echo "Step 1: Gathering data..."
python main.py scrape \
  --state AL \
  --municipality "Tuscaloosa" \
  --url https://tuscaloosaal.suiteonemedia.com \
  --platform suiteonemedia \
  --max-events 0 \
  --start-year 0 \
  --include-social

# Note: eBoard scraping requires manual cookies (see Step 1.2 above)

# Step 2: Structure
echo "Step 2: Loading to Delta Lake..."
python -c "
from pipeline.delta_lake import DeltaLakePipeline
import json
from pathlib import Path

pipeline = DeltaLakePipeline()
all_docs = []

for json_file in Path('output/tuscaloosa').glob('*.json'):
    with open(json_file) as f:
        all_docs.extend(json.load(f))

pipeline.write_raw_documents(all_docs)
print(f'✓ Loaded {len(all_docs)} documents')
"

echo "Step 3: Classifying documents..."
python -c "
import asyncio
from agents.classifier import ClassifierAgent
from pipeline.delta_lake import DeltaLakePipeline

async def run():
    classifier = ClassifierAgent()
    pipeline = DeltaLakePipeline()
    spark = pipeline.get_spark_session()
    
    df = spark.read.format('delta').load('data/delta/bronze/documents')
    docs = df.filter(df.municipality.like('%Tuscaloosa%')).collect()
    
    classified = []
    for doc in docs:
        result = await classifier.classify(doc.content, doc.municipality)
        classified.append({**doc.asDict(), **result})
    
    pipeline.write_classified_documents(classified)
    print(f'✓ Classified {len(classified)} documents')

asyncio.run(run())
"

# Step 4: Deliver
echo "Step 4: Generating briefing..."
python -c "
from pipeline.delta_lake import DeltaLakePipeline

pipeline = DeltaLakePipeline()
spark = pipeline.get_spark_session()

df = spark.read.format('delta').load('data/delta/silver/classified_documents')
tuscaloosa = df.filter(df.municipality.like('%Tuscaloosa%'))

print('\\n=== TUSCALOOSA POLICY SUMMARY ===')
topics = tuscaloosa.groupBy('topic').count().orderBy('count', ascending=False)
topics.show()
"

echo "✓ Pipeline complete!"
```

---

## Monitoring & Maintenance

### Daily Updates

Run scraper daily to get new meetings:

```bash
# Add to crontab
0 6 * * * cd /home/developer/projects/open-navigator && source .venv/bin/activate && python main.py scrape --state AL --municipality Tuscaloosa --url https://tuscaloosaal.suiteonemedia.com --platform suiteonemedia --max-events 10
```

### View Current Status

```bash
python -c "
from pipeline.delta_lake import DeltaLakePipeline

pipeline = DeltaLakePipeline()
spark = pipeline.get_spark_session()

print('\\n=== DATA PIPELINE STATUS ===')
print('\\nBronze Layer (Raw):')
bronze = spark.read.format('delta').load('data/delta/bronze/documents')
print(f'  Total documents: {bronze.count()}')
print(f'  Tuscaloosa documents: {bronze.filter(bronze.municipality.like(\"%Tuscaloosa%\")).count()}')

print('\\nSilver Layer (Classified):')
silver = spark.read.format('delta').load('data/delta/silver/classified_documents')
print(f'  Total classified: {silver.count()}')
print(f'  Tuscaloosa classified: {silver.filter(silver.municipality.like(\"%Tuscaloosa%\")).count()}')
"
```

---

## Step 5: COMMUNITY BRIDGE - Connect Government Decisions with Nonprofits

### Quick Start: Automated Nonprofit Discovery

```bash
# Discover all Tuscaloosa nonprofits using free APIs (ProPublica, IRS)
source .venv/bin/activate
python scripts/discover_tuscaloosa_nonprofits.py

# Output: frontend/policy-dashboards/src/data/tuscaloosa_nonprofits.json
# Contains: Financial data, NTEE codes, mission statements for 50-200+ orgs
```

**What this does:**
- ✅ Searches ProPublica Nonprofit Explorer API for all Tuscaloosa organizations
- ✅ Filters by relevant NTEE codes (health, education, youth, food, religion)
- ✅ Pulls 5+ years of IRS Form 990 financial data
- ✅ Enriches with mission statements from Every.org
- ✅ Exports in frontend-compatible JSON format
- ✅ Caches results for fast repeated runs

---

### Overview: The Split-Screen Strategy

When government says "no" to a policy, show citizens **who's already saying "yes"** - the nonprofits and churches filling the gap.

**The Flow:**
1. **Identify the Neglect**: Board tabled dental screening partnership
2. **Highlight the Logic**: "Legal risk concerns" used to defer
3. **Bridge the Gap**: 3 local nonprofits providing free screenings to 3,250 students

See full documentation: [docs/SPLIT_SCREEN_SYSTEM.md](docs/SPLIT_SCREEN_SYSTEM.md)

---

### 5.1 NTEE Code Classification

Add nonprofit classification codes to government decisions:

```python
from pipeline.delta_lake import DeltaLakePipeline

# NTEE (National Taxonomy of Exempt Entities) mapping
ntee_mapping = {
    # Health decisions
    'dental_health': 'E32',  # School-Based Health Care
    'health': 'E40',          # Health - General
    'mental_health': 'E80',   # Mental Health
    
    # Education decisions  
    'school_nutrition': 'K34', # School Nutrition
    'after_school': 'O50',     # Youth Development
    
    # Infrastructure
    'water_quality': 'W40',    # Water Quality
    
    # Safety
    'youth_violence': 'I20'    # Youth Violence Prevention
}

pipeline = DeltaLakePipeline()
spark = pipeline.get_spark_session()

# Load classified decisions
df = spark.read.format('delta').load('data/delta/silver/classified_documents')
tuscaloosa_df = df.filter(df.municipality.like('%Tuscaloosa%'))

# Add NTEE codes
from pyspark.sql.functions import when, col

enriched_df = tuscaloosa_df.withColumn(
    'ntee_code',
    when(col('topic') == 'dental_health', 'E32')
    .when(col('topic') == 'health', 'E40')
    .when(col('topic') == 'mental_health', 'E80')
    .when(col('topic') == 'school_nutrition', 'K34')
    .when(col('topic') == 'after_school', 'O50')
    .when(col('topic') == 'water_quality', 'W40')
    .otherwise(None)
)

# Write enhanced decisions
enriched_df.write.format('delta').mode('overwrite').save('data/delta/gold/decisions_with_ntee')

print("✓ Added NTEE codes to Tuscaloosa decisions")
```

---

### 5.2 Nonprofit Data Collection

#### Option A: Automated Discovery (FREE APIs) ⭐ RECOMMENDED

**NEW: Automated nonprofit discovery using free open data APIs**

Run the automated discovery script:

```bash
source .venv/bin/activate
python scripts/discover_tuscaloosa_nonprofits.py
```

This script automatically:
1. **ProPublica Nonprofit Explorer API** - Pulls financial data, EIN, NTEE codes for all Tuscaloosa nonprofits
2. **IRS Tax-Exempt Organization data** - Official tax status and classification
3. **Every.org Charity API** - Mission statements, logos, cause categories
4. **Caches results** - Downloads once, reuses cached data on subsequent runs

**Output:** `frontend/policy-dashboards/src/data/tuscaloosa_nonprofits.json`

**What you get for FREE:**
- ✅ All registered nonprofits in Tuscaloosa County
- ✅ Annual revenue, expenses, assets
- ✅ NTEE codes (standardized classification)
- ✅ EIN (tax ID) for verification
- ✅ Mission statements and descriptions
- ✅ Organization logos

**What's still manual:**
- ⚠️ Specific "services provided" (e.g., "Free dental screenings on Tuesdays")
- ⚠️ Phone numbers and email addresses
- ⚠️ Volunteer opportunities
- ⚠️ Board member openings

**Data sources used:**

1. **ProPublica Nonprofit Explorer API**
   - API Docs: https://projects.propublica.org/nonprofits/api
   - Coverage: 3+ million organizations, 10+ years of 990 data
   - Rate Limit: Free, ~1 request/second suggested
   - Example:
     ```python
     from discovery.nonprofit_discovery import NonprofitDiscovery
     
     discovery = NonprofitDiscovery()
     
     # Search by state, city, and NTEE code
     health_orgs = discovery.search_propublica(
         state="AL",
         city="Tuscaloosa",
         ntee_code="E32"  # School-Based Health Care
     )
     
     # Get detailed financials for specific org
     details = discovery.get_propublica_org_details("63-0123456")
     ```

2. **IRS Tax-Exempt Organization Search (TEOS)**
   - Source: IRS Pub 78 - official list of deductible organizations
   - Bulk Download: https://www.irs.gov/charities-non-profits/tax-exempt-organization-search-bulk-data-downloads
   - Updates: Monthly
   - Included in ProPublica API

3. **Every.org Charity API**
   - API Docs: https://www.every.org/nonprofit-api
   - Best for: Human-readable missions, logos, images
   - Note: May require API key for full access
   - Example:
     ```python
     # Search by location and cause
     orgs = discovery.search_everyorg(
         location="Tuscaloosa, AL",
         causes=["health", "education", "youth"]
     )
     ```

**Running manually for specific NTEE codes:**

```python
from discovery.nonprofit_discovery import NonprofitDiscovery

discovery = NonprofitDiscovery()

# Just dental/health organizations
dental_orgs = discovery.search_propublica(
    state="AL",
    city="Tuscaloosa", 
    ntee_code="E32"  # School-Based Health Care
)

# Churches with health ministries  
churches = discovery.search_propublica(
    state="AL",
    city="Tuscaloosa",
    ntee_code="X20"  # Christian
)

# Merge and export
all_orgs = discovery.merge_nonprofit_data(dental_orgs, churches)
discovery.export_to_frontend(all_orgs)
```

**NTEE Code Reference:**

| Code | Category | Example Organizations |
|------|----------|----------------------|
| E32 | School-Based Health Care | Mobile dental clinics in schools |
| E40 | Health - General | Community health centers |
| E80 | Health - Mental Health | School counseling programs |
| F30 | Mental Health Treatment | Crisis intervention services |
| K30 | Food Service Programs | School breakfast/lunch programs |
| O50 | Youth Development | After-school programs |
| P30 | Children & Youth Services | Family support services |
| X20 | Christian | Church health ministries |
| W40 | Water Quality | Clean water advocacy |

---

#### Option B: Manual Curation (Supplement Automated Data)

Add specific service details that APIs don't provide:

```python
import json

tuscaloosa_nonprofits = [
    {
        "name": "West Alabama Health Services",
        "ein": "63-0123456",  # IRS Tax ID
        "ntee_code": "E40",
        "ntee_description": "Health - General",
        "mission": "Providing accessible healthcare to underserved communities in West Alabama",
        "services": [
            "Free dental screenings for school children",
            "Mobile health unit",
            "Community health education"
        ],
        "annual_budget": 850000,
        "students_served": 1200,
        "contact": {
            "website": "https://wahealthservices.org",
            "email": "info@wahealthservices.org",
            "phone": "(205) 555-0100"
        },
        "volunteer_opportunities": True,
        "accepting_board_members": True
    },
    {
        "name": "First Baptist Church Tuscaloosa - Health Ministry",
        "ein": "63-0234567",
        "ntee_code": "E32",
        "ntee_description": "School-Based Health Care",
        "mission": "Faith-based health outreach serving Tuscaloosa families",
        "services": [
            "Free dental hygiene kits distribution",
            "Health screenings after Sunday service",
            "Nutrition education classes"
        ],
        "annual_budget": 45000,
        "families_served": 450,
        "contact": {
            "website": "https://fbctuscaloosa.org/health",
            "email": "health@fbctuscaloosa.org",
            "phone": "(205) 555-0200"
        },
        "volunteer_opportunities": True,
        "accepting_board_members": False
    },
    {
        "name": "Tuscaloosa County Interfaith Dental Initiative",
        "ein": "63-0345678",
        "ntee_code": "E32",
        "ntee_description": "School-Based Health Care",
        "mission": "Multi-faith collaboration providing free dental care",
        "services": [
            "Mobile dental unit serving Title I schools",
            "Free toothbrush and fluoride programs",
            "Parent education workshops"
        ],
        "annual_budget": 125000,
        "students_served": 2400,
        "contact": {
            "website": "https://tuscaloosainterfaithdental.org",
            "email": "contact@tuscaloosainterfaithdental.org",
            "phone": "(205) 555-0300"
        },
        "volunteer_opportunities": True,
        "accepting_board_members": True
    }
]

# Save for frontend
with open('frontend/policy-dashboards/src/data/tuscaloosa_nonprofits.json', 'w') as f:
    json.dump(tuscaloosa_nonprofits, f, indent=2)

print(f"✓ Curated {len(tuscaloosa_nonprofits)} Tuscaloosa nonprofits")
```

#### Option C: Local Service Directories (For Specific Services)

**Findhelp.org (Aunt Bertha)** - Most comprehensive local services directory

```bash
# Visit their search page
# https://www.findhelp.org/search?query=dental&location=Tuscaloosa,%20AL

# Results include:
# - Specific services offered (e.g., "Free dental screenings Tuesdays 9am-2pm")
# - Walk-in hours
# - Eligibility requirements
# - Contact information
```

**211 Alabama** - Regional social services directory

```bash
# Alabama 211 website
# https://www.211connects.org

# Search for:
# - "Dental care" in Tuscaloosa County
# - "Food assistance" 
# - "Youth programs"

# Results more detailed than IRS data:
# - Days/hours of operation
# - Languages spoken
# - Insurance accepted
```

**Strategy: Scrape for service details, match to IRS data by name**

```python
from discovery.nonprofit_discovery import NonprofitDiscovery

discovery = NonprofitDiscovery()

# Get financial backbone from ProPublica
financial_data = discovery.search_propublica(
    state="AL",
    city="Tuscaloosa",
    ntee_code="E32"
)

# Then manually add service details from Findhelp.org/211
# Match by organization name and enrich the records
```

---

#### Option D: Charity Navigator API (Premium Ratings)

Enrich nonprofit data with ratings and financials:

```python
import os
import requests

def enrich_nonprofit_data(ein):
    """Get ratings, financials, and impact metrics from Charity Navigator"""
    
    api_key = os.getenv('CHARITY_NAVIGATOR_API_KEY')
    url = f"https://api.charitynavigator.org/v1/organizations/{ein}"
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        return {
            'overall_rating': data.get('currentRating', {}).get('overallRating'),
            'financial_rating': data.get('currentRating', {}).get('financialRating'),
            'accountability_rating': data.get('currentRating', {}).get('accountabilityRating'),
            'program_expense_ratio': data.get('financials', {}).get('programExpenseRatio'),
            'admin_expense_ratio': data.get('financials', {}).get('adminExpenseRatio'),
            'revenue': data.get('financials', {}).get('totalRevenue')
        }
    else:
        print(f"⚠️  Could not fetch data for EIN {ein}: {response.status_code}")
        return None

# Example usage
ein = "63-0123456"  # West Alabama Health Services
enriched = enrich_nonprofit_data(ein)
print(f"Overall Rating: {enriched['overall_rating']}/4")
print(f"Program Expense Ratio: {enriched['program_expense_ratio']*100:.1f}%")
```

---

### 5.3 Match Decisions to Nonprofits

Create the split-screen view by matching government decisions to community organizations:

```python
import json
from pathlib import Path

# Load government decisions with NTEE codes
with open('frontend/policy-dashboards/src/data/tuscaloosa_policies.json') as f:
    decisions = json.load(f)

# Load nonprofits
with open('frontend/policy-dashboards/src/data/tuscaloosa_nonprofits.json') as f:
    nonprofits = json.load(f)

# Add community gap analysis
for decision in decisions:
    if decision.get('outcome') in ['Tabled', 'Deferred', 'Rejected']:
        ntee_code = decision.get('ntee_code')
        
        if ntee_code:
            # Find matching nonprofits
            matching_orgs = [
                np for np in nonprofits 
                if np['ntee_code'] == ntee_code or 
                   np['ntee_code'].startswith(ntee_code[0])
            ]
            
            if matching_orgs:
                total_served = sum(
                    np.get('students_served', 0) + 
                    np.get('families_served', 0) + 
                    np.get('youth_served', 0)
                    for np in matching_orgs
                )
                
                decision['community_gap'] = {
                    'description': f"{len(matching_orgs)} nonprofits already serving {total_served} people in this area",
                    'nonprofit_filling_gap': True,
                    'matching_organizations': len(matching_orgs)
                }

# Save enhanced decisions
with open('frontend/policy-dashboards/src/data/tuscaloosa_policies_enhanced.json', 'w') as f:
    json.dump(decisions, f, indent=2)

print(f"✓ Matched {sum(1 for d in decisions if d.get('community_gap'))} decisions to nonprofits")
```

---

### 5.4 Launch Frontend with Split-Screen View

The frontend is already configured with the split-screen component:

```bash
cd frontend/policy-dashboards
npm start
```

**What users see:**

1. **Browse Decisions** → See green "🤝 Community filling gap" badges on deferred/tabled decisions
2. **Click Decision** → View split-screen:
   - **Left**: Government rationale, vote, outcome
   - **Right**: Nonprofits doing this work NOW with contact info
3. **Take Action** → Volunteer, join boards, cite in public meetings

**Example Flow:**
```
Decision: "Tabled dental screening partnership - Legal risk concerns"
         ↓
Community Response: 
  - Interfaith Dental Initiative: 2,400 students served
  - First Baptist Health Ministry: 450 families served  
  - West Alabama Health Services: 1,200 students served
         ↓
Actions: [Website] [Email] [Volunteer] [Join Board]
```

---

### 5.5 The "Marketplace for Solutions" Pattern

Show cost comparisons to expose bureaucratic inefficiency:

```python
# Calculate government "study cost" vs nonprofit "solution cost"
government_cost_per_analysis = {
    'Legal Review': 5000,      # Attorney billable hours
    'Risk Assessment': 3500,   # Consultant fees  
    'Feasibility Study': 8000  # Multi-month study
}

nonprofit_cost_per_service = {
    'Dental Screening': 25,    # Per child
    'Fluoride Treatment': 15,  # Per child
    'Toothbrush Kit': 5        # Per child
}

# Example: Dental screening partnership tabled
board_spent_studying = government_cost_per_analysis['Legal Review']  # $5,000
nonprofit_could_serve = board_spent_studying / nonprofit_cost_per_service['Dental Screening']  # 200 kids

print(f"""
BUREAUCRATIC EFFICIENCY GAP:

Government: Spent ${board_spent_studying:,} on legal review to study dental screenings

Nonprofit: Could screen {int(nonprofit_could_serve)} children for the same cost

The "Legal Risk" excuse cost enough to provide the actual solution to 200 kids.
""")
```

Display this comparison on the frontend to create "social pressure":

```javascript
// In SplitScreenView.jsx
<div className="efficiency-gap">
  <div className="government-cost">
    💰 Board spent: $5,000 on legal review
  </div>
  <div className="nonprofit-alternative">
    ✓ Nonprofits could screen: 200 children for same cost
  </div>
  <div className="gap-metric">
    📊 Bureaucratic Efficiency Gap: 200x
  </div>
</div>
```

---

### 5.6 API Integration Status

**✅ Phase 1: Static Curated Data** - COMPLETE
- Manually researched Tuscaloosa nonprofits
- ~10-20 key organizations with verified contact info
- Frontend example data in place

**✅ Phase 2: IRS/ProPublica Integration** - COMPLETE
- Automated nonprofit discovery via ProPublica API
- Financial data (revenue, expenses, assets) for all Tuscaloosa nonprofits
- NTEE code classification
- Cached data for fast repeated access
- **Run with:** `python scripts/discover_tuscaloosa_nonprofits.py`

**🔨 Phase 3: Local Service Directories** - IN PROGRESS
- Manual enrichment from Findhelp.org and 211 directories
- Specific services, hours, contact details
- Volunteer opportunities verification
- **To Do:** Build automated scrapers for Findhelp.org/211

**🔮 Phase 4: Charity Navigator/GuideStar** - PLANNED
- Add effectiveness ratings
- Financial transparency scores
- Impact metrics verification
- **Requires:** API key ($$$) or web scraping

**🔮 Phase 5: Real-Time Project Data** - FUTURE
- Pull active campaigns from nonprofits
- Current funding needs
- Live volunteer opportunities feed
- **Requires:** Direct nonprofit partnerships or aggregator APIs

---

### 5.7 Church Integration Strategy

Churches often run health ministries without formal 501(c)(3) status. Include them by:

1. **Curated Church List**: Manually research faith-based health programs
2. **NTEE Code X20**: "Christian" category for faith-based services
3. **Ecumenical Partnerships**: Many churches collaborate (e.g., Interfaith Dental Initiative)

```python
# Churches often fall under umbrella organizations
church_health_programs = [
    {
        "name": "First Baptist Church - Health Ministry",
        "parent_org": "First Baptist Church Tuscaloosa",
        "ein": "63-0234567",  # Church's EIN
        "ntee_code": "X20",    # Christian
        "services": ["Free dental kits", "Health screenings"],
        "contact": {"website": "https://fbctuscaloosa.org/health"}
    },
    {
        "name": "Catholic Social Services - Dental Outreach",
        "parent_org": "Diocese of Birmingham",
        "ein": "63-0456789",
        "ntee_code": "X20",
        "services": ["Mobile dental unit", "School partnerships"],
        "contact": {"website": "https://cssalabama.org"}
    }
]
```

---

### 5.8 Success Metrics

Track citizen engagement with the community bridge:

```python
# Analytics to track
metrics = {
    'split_screen_views': 0,           # How many users viewed split-screen
    'nonprofit_clicks': 0,              # Clicks to nonprofit websites
    'volunteer_inquiries': 0,           # Form submissions
    'board_interest': 0,                # Board opportunity clicks
    'email_contacts': 0,                # Email button clicks
    'government_citations': 0           # Nonprofits cited in public meetings
}

# Goal: If 10% of site visitors contact a nonprofit, you've created real impact
```

**Real-World Impact:**
- Nonprofits report increased volunteer inquiries
- Citizens cite these orgs in school board meetings
- Board members recruited through the platform
- Donations increase to featured organizations

---

## Next Steps

1. **Expand Sources**: Add more Tuscaloosa data sources (school board, county commission, etc.)
2. **Deep Analysis**: Use LLM to extract specific policy details (budgets, votes, impacts)
3. **Build Dashboard**: Create interactive visualization with the frontend ✅ **DONE**
4. **Nonprofit Integration**: Connect decisions to community organizations ✅ **DONE**
5. **Set Alerts**: Monitor for specific keywords or topics
6. **Church Outreach**: Partner with faith-based health ministries
7. **API Integration**: Automate nonprofit data with IRS/Charity Navigator APIs
8. **Share Insights**: Publish findings to HuggingFace or local news outlets

For questions, see:
- [QUICKSTART.md](QUICKSTART.md) - General setup
- [docs/EBOARD_COOKIE_GUIDE.md](docs/EBOARD_COOKIE_GUIDE.md) - eBoard scraping
- [docs/SPLIT_SCREEN_SYSTEM.md](docs/SPLIT_SCREEN_SYSTEM.md) - Nonprofit integration ✅ **NEW**
- [DATABRICKS_MIGRATION.md](DATABRICKS_MIGRATION.md) - Scaling to Databricks
