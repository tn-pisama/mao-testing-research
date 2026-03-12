/**
 * Google Analytics 4 Event Tracking
 *
 * Usage:
 * import { trackEvent } from '@/lib/analytics'
 * trackEvent('waitlist_signup', { method: 'modal' })
 */

declare global {
  interface Window {
    gtag?: (
      command: 'event' | 'config' | 'set',
      targetId: string,
      config?: Record<string, unknown>
    ) => void
  }
}

export const GA_MEASUREMENT_ID = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID

/**
 * Track custom events in Google Analytics
 */
export const trackEvent = (
  eventName: string,
  eventParams?: Record<string, unknown>
) => {
  if (typeof window !== 'undefined' && window.gtag && GA_MEASUREMENT_ID) {
    window.gtag('event', eventName, {
      ...eventParams,
      send_to: GA_MEASUREMENT_ID,
    })
  }
}

/**
 * Track page views (automatically handled by Next.js GoogleAnalytics component)
 */
export const trackPageView = (url: string) => {
  if (typeof window !== 'undefined' && window.gtag && GA_MEASUREMENT_ID) {
    window.gtag('config', GA_MEASUREMENT_ID, {
      page_path: url,
    })
  }
}

/**
 * Predefined event trackers for common actions
 */
export const analytics = {
  // Conversion Events
  waitlistSignup: (method: 'modal' | 'inline' | 'hero') => {
    trackEvent('waitlist_signup', {
      method,
      event_category: 'conversion',
      event_label: 'Waitlist Signup',
    })
  },

  // CTA Clicks
  ctaClick: (location: string, ctaText: string) => {
    trackEvent('cta_click', {
      location,
      cta_text: ctaText,
      event_category: 'engagement',
    })
  },

  // Demo Video
  videoPlay: () => {
    trackEvent('video_play', {
      video_title: 'PISAMA Demo',
      event_category: 'engagement',
    })
  },

  // Section Views (scroll tracking)
  sectionView: (sectionName: string) => {
    trackEvent('section_view', {
      section_name: sectionName,
      event_category: 'engagement',
    })
  },

  // FAQ Interactions
  faqOpen: (question: string) => {
    trackEvent('faq_open', {
      question,
      event_category: 'engagement',
    })
  },

  // External Links
  externalLinkClick: (url: string, linkText: string) => {
    trackEvent('external_link_click', {
      url,
      link_text: linkText,
      event_category: 'navigation',
    })
  },

  // Email Submission (success/error)
  emailSubmit: (status: 'success' | 'error', method: string) => {
    trackEvent('email_submit', {
      status,
      method,
      event_category: 'conversion',
    })
  },
}
