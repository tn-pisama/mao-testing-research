# OpenClaw Failure Modes

Platform-specific detectors for OpenClaw multi-agent chat sessions. These catch issues unique to OpenClaw's event-driven session model, multi-channel messaging, agent spawning, sandbox isolation, and elevated privilege modes.

---

## Session Loops

| Field | Value |
|---|---|
| **Detector key** | `openclaw_session_loop` |
| **Severity** | Critical |

**Plain language:** Your agent is stuck in a loop within its session. It keeps calling the same tool, sending the same message, or spawning the same sub-agent over and over -- burning time and resources without making progress.

**Technical:** Analyzes the session event stream for exact tool call repetition (same name + input hash, 3+ consecutive), fuzzy tool loops (same tool and key structure but different values, 5+ consecutive), spawn/send ping-pong patterns (A-B-A-B alternation with 4+ cycles), and repeated identical messages (3+ consecutive). Uses SHA256 hashing for exact matching and structural hashing (key names + type placeholders) for fuzzy matching.

**Examples (non-technical):**

- The agent calls the same search tool 8 times with identical queries
- Two sub-agents keep handing a task back and forth between each other
- The agent sends the same response message to the user 5 times in a row

**Examples (technical):**

- Tool call loop: `search_web({"query": "weather SF"})` called 6 consecutive times (exact hash match, threshold: 3)
- Fuzzy tool loop: `query_db({"table": "users", "limit": 10})` then `query_db({"table": "users", "limit": 20})` -- same structure, different values, 5 times
- Spawn ping-pong: `session.spawn(agent_B)` → `session.send(agent_A)` → `session.spawn(agent_B)` → ... (4+ alternations)
- Message loop: `message.sent("I'll help you with that")` repeated 4 times with identical content

**Detection methods:**

- **Exact Tool Loop**: SHA256 hash of `tool_name + tool_input`, flags 3+ consecutive matches (tolerates up to 4 event gaps)
- **Fuzzy Tool Loop**: Structural hash of key names + type placeholders, flags 5+ consecutive
- **Spawn Ping-Pong**: Detects repeated targeting of same session or A-B-A-B alternation between two targets
- **Message Loop**: Identifies 3+ consecutive identical message.sent/message.send events

**Sub-types:** `tool_call_loop`, `fuzzy_tool_loop`, `spawn_ping_pong`, `abab_ping_pong`, `message_sent_loop`

---

## Tool Abuse

| Field | Value |
|---|---|
| **Detector key** | `openclaw_tool_abuse` |
| **Severity** | High |

**Plain language:** Your agent is misusing its tools. It's making too many calls, calling the same tool redundantly, failing more than half the time, or using sensitive tools like file deletion or shell commands that could be dangerous.

**Technical:** Monitors tool call volume (flags >4 total calls), per-tool redundancy (3+ calls to same tool), error rate (>50% failure when 3+ calls), and sensitive tool usage via exact name matching (exec, eval, shell, delete_file, etc.) and keyword matching (delete, ban, bulk, export, dump, etc.).

**Examples (non-technical):**

- The agent made 12 tool calls in a single turn -- that's excessive for a simple task
- The agent called the same database query 5 times when once would have been enough
- The agent tried to run a shell command -- a tool it should never need for customer support

**Examples (technical):**

- Excessive calls: 9 tool.call events in one session (threshold: 4)
- Redundant: `fetch_user_profile` called 4 times (threshold: 3) -- same data, no state change between calls
- High error rate: 5/8 tool calls returned `status: "failed"` (62.5%, threshold: 50%)
- Sensitive tool: agent called `run_command` (exact match) and `bulk_delete_users` (keyword match: "bulk" + "delete")

**Detection methods:**

- **Volume Tracking**: Total tool.call events per session (threshold: 4)
- **Redundancy Detection**: Per-tool call counts (threshold: 3 for same tool)
- **Error Rate Monitoring**: Failed/total ratio when 3+ calls made (threshold: 50%)
- **Sensitive Tool Detection**: Exact match against blocklist + keyword matching against dangerous operation terms

**Sub-types:** `excessive_calls`, `redundant_calls`, `high_error_rate`, `sensitive_tools`

---

## Elevated Privilege Risk

| Field | Value |
|---|---|
| **Detector key** | `openclaw_elevated_risk` |
| **Severity** | High |

**Plain language:** Your agent is performing risky operations, either in elevated mode (where it has extra permissions) or attempting dangerous actions without proper authorization. This could mean file system access, code execution, or admin-level operations.

**Technical:** Checks the session's `elevated_mode` flag, then categorizes each tool call against risk categories: file system operations (read/write/delete), code execution (exec, eval, run_code), system commands (shell, subprocess), admin actions (delete, ban, suspend), permission operations (escalate, grant), data operations (bulk, export, dump), and credential operations (password, reset). Also scans tool inputs for dangerous patterns (rm -rf, /etc/passwd, SSN, bulk delete). Non-elevated sessions using risky tools are flagged as escalation attempts (highest severity).

**Examples (non-technical):**

- An agent in elevated mode is deleting files and running shell commands -- these are risky even when authorized
- A regular (non-elevated) agent tried to execute code -- it's attempting to escalate its privileges
- An agent's tool input contains `rm -rf /` -- a destructive system command

**Examples (technical):**

- Elevated mode + tool `write_file`: legitimate but logged as `elevated_operation` (MODERATE)
- Non-elevated + tool `exec`: escalation attempt -- agent shouldn't have code execution (SEVERE)
- Tool input matches pattern: `"rm -rf /"` or `"/etc/passwd"` (risky_input)
- Risk categories triggered: `{file_system, code_execution, system_commands}` -- 3 categories (MODERATE threshold: 3)
- Tool `bulk_export_data` matches keyword "bulk" + "export" (data_operations category)

**Detection methods:**

- **Privilege Context Check**: Compares tool risk against session's elevated_mode flag
- **Escalation Detection**: Flags risky tool usage in non-elevated sessions (highest severity)
- **Risk Categorization**: Classifies tools into 7 risk categories via exact match and keyword matching
- **Input Pattern Scanning**: Regex matching against dangerous command patterns in tool inputs

**Sub-types:** `elevated_operation`, `escalation_attempt`, `risky_input`, categories: `file_system`, `code_execution`, `system_commands`, `admin_actions`, `permission_ops`, `data_operations`, `credential_ops`

---

## Spawn Chain Depth

| Field | Value |
|---|---|
| **Detector key** | `openclaw_spawn_chain` |
| **Severity** | High |

**Plain language:** Your agents are spawning too many levels of sub-agents. Agent A spawns Agent B, which spawns Agent C, which spawns Agent D -- creating a deep chain that's hard to control. Even worse, some agents might be spawning each other in circles, or escalating to privileged agents they shouldn't access.

**Technical:** Tracks session.spawn events to measure chain depth (safe threshold: 3 levels), detects circular references (spawned session ID already seen), and identifies privilege escalation patterns (spawning agents matching privilege keywords like admin, root, supervisor, master, controller).

**Examples (non-technical):**

- An agent spawned 5 levels of sub-agents to handle a simple question -- way too deep
- Agent A spawned Agent B, which spawned Agent A again -- creating an infinite loop
- A regular agent spawned an "admin" agent -- attempting to gain higher privileges

**Examples (technical):**

- Spawn depth: 6 `session.spawn` events in one session (safe threshold: 3)
- Circular reference: `spawned_session_id: "sess_abc"` already in seen_ids set -- agent is re-spawning itself
- Privilege escalation: spawn targets include `"admin_agent"` and `"supervisor_bot"` -- 2 privileged agents in chain
- Depth field: `data.depth: 5` exceeds MAX_SAFE_SPAWN_DEPTH (3)
- Total children: spawn event with `child_session_ids: ["s1", "s2", "s3"]` -- fan-out of 3 at one level

**Detection methods:**

- **Depth Tracking**: Counts spawn events and explicit depth fields per session
- **Circular Reference Detection**: Maintains seen_ids set, flags if spawned ID already exists
- **Privilege Keyword Matching**: Case-insensitive substring match against admin/root/supervisor/master/controller/elevated/privileged/system/internal
- **Fan-Out Monitoring**: Counts total child sessions spawned

**Sub-types:** `excessive_depth`, `circular_reference`, `privilege_escalation`

---

## Channel Mismatch

| Field | Value |
|---|---|
| **Detector key** | `openclaw_channel_mismatch` |
| **Severity** | Medium |

**Plain language:** Your agent is sending messages formatted wrong for the messaging channel. Code blocks sent to WhatsApp don't render, messages are too long for the platform's limits, or sensitive personal information is being sent through channels where it shouldn't appear.

**Technical:** Checks for cross-channel routing (event channel differs from session channel) and channel-specific content violations: WhatsApp (code blocks, markdown tables, messages >1000 chars), Telegram (messages >4096 chars), Slack (SSN and credit card number patterns), Discord (messages >2000 chars).

**Examples (non-technical):**

- The agent sends a code snippet with triple backticks to WhatsApp -- it shows as garbled text
- A response meant for Telegram is 6,000 characters long -- it'll be truncated or rejected
- The agent sends a customer's credit card number through Slack -- a serious PII violation

**Examples (technical):**

- WhatsApp: message contains ` ```python\nprint("hello")\n``` ` -- code blocks don't render (formatting violation)
- WhatsApp: message is 1,847 chars (threshold: 1,000) -- too long for mobile display
- Telegram: message is 5,200 chars (threshold: 4,096) -- exceeds API limit
- Slack: message contains `"SSN: 123-45-6789"` pattern match (pii_exposure, SEVERE)
- Discord: message is 2,500 chars (threshold: 2,000) -- exceeds embed limit
- Cross-channel: event.channel = `"telegram"` but session.channel = `"whatsapp"` (routing error)

**Detection methods:**

- **Cross-Channel Detection**: Compares event channel against session channel
- **WhatsApp Format Check**: Detects code blocks (```), markdown tables (|---|), and long messages (>1000 chars)
- **Telegram Length Check**: Flags messages exceeding 4096-character API limit
- **Slack PII Detection**: Regex matching for SSN (###-##-####) and credit card (####-####-####-####) patterns
- **Discord Length Check**: Flags messages exceeding 2000-character limit

**Sub-types:** `cross_channel_routing`, `formatting`, `length`, `pii_exposure`

---

## Sandbox Escape

| Field | Value |
|---|---|
| **Detector key** | `openclaw_sandbox_escape` |
| **Severity** | Critical |

**Plain language:** Your agent is trying to break out of its sandbox. The sandbox is supposed to restrict what the agent can do, but it's attempting to access files, make network calls, execute code, or query databases -- all things it's not supposed to do in a sandboxed environment.

**Technical:** Checks the session's `sandbox_enabled` flag, then monitors all tool.call events against 5 restricted categories: file system (read_file, write_file, delete_file, list_dir), network (http_request, api_call, fetch_url, webhook_forward), code execution (exec, eval, run_code, shell), system commands (os_command, system, subprocess), and database (query_database, sql_query, db_execute). When sandbox is enabled, any matching tool call is an escape attempt. When sandbox is disabled, matches are logged as audit flags at lower severity.

**Examples (non-technical):**

- A sandboxed agent tried to read files from the server -- it shouldn't have file access
- A sandboxed agent attempted to make an HTTP request to an external API -- network access is restricted
- A sandboxed agent tried to run a shell command -- code execution is blocked in sandbox mode

**Examples (technical):**

- Sandbox enabled + tool `read_file`: escape attempt in `file_system` category (SEVERE)
- Sandbox enabled + tool `http_request`: escape attempt in `network` category (SEVERE)
- Sandbox enabled + tool `eval`: escape attempt in `code_execution` category (SEVERE)
- Sandbox enabled + tools across 3 categories: `{file_system, network, code_execution}` -- multi-vector escape (SEVERE, 2+ categories)
- Sandbox disabled + tool `delete_file`: audit flag, lower severity (MINOR), confidence reduced by 0.2

**Detection methods:**

- **Tool Category Matching**: Exact tool name matching against 5 restricted category blocklists
- **Sandbox Context**: Severity escalation when `sandbox_enabled=True` (escape attempt vs audit)
- **Multi-Category Detection**: Tracks number of distinct violation categories (escalates at 2+)
- **Audit Mode**: When sandbox is disabled, still logs suspicious tool usage at lower confidence

**Sub-types:** `file_system`, `network`, `code_execution`, `system`, `database`
