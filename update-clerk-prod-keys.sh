#!/bin/bash
#
# Update Clerk Production Keys in Vercel
#
# Usage: ./update-clerk-prod-keys.sh
#

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}        Update Clerk Production Keys in Vercel${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${YELLOW}⚠️  Current Status:${NC}"
echo "   Production is using Clerk TEST keys (pk_test_...)"
echo "   This causes the warning: 'Clerk has been loaded with development keys'"
echo ""

echo -e "${BLUE}📋 Before running this script:${NC}"
echo ""
echo "   1. Open Clerk Dashboard:"
echo -e "      ${GREEN}https://dashboard.clerk.com${NC}"
echo ""
echo "   2. Navigate to: Configure → API Keys → Production"
echo ""
echo "   3. Copy both keys:"
echo "      • Publishable key (starts with pk_live_)"
echo "      • Secret key (starts with sk_live_)"
echo ""

read -p "Do you have your production keys ready? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Please get your production keys first, then run this script again.${NC}"
    exit 0
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Step 1: Remove old test keys from Vercel${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

cd /Users/tuomonikulainen/mao-testing-research/frontend

echo "Removing NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY..."
vercel env rm NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY production --yes || echo "Key already removed"

echo "Removing CLERK_SECRET_KEY..."
vercel env rm CLERK_SECRET_KEY production --yes || echo "Key already removed"

echo ""
echo -e "${GREEN}✓ Old keys removed${NC}"
echo ""

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Step 2: Add production keys${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${YELLOW}When prompted, paste your production keys:${NC}"
echo ""

echo "Adding NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY (pk_live_...)..."
vercel env add NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY production

echo ""
echo "Adding CLERK_SECRET_KEY (sk_live_...)..."
vercel env add CLERK_SECRET_KEY production

echo ""
echo -e "${GREEN}✓ Production keys added to Vercel${NC}"
echo ""

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Step 3: Deploy to production${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo "Deploying with new production keys..."
vercel --prod

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Success! Clerk production keys configured${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${YELLOW}📋 Next Steps:${NC}"
echo ""
echo "1. Wait 1-2 minutes for deployment to complete"
echo "2. Go to https://pisama.ai"
echo "3. Hard refresh: Cmd+Shift+R (Mac) or Ctrl+Shift+F5 (Windows)"
echo "4. Open DevTools → Console"
echo "5. Verify NO warning about development keys"
echo ""
echo "6. Check Network tab:"
echo "   ✅ URLs should have real UUIDs: /api/v1/tenants/abc-123.../traces"
echo "   ✅ Status should be: 200 OK"
echo "   ✅ Badge should show: green 'Live'"
echo ""
echo -e "${GREEN}Done!${NC}"
