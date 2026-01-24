#!/bin/bash
#
# Watch Vercel Deployment Status
# Checks every 30 seconds for new deployment
#

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Watching for Vercel deployment...${NC}"
echo "Press Ctrl+C to stop"
echo ""

LAST_DEPLOYMENT=""
CHECK_COUNT=0

while true; do
    CHECK_COUNT=$((CHECK_COUNT + 1))
    echo -e "${YELLOW}[Check $CHECK_COUNT] $(date '+%H:%M:%S')${NC}"

    cd /Users/tuomonikulainen/mao-testing-research/frontend
    CURRENT=$(vercel list 2>/dev/null | grep "Ready" | head -1 | awk '{print $2}')

    if [ "$CURRENT" != "$LAST_DEPLOYMENT" ] && [ -n "$CURRENT" ]; then
        echo -e "${GREEN}✓ NEW DEPLOYMENT DETECTED!${NC}"
        echo "  URL: $CURRENT"
        echo ""
        echo -e "${GREEN}Deployment is live! Next steps:${NC}"
        echo "1. Go to https://pisama.ai/traces"
        echo "2. Hard refresh: Cmd+Shift+R (Mac) or Ctrl+Shift+F5"
        echo "3. Open DevTools → Network tab"
        echo "4. Check URL contains real UUID (not {tenant_id})"
        echo ""
        break
    else
        echo "  Waiting for new deployment..."
        LAST_DEPLOYMENT="$CURRENT"
    fi

    sleep 30
done

echo -e "${GREEN}Done!${NC}"
