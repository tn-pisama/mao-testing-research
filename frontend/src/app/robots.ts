import type { MetadataRoute } from 'next'

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: '*',
        allow: ['/', '/docs/', '/terms', '/llms.txt', '/llms-full.txt'],
        disallow: [
          '/api/',
          '/dashboard/',
          '/settings/',
          '/account/',
          '/sign-in/',
          '/sign-up/',
          '/agents/',
          '/traces/',
          '/detections/',
          '/healing/',
          '/quality/',
          '/evals/',
          '/testing/',
          '/chaos/',
          '/replay/',
          '/regression/',
          '/security/',
          '/memory/',
          '/integrations/',
          '/import/',
          '/metrics/',
          '/benchmarks/',
          '/tools/',
          '/n8n/',
          '/dify/',
          '/langgraph/',
          '/openclaw/',
          '/diagnose/',
          '/review/',
          '/detector-status/',
          '/conversation-evaluations/',
          '/workflows/',
          '/marketplace/',
        ],
      },
    ],
    sitemap: 'https://pisama.ai/sitemap.xml',
  }
}
