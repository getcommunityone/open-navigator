#!/bin/bash
# Force HuggingFace Space rebuild by making a commit and force-pushing

echo "🔄 Forcing HuggingFace Space rebuild..."
echo ""

# Add a timestamp to force a new commit
echo "# Last rebuild: $(date)" >> .huggingface/rebuild.txt

git add .huggingface/rebuild.txt
git commit -m "Force rebuild at $(date +%Y%m%d-%H%M%S)"

echo ""
echo "📤 Force pushing to HuggingFace..."
git push hf-www HEAD:main --force

echo ""
echo "✅ Force push complete!"
echo ""
echo "Now do ONE of these:"
echo "1. Go to https://huggingface.co/spaces/CommunityOne/www.communityone.com"
echo "2. Click 'Settings' → Find 'Factory reboot' or 'Restart Space'"
echo "3. Wait 15-20 minutes for Docker rebuild"
echo ""
echo "Check build logs at: https://huggingface.co/spaces/CommunityOne/www.communityone.com/logs"
