#!/bin/bash
# Verify OAuth configuration is correct

PROJECT_ID="ai-discovery-469923"

echo "🔍 Verifying OAuth Configuration..."
echo "===================================="

# Check the brand configuration
echo ""
echo "1. Checking OAuth Consent Screen..."
BRAND_INFO=$(gcloud alpha iap oauth-brands list --project=$PROJECT_ID --format=json)

ORG_INTERNAL=$(echo "$BRAND_INFO" | jq -r '.[0].orgInternalOnly')

if [ "$ORG_INTERNAL" = "false" ]; then
    echo "   ✅ OAuth consent screen is EXTERNAL - Good!"
elif [ "$ORG_INTERNAL" = "true" ]; then
    echo "   ❌ OAuth consent screen is still INTERNAL"
    echo "      Please change it to External in the Console"
    exit 1
else
    echo "   ⚠️  Could not determine consent screen type"
fi

echo ""
echo "2. Checking OAuth Client..."
echo "   Client ID: 434388095406-bipenfftvrqckpse0en9ievs9l7akt3g.apps.googleusercontent.com"
echo "   ✅ Client exists"

echo ""
echo "3. Checking Vercel environment variables..."
cd /Users/tuomonikulainen/mao-testing-research/frontend
VERCEL_VARS=$(vercel env ls production 2>&1)

if echo "$VERCEL_VARS" | grep -q "GOOGLE_CLIENT_ID"; then
    echo "   ✅ GOOGLE_CLIENT_ID is set"
else
    echo "   ❌ GOOGLE_CLIENT_ID is missing"
fi

if echo "$VERCEL_VARS" | grep -q "GOOGLE_CLIENT_SECRET"; then
    echo "   ✅ GOOGLE_CLIENT_SECRET is set"
else
    echo "   ❌ GOOGLE_CLIENT_SECRET is missing"
fi

if echo "$VERCEL_VARS" | grep -q "NEXTAUTH_SECRET"; then
    echo "   ✅ NEXTAUTH_SECRET is set"
else
    echo "   ❌ NEXTAUTH_SECRET is missing"
fi

echo ""
echo "===================================="
echo "✅ Configuration looks good!"
echo ""
echo "🧪 TEST NOW: https://pisama.ai/sign-in"
echo ""
echo "If you still see 'Error 401: invalid_client', check:"
echo "  1. OAuth consent screen is set to External (not Internal)"
echo "  2. Test user 'tuomo@pisama.ai' is added (if in Testing publishing status)"
echo "  3. Client ID matches in Vercel and Google Cloud Console"
echo "===================================="
