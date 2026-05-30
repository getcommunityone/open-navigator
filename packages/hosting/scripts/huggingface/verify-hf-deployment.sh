#!/bin/bash

# Verification script for HuggingFace deployment
# This checks if the new HTTPS fix is live on production

echo "🔍 Checking HuggingFace deployment status..."
echo ""

# Check if the new JS bundle is being served
echo "1️⃣ Checking main page..."
RESPONSE=$(curl -s https://www.communityone.com/)

if echo "$RESPONSE" | grep -q "index-SmPxj_Wp.js"; then
    echo "✅ NEW version deployed! (index-SmPxj_Wp.js found)"
    NEW_VERSION=true
elif echo "$RESPONSE" | grep -q "index-4CPp14-T.js"; then
    echo "❌ OLD version still running (index-4CPp14-T.js found)"
    echo "   HuggingFace is still building. Wait 5-10 more minutes."
    NEW_VERSION=false
else
    echo "⚠️  Unknown version. Check manually:"
    echo "$RESPONSE" | grep -o 'index-[^"]*\.js' | head -1
    NEW_VERSION=false
fi

echo ""

# Check if the API is responding
echo "2️⃣ Checking API health..."
API_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" https://www.communityone.com/api/health)

if [ "$API_RESPONSE" = "200" ]; then
    echo "✅ API is healthy (HTTP $API_RESPONSE)"
else
    echo "❌ API returned HTTP $API_RESPONSE"
fi

echo ""

# Final instructions
if [ "$NEW_VERSION" = true ]; then
    echo "════════════════════════════════════════════════════"
    echo "✅ New version is LIVE!"
    echo "════════════════════════════════════════════════════"
    echo ""
    echo "To clear your browser cache and load the new code:"
    echo ""
    echo "  Chrome/Edge/Firefox (Windows/Linux):"
    echo "    Press: Ctrl + Shift + R"
    echo ""
    echo "  Safari/Chrome (Mac):"
    echo "    Press: Cmd + Shift + R"
    echo ""
    echo "  Alternative:"
    echo "    1. Open DevTools (F12)"
    echo "    2. Right-click the refresh button"
    echo "    3. Select 'Empty Cache and Hard Reload'"
    echo ""
    echo "After hard refresh, you should see:"
    echo "  - No mixed content errors"
    echo "  - Console shows: index-SmPxj_Wp.js"
    echo "════════════════════════════════════════════════════"
else
    echo "════════════════════════════════════════════════════"
    echo "⏳ Deployment still in progress"
    echo "════════════════════════════════════════════════════"
    echo ""
    echo "HuggingFace is still building the new version."
    echo "This usually takes 10-15 minutes."
    echo ""
    echo "Monitor the build at:"
    echo "  https://huggingface.co/spaces/CommunityOne/www.communityone.com"
    echo ""
    echo "Run this script again in 5 minutes to check status."
    echo "════════════════════════════════════════════════════"
fi
