'use client'

import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { analytics } from '@/lib/analytics'

export function FAQSection() {
  const [openIndex, setOpenIndex] = useState<number | null>(0)

  const faqs = [
    {
      question: 'How is PISAMA different from LangSmith?',
      answer: 'LangSmith is great for observability and debugging in production. PISAMA is designed for *testing* before production—it\'s optimized for CI/CD and detects multi-agent-specific failure modes. Use both: PISAMA in testing, LangSmith in production.',
    },
    {
      question: 'Does PISAMA work with my custom agent framework?',
      answer: 'Yes! If your framework can emit OpenTelemetry traces with `gen_ai.*` semantic conventions, PISAMA can analyze it. We have native integrations for LangGraph, CrewAI, AutoGen, and n8n.',
    },
    {
      question: 'What\'s the performance overhead?',
      answer: 'Minimal. Tier 1 detection adds <5ms latency. Tier 3 (embeddings) adds ~100ms. You control which tiers run via configuration. Most users run Tier 1-2 in CI, Tier 3-4 only on critical workflows.',
    },
    {
      question: 'Can I self-host PISAMA?',
      answer: 'Yes! Core detection engine is open source (MIT license). Self-hosting guide in the docs. Enterprise plan includes support for self-hosted deployments.',
    },
    {
      question: 'How do you handle my trace data?',
      answer: 'Traces are encrypted in transit and at rest. We never train on your data. Enterprise customers can self-host for complete data control.',
    },
    {
      question: 'What if I hit my trace limit?',
      answer: 'We\'ll email you at 80% and 100% usage. After hitting your limit, you can upgrade or wait until next month. We don\'t cut you off mid-test—current tests complete normally.',
    },
    {
      question: 'Do you offer educational discounts?',
      answer: 'Yes! Students and educators get the Startup plan free. Email support@pisama.ai with your .edu address.',
    },
    {
      question: 'What\'s your refund policy?',
      answer: '30-day money-back guarantee on paid plans, no questions asked.',
    },
  ]

  return (
    <section className="py-20 px-4">
      <div className="max-w-3xl mx-auto">
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
            Frequently Asked Questions
          </h2>
          <p className="text-zinc-400">
            Everything you need to know about PISAMA
          </p>
        </div>

        <div className="space-y-4">
          {faqs.map((faq, index) => (
            <div
              key={index}
              className="bg-zinc-800/50 border border-zinc-700 rounded-lg overflow-hidden hover:border-sky-500/50 transition-colors"
            >
              <button
                onClick={() => {
                  const newIndex = openIndex === index ? null : index
                  setOpenIndex(newIndex)
                  // Track when opening (not closing)
                  if (newIndex === index) {
                    analytics.faqOpen(faq.question)
                  }
                }}
                className="w-full flex items-center justify-between p-6 text-left"
              >
                <span className="text-white font-medium pr-8">
                  {faq.question}
                </span>
                <ChevronDown
                  className={`w-5 h-5 text-zinc-400 flex-shrink-0 transition-transform ${
                    openIndex === index ? 'rotate-180' : ''
                  }`}
                />
              </button>

              {openIndex === index && (
                <div className="px-6 pb-6">
                  <p className="text-zinc-400 leading-relaxed">
                    {faq.answer}
                  </p>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Contact CTA */}
        <div className="mt-12 text-center">
          <p className="text-zinc-400 mb-4">
            Still have questions?
          </p>
          <a
            href="mailto:support@pisama.ai"
            className="inline-flex items-center gap-2 text-sky-400 hover:text-sky-300 font-medium transition-colors"
          >
            Contact Support →
          </a>
        </div>
      </div>
    </section>
  )
}
