'use client'

import { Terminal, Copy, Check, AlertTriangle } from 'lucide-react'
import { useState } from 'react'

export function CodeBlock({ title, language, children }: { title: string; language: string; children: React.ReactNode }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    const text = typeof children === 'string' ? children : ''
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="rounded-lg bg-zinc-900 border border-zinc-700 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-zinc-700 bg-zinc-800/50">
        <div className="flex items-center gap-2">
          <Terminal size={14} className="text-zinc-400" />
          <span className="text-sm text-zinc-400">{title}</span>
        </div>
        <button onClick={handleCopy} className="p-1 text-zinc-400 hover:text-white transition-colors" aria-label="Copy code">
          {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
        </button>
      </div>
      <pre className="p-4 text-sm text-zinc-300 overflow-x-auto">
        <code>{children}</code>
      </pre>
    </div>
  )
}

export function FeatureCard({
  icon: Icon,
  title,
  description,
  accentColor = 'text-blue-400',
}: {
  icon: React.ElementType
  title: string
  description: string
  accentColor?: string
}) {
  return (
    <div className="p-4 rounded-xl bg-zinc-800/50 border border-zinc-700">
      <div className="flex items-center gap-2 mb-2">
        <Icon size={18} className={accentColor} />
        <h3 className="font-semibold text-white">{title}</h3>
      </div>
      <p className="text-sm text-zinc-400">{description}</p>
    </div>
  )
}

export function MethodCard({
  title,
  description,
  pros,
  cons,
  children,
}: {
  title: string
  description: string
  pros: string[]
  cons: string[]
  children: React.ReactNode
}) {
  return (
    <div className="rounded-xl bg-zinc-800/30 border border-zinc-700 p-6">
      <h3 className="text-lg font-bold text-white mb-2">{title}</h3>
      <p className="text-zinc-300 mb-4">{description}</p>

      <div className="grid md:grid-cols-2 gap-4 mb-4">
        <div>
          <h4 className="text-sm font-semibold text-emerald-400 mb-2">Pros</h4>
          <ul className="space-y-1">
            {pros.map((pro) => (
              <li key={pro} className="flex items-center gap-2 text-sm text-zinc-300">
                <Check size={14} className="text-emerald-400" />
                {pro}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h4 className="text-sm font-semibold text-amber-400 mb-2">Cons</h4>
          <ul className="space-y-1">
            {cons.map((con) => (
              <li key={con} className="flex items-center gap-2 text-sm text-zinc-300">
                <AlertTriangle size={14} className="text-amber-400" />
                {con}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {children}
    </div>
  )
}

export function SetupStep({ number, children, accentColor = 'bg-blue-600' }: { number: number; children: React.ReactNode; accentColor?: string }) {
  return (
    <li className="flex gap-4">
      <div className={`flex-shrink-0 w-8 h-8 rounded-full ${accentColor} text-white font-bold flex items-center justify-center text-sm`}>
        {number}
      </div>
      <div className="flex-1 text-zinc-300">{children}</div>
    </li>
  )
}

export function DetectionTable({ detections }: { detections: Array<{ name: string; description: string; trigger: string }> }) {
  return (
    <div className="rounded-lg bg-zinc-900 border border-zinc-700 overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-zinc-800/50 border-b border-zinc-700">
          <tr>
            <th className="px-4 py-3 text-left text-zinc-300 font-medium">Detection Type</th>
            <th className="px-4 py-3 text-left text-zinc-300 font-medium">Description</th>
            <th className="px-4 py-3 text-left text-zinc-300 font-medium">Trigger</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-700">
          {detections.map((d) => (
            <tr key={d.name}>
              <td className="px-4 py-3 text-white">{d.name}</td>
              <td className="px-4 py-3 text-zinc-400">{d.description}</td>
              <td className="px-4 py-3 text-zinc-400">{d.trigger}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function DataMappingTable({ sourceLabel, mappings }: { sourceLabel: string; mappings: Array<{ source: string; target: string }> }) {
  return (
    <div className="rounded-lg bg-zinc-900 border border-zinc-700 overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-zinc-800/50 border-b border-zinc-700">
          <tr>
            <th className="px-4 py-3 text-left text-zinc-300 font-medium">{sourceLabel} Field</th>
            <th className="px-4 py-3 text-left text-zinc-300 font-medium">Pisama Field</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-700">
          {mappings.map((m) => (
            <tr key={m.source}>
              <td className="px-4 py-3"><code className="text-blue-400">{m.source}</code></td>
              <td className="px-4 py-3 text-zinc-400">{m.target}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function SecurityNote({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-4 p-4 rounded-lg bg-amber-500/10 border border-amber-500/30">
      <div className="flex gap-2">
        <AlertTriangle size={18} className="text-amber-400 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-amber-200 font-medium">Security Note</p>
          <p className="text-amber-200/80 text-sm">{children}</p>
        </div>
      </div>
    </div>
  )
}

export function RelatedDocs({ links }: { links: Array<{ href: string; title: string; description: string }> }) {
  return (
    <section className="bg-zinc-800/50 rounded-xl border border-zinc-700 p-6">
      <h2 className="text-lg font-bold text-white mb-4">Related Documentation</h2>
      <div className="grid md:grid-cols-2 gap-4">
        {links.map((link) => (
          <a
            key={link.href}
            href={link.href}
            className="p-4 rounded-lg bg-zinc-900/50 border border-zinc-700 hover:border-blue-500/50 transition-colors"
          >
            <h3 className="font-medium text-white">{link.title}</h3>
            <p className="text-sm text-zinc-400">{link.description}</p>
          </a>
        ))}
      </div>
    </section>
  )
}
