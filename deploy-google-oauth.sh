#!/bin/bash
# Complete Google OAuth Deployment Script for PISAMA
# Automates: Vercel env vars, Fly.io secrets, DB migration, and deployment

set -e

echo "🚀 PISAMA Google OAuth Deployment"
echo "===================================="
echo ""

# Pre-generated secrets
NEXTAUTH_SECRET="O1a7nYdTSgevRPB1ATSjYwf77eR+BmGmW7HyLktS37M="
NEXTAUTH_URL="https://pisama.ai"
BACKEND_URL="https://mao-api.fly.dev"

echo "✅ Generated secrets loaded"
echo ""

# Check if credentials are provided as arguments
if [ "$#" -eq 2 ]; then
    GOOGLE_CLIENT_ID="$1"
    GOOGLE_CLIENT_SECRET="$2"
    echo "✅ Using credentials from arguments"
else
    # Prompt for credentials
    echo "📝 Enter your Google OAuth credentials from:"
    echo "   https://console.cloud.google.com/apis/credentials?project=ai-discovery-469923"
    echo ""
    read -p "GOOGLE_CLIENT_ID: " GOOGLE_CLIENT_ID
    read -p "GOOGLE_CLIENT_SECRET: " GOOGLE_CLIENT_SECRET
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 STEP 1: Updating Vercel Environment Variables"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd /Users/tuomonikulainen/mao-testing-research/frontend

echo "Setting GOOGLE_CLIENT_ID..."
echo "$GOOGLE_CLIENT_ID" | vercel env add GOOGLE_CLIENT_ID production --yes 2>/dev/null || \
  vercel env rm GOOGLE_CLIENT_ID production --yes && echo "$GOOGLE_CLIENT_ID" | vercel env add GOOGLE_CLIENT_ID production --yes

echo "Setting GOOGLE_CLIENT_SECRET..."
echo "$GOOGLE_CLIENT_SECRET" | vercel env add GOOGLE_CLIENT_SECRET production --yes 2>/dev/null || \
  vercel env rm GOOGLE_CLIENT_SECRET production --yes && echo "$GOOGLE_CLIENT_SECRET" | vercel env add GOOGLE_CLIENT_SECRET production --yes

echo "Setting NEXTAUTH_SECRET..."
echo "$NEXTAUTH_SECRET" | vercel env add NEXTAUTH_SECRET production --yes 2>/dev/null || \
  vercel env rm NEXTAUTH_SECRET production --yes && echo "$NEXTAUTH_SECRET" | vercel env add NEXTAUTH_SECRET production --yes

echo "Setting NEXTAUTH_URL..."
echo "$NEXTAUTH_URL" | vercel env add NEXTAUTH_URL production --yes 2>/dev/null || \
  vercel env rm NEXTAUTH_URL production --yes && echo "$NEXTAUTH_URL" | vercel env add NEXTAUTH_URL production --yes

echo "✅ Vercel environment variables updated"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 STEP 2: Updating Fly.io Secrets"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd /Users/tuomonikulainen/mao-testing-research/backend

echo "Setting Google OAuth secrets on Fly.io..."
flyctl secrets set \
  GOOGLE_CLIENT_ID="$GOOGLE_CLIENT_ID" \
  GOOGLE_CLIENT_SECRET="$GOOGLE_CLIENT_SECRET" \
  --app mao-api

echo "✅ Fly.io secrets updated"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🗄️  STEP 3: Running Database Migration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "Starting mao-api machine..."
flyctl machine start --app mao-api 2>/dev/null || echo "Machine already running"

sleep 5

echo "Running Alembic migration..."
flyctl ssh console --app mao-api -C "cd /app && alembic upgrade head"

echo "✅ Database migration completed"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 STEP 4: Deploying Frontend to Vercel"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd /Users/tuomonikulainen/mao-testing-research/frontend

echo "Triggering production deployment..."
vercel --prod --yes

echo "✅ Frontend deployed"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ DEPLOYMENT COMPLETE!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🎉 Google OAuth is now live!"
echo ""
echo "📍 Test your authentication:"
echo "   https://pisama.ai/sign-in"
echo ""
echo "🔍 Verify backend health:"
echo "   https://mao-api.fly.dev/health"
echo ""
echo "💰 Cost savings: $300-$1,200/year (removed Clerk)"
echo ""
