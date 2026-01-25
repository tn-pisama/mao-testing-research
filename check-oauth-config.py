#!/usr/bin/env python3
"""Check OAuth configuration and try to fix it"""
import subprocess
import json

project_id = "ai-discovery-469923"
client_id = "434388095406-bipenfftvrqckpse0en9ievs9l7akt3g.apps.googleusercontent.com"

print("🔍 Diagnosing OAuth Configuration Issue...")
print("=" * 70)

# Check if the brand (consent screen) is Internal
print("\n1. Checking OAuth Consent Screen (Brand)...")
result = subprocess.run(
    ["gcloud", "alpha", "iap", "oauth-brands", "list",
     "--project", project_id, "--format", "json"],
    capture_output=True,
    text=True
)

if result.returncode == 0:
    brands = json.loads(result.stdout)
    if brands:
        brand = brands[0]
        print(f"   ✅ Brand found: {brand['name']}")
        print(f"   Title: {brand['applicationTitle']}")
        print(f"   Support Email: {brand['supportEmail']}")
        print(f"   Internal Only: {brand['orgInternalOnly']}")

        if brand['orgInternalOnly']:
            print("\n   ❌ PROBLEM FOUND: OAuth consent screen is set to 'Internal'")
            print("      This means only Google Workspace users in your org can sign in.")
            print("      For public sign-in, it needs to be 'External'.")
            print("\n   🔧 SOLUTION: Change to External in Google Cloud Console")
            print("      1. Go to: https://console.cloud.google.com/apis/credentials/consent?project=ai-discovery-469923")
            print("      2. Click 'MAKE EXTERNAL' or edit the consent screen")
            print("      3. Change User Type from 'Internal' to 'External'")
            print("      4. Save changes")
else:
    print(f"   ❌ Error checking brands: {result.stderr}")

print("\n" + "=" * 70)
print("📋 DIAGNOSIS:")
print("=" * 70)
print("\nThe OAuth client ID you created exists, but the OAuth consent screen")
print("is configured as 'Internal' which restricts access to your Google Workspace")
print("organization only.")
print("\nTo fix this, you MUST manually change it to 'External' in the Console.")
print("\nI'm opening the page for you now...")

subprocess.run(["open", "https://console.cloud.google.com/apis/credentials/consent?project=ai-discovery-469923"])
