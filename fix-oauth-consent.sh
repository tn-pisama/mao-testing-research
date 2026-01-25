#!/bin/bash
# Script to automate OAuth consent screen configuration

PROJECT_ID="ai-discovery-469923"
BRAND_NAME="projects/434388095406/brands/434388095406"

echo "🔧 Attempting to fix OAuth Consent Screen..."
echo "================================================"

# Try to update the brand to external using REST API
ACCESS_TOKEN=$(gcloud auth application-default print-access-token)

echo ""
echo "Attempting to update OAuth consent screen to External..."

# The Google IAP API doesn't support updating orgInternalOnly from true to false
# This MUST be done manually in the Console

echo ""
echo "❌ Google does NOT provide an API to change consent screen from Internal to External"
echo ""
echo "📋 Here's what you MUST do manually (takes 2 minutes):"
echo ""
echo "I'm opening the Google Cloud Console OAuth consent screen page..."
echo ""

open "https://console.cloud.google.com/apis/credentials/consent?project=ai-discovery-469923"

echo "On the page that just opened:"
echo ""
echo "1. Look for the 'User type' section"
echo "2. It currently says: 'Internal'"
echo "3. Click the 'MAKE EXTERNAL' button (if available)"
echo "   OR"
echo "   Click 'EDIT APP' and change User Type to 'External'"
echo ""
echo "4. Fill in the required fields:"
echo "   - App name: PISAMA"
echo "   - User support email: tuomo@pisama.ai"
echo "   - Authorized domains: pisama.ai"
echo "   - Developer contact: tuomo@pisama.ai"
echo ""
echo "5. On the Scopes page, add:"
echo "   - .../auth/userinfo.email"
echo "   - .../auth/userinfo.profile"
echo "   - openid"
echo ""
echo "6. On Test users page (for External apps in testing):"
echo "   - Add: tuomo@pisama.ai"
echo ""
echo "7. Click 'SAVE AND CONTINUE' through all pages"
echo ""
echo "8. When done, come back and run:"
echo "   ./verify-oauth-fix.sh"
echo ""
echo "================================================"
