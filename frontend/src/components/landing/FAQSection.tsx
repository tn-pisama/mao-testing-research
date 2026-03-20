'use client'

import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { analytics } from '@/lib/analytics'

export function FAQSection() {
  const [openIndex, setOpenIndex] = useState<number | null>(0)

  const faqs = [
    {
      question: 'How is Pisama different from LangSmith or Langfuse?',
      answer: 'LangSmith and Langfuse are general-purpose observability tools for LLM applications. Pisama is purpose-built for multi-agent failure detection — it identifies 42 specific failure modes like infinite loops, state corruption, persona drift, and convergence issues that general observability tools don\'t detect.',
    },
    {
      question: 'What frameworks does Pisama support?',
      answer: 'Pisama has native integrations for LangGraph, CrewAI, AutoGen, n8n, Dify, OpenClaw, and Claude Code. Any framework that emits OpenTelemetry traces with gen_ai.* semantic conventions works out of the box.',
    },
    {
      question: 'What\'s the performance overhead?',
      answer: 'Minimal. Tier 1 detection (hash-based) adds <5ms. Tier 2 (state delta) adds ~10ms. Tier 3 (embeddings) adds ~100ms. You control which tiers run via configuration.',
    },
    {
      question: 'Can I self-host Pisama?',
      answer: 'Yes. The core detection engine is open source under the MIT license. Deploy with Docker Compose or Fly.io — see the deployment guide in our docs.',
    },
    {
      question: 'What does self-healing do?',
      answer: 'When Pisama detects a failure, it generates AI-powered fix suggestions with code changes. Safe fixes (config changes, retry limits) can auto-apply. Risky fixes (prompt modifications) require manual approval. All fixes include rollback capability.',
    },
    {
      question: 'How accurate are the detectors?',
      answer: '31 of 42 detectors are production-grade with F1 scores above 0.70. The top detectors (decomposition, loop, corruption) achieve F1 > 0.90. All detectors are calibrated against golden datasets with cross-validation.',
    },
  ]

  return (
    <section className="py-16 px-4">
      <div className="max-w-3xl mx-auto">
        <div className="text-center mb-10">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-3">
            Frequently Asked Questions
          </h2>
          <p className="text-zinc-400">
            Everything you need to know about Pisama
          </p>
        </div>

        <div className="space-y-3">
          {faqs.map((faq, index) => (
            <div
              key={index}
              className="bg-zinc-800/50 border border-zinc-700 rounded-lg overflow-hidden hover:border-zinc-600 transition-colors"
            >
              <button
                onClick={() => {
                  const newIndex = openIndex === index ? null : index
                  setOpenIndex(newIndex)
                  if (newIndex === index) {
                    analytics.faqOpen(faq.question)
                  }
                }}
                className="w-full flex items-center justify-between p-5 text-left"
                aria-expanded={openIndex === index}
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
                <div className="px-5 pb-5">
                  <p className="text-zinc-400 leading-relaxed">
                    {faq.answer}
                  </p>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
