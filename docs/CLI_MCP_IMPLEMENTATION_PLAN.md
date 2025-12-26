# CLI + MCP Implementation Plan for MAO

## Overview

Add two new interfaces to MAO Testing Platform:
1. **CLI** - Command-line interface for developers and CI/CD
2. **MCP Server** - Model Context Protocol server for AI assistant integration

---

## Agent Review Feedback Applied

### Backend Architect Recommendations ✓
- Layered architecture with Core/CLI/MCP separation
- Async httpx client with connection pooling and retries
- Multi-level caching (memory → Redis → disk)
- Structured error handling with exit codes

### UX Researcher Recommendations ✓
- Unified `mao debug` command for common workflow
- Progress indicators and streaming output
- Command aliases (d, w, f)
- Contextual help with next-step suggestions

### Security Reviewer Recommendations ✓
- Confirmation required for fix application
- Secure credential storage with proper encryption
- Input validation on all parameters
- Comprehensive audit logging
- Rate limiting on MCP server

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         MAO Interfaces                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────────────┐   │
│  │   mao CLI   │     │  MCP Server │     │  CI/CD Integration  │   │
│  │  (Click)    │     │  (stdio)    │     │  (GitHub Actions)   │   │
│  └──────┬──────┘     └──────┬──────┘     └──────────┬──────────┘   │
│         │                   │                        │              │
│         └───────────────────┼────────────────────────┘              │
│                             │                                        │
│                    ┌────────▼────────┐                              │
│                    │  MAO Core       │                              │
│                    │  (Shared Logic) │                              │
│                    └────────┬────────┘                              │
│                             │                                        │
│         ┌───────────────────┼───────────────────┐                   │
│         │                   │                   │                    │
│  ┌──────▼──────┐    ┌──────▼──────┐    ┌───────▼──────┐            │
│  │ HTTP Client │    │ Multi-Level │    │ Security     │            │
│  │ (httpx)     │    │ Cache       │    │ Layer        │            │
│  └─────────────┘    └─────────────┘    └──────────────┘            │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
mao/
├── cli/
│   ├── __init__.py
│   ├── main.py              # Entry point, Click app
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── debug.py         # Unified analyze+detect command
│   │   ├── fix.py           # Generate/apply fixes
│   │   ├── import_cmd.py    # Import traces
│   │   ├── config.py        # Configuration
│   │   ├── watch.py         # Live monitoring
│   │   └── ci.py            # CI/CD helpers
│   └── output/
│       ├── __init__.py
│       ├── formatting.py    # Rich output formatting
│       └── progress.py      # Progress indicators
├── mcp/
│   ├── __init__.py
│   ├── server.py            # MCP server (stdio transport)
│   ├── tools.py             # MCP tools with security
│   ├── resources.py         # MCP resources
│   └── auth.py              # Authentication layer
├── core/
│   ├── __init__.py
│   ├── client.py            # Shared API client
│   ├── cache.py             # Multi-level caching
│   ├── errors.py            # Domain errors
│   └── security.py          # Input validation, credentials
└── tests/
    ├── cli/
    ├── mcp/
    └── core/
```

## Phase 1: Core + CLI Foundation

### 1.1 Shared HTTP Client

```python
# core/client.py
import httpx
import backoff
from typing import Optional, Dict, Any

class MAOClient:
    def __init__(self, endpoint: str, api_key: str):
        limits = httpx.Limits(
            max_keepalive_connections=20,
            max_connections=100,
        )
        timeout = httpx.Timeout(connect=5.0, read=30.0, write=10.0)
        
        self._client = httpx.AsyncClient(
            base_url=endpoint,
            limits=limits,
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"},
        )
    
    @backoff.on_exception(backoff.expo, httpx.TransportError, max_tries=3)
    async def analyze_trace(self, trace_id: str) -> Dict[str, Any]:
        response = await self._client.get(f"/api/v1/traces/{trace_id}/analyze")
        response.raise_for_status()
        return response.json()
    
    async def get_detections(self, trace_id: str) -> list:
        response = await self._client.get(f"/api/v1/traces/{trace_id}/detections")
        response.raise_for_status()
        return response.json()
    
    async def suggest_fixes(self, detection_id: str) -> list:
        response = await self._client.get(f"/api/v1/detections/{detection_id}/fixes")
        response.raise_for_status()
        return response.json()
```

### 1.2 CLI Commands

```bash
# Unified debug command (UX improvement)
mao debug <trace-id>                # Analyze + detect in one step
mao debug --last 5                  # Debug last 5 traces
mao debug --since 1h                # Debug traces from last hour
mao debug trace-123 --fix           # Include fix suggestions
mao debug trace-123 --fix --apply   # Apply safe fixes

# Command aliases
mao d trace-123                     # Short for debug
mao w                               # Short for watch
mao f detection-456                 # Short for fix

# Configuration (secure input)
mao config init                     # Interactive setup wizard
mao config set endpoint <url>       
mao config set api-key              # Prompts securely (no shell history)
mao config show                     # Show config (redacted keys)

# Fix management (with confirmation)
mao fix <detection-id>              # Show suggestions
mao fix <detection-id> --apply      # Requires confirmation
mao fix <detection-id> --apply -y   # Skip confirmation (CI mode)

# Watch with streaming output
mao watch                           # Stream new detections
mao watch --severity high           # Filter by severity

# CI/CD helpers
mao ci check                        # Run against golden dataset
mao ci check --threshold 90         # Fail if accuracy < 90%
mao ci report --format junit        # JUnit XML output
```

### 1.3 Output with Progress Indicators

```python
# cli/output/formatting.py
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()

def print_analysis_result(result: dict):
    """Print analysis result with next-step suggestions."""
    console.print(f"[bold]🔍 Trace: {result['trace_id']}[/bold]")
    console.print(f"├─ Framework: {result['framework']}")
    console.print(f"├─ Duration: {result['duration_ms']}ms")
    console.print(f"└─ Status: [{'green' if result['healthy'] else 'red'}]{result['status']}[/]")
    
    if result['detections']:
        console.print("\n[bold]Issues Found:[/bold]")
        for d in result['detections']:
            icon = "🔴" if d['severity'] == 'high' else "🟡"
            console.print(f"  {icon} {d['type']} ({d['severity'].upper()})  {d['id']}")
            console.print(f"     {d['summary']}")
        
        console.print(f"\n💡 Run [cyan]mao fix {result['trace_id']}[/cyan] to see suggested fixes")
    else:
        console.print("\n[green]✅ No issues detected[/green]")

async def run_with_progress(coro, message: str):
    """Run coroutine with spinner."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description=message, total=None)
        return await coro
```

## Phase 2: Security Layer

### 2.1 Secure Credential Storage

```python
# core/security.py
import os
import sys
import getpass
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

def get_credentials_path() -> Path:
    return Path.home() / ".mao" / "credentials.enc"

def store_api_key(api_key: str):
    """Store API key securely."""
    if sys.platform == "darwin":
        # macOS: use Keychain
        import keyring
        keyring.set_password("mao", "api_key", api_key)
    elif sys.platform == "win32":
        # Windows: use Credential Manager
        import keyring
        keyring.set_password("mao", "api_key", api_key)
    else:
        # Linux: encrypted file with user password
        password = getpass.getpass("Create password to protect credentials: ")
        salt = os.urandom(16)
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        
        fernet = Fernet(key)
        encrypted = fernet.encrypt(api_key.encode())
        
        cred_path = get_credentials_path()
        cred_path.parent.mkdir(mode=0o700, exist_ok=True)
        cred_path.write_bytes(salt + encrypted)
        cred_path.chmod(0o600)

def validate_trace_id(trace_id: str) -> str:
    """Validate trace ID format to prevent injection."""
    import re
    if not re.match(r'^[a-zA-Z0-9_-]{1,128}$', trace_id):
        raise ValueError(f"Invalid trace ID format: {trace_id}")
    return trace_id

def validate_file_path(file_path: str, project_root: Path) -> Path:
    """Validate file path is within project and safe."""
    path = Path(file_path).resolve()
    
    # Prevent path traversal
    if not str(path).startswith(str(project_root.resolve())):
        raise ValueError("File path outside project directory")
    
    # Whitelist extensions
    allowed_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.go', '.rs'}
    if path.suffix not in allowed_extensions:
        raise ValueError(f"File type not allowed: {path.suffix}")
    
    return path
```

### 2.2 Fix Application with Safeguards

```python
# core/fix_applier.py
from pathlib import Path
import shutil
from datetime import datetime

class FixApplier:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.backup_dir = project_root / ".mao" / "backups"
    
    def apply_fix(
        self, 
        file_path: Path, 
        fix: dict,
        dry_run: bool = False,
        require_confirmation: bool = True,
    ) -> dict:
        """Apply fix with backup and confirmation."""
        
        # Validate path
        validated_path = validate_file_path(str(file_path), self.project_root)
        
        # Show diff
        console.print("[bold]Proposed change:[/bold]")
        console.print(fix['diff'])
        
        if require_confirmation:
            if not Confirm.ask("Apply this fix?"):
                return {"status": "cancelled"}
        
        if dry_run:
            return {"status": "dry_run", "would_apply": True}
        
        # Create backup
        backup_path = self._create_backup(validated_path)
        
        # Apply change
        try:
            self._apply_change(validated_path, fix)
            return {
                "status": "applied",
                "backup": str(backup_path),
                "file": str(validated_path),
            }
        except Exception as e:
            # Restore backup on failure
            shutil.copy(backup_path, validated_path)
            raise
    
    def _create_backup(self, file_path: Path) -> Path:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"{file_path.name}.{timestamp}.bak"
        shutil.copy(file_path, backup_path)
        return backup_path
```

## Phase 3: MCP Server

### 3.1 Secure MCP Server

```python
# mcp/server.py
import asyncio
from mcp import Server
from mcp.server.stdio import stdio_server
from core.client import MAOClient
from core.security import validate_trace_id

class MAOMCPServer:
    def __init__(self):
        self.server = Server("mao-agent-testing")
        self.client: MAOClient = None
        self.rate_limiter = RateLimiter(requests_per_minute=60)
        self.audit_logger = AuditLogger()
    
    async def setup(self, endpoint: str, api_key: str):
        self.client = MAOClient(endpoint, api_key)
        await self._register_tools()
    
    async def _register_tools(self):
        @self.server.call_tool()
        async def mao_analyze_trace(trace_id: str):
            """Analyze a trace for agent failures."""
            # Rate limit
            await self.rate_limiter.acquire()
            
            # Validate input
            validated_id = validate_trace_id(trace_id)
            
            # Audit log
            self.audit_logger.log("analyze_trace", {"trace_id": validated_id})
            
            result = await self.client.analyze_trace(validated_id)
            return [{"type": "text", "text": format_analysis(result)}]
        
        @self.server.call_tool()
        async def mao_get_fix_suggestion(detection_id: str):
            """Get fix suggestions for a detection (read-only)."""
            await self.rate_limiter.acquire()
            validated_id = validate_trace_id(detection_id)
            
            fixes = await self.client.suggest_fixes(validated_id)
            return [{"type": "text", "text": format_fixes(fixes)}]
        
        # NOTE: mao_apply_fix is intentionally NOT exposed via MCP
        # Fixes must be applied via CLI with user confirmation
```

### 3.2 MCP Resources

```python
# mcp/resources.py
@server.list_resources()
async def list_resources():
    return [
        {
            "uri": "mao://docs/detection-types",
            "name": "Detection Types",
            "description": "Documentation for loop, corruption, drift, deadlock detection",
            "mimeType": "text/markdown",
        },
        {
            "uri": "mao://docs/fix-types", 
            "name": "Fix Types",
            "description": "Documentation for available fix suggestions",
            "mimeType": "text/markdown",
        },
    ]

@server.read_resource()
async def read_resource(uri: str):
    if uri == "mao://docs/detection-types":
        return DETECTION_DOCS
    elif uri == "mao://docs/fix-types":
        return FIX_DOCS
```

## Phase 4: Multi-Level Caching

```python
# core/cache.py
from typing import Optional, Any
from datetime import timedelta
import json

class MultiLevelCache:
    def __init__(self, redis_url: Optional[str] = None):
        self.memory = {}  # L1: In-memory LRU
        self.redis = redis.from_url(redis_url) if redis_url else None  # L2: Redis
        self.disk = DiskCache(Path.home() / ".mao" / "cache")  # L3: Disk
    
    async def get(self, key: str) -> Optional[Any]:
        # L1: Memory
        if key in self.memory:
            return self.memory[key]
        
        # L2: Redis
        if self.redis:
            try:
                value = await self.redis.get(key)
                if value:
                    parsed = json.loads(value)
                    self.memory[key] = parsed
                    return parsed
            except Exception:
                pass
        
        # L3: Disk (offline support)
        value = self.disk.get(key)
        if value:
            self.memory[key] = value
        return value
    
    async def set(self, key: str, value: Any, ttl: timedelta = None):
        self.memory[key] = value
        
        if self.redis:
            try:
                await self.redis.set(key, json.dumps(value), ex=int(ttl.total_seconds()) if ttl else None)
            except Exception:
                pass
        
        self.disk.set(key, value, ttl)
```

## Implementation Schedule

### Week 1: Core + CLI Foundation
- [ ] Core client with httpx, retries, caching
- [ ] Security layer (credentials, validation)
- [ ] CLI skeleton with Click
- [ ] `mao debug` and `mao config` commands

### Week 2: CLI Completion
- [ ] `mao fix` with confirmation and backups
- [ ] `mao watch` with streaming
- [ ] `mao ci` helpers
- [ ] Rich output formatting

### Week 3: MCP Server
- [ ] MCP server with stdio transport
- [ ] Read-only tools (analyze, detect, suggest)
- [ ] Rate limiting and audit logging
- [ ] Resources (documentation)

### Week 4: Polish
- [ ] Integration tests
- [ ] Documentation
- [ ] Error messages with suggestions
- [ ] Shell completions

## Success Criteria

### CLI
- [x] Secure credential storage (keyring/encrypted)
- [x] Input validation on all parameters
- [x] Progress indicators for >2s operations
- [x] Exit codes: 0=success, 1=issues found, 2=error
- [x] `--help` on all commands with examples

### MCP
- [x] Read-only tools only (no `apply_fix` via MCP)
- [x] Rate limiting (60 req/min)
- [x] Audit logging for all operations
- [x] < 2s response time
- [x] Graceful error handling

### Security
- [x] API keys never in shell history
- [x] Fix application requires confirmation
- [x] Backups created before any file modification
- [x] Path traversal protection
- [x] Comprehensive audit trail
