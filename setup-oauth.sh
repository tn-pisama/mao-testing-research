#!/bin/bash
# Google OAuth Setup Script for PISAMA
# Run after creating OAuth credentials in Google Cloud Console

set -e

echo "🔐 PISAMA Google OAuth Setup"
echo "================================"
echo ""

# Generated secrets
NEXTAUTH_SECRET="O1a7nYdTSgevRPB1ATSjYwf77eR+BmGmW7HyLktS37M="
NEXTAUTH_URL="https://pisama.ai"

echo "✅ NEXTAUTH_SECRET generated"
echo "✅ NEXTAUTH_URL set to: $NEXTAUTH_URL"
echo ""

# Prompt for Google OAuth credentials
echo "📝 Please paste your Google OAuth credentials:"
echo ""
read -p "GOOGLE_CLIENT_ID: " GOOGLE_CLIENT_ID
read -p "GOOGLE_CLIENT_SECRET: " GOOGLE_CLIENT_SECRET

echo ""
echo "🚀 Setting up environment variables..."
echo ""

# Update Vercel (Frontend)
echo "📦 Updating Vercel environment variables..."
cd /Users/tuomonikulainen/mao-testing-research/frontend

vercel env add GOOGLE_CLIENT_ID production <<< "$GOOGLE_CLIENT_ID"
vercel env add GOOGLE_CLIENT_SECRET production <<< "$GOOGLE_CLIENT_SECRET"
vercel env add NEXTAUTH_SECRET production <<< "$NEXTAUTH_SECRET"
vercel env add NEXTAUTH_URL production <<< "$NEXTAUTH_URL"

echo "✅ Vercel env vars updated"
echo ""

# Update Fly.io (Backend)
echo "📦 Updating Fly.io environment variables..."
cd /Users/tuomonikulainen/mao-testing-research/backend

flyctl secrets set \
  GOOGLE_CLIENT_ID="$GOOGLE_CLIENT_ID" \
  GOOGLE_CLIENT_SECRET="$GOOGLE_CLIENT_SECRET" \
  --app mao-api

echo "✅ Fly.io secrets updated"
echo ""

# Run database migration
echo "🗄️  Running database migration..."
flyctl ssh console --app mao-api -C "cd /app && alembic upgrade head"

echo "✅ Database migrated"
echo ""

# Trigger deployments
echo "🚀 Triggering deployments..."
cd /Users/tuomonikulainen/mao-testing-research/frontend
vercel --prod

echo ""
echo "✅ All done! Google OAuth is now configured."
echo ""
echo "Test your authentication at: https://pisama.ai/sign-in"
