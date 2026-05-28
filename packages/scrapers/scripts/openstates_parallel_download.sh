#!/bin/bash
# Parallel OpenStates Document Downloader
# Downloads documents for multiple states simultaneously

cd /home/developer/projects/open-navigator

# Create log directory
mkdir -p /tmp/openstates_parallel

# Define state groups (split into batches for parallel processing)
BATCH1="AK,AL,AR,AZ,CA,CO,CT"
BATCH2="DE,FL,GA,HI,IA,ID,IL"
BATCH3="IN,KS,KY,LA,MA,MD,ME"
BATCH4="MI,MN,MO,MS,MT,NC,ND"
BATCH5="NE,NH,NJ,NM,NV,NY,OH"
BATCH6="OK,OR,PA,RI,SC,SD,TN"
BATCH7="TX,UT,VA,VT,WA,WI,WV,WY"

# Function to download a batch of states
download_batch() {
    local batch_num=$1
    local states=$2
    local log_file="/tmp/openstates_parallel/batch_${batch_num}.log"
    
    echo "Starting batch $batch_num: $states"
    python scripts/datasources/openstates/download_documents.py \
        --states "$states" \
        --resume \
        > "$log_file" 2>&1 &
    
    echo "Batch $batch_num PID: $!"
}

echo "🚀 Starting parallel OpenStates document download"
echo "📊 Downloading from 7 batches of states simultaneously"
echo "📁 Logs: /tmp/openstates_parallel/"
echo ""

# Start all batches in parallel
download_batch 1 "$BATCH1"
download_batch 2 "$BATCH2"
download_batch 3 "$BATCH3"
download_batch 4 "$BATCH4"
download_batch 5 "$BATCH5"
download_batch 6 "$BATCH6"
download_batch 7 "$BATCH7"

echo ""
echo "✅ All batches started!"
echo ""
echo "Monitor progress:"
echo "  tail -f /tmp/openstates_parallel/batch_*.log"
echo ""
echo "Check running processes:"
echo "  ps aux | grep download_documents.py | grep -v grep"
echo ""
echo "Stop all downloads:"
echo "  pkill -f download_documents.py"
