'use client'

export const dynamic = 'force-dynamic'

import { useState } from 'react'
import { Layout } from '@/components/common/Layout'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import {
  Terminal,
  Copy,
  Check,
  ExternalLink,
  Key,
  Zap,
  Shield,
  Search,
  Bug,
  BarChart3,
  FileCode,
  MessageSquare,
  Sparkles,
} from 'lucide-react'
import Link from 'next/link'

interface McpTool {
  name: string
  description: string
  icon: React.ElementType
  category: 'observe' | 'detect' | 'evaluate' | 'fix'
}

const MCP_TOOLS: McpTool[] = [
  { name: 'pisama_ingest_trace', description: 'Ingest a trace from any framework (LangGraph, CrewAI, AutoGen, n8n) for analysis', icon: Zap, category: 'observe' },
  { name: 'pisama_list_traces', description: 'List recent traces with filtering by status, framework, and date range', icon: Search, category: 'observe' },
  { name: 'pisama_get_trace', description: 'Get full trace details including states, tokens, cost, and timeline', icon: FileCode, category: 'observe' },
  { name: 'pisama_detect', description: 'Run all 17 detectors on a trace: loop, corruption, persona drift, injection, hallucination, and more', icon: Shield, category: 'detect' },
  { name: 'pisama_list_detections', description: 'List detections across traces with filtering by type, confidence, and validation status', icon: Bug, category: 'detect' },
  { name: 'pisama_get_detection', description: 'Get detection details with plain-English explanation, business impact, and suggested action', icon: Bug, category: 'detect' },
  { name: 'pisama_evaluate', description: 'Run quality evaluations (relevance, coherence, helpfulness, safety) on agent output', icon: BarChart3, category: 'evaluate' },
  { name: 'pisama_evaluate_conversation', description: 'Evaluate multi-turn conversation quality with per-turn annotations and dimension scores', icon: MessageSquare, category: 'evaluate' },
  { name: 'pisama_create_scorer', description: 'Create a custom scorer from natural language description of a quality concern', icon: Sparkles, category: 'evaluate' },
  { name: 'pisama_run_scorer', description: 'Run a custom scorer against recent traces and get pass/warn/fail verdicts', icon: Sparkles, category: 'evaluate' },
  { name: 'pisama_generate_fix', description: 'Generate an AI-powered source code fix for a detected issue', icon: FileCode, category: 'fix' },
  { name: 'pisama_system_summary', description: 'Get a full system health overview: trace counts, detection breakdown, quality scores', icon: BarChart3, category: 'observe' },
]

const CATEGORY_COLORS: Record<string, { bg: string; text: string; border: string; label: string }> = {
  observe: { bg: 'bg-blue-500/10', text: 'text-blue-400', border: 'border-blue-500/30', label: 'Observe' },
  detect: { bg: 'bg-red-500/10', text: 'text-red-400', border: 'border-red-500/30', label: 'Detect' },
  evaluate: { bg: 'bg-violet-500/10', text: 'text-violet-400', border: 'border-violet-500/30', label: 'Evaluate' },
  fix: { bg: 'bg-green-500/10', text: 'text-green-400', border: 'border-green-500/30', label: 'Fix' },
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <button
      onClick={handleCopy}
      className="absolute top-3 right-3 p-1.5 rounded-md bg-zinc-700/50 hover:bg-zinc-700 transition-colors text-zinc-400 hover:text-zinc-200"
      title="Copy to clipboard"
    >
      {copied ? <Check size={14} /> : <Copy size={14} />}
    </button>
  )
}

const MCP_CONFIG = `{
  "mcpServers": {
    "pisama": {
      "command": "pisama",
      "args": ["mcp-server"],
      "env": {
        "PISAMA_API_KEY": "your-api-key",
        "PISAMA_API_URL": "https://api.pisama.dev/api/v1"
      }
    }
  }
}`

const CLI_INSTALL = `# Install via pip
pip install pisama-cli

# Or with pipx for isolated install
pipx install pisama-cli

# Authenticate
pisama auth login --api-key YOUR_API_KEY

# Verify connection
pisama status`

const QUICK_START = `# Ingest a trace and run detection
pisama traces ingest ./my-trace.json
pisama detect --trace-id <trace-id>

# Create a custom scorer
pisama scorers create "Check if agent properly cites sources"

# Evaluate a conversation
pisama evals conversation --trace-id <trace-id>

# Generate a source fix
pisama fixes generate --detection-id <detection-id> --file ./agent.py`

export default function DeveloperApiPage() {
  return (
    <Layout>
      <div className="p-6 max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 bg-violet-600/20 rounded-lg">
            <Terminal className="w-6 h-6 text-violet-400" />
          </div>
          <h1 className="text-2xl font-bold text-white">Developer API</h1>
        </div>
        <p className="text-zinc-400 mb-8">
          Integrate Pisama into your development workflow via MCP, CLI, or REST API.
        </p>

        {/* MCP Setup */}
        <Card className="mb-6" padding="lg">
          <CardHeader>
            <div className="flex items-center gap-2">
              <Sparkles size={20} className="text-violet-400" />
              <CardTitle>MCP Server (Claude Code / Claude Desktop)</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-zinc-400 mb-4">
              Add Pisama as an MCP server to get all 12 tools directly in Claude Code or Claude Desktop.
              Copy this configuration into your <code className="text-violet-400 bg-zinc-800 px-1.5 py-0.5 rounded text-xs">settings.json</code> or <code className="text-violet-400 bg-zinc-800 px-1.5 py-0.5 rounded text-xs">claude_desktop_config.json</code>:
            </p>
            <div className="relative">
              <pre className="bg-zinc-950 border border-zinc-800 rounded-lg p-4 text-sm text-zinc-300 overflow-x-auto">
                <code>{MCP_CONFIG}</code>
              </pre>
              <CopyButton text={MCP_CONFIG} />
            </div>
            <div className="mt-4 flex items-center gap-2">
              <Key size={14} className="text-zinc-500" />
              <span className="text-sm text-zinc-500">
                Get your API key from{' '}
                <Link href="/settings/api-keys" className="text-blue-400 hover:text-blue-300 underline">
                  Settings &rarr; API Keys
                </Link>
              </span>
            </div>
          </CardContent>
        </Card>

        {/* CLI Install */}
        <Card className="mb-6" padding="lg">
          <CardHeader>
            <div className="flex items-center gap-2">
              <Terminal size={20} className="text-green-400" />
              <CardTitle>CLI Installation</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="relative">
              <pre className="bg-zinc-950 border border-zinc-800 rounded-lg p-4 text-sm text-zinc-300 overflow-x-auto">
                <code>{CLI_INSTALL}</code>
              </pre>
              <CopyButton text={CLI_INSTALL} />
            </div>
          </CardContent>
        </Card>

        {/* Quick Start */}
        <Card className="mb-8" padding="lg">
          <CardHeader>
            <div className="flex items-center gap-2">
              <Zap size={20} className="text-amber-400" />
              <CardTitle>Quick Start</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="relative">
              <pre className="bg-zinc-950 border border-zinc-800 rounded-lg p-4 text-sm text-zinc-300 overflow-x-auto">
                <code>{QUICK_START}</code>
              </pre>
              <CopyButton text={QUICK_START} />
            </div>
          </CardContent>
        </Card>

        {/* MCP Tools List */}
        <div className="mb-4">
          <h2 className="text-lg font-semibold text-white mb-1">Available MCP Tools</h2>
          <p className="text-sm text-zinc-400">
            All 12 tools are available through the MCP server, CLI, and REST API.
          </p>
        </div>

        <div className="grid gap-3">
          {MCP_TOOLS.map((tool) => {
            const cat = CATEGORY_COLORS[tool.category]
            const Icon = tool.icon
            return (
              <Card key={tool.name} padding="sm" className="hover:border-zinc-600 transition-colors">
                <div className="flex items-start gap-3 p-2">
                  <div className={`p-1.5 rounded-md ${cat.bg} flex-shrink-0 mt-0.5`}>
                    <Icon size={16} className={cat.text} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <code className="text-sm font-mono text-white">{tool.name}</code>
                      <span className={`text-[10px] uppercase tracking-wider font-medium px-1.5 py-0.5 rounded ${cat.bg} ${cat.text} border ${cat.border}`}>
                        {cat.label}
                      </span>
                    </div>
                    <p className="text-sm text-zinc-400">{tool.description}</p>
                  </div>
                </div>
              </Card>
            )
          })}
        </div>

        {/* REST API Link */}
        <Card className="mt-8" padding="lg">
          <CardContent>
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-white font-medium mb-1">REST API Documentation</h3>
                <p className="text-sm text-zinc-400">
                  Full OpenAPI documentation with interactive examples.
                </p>
              </div>
              <a
                href="https://mao-api.fly.dev/docs"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors"
              >
                Open API Docs
                <ExternalLink size={14} />
              </a>
            </div>
          </CardContent>
        </Card>
      </div>
    </Layout>
  )
}
