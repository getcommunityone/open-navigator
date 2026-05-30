#!/bin/bash

# Hugging Face Setup & Deployment Script
# Helps you login, manage datasets, and deploy to Spaces

set -e

echo "🤗 Hugging Face Setup & Deployment"
echo "===================================="
echo ""

# Load environment variables
if [ -f .env ]; then
    source .env
fi

# Check if HF_USERNAME is set
if [ -z "$HF_USERNAME" ]; then
    echo "❌ HF_USERNAME not set in .env"
    echo "Please add: HF_USERNAME=your_username"
    exit 1
fi

echo "👤 Username: $HF_USERNAME"
echo ""

# Step 1: Login to Hugging Face
echo "📝 Step 1: Login to Hugging Face"
echo "================================"
echo ""
echo "You'll need a Hugging Face token with WRITE permission."
echo "Get one at: https://huggingface.co/settings/tokens"
echo ""
read -p "Press Enter to login (or Ctrl+C to cancel)..."
huggingface-cli login

echo ""
echo "✅ Login successful!"
echo ""

# Step 2: Check existing datasets
echo "📊 Step 2: List Existing Datasets"
echo "=================================="
echo ""
echo "Checking for datasets under your account..."
echo ""

# List datasets
huggingface-cli repo list --type dataset || echo "No datasets found or error listing"
echo ""

# Step 3: Offer to delete datasets
echo "🗑️  Step 3: Delete Datasets (Optional)"
echo "======================================="
echo ""
read -p "Do you want to delete any datasets? (y/N): " delete_choice

if [[ "$delete_choice" =~ ^[Yy]$ ]]; then
    echo ""
    echo "To delete a dataset, use:"
    echo "  huggingface-cli repo delete --type dataset USERNAME/DATASET-NAME"
    echo ""
    read -p "Enter dataset name to delete (or press Enter to skip): " dataset_name
    
    if [ -n "$dataset_name" ]; then
        echo "Deleting dataset: $dataset_name"
        huggingface-cli repo delete --type dataset "$dataset_name" --yes || echo "Failed to delete, skipping..."
    fi
fi

echo ""
echo "✅ Dataset management complete"
echo ""

# Step 4: Check required environment variables
echo "🔧 Step 4: Verify Environment Variables"
echo "========================================"
echo ""

required_vars=("HF_USERNAME" "OPENAI_API_KEY")
missing_vars=()

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    else
        # Mask the value for security
        masked="${!var:0:8}..."
        echo "✅ $var = $masked"
    fi
done

if [ ${#missing_vars[@]} -gt 0 ]; then
    echo ""
    echo "⚠️  Missing environment variables in .env:"
    for var in "${missing_vars[@]}"; do
        echo "  - $var"
    done
    echo ""
    echo "Please add these to your .env file before deploying."
    exit 1
fi

echo ""
echo "✅ All required environment variables set"
echo ""

# Step 5: Deploy to Hugging Face Spaces
echo "🚀 Step 5: Deploy to Hugging Face Spaces"
echo "========================================="
echo ""
echo "This will deploy all three apps to Hugging Face:"
echo "  - Documentation (Docusaurus)"
echo "  - Main Application (React)"
echo "  - API Backend (FastAPI)"
echo ""
echo "Cost: ~\$22/month for CPU Basic hardware"
echo ""
read -p "Proceed with deployment? (y/N): " deploy_choice

if [[ "$deploy_choice" =~ ^[Yy]$ ]]; then
    echo ""
    echo "🚀 Starting deployment..."
    ./deploy-huggingface.sh "$HF_USERNAME"
else
    echo ""
    echo "ℹ️  Deployment skipped. To deploy later, run:"
    echo "   ./deploy-huggingface.sh"
fi

echo ""
echo "🎉 Setup Complete!"
echo "=================="
echo ""
echo "Next Steps:"
echo "1. Go to: https://huggingface.co/spaces/$HF_USERNAME/open-navigator"
echo "2. Settings → Resource configuration → Select 'CPU Basic'"
echo "3. Settings → Variables and secrets → Add your API keys as secrets:"
echo "   - OPENAI_API_KEY"
echo "   - ANTHROPIC_API_KEY"
echo "4. Wait for build (~10-15 minutes)"
echo ""
echo "Your Space URL will be:"
echo "https://$HF_USERNAME-open-navigator.hf.space/"
echo ""
