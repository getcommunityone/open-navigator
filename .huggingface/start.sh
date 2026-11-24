#!/bin/bash
set -e

echo "🚀 Starting CommunityOne on Hugging Face Spaces..."
echo "📊 Three services architecture:"
echo "  1. Documentation (Docusaurus) - Port 3000"
echo "  2. Main Application (React + Vite) - Port 5173"
echo "  3. API Backend (FastAPI) - Port 8000"
echo "  4. Nginx Reverse Proxy - Port 7860 (HF Spaces public port)"
echo ""

# DEBUG: Check environment variable
echo "🔍 Environment Check:"
echo "   HF_SPACES = ${HF_SPACES:-NOT SET}"
if [ "$HF_SPACES" = "1" ]; then
    echo "   ✅ HF_SPACES is correctly set to 1"
else
    echo "   ❌ WARNING: HF_SPACES is not set to 1"
    echo "   Setting HF_SPACES=1 now..."
    export HF_SPACES=1
fi
echo ""

# Create required directories
mkdir -p /app/logs /app/data /var/log/supervisor

# Verify static files exist
echo "📁 Verifying static files..."
if [ -d "/app/static/docs" ]; then
    echo "✅ Documentation static files found"
    ls -lh /app/static/docs/ | head -5
else
    echo "❌ ERROR: Documentation static files missing at /app/static/docs"
    exit 1
fi

if [ -d "/app/static/frontend" ]; then
    echo "✅ Frontend static files found"
    ls -lh /app/static/frontend/ | head -5
else
    echo "❌ ERROR: Frontend static files missing at /app/static/frontend"
    exit 1
fi

# Install serve for static file hosting (if not already installed)
if ! command -v serve &> /dev/null; then
    echo "📦 Installing serve for static file hosting..."
    npm install -g serve
fi

# Test nginx configuration
echo "🔧 Testing nginx configuration..."
nginx -t

# Initialize database if needed
echo "💾 Initializing database..."
python -c "from api.database import init_db; init_db()" || echo "⚠️  Database init skipped"

# Served files that are still Git LFS pointers are swapped for the real files (#911). This runs
# beside the services so it never delays or fails the start.
if [ -x /app/restore_lfs_static.sh ]; then
    /app/restore_lfs_static.sh /app /app/static/frontend /app/static/docs /app/api/static > /app/logs/restore_lfs_static.log 2>&1 &
fi

# Start all services with supervisor
echo "🎬 Starting all services with supervisor..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
