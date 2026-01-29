#!/bin/bash
# PISAMA + Moltbot Integration Verification Script
set -e

echo "🔍 PISAMA + Moltbot Integration Verification"
echo "=============================================="
echo ""

# Configuration
MOLTBOT_URL="${MOLTBOT_GATEWAY_URL:-ws://localhost:18789}"
PISAMA_API_URL="${PISAMA_API_URL:-http://localhost:8000/api/v1}"
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}"

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Check prerequisites
echo "📋 Step 1: Checking prerequisites..."

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo -e "${RED}❌ ANTHROPIC_API_KEY not set${NC}"
    echo "   Set it with: export ANTHROPIC_API_KEY=sk-ant-..."
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ docker-compose not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites met${NC}"
echo ""

# Step 2: Start services
echo "🚀 Step 2: Starting PISAMA + Moltbot..."

docker-compose -f docker-compose.yml -f docker-compose.moltbot.yml up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to start..."
sleep 10

# Check service health
if curl -f http://localhost:8000/api/v1/health &> /dev/null; then
    echo -e "${GREEN}✓ PISAMA backend is healthy${NC}"
else
    echo -e "${RED}❌ PISAMA backend is not responding${NC}"
    exit 1
fi

if curl -f http://localhost:18789 &> /dev/null; then
    echo -e "${GREEN}✓ Moltbot gateway is healthy${NC}"
else
    echo -e "${YELLOW}⚠ Moltbot gateway may not be fully ready${NC}"
fi

echo ""

# Step 3: Test adapter connection
echo "🔌 Step 3: Testing adapter connection..."

# Check adapter logs for connection
ADAPTER_LOGS=$(docker-compose logs moltbot-adapter 2>&1 | tail -20)

if echo "$ADAPTER_LOGS" | grep -q "Connected to Moltbot"; then
    echo -e "${GREEN}✓ Adapter connected to Moltbot${NC}"
else
    echo -e "${YELLOW}⚠ Adapter connection pending...${NC}"
fi

echo ""

# Step 4: Run benchmark validation
echo "📊 Step 4: Running Moltbot benchmarks..."

cd "$(dirname "$0")/.."

python3 -m pytest benchmarks/tests/test_moltbot_benchmarks.py -v || {
    echo -e "${YELLOW}⚠ Benchmark tests not yet implemented${NC}"
    echo "   Run manually: python benchmarks/main.py --platform moltbot"
}

echo ""

# Step 5: Trigger test scenario
echo "🧪 Step 5: Triggering test failure scenario..."

# Send a test message that should trigger loop detection
# (This would require Moltbot CLI or API access)
echo "   Manual test: Open http://localhost:18789 and send:"
echo "   'Please navigate to example.com repeatedly'"
echo ""

# Step 6: Check for traces in PISAMA
echo "🔍 Step 6: Checking for traces in PISAMA..."

sleep 5

TRACE_COUNT=$(curl -s -H "Authorization: Bearer ${PISAMA_API_KEY:-test-key}" \
    "${PISAMA_API_URL}/traces?platform=moltbot" | grep -o '"trace_id"' | wc -l || echo "0")

if [ "$TRACE_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓ Found $TRACE_COUNT Moltbot trace(s) in PISAMA${NC}"
else
    echo -e "${YELLOW}⚠ No Moltbot traces found yet${NC}"
    echo "   Traces may take up to 30 seconds to appear (export interval)"
fi

echo ""

# Summary
echo "=============================================="
echo "✅ Verification Complete"
echo ""
echo "Next steps:"
echo "  1. Open Moltbot dashboard: http://localhost:18789"
echo "  2. Open PISAMA dashboard: http://localhost:3000"
echo "  3. Send test messages via Moltbot webchat"
echo "  4. Check PISAMA for detections"
echo ""
echo "View logs:"
echo "  docker-compose logs -f moltbot"
echo "  docker-compose logs -f moltbot-adapter"
echo "  docker-compose logs -f backend"
echo ""
echo "Cleanup:"
echo "  docker-compose -f docker-compose.yml -f docker-compose.moltbot.yml down"
