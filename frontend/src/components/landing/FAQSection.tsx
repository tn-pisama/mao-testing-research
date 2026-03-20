'use client'

import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { analytics } from '@/lib/analytics'

export function FAQSection() {
  const [openIndex, setOpenIndex] = useState<number | null>(0)

  const faqs = [
    {
      question: 'What problems does Pisama solve?',
      answer: 'AI agents fail silently — a coding agent loops for 40 minutes burning tokens, a research agent hallucinates citations, a support agent drifts from its role. Pisama detects these failures automatically and suggests fixes before they reach production.',
    },
    {
      question: 'How do I get started?',
      answer: 'Sign up, connect your agent framework, and send your first trace. Pisama starts detecting failures immediately — no training data or configuration required. Most teams are up and running in under 5 minutes.',
    },
    {
      question: 'What frameworks are supported?',
      answer: 'LangGraph, CrewAI, AutoGen, n8n, Dify, OpenClaw, and Claude Code all have native integrations. Any framework that supports OpenTelemetry also works out of the box.',
    },
    {
      question: 'How is this different from LangSmith or Langfuse?',
      answer: 'Those tools are general-purpose observability — they show you what happened. Pisama tells you what went wrong and how to fix it. It detects 42 specific failure modes across multi-agent systems that general logging tools miss.',
    },
    {
      question: 'What happens when a failure is detected?',
      answer: 'Pisama identifies the root cause, generates a fix suggestion with actual code changes, and can auto-apply safe fixes like retry limits or circuit breakers. Fixes that modify prompts or core logic require your approval first. Everything is reversible.',
    },
    {
      question: 'Can I self-host it?',
      answer: 'Yes. Pisama is open source under the MIT license. You can deploy it with Docker Compose or on Fly.io. Full control over your data.',
    },
    {
      question: 'Will it slow down my agents?',
      answer: 'No. Detection runs on your traces after the fact, not inline with your agent execution. There is zero performance impact on your running agents.',
    },
  ]

  return (
    <section className="py-16 px-4">
      <div className="max-w-3xl mx-auto">
        <div className="text-center mb-10">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-3">
            Frequently Asked Questions
          </h2>
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
