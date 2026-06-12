#!/bin/bash
# Enrich all 5 dev states using local Form 990 XMLs
# Much faster than S3 downloads (100-200 orgs/sec vs 10-20)

set -e

STATES=("WA" "MA" "AL" "GA" "WI")
CONCURRENT=100

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║   Fast Form 990 Enrichment - All Dev States (Local)      ║"
echo "╔═══════════════════════════════════════════════════════════╗"
echo ""

# Step 1: Build local index (if not exists or older than XMLs)
INDEX_FILE="data/cache/form990/local_index_dev_states.parquet"
if [ ! -f "$INDEX_FILE" ]; then
    echo "📊 Building local XML index..."
    python scripts/build_990_local_index.py
    echo ""
fi

# Step 2: Enrich each state
for state in "${STATES[@]}"; do
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "  Enriching $state"
    echo "═══════════════════════════════════════════════════════════"
    
    INPUT="data/gold/states/$state/nonprofits_organizations.parquet"
    OUTPUT="data/gold/states/$state/nonprofits_form990.parquet"
    
    if [ ! -f "$INPUT" ]; then
        echo "⚠️  Skipping $state: No organizations file found"
        continue
    fi
    
    # Use fast MA script for MA, generic for others
    if [ "$state" = "MA" ]; then
        python scripts/enrich_ma_990_fast.py \
            --use-local \
            --concurrent $CONCURRENT
    else
        python -m scrapers.irs.enrich_nonprofits_gt990 \
            --use-local \
            --input "$INPUT" \
            --output "$OUTPUT" \
            --concurrent $CONCURRENT
    fi
done

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║   ✅ All States Enriched!                                  ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Show results
echo "Results per state:"
echo ""
for state in "${STATES[@]}"; do
    OUTPUT="data/gold/states/$state/nonprofits_form990.parquet"
    
    if [ -f "$OUTPUT" ]; then
        python -c "
import pandas as pd
df = pd.read_parquet('$OUTPUT')
enriched = df['has_form990'].sum() if 'has_form990' in df.columns else 0
print(f'  {state}: {len(df):,} orgs | {enriched:,} with 990 data')
" 2>/dev/null || echo "  $state: (error reading file)"
    else
        echo "  $state: No output file"
    fi
done

echo ""
echo "💾 Form 990 tables saved to:"
echo "   data/gold/states/{WA,MA,AL,GA,WI}/nonprofits_form990.parquet"
echo ""

# Step 3: Normalize officers into contact tables
echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║   Step 3: Creating Officer Contact Tables                 ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "Normalizing form_990_officers JSON → contact tables..."
echo ""

python scripts/create_nonprofit_officer_contacts.py --all-states

echo ""
echo "✅ Contact tables created:"
echo "   • contacts_nonprofit_officers.parquet (current snapshot)"
echo "   • contacts_nonprofit_officers_YYYY.parquet (by year)"
echo "   • contacts_nonprofit_officers_history.parquet (salary trends)"
echo ""
