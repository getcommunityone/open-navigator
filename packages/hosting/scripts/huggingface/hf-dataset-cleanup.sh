#!/bin/bash

# Quick script to list and delete Hugging Face datasets

echo "🗑️  Hugging Face Dataset Cleanup"
echo "================================="
echo ""

# Check if logged in
if ! huggingface-cli whoami &> /dev/null; then
    echo "❌ Not logged in to Hugging Face"
    echo "Run: huggingface-cli login"
    exit 1
fi

USERNAME=$(huggingface-cli whoami | grep -oP '(?<=username: ).*')
echo "👤 Logged in as: $USERNAME"
echo ""

# List all datasets
echo "📊 Your datasets:"
echo ""
huggingface-cli repo list --type dataset

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "To delete a dataset, run:"
echo "  huggingface-cli repo delete --type dataset USERNAME/DATASET-NAME --yes"
echo ""
echo "Example:"
echo "  huggingface-cli repo delete --type dataset $USERNAME/open-navigator --yes"
echo ""
echo "To delete ALL datasets with a prefix (⚠️  DANGEROUS):"
echo "  huggingface-cli repo list --type dataset | grep 'communityone\\|oral-health' | while read repo; do"
echo "    huggingface-cli repo delete --type dataset \$repo --yes"
echo "  done"
echo ""
