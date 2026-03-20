import type { MetadataRoute } from 'next'

export default function sitemap(): MetadataRoute.Sitemap {
  const base = 'https://pisama.ai'
  return [
    { url: base, lastModified: new Date(), changeFrequency: 'weekly', priority: 1 },
    { url: `${base}/docs`, lastModified: new Date(), changeFrequency: 'weekly', priority: 0.8 },
    { url: `${base}/docs/getting-started`, lastModified: new Date(), changeFrequency: 'monthly', priority: 0.8 },
    { url: `${base}/docs/api-reference`, lastModified: new Date(), changeFrequency: 'monthly', priority: 0.7 },
    { url: `${base}/docs/failure-modes`, lastModified: new Date(), changeFrequency: 'monthly', priority: 0.7 },
    { url: `${base}/docs/sdk`, lastModified: new Date(), changeFrequency: 'monthly', priority: 0.7 },
    { url: `${base}/docs/cli`, lastModified: new Date(), changeFrequency: 'monthly', priority: 0.6 },
    { url: `${base}/docs/n8n`, lastModified: new Date(), changeFrequency: 'monthly', priority: 0.6 },
    { url: `${base}/docs/langgraph`, lastModified: new Date(), changeFrequency: 'monthly', priority: 0.6 },
    { url: `${base}/docs/dify`, lastModified: new Date(), changeFrequency: 'monthly', priority: 0.6 },
    { url: `${base}/docs/openclaw`, lastModified: new Date(), changeFrequency: 'monthly', priority: 0.6 },
    { url: `${base}/docs/detections`, lastModified: new Date(), changeFrequency: 'monthly', priority: 0.7 },
    { url: `${base}/docs/methodology`, lastModified: new Date(), changeFrequency: 'monthly', priority: 0.6 },
    { url: `${base}/terms`, lastModified: new Date(), changeFrequency: 'yearly', priority: 0.3 },
  ]
}
