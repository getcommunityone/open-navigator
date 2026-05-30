#!/bin/bash
# Setup dbt project for Open Navigator
# This script initializes the dbt environment and tests connectivity

set -e  # Exit on error

echo "🔧 Setting up dbt for Open Navigator..."
echo ""

# Check if in correct directory
if [ ! -f "dbt_project.yml" ]; then
    echo "❌ Error: Must run from dbt_project/ directory"
    echo "   cd dbt_project && ./setup.sh"
    exit 1
fi

# Install dbt if not already installed
if ! command -v dbt &> /dev/null; then
    echo "📦 Installing dbt-postgres..."
    pip install dbt-postgres dbt-utils
else
    echo "✅ dbt already installed: $(dbt --version | head -1)"
fi

# Set up profiles.yml if it doesn't exist
PROFILES_DIR="$HOME/.dbt"
PROFILES_FILE="$PROFILES_DIR/profiles.yml"

if [ ! -f "$PROFILES_FILE" ]; then
    echo ""
    echo "📝 Setting up profiles.yml..."
    mkdir -p "$PROFILES_DIR"
    
    # Copy example and prompt for password
    cp profiles.yml.example "$PROFILES_FILE"
    
    echo "✅ Created $PROFILES_FILE"
    echo "   (Using POSTGRES_PASSWORD environment variable)"
else
    echo "✅ profiles.yml already exists"
fi

# Install dbt packages
echo ""
echo "📦 Installing dbt packages (dbt_utils, dbt_expectations)..."
dbt deps

# Test connection
echo ""
echo "🔌 Testing database connection..."
if dbt debug; then
    echo ""
    echo "✅ Database connection successful!"
else
    echo ""
    echo "❌ Database connection failed"
    echo "   Check your profiles.yml configuration"
    echo "   Set POSTGRES_PASSWORD environment variable"
    exit 1
fi

# Supporting indexes (CONCURRENTLY — must run outside dbt; no-op if int_jurisdictions missing yet)
echo ""
echo "📇 Ensuring support indexes on intermediate.int_jurisdictions (if table exists)..."
if [[ -f "scripts/ensure_int_jurisdictions_indexes.sh" ]]; then
    bash "scripts/ensure_int_jurisdictions_indexes.sh" || echo "⚠️  Index step failed (continuing setup)"
fi

# Try to run staging models
echo ""
echo "🚀 Testing dbt models..."
if dbt run --select staging; then
    echo ""
    echo "✅ Staging models ran successfully!"
else
    echo ""
    echo "⚠️  Staging models failed - this is OK if bronze tables don't exist yet"
    echo "   Run: python -m llm.enrichment.load_meeting_transcripts"
fi

echo ""
echo "=" * 70
echo "✅ dbt setup complete!"
echo "=" * 70
echo ""
echo "Next steps:"
echo "  1. Load bronze data: python -m llm.enrichment.load_meeting_transcripts"
echo "  2. Run dbt models: dbt run"
echo "  3. Run tests: dbt test"
echo "  4. View docs: dbt docs generate && dbt docs serve"
echo ""
