import Link from 'next/link'
import { Terminal, Copy, AlertTriangle, Download, Upload, Search, Eye } from 'lucide-react'

export default function CLIPage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-4">CLI Reference</h1>
        <p className="text-lg text-zinc-300">
          Command-line interface for importing traces, querying detections, and managing 
          your Pisama workspace.
        </p>
      </div>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Installation</h2>
        <CodeBlock title="Install via pip" language="bash">
          pip install mao-testing
        </CodeBlock>
        
        <p className="mt-4 text-zinc-300">
          The CLI is included with the Python SDK. After installation, the <code className="bg-zinc-800 px-1 rounded">mao</code> command 
          is available in your terminal.
        </p>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Configuration</h2>
        <p className="text-zinc-300 mb-4">
          Set your API key before using CLI commands:
        </p>

        <CodeBlock title="Environment Variable" language="bash">
          export MAO_API_KEY=your_api_key_here
        </CodeBlock>

        <div className="mt-4">
          <CodeBlock title="Or use config file" language="bash">
{`# Create config at ~/.mao/config.yaml
mao config init

# Set API key
mao config set api_key your_api_key_here

# View current config
mao config show`}
          </CodeBlock>
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Commands</h2>

        <div className="space-y-8">
          <CommandSection
            name="mao import"
            description="Import trace data from files or OTEL collectors"
            icon={Upload}
          >
            <CodeBlock title="Import OTEL JSON" language="bash">
{`# Import from OTEL JSON export
mao import traces.json

# Import multiple files
mao import trace1.json trace2.json trace3.json

# Import from directory
mao import ./traces/

# Import with custom framework tag
mao import traces.json --framework langgraph

# Dry run (validate without importing)
mao import traces.json --dry-run`}
            </CodeBlock>

            <div className="mt-4">
              <h4 className="text-sm font-semibold text-zinc-400 mb-2">Options</h4>
              <OptionTable options={[
                { flag: "--framework", description: "Framework tag (langgraph, autogen, crewai, custom)" },
                { flag: "--environment", description: "Environment tag (production, staging, development)" },
                { flag: "--dry-run", description: "Validate file without importing" },
                { flag: "--format", description: "Input format (otel, jaeger, zipkin). Auto-detected by default" },
              ]} />
            </div>
          </CommandSection>

          <CommandSection
            name="mao traces"
            description="List and view traces"
            icon={Eye}
          >
            <CodeBlock title="List Traces" language="bash">
{`# List recent traces
mao traces list

# Filter by framework
mao traces list --framework langgraph

# Filter by status
mao traces list --status error

# Filter by date range
mao traces list --since 2024-01-01 --until 2024-01-31

# Limit results
mao traces list --limit 50

# Output as JSON
mao traces list --format json`}
            </CodeBlock>

            <div className="mt-4">
              <CodeBlock title="View Trace Details" language="bash">
{`# View specific trace
mao traces show <trace-id>

# View with full state dumps
mao traces show <trace-id> --verbose

# Export trace to file
mao traces show <trace-id> --output trace.json`}
              </CodeBlock>
            </div>

            <div className="mt-4">
              <h4 className="text-sm font-semibold text-zinc-400 mb-2">Options</h4>
              <OptionTable options={[
                { flag: "--framework", description: "Filter by framework" },
                { flag: "--status", description: "Filter by status (running, completed, error)" },
                { flag: "--since", description: "Start date (ISO format)" },
                { flag: "--until", description: "End date (ISO format)" },
                { flag: "--limit", description: "Maximum results (default: 20)" },
                { flag: "--format", description: "Output format (table, json, csv)" },
              ]} />
            </div>
          </CommandSection>

          <CommandSection
            name="mao detections"
            description="List and manage failure detections"
            icon={AlertTriangle}
          >
            <CodeBlock title="List Detections" language="bash">
{`# List all detections
mao detections list

# Filter by type
mao detections list --type loop
mao detections list --type corruption
mao detections list --type persona_drift
mao detections list --type deadlock

# Filter by validation status
mao detections list --validated false

# Filter by confidence
mao detections list --min-confidence 80

# Show only false positives
mao detections list --false-positives`}
            </CodeBlock>

            <div className="mt-4">
              <CodeBlock title="Validate Detections" language="bash">
{`# View detection details
mao detections show <detection-id>

# Mark as validated (confirmed issue)
mao detections validate <detection-id>

# Mark as false positive
mao detections validate <detection-id> --false-positive

# Add notes
mao detections validate <detection-id> --notes "Fixed in PR #123"`}
              </CodeBlock>
            </div>

            <div className="mt-4">
              <CodeBlock title="Get Fix Suggestions" language="bash">
{`# Get AI-generated fix suggestions
mao detections fixes <detection-id>

# Output as JSON for automation
mao detections fixes <detection-id> --format json`}
              </CodeBlock>
            </div>
          </CommandSection>

          <CommandSection
            name="mao watch"
            description="Real-time monitoring of traces and detections"
            icon={Search}
          >
            <CodeBlock title="Watch Mode" language="bash">
{`# Watch for new detections in real-time
mao watch detections

# Watch specific detection types
mao watch detections --type loop,corruption

# Watch traces
mao watch traces

# Watch with desktop notifications
mao watch detections --notify

# Stop after N events
mao watch detections --count 10`}
            </CodeBlock>
          </CommandSection>

          <CommandSection
            name="mao export"
            description="Export data for analysis or backup"
            icon={Download}
          >
            <CodeBlock title="Export Data" language="bash">
{`# Export all traces from last 7 days
mao export traces --since 7d --output traces.json

# Export detections
mao export detections --output detections.json

# Export specific trace with all states
mao export trace <trace-id> --output trace.json

# Export as CSV for spreadsheet analysis
mao export detections --format csv --output detections.csv`}
            </CodeBlock>
          </CommandSection>

          <CommandSection
            name="mao config"
            description="Manage CLI configuration"
            icon={Terminal}
          >
            <CodeBlock title="Configuration Commands" language="bash">
{`# Initialize config file
mao config init

# Set configuration value
mao config set api_key <your-key>
mao config set endpoint https://api.mao-testing.com
mao config set default_format json

# Get configuration value
mao config get api_key

# Show all configuration
mao config show

# Reset to defaults
mao config reset`}
            </CodeBlock>
          </CommandSection>
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">MCP Server Mode</h2>
        <p className="text-zinc-300 mb-4">
          Run Pisama as an MCP (Model Context Protocol) server for AI assistant integration:
        </p>

        <CodeBlock title="MCP Server" language="bash">
{`# Start MCP server
mao mcp serve

# Or with custom port
mao mcp serve --port 8080

# Configure for Claude Desktop
mao mcp install-claude`}
        </CodeBlock>

        <div className="mt-4 p-4 rounded-lg bg-blue-500/10 border border-zinc-800">
          <p className="text-zinc-300 text-sm">
            MCP mode allows AI assistants like Claude to query your traces and detections 
            directly, enabling intelligent debugging assistance.
          </p>
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Common Workflows</h2>

        <div className="space-y-6">
          <WorkflowExample
            title="Debug a Failed Trace"
            steps={[
              "mao traces list --status error --limit 5",
              "mao traces show <trace-id> --verbose",
              "mao detections list --trace <trace-id>",
              "mao detections fixes <detection-id>",
            ]}
          />

          <WorkflowExample
            title="Import and Analyze Existing Traces"
            steps={[
              "mao import ./otel-traces/ --framework langgraph",
              "mao detections list --since 1h",
              "mao detections validate <id> --false-positive",
            ]}
          />

          <WorkflowExample
            title="Monitor Production"
            steps={[
              "mao watch detections --type loop,corruption --notify",
            ]}
          />
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-xl font-bold text-white mb-4">Exit Codes</h2>
        <div className="rounded-lg bg-zinc-900 border border-zinc-700 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-zinc-800/50 border-b border-zinc-700">
              <tr>
                <th className="px-4 py-3 text-left text-zinc-300 font-medium">Code</th>
                <th className="px-4 py-3 text-left text-zinc-300 font-medium">Meaning</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-700">
              <tr>
                <td className="px-4 py-3 text-zinc-300">0</td>
                <td className="px-4 py-3 text-zinc-400">Success</td>
              </tr>
              <tr>
                <td className="px-4 py-3 text-zinc-300">1</td>
                <td className="px-4 py-3 text-zinc-400">General error</td>
              </tr>
              <tr>
                <td className="px-4 py-3 text-zinc-300">2</td>
                <td className="px-4 py-3 text-zinc-400">Invalid arguments</td>
              </tr>
              <tr>
                <td className="px-4 py-3 text-zinc-300">3</td>
                <td className="px-4 py-3 text-zinc-400">Authentication failed</td>
              </tr>
              <tr>
                <td className="px-4 py-3 text-zinc-300">4</td>
                <td className="px-4 py-3 text-zinc-400">Resource not found</td>
              </tr>
              <tr>
                <td className="px-4 py-3 text-zinc-300">5</td>
                <td className="px-4 py-3 text-zinc-400">API error</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className="bg-zinc-800/50 rounded-xl border border-zinc-700 p-6">
        <h2 className="text-lg font-bold text-white mb-4">Related</h2>
        <div className="grid md:grid-cols-2 gap-4">
          <Link
            href="/docs/sdk"
            className="p-4 rounded-lg bg-zinc-900/50 border border-zinc-700 hover:border-zinc-700 transition-colors"
          >
            <h3 className="font-medium text-white">Python SDK</h3>
            <p className="text-sm text-zinc-400">Programmatic access for custom integrations</p>
          </Link>
          <Link
            href="/docs/api-reference"
            className="p-4 rounded-lg bg-zinc-900/50 border border-zinc-700 hover:border-zinc-700 transition-colors"
          >
            <h3 className="font-medium text-white">REST API</h3>
            <p className="text-sm text-zinc-400">Direct HTTP API access</p>
          </Link>
        </div>
      </section>
    </div>
  )
}

function CodeBlock({ title, language: _language, children }: { title: string; language: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg bg-zinc-900 border border-zinc-700 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-zinc-700 bg-zinc-800/50">
        <div className="flex items-center gap-2">
          <Terminal size={14} className="text-zinc-400" />
          <span className="text-sm text-zinc-400">{title}</span>
        </div>
        <button className="p-1 text-zinc-400 hover:text-white transition-colors" aria-label="Copy code">
          <Copy size={14} />
        </button>
      </div>
      <pre className="p-4 text-sm text-zinc-300 overflow-x-auto">
        <code>{children}</code>
      </pre>
    </div>
  )
}

function CommandSection({
  name,
  description,
  icon: Icon,
  children,
}: {
  name: string
  description: string
  icon: typeof Terminal
  children: React.ReactNode
}) {
  return (
    <div className="rounded-xl bg-zinc-800/30 border border-zinc-700 p-6">
      <div className="flex items-center gap-3 mb-4">
        <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400">
          <Icon size={20} />
        </div>
        <div>
          <h3 className="text-lg font-bold text-white">{name}</h3>
          <p className="text-sm text-zinc-400">{description}</p>
        </div>
      </div>
      {children}
    </div>
  )
}

function OptionTable({ options }: { options: Array<{ flag: string; description: string }> }) {
  return (
    <div className="rounded-lg bg-zinc-900 border border-zinc-700 overflow-hidden">
      <table className="w-full text-sm">
        <tbody className="divide-y divide-zinc-700">
          {options.map((opt) => (
            <tr key={opt.flag}>
              <td className="px-4 py-2 w-40">
                <code className="text-blue-400">{opt.flag}</code>
              </td>
              <td className="px-4 py-2 text-zinc-400">{opt.description}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function WorkflowExample({ title, steps }: { title: string; steps: string[] }) {
  return (
    <div className="rounded-lg bg-zinc-800/50 border border-zinc-700 p-4">
      <h4 className="font-semibold text-white mb-3">{title}</h4>
      <div className="space-y-2">
        {steps.map((step, i) => (
          <div key={i} className="flex items-start gap-3">
            <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-600/20 text-blue-400 text-xs flex items-center justify-center font-medium">
              {i + 1}
            </span>
            <code className="text-sm text-zinc-300 bg-zinc-900 px-2 py-1 rounded">{step}</code>
          </div>
        ))}
      </div>
    </div>
  )
}
