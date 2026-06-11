#!/bin/bash
# Complete Tuscaloosa Policy Pulse Pipeline
# Run the 4-step process: Gather → Structure → Analyze → Deliver

set -e

echo "========================================="
echo "  TUSCALOOSA POLICY PULSE PIPELINE"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Activate environment
source .venv/bin/activate

# ==================================================
# STEP 1: GATHER - Collect Meeting Data
# ==================================================
echo -e "${BLUE}[1/4] GATHER${NC} - Collecting meeting data..."

# Tuscaloosa City Government
echo "  → Scraping Tuscaloosa City (SuiteOne)..."
python main.py scrape \
  --state AL \
  --municipality "Tuscaloosa" \
  --url https://tuscaloosaal.suiteonemedia.com \
  --platform suiteonemedia \
  --max-events 0 \
  --start-year 0 \
  --include-social

# Check for eBoard cookies
if [ ! -f "eboard_cookies.json" ]; then
    echo -e "${YELLOW}  ⚠️  Warning: eboard_cookies.json not found${NC}"
    echo "     Tuscaloosa City Schools requires browser cookies."
    echo "     See web_docs/docs/integrations/eboard-cookies.md for instructions."
    echo ""
else
    echo "  → Scraping Tuscaloosa City Schools (eBoard)..."
    python main.py scrape \
      --state AL \
      --municipality "Tuscaloosa City Schools" \
      --url http://simbli.eboardsolutions.com/index.aspx?s=2088 \
      --platform eboard \
      --max-events 0 \
      --start-year 0 \
      --no-include-social
fi

# Count documents gathered
echo ""
echo -e "${GREEN}✓ Gather complete${NC}"
python -c "
import json
from pathlib import Path

count = 0
for json_file in Path('output').rglob('*.json'):
    try:
        with open(json_file) as f:
            docs = json.load(f)
            if isinstance(docs, list):
                count += len(docs)
    except:
        pass

print(f'  Gathered {count} total documents')
"

# ==================================================
# STEP 2: STRUCTURE - Process with AI
# ==================================================
echo ""
echo -e "${BLUE}[2/4] STRUCTURE${NC} - Structuring data with AI..."

echo "  → Loading documents to Delta Lake (Bronze layer)..."
python -c "
import json
from pathlib import Path
from pipeline.delta_lake import DeltaLakePipeline

pipeline = DeltaLakePipeline()
all_docs = []

# Load all Tuscaloosa documents
for json_file in Path('output').rglob('*.json'):
    try:
        with open(json_file) as f:
            docs = json.load(f)
            if isinstance(docs, list):
                # Filter to Tuscaloosa
                tuscaloosa_docs = [d for d in docs if 'Tuscaloosa' in d.get('municipality', '')]
                all_docs.extend(tuscaloosa_docs)
    except Exception as e:
        pass

if all_docs:
    pipeline.write_raw_documents(all_docs)
    print(f'✓ Loaded {len(all_docs)} Tuscaloosa documents to Bronze layer')
else:
    print('⚠️  No Tuscaloosa documents found')
"

echo "  → Classifying documents (Silver layer)..."
python -c "
import asyncio
from agents.classifier import ClassifierAgent
from pipeline.delta_lake import DeltaLakePipeline

async def classify():
    pipeline = DeltaLakePipeline()
    classifier = ClassifierAgent()
    
    async with classifier:
        spark = pipeline.get_spark_session()
        
        # Get Tuscaloosa documents from Bronze
        try:
            df = spark.read.format('delta').load('data/delta/bronze/documents')
            tuscaloosa_df = df.filter(df.municipality.like('%Tuscaloosa%'))
            docs = tuscaloosa_df.collect()
            
            print(f'  Classifying {len(docs)} documents...')
            
            classified = []
            for i, doc in enumerate(docs):
                if i % 10 == 0 and i > 0:
                    print(f'    Progress: {i}/{len(docs)}')
                
                result = await classifier.classify(
                    content=doc.content[:5000],  # Limit content for speed
                    municipality=doc.municipality
                )
                
                classified.append({
                    **doc.asDict(),
                    'primary_topic': result.get('primary_topic', 'unknown'),
                    'confidence': result.get('confidence', 0.0),
                    'themes': result.get('themes', [])
                })
            
            # Write to Silver layer
            pipeline.write_classified_documents(classified)
            print(f'✓ Classified {len(classified)} documents')
            
        except Exception as e:
            print(f'⚠️  Classification skipped: {e}')

asyncio.run(classify())
"

echo ""
echo -e "${GREEN}✓ Structure complete${NC}"

# ==================================================
# STEP 3: ANALYZE - Extract Insights
# ==================================================
echo ""
echo -e "${BLUE}[3/4] ANALYZE${NC} - Extracting policy insights..."

python -c "
from pipeline.delta_lake import DeltaLakePipeline
from pyspark.sql.functions import count, countDistinct

pipeline = DeltaLakePipeline()
spark = pipeline.get_spark_session()

print('  → Analyzing policy topics...')

try:
    df = spark.read.format('delta').load('data/delta/silver/classified_documents')
    tuscaloosa_df = df.filter(df.municipality.like('%Tuscaloosa%'))
    
    # Topic summary
    topics = tuscaloosa_df.groupBy('primary_topic').agg(
        count('*').alias('count')
    ).orderBy('count', ascending=False)
    
    print('\\n  Top Policy Topics:')
    for row in topics.take(10):
        print(f'    {row.primary_topic}: {row.count} documents')
    
    # Time analysis
    from pyspark.sql.functions import year
    by_year = tuscaloosa_df.groupBy(year('meeting_date').alias('year')).count()
    print('\\n  Documents by Year:')
    for row in by_year.orderBy('year').collect():
        print(f'    {row.year}: {row.count}')
    
except Exception as e:
    print(f'  ⚠️  Analysis skipped: {e}')
"

echo ""
echo -e "${GREEN}✓ Analysis complete${NC}"

# ==================================================
# STEP 4: DELIVER - Create Insights
# ==================================================
echo ""
echo -e "${BLUE}[4/4] DELIVER${NC} - Generating deliverables..."

echo "  → Creating executive briefing..."
python -c "
from pipeline.delta_lake import DeltaLakePipeline
from datetime import datetime, timedelta

pipeline = DeltaLakePipeline()
spark = pipeline.get_spark_session()

try:
    df = spark.read.format('delta').load('data/delta/silver/classified_documents')
    tuscaloosa_df = df.filter(df.municipality.like('%Tuscaloosa%'))
    
    # Recent activity
    recent_date = datetime.now() - timedelta(days=90)
    recent_df = tuscaloosa_df.filter(df.meeting_date >= recent_date)
    
    with open('output/tuscaloosa_briefing.txt', 'w') as f:
        f.write('='*60 + '\\n')
        f.write('TUSCALOOSA POLICY BRIEFING\\n')
        f.write(f'Generated: {datetime.now().strftime(\"%Y-%m-%d\")}\\n')
        f.write('='*60 + '\\n\\n')
        
        f.write('SUMMARY\\n')
        f.write(f'  Total documents: {tuscaloosa_df.count()}\\n')
        f.write(f'  Last 90 days: {recent_df.count()}\\n\\n')
        
        f.write('TOP TOPICS (All Time)\\n')
        topics = tuscaloosa_df.groupBy('primary_topic').count().orderBy('count', ascending=False)
        for i, row in enumerate(topics.take(10), 1):
            f.write(f'  {i}. {row.primary_topic}: {row.count}\\n')
    
    print('✓ Briefing saved to output/tuscaloosa_briefing.txt')
    
except Exception as e:
    print(f'⚠️  Briefing generation skipped: {e}')
"

echo "  → Exporting dashboard data..."
python -c "
import json
from pathlib import Path
from pipeline.delta_lake import DeltaLakePipeline

pipeline = DeltaLakePipeline()
spark = pipeline.get_spark_session()

try:
    df = spark.read.format('delta').load('data/delta/silver/classified_documents')
    tuscaloosa_df = df.filter(df.municipality.like('%Tuscaloosa%'))
    
    # Export for web dashboard
    dashboard_data = []
    for row in tuscaloosa_df.collect():
        dashboard_data.append({
            'id': row.document_id,
            'date': row.meeting_date.isoformat() if row.meeting_date else None,
            'title': row.title,
            'topic': row.primary_topic,
            'municipality': row.municipality,
            'url': row.source_url
        })
    
    Path('frontend/src/data').mkdir(parents=True, exist_ok=True)
    with open('frontend/src/data/tuscaloosa_policies.json', 'w') as f:
        json.dump(dashboard_data, f, indent=2)
    
    print(f'✓ Exported {len(dashboard_data)} policies for dashboard')
    
except Exception as e:
    print(f'⚠️  Dashboard export skipped: {e}')
"

echo ""
echo -e "${GREEN}✓ Deliver complete${NC}"

# ==================================================
# SUMMARY
# ==================================================
echo ""
echo "========================================="
echo "  PIPELINE COMPLETE ✓"
echo "========================================="
echo ""
echo "Outputs:"
echo "  • Raw data: output/tuscaloosa/"
echo "  • Delta Lake: data/delta/"
echo "  • Briefing: output/tuscaloosa_briefing.txt"
echo "  • Dashboard: frontend/src/data/tuscaloosa_policies.json"
echo ""
echo "Next steps:"
echo "  • View briefing: cat output/tuscaloosa_briefing.txt"
echo "  • Query data: python -c 'from pipeline.delta_lake import ...'"
echo "  • Publish: python main.py publish-to-hf --dataset tuscaloosa"
echo ""
