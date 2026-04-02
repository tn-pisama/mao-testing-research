# Google Search Console Setup — pisama.ai

This is the ONE thing only you can do. Takes 5 minutes, one-time.

## Step 1: Go to Search Console
https://search.google.com/search-console/welcome

## Step 2: Add Property
- Choose **"URL prefix"** method
- Enter: `https://pisama.ai`

## Step 3: Verify Ownership
Easiest method for Vercel:
1. Choose **"HTML tag"** verification
2. Copy the meta tag they give you (looks like `<meta name="google-site-verification" content="xxxxx" />`)
3. Add it to `frontend/src/app/layout.tsx` in the metadata export:
```typescript
export const metadata: Metadata = {
  // ... existing metadata ...
  verification: {
    google: 'xxxxx', // paste the content value here
  },
}
```
4. Deploy (`vercel --prod`)
5. Click "Verify" in Search Console

## Step 4: Submit Sitemap
1. In Search Console sidebar, click **"Sitemaps"**
2. Enter: `sitemap.xml`
3. Click **"Submit"**

## Step 5: Request Indexing (optional but speeds things up)
1. In the top search bar, paste: `https://pisama.ai`
2. Click **"Request Indexing"**
3. Repeat for `https://pisama.ai/docs` and any other key pages

## That's It
Google will start crawling within 24-48 hours after sitemap submission.
The IndexNow submission (already done) handles Bing/Yandex/Seznam/Naver.
