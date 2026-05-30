#!/usr/bin/env python3
"""
Check HuggingFace Spaces environment variables and secrets.
"""
import os
import sys
from huggingface_hub import HfApi

# Get token from environment
token = os.getenv('HF_TOKEN')
if not token:
    print("❌ HF_TOKEN not found in environment")
    print("   Run: source .env")
    sys.exit(1)

api = HfApi(token=token)
space_id = "CommunityOne/www.communityone.com"

print(f"\n🔍 Checking HuggingFace Space: {space_id}\n")

try:
    # Get space info
    space_info = api.space_info(space_id)
    print(f"✅ Space found: {space_info.id}")
    print(f"   SDK: {space_info.sdk}")
    print(f"   Runtime: {getattr(space_info, 'runtime', 'N/A')}")
    print(f"   Hardware: {getattr(space_info, 'hardware', 'N/A')}")
    
    # Try to list variables (this might not work with the API)
    print("\n📋 Space Configuration:")
    print(f"   Last modified: {space_info.last_modified}")
    print(f"   Private: {getattr(space_info, 'private', 'N/A')}")
    
    # Check if there's a variables attribute
    if hasattr(space_info, 'variables'):
        print(f"\n🔧 Variables found:")
        for key, value in space_info.variables.items():
            # Don't print secret values
            print(f"   - {key}: {'***' if 'TOKEN' in key or 'SECRET' in key else value}")
    else:
        print("\n⚠️  Cannot list variables via API")
        print("   Variables and secrets must be checked in the web UI:")
        print(f"   👉 https://huggingface.co/spaces/{space_id}/settings")
    
    print("\n" + "="*70)
    print("🌐 TO CHECK/DELETE VITE_API_URL:")
    print("="*70)
    print(f"1. Open: https://huggingface.co/spaces/{space_id}/settings")
    print("2. Scroll to 'Variables and secrets' section")
    print("3. Look for 'VITE_API_URL' in the list")
    print("4. If found, DELETE it (trash icon)")
    print("5. Or change value to: /api (just '/api', NOT 'http://...')")
    print("="*70)
    
except Exception as e:
    print(f"❌ Error: {e}")
    print(f"\n💡 Check manually at: https://huggingface.co/spaces/{space_id}/settings")
