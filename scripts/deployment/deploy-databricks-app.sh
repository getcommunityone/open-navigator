#!/bin/bash

# Build and deploy React + FastAPI app to Databricks Apps

set -e

echo "🚀 Building CommunityOne Open Navigator for Databricks Apps..."

# Step 1: Build React frontend
echo ""
echo "📦 Step 1/4: Building React frontend..."
cd frontend
npm install
npm run build
cd ..

# Step 2: Verify build output
echo ""
echo "✅ Step 2/4: Verifying build..."
if [ -d "api/static" ]; then
    echo "   Frontend build successful! Static files ready."
else
    echo "   ❌ Frontend build failed - static files not found"
    exit 1
fi

# Step 3: Deploy to Databricks
echo ""
echo "☁️  Step 3/4: Deploying to Databricks..."

# Check if Databricks CLI is installed
if ! command -v databricks &> /dev/null; then
    echo "   ❌ Databricks CLI not found. Installing..."
    pip install databricks-cli
fi

# Check for required environment variables
if [ -z "$DATABRICKS_HOST" ] || [ -z "$DATABRICKS_TOKEN" ]; then
    echo "   ⚠️  Please set DATABRICKS_HOST and DATABRICKS_TOKEN environment variables"
    echo "   Example:"
    echo "   export DATABRICKS_HOST=https://your-workspace.cloud.databricks.com"
    echo "   export DATABRICKS_TOKEN=your_token_here"
    exit 1
fi

# Create or update secrets (if they don't exist)
echo "   Setting up secrets..."
databricks secrets create-scope --scope oral-health-app 2>/dev/null || true
databricks secrets put --scope oral-health-app --key host --string-value "$DATABRICKS_HOST" 2>/dev/null || true
databricks secrets put --scope oral-health-app --key token --string-value "$DATABRICKS_TOKEN" 2>/dev/null || true

if [ -n "$OPENAI_API_KEY" ]; then
    databricks secrets put --scope oral-health-app --key openai_key --string-value "$OPENAI_API_KEY" 2>/dev/null || true
fi

# Deploy the app
echo "   Deploying app to Databricks..."
databricks apps deploy oral-health-policy-pulse --source-dir . --config app.yaml

# Step 4: Get app URL
echo ""
echo "✨ Step 4/4: Deployment complete!"
echo ""
echo "📱 Your app is being deployed to Databricks Apps"
echo "🔗 Access it at: ${DATABRICKS_HOST}/apps/oral-health-policy-pulse"
echo ""
echo "To monitor deployment status:"
echo "  databricks apps get oral-health-policy-pulse"
echo ""
echo "To view logs:"
echo "  databricks apps logs oral-health-policy-pulse"
echo ""
