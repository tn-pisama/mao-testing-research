#!/bin/bash
cd /Users/tuomonikulainen/mao-testing-research/frontend

# Function to set env var
set_env() {
  local name=$1
  local value=$2
  echo "Setting $name..."
  printf "%s\ny\n" "$value" | vercel env add "$name" production 2>&1 | grep -E "✅|Added|Error" || echo "Set $name"
}

# Set all environment variables
set_env "GOOGLE_CLIENT_ID" "434388095406-cts6c7adorf7pmene3e87hn1rkj38ol6.apps.googleusercontent.com"
set_env "GOOGLE_CLIENT_SECRET" "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"
set_env "NEXTAUTH_SECRET" "O1a7nYdTSgevRPB1ATSjYwf77eR+BmGmW7HyLktS37M="
set_env "NEXTAUTH_URL" "https://pisama.ai"

echo "✅ All environment variables set"
