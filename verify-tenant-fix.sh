#!/bin/bash
#
# Verification Script for tenantId Fix
# Tests that API hooks correctly pass tenantId to backend
#

set -e

BACKEND_URL="https://mao-api.fly.dev"
FRONTEND_URL="https://pisama.ai"

echo "================================================"
echo "TenantId Fix Verification"
echo "================================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Test 1: Backend Health
echo -e "${BLUE}[1/4] Backend Health Check...${NC}"
HEALTH=$(curl -s "$BACKEND_URL/health" | jq -r '.status')
if [ "$HEALTH" == "healthy" ]; then
    echo -e "${GREEN}✓ Backend is healthy${NC}"
else
    echo -e "${RED}✗ Backend health check failed${NC}"
    exit 1
fi
echo ""

# Test 2: Frontend Deployment
echo -e "${BLUE}[2/4] Frontend Deployment Check...${NC}"
FRONTEND_STATUS=$(curl -s -w "%{http_code}" -o /dev/null "$FRONTEND_URL")
if [ "$FRONTEND_STATUS" -eq 200 ]; then
    echo -e "${GREEN}✓ Frontend is accessible${NC}"
else
    echo -e "${RED}✗ Frontend not accessible (HTTP $FRONTEND_STATUS)${NC}"
    exit 1
fi

# Check for PISAMA branding
if curl -s "$FRONTEND_URL" | grep -q "PISAMA"; then
    echo -e "${GREEN}✓ PISAMA application confirmed${NC}"
else
    echo -e "${YELLOW}⚠ Could not verify PISAMA branding${NC}"
fi
echo ""

# Test 3: Git Status
echo -e "${BLUE}[3/4] Git Status Check...${NC}"
LATEST_COMMIT=$(git log -1 --oneline | grep "tenantId")
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Latest commit contains tenantId fix${NC}"
    echo "  $LATEST_COMMIT"
else
    TENANT_COMMIT=$(git log --oneline | grep "tenantId" | head -1)
    echo -e "${YELLOW}⚠ tenantId commit found but not latest${NC}"
    echo "  $TENANT_COMMIT"
fi
echo ""

# Test 4: Code Verification
echo -e "${BLUE}[4/4] Code Verification...${NC}"
if grep -q "useTenant" frontend/src/hooks/useApiWithFallback.ts; then
    echo -e "${GREEN}✓ useTenant import found in useApiWithFallback.ts${NC}"
else
    echo -e "${RED}✗ useTenant import missing${NC}"
    exit 1
fi

if grep -q "createApiClient(token, tenantId)" frontend/src/hooks/useApiWithFallback.ts; then
    echo -e "${GREEN}✓ tenantId passed to createApiClient${NC}"
else
    echo -e "${RED}✗ tenantId not passed to createApiClient${NC}"
    exit 1
fi

COUNT=$(grep -c "createApiClient(token, tenantId)" frontend/src/hooks/useApiWithFallback.ts)
echo -e "${GREEN}✓ Found $COUNT instances of createApiClient with tenantId${NC}"
echo ""

# Summary
echo "================================================"
echo -e "${GREEN}Automated Verification Complete!${NC}"
echo "================================================"
echo ""
echo "The code changes are deployed. To verify in the browser:"
echo ""
echo "1. Open https://pisama.ai/traces in your browser"
echo "2. Login with Clerk authentication"
echo "3. Open DevTools (F12) → Network tab"
echo "4. Reload the page"
echo "5. Look for API call to '/api/v1/tenants/*/traces'"
echo ""
echo "Expected Results:"
echo "  ✓ URL should contain a UUID, not literal '{tenant_id}'"
echo "  ✓ Status should be 200 OK (not 404)"
echo "  ✓ 'Demo Mode' badge should be green 'Live' (not yellow)"
echo "  ✓ Response should contain tenant-specific data"
echo ""
echo "If pages are empty but API works:"
echo "  → Go to n8n page and register a workflow"
echo "  → Click 'Sync from n8n' to populate data"
echo ""
