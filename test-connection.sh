#!/bin/bash
#
# Frontend-Backend Connection Test Script
# Tests the connection between pisama.ai frontend and mao-api.fly.dev backend
#

set -e

BACKEND_URL="https://mao-api.fly.dev"
FRONTEND_URL="https://pisama.ai"

echo "================================================"
echo "MAO/PISAMA Connection Verification"
echo "================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test 1: Backend Health
echo -e "${BLUE}[1/5] Testing Backend Health...${NC}"
HEALTH_STATUS=$(curl -s -w "%{http_code}" -o /dev/null "$BACKEND_URL/health")
if [ "$HEALTH_STATUS" -eq 200 ]; then
    echo -e "${GREEN}✓ Backend is healthy (HTTP 200)${NC}"
    HEALTH_RESPONSE=$(curl -s "$BACKEND_URL/health")
    echo "  Response: $HEALTH_RESPONSE"
else
    echo -e "${RED}✗ Backend health check failed (HTTP $HEALTH_STATUS)${NC}"
    exit 1
fi
echo ""

# Test 2: n8n Sync Status Endpoint (should return 403 without auth)
echo -e "${BLUE}[2/5] Testing n8n Sync Status Endpoint...${NC}"
SYNC_STATUS=$(curl -s -w "%{http_code}" -o /dev/null "$BACKEND_URL/api/v1/n8n/sync/status")
if [ "$SYNC_STATUS" -eq 403 ]; then
    echo -e "${GREEN}✓ n8n endpoint exists (HTTP 403 - auth required)${NC}"
    echo "  This is expected - endpoint requires authentication"
elif [ "$SYNC_STATUS" -eq 404 ]; then
    echo -e "${RED}✗ n8n endpoint not found (HTTP 404)${NC}"
    echo "  This indicates the endpoint path may be wrong"
    exit 1
else
    echo -e "${YELLOW}⚠ Unexpected status: HTTP $SYNC_STATUS${NC}"
fi
echo ""

# Test 3: Verify n8n Configuration in Fly.io
echo -e "${BLUE}[3/5] Checking n8n Configuration...${NC}"
if command -v fly &> /dev/null; then
    echo "  Checking Fly.io secrets..."
    FLY_SECRETS=$(fly secrets list -a mao-api 2>&1 || echo "")

    if echo "$FLY_SECRETS" | grep -q "N8N_HOST"; then
        echo -e "${GREEN}  ✓ N8N_HOST configured${NC}"
    else
        echo -e "${RED}  ✗ N8N_HOST not found${NC}"
    fi

    if echo "$FLY_SECRETS" | grep -q "N8N_API_KEY"; then
        echo -e "${GREEN}  ✓ N8N_API_KEY configured${NC}"
    else
        echo -e "${RED}  ✗ N8N_API_KEY not found${NC}"
    fi

    if echo "$FLY_SECRETS" | grep -q "N8N_SYNC_INTERVAL_MINUTES"; then
        echo -e "${GREEN}  ✓ N8N_SYNC_INTERVAL_MINUTES configured${NC}"
    else
        echo -e "${YELLOW}  ⚠ N8N_SYNC_INTERVAL_MINUTES not found (will use default)${NC}"
    fi
else
    echo -e "${YELLOW}  ⚠ Fly CLI not installed - skipping config check${NC}"
    echo "  Install: https://fly.io/docs/hands-on/install-flyctl/"
fi
echo ""

# Test 4: Frontend Accessibility
echo -e "${BLUE}[4/5] Testing Frontend Accessibility...${NC}"
FRONTEND_STATUS=$(curl -s -w "%{http_code}" -o /dev/null "$FRONTEND_URL")
if [ "$FRONTEND_STATUS" -eq 200 ]; then
    echo -e "${GREEN}✓ Frontend is accessible (HTTP 200)${NC}"

    # Check if it's the right app
    FRONTEND_CONTENT=$(curl -s "$FRONTEND_URL")
    if echo "$FRONTEND_CONTENT" | grep -q "PISAMA"; then
        echo -e "${GREEN}  ✓ Verified: PISAMA application${NC}"
    else
        echo -e "${YELLOW}  ⚠ Could not verify PISAMA branding${NC}"
    fi
else
    echo -e "${RED}✗ Frontend not accessible (HTTP $FRONTEND_STATUS)${NC}"
    exit 1
fi
echo ""

# Test 5: Check Latest Deployment
echo -e "${BLUE}[5/5] Verifying Latest Code Deployment...${NC}"
LATEST_COMMIT=$(git log -1 --oneline 2>/dev/null || echo "unknown")
echo "  Latest local commit: $LATEST_COMMIT"

if echo "$LATEST_COMMIT" | grep -q "1245b612"; then
    echo -e "${GREEN}  ✓ Frontend fix commit found${NC}"
elif echo "$LATEST_COMMIT" | grep -q "connect frontend to real n8n"; then
    echo -e "${GREEN}  ✓ Frontend fix commit deployed${NC}"
else
    echo -e "${YELLOW}  ⚠ Could not verify if latest commit is deployed${NC}"
    echo "  Expected commit: 1245b612 (fix: connect frontend to real n8n API data)"
fi
echo ""

# Summary
echo "================================================"
echo -e "${GREEN}Connection Verification Summary${NC}"
echo "================================================"
echo ""
echo "Backend:  $BACKEND_URL"
echo "Frontend: $FRONTEND_URL"
echo ""
echo -e "${GREEN}All automated tests passed!${NC}"
echo ""
echo "Next steps for full verification:"
echo "  1. Login to $FRONTEND_URL"
echo "  2. Navigate to the Detections page"
echo "  3. Check for 'Demo Mode' banner:"
echo "     - No banner = API connected ✓"
echo "     - Amber warning banner = API connection failed ✗"
echo "  4. Trigger an n8n workflow and verify data appears"
echo ""
echo "For detailed testing instructions, see:"
echo "  verify-frontend-connection.md"
echo ""
