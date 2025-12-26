# E2E Testing Implementation Plan

## Overview

Implement comprehensive end-to-end testing for MAO with real data, real framework integrations, and validated fix suggestions.

## Agent Review Feedback (Incorporated)

### Backend Architect
- ✅ Use containers for fix validation isolation
- ✅ SQLite for unit tests, PostgreSQL for integration
- ✅ Transaction rollback for test data isolation
- ✅ Cassette versioning and refresh strategy

### UX Researcher
- ✅ Visual hierarchy with trend arrows
- ✅ Keyboard shortcuts (C/F/U/S) for fast labeling
- ✅ Bulk actions and filtering
- ✅ Progress tracking and feedback
- ✅ Error/loading/empty states

### Security Reviewer
- ✅ Docker sandbox for code execution (CRITICAL)
- ✅ Filter secrets from response bodies (not just headers)
- ✅ Multi-reviewer consensus for training data
- ✅ Secrets management with environment variables

---

## Phase 1: Infrastructure (Week 1)

### 1.1 VCR Recording Setup
**Files to create:**
- `backend/tests/conftest.py` - VCR configuration with enhanced scrubbing
- `backend/tests/cassettes/` - Recorded HTTP interactions
- `backend/pytest.ini` - Test configuration

**Implementation (with security feedback):**
```python
# backend/tests/conftest.py
import pytest
import re
import os

SENSITIVE_PATTERNS = [
    (r'sk-[a-zA-Z0-9]{48}', '[OPENAI_KEY_REDACTED]'),
    (r'xai-[a-zA-Z0-9]+', '[GROK_KEY_REDACTED]'),
    (r'AIza[0-9A-Za-z\-_]{35}', '[GOOGLE_KEY_REDACTED]'),
    (r'Bearer\s+[A-Za-z0-9\-._~+/]+=*', 'Bearer [REDACTED]'),
]

def scrub_response(response):
    """Remove sensitive data from recorded responses."""
    body = response['body']['string']
    if isinstance(body, bytes):
        body = body.decode('utf-8', errors='ignore')
    
    for pattern, replacement in SENSITIVE_PATTERNS:
        body = re.sub(pattern, replacement, body)
    
    response['body']['string'] = body.encode('utf-8')
    return response

@pytest.fixture(scope="module")
def vcr_config():
    return {
        "cassette_library_dir": "tests/cassettes",
        "record_mode": os.getenv("MAO_RECORD_MODE", "none"),
        "match_on": ["method", "scheme", "host", "port", "path", "query"],
        "filter_headers": ["authorization", "x-api-key", "openai-api-key"],
        "before_record_response": scrub_response,
    }
```

### 1.2 Test Database Setup (with transaction isolation)
```python
# backend/tests/database.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture
def db_session():
    """Transaction-isolated database session."""
    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Begin transaction
    session.begin_nested()
    
    yield session
    
    # Rollback - no data persists
    session.rollback()
    session.close()
```

### 1.3 Docker Test Environment (with sandbox)
```yaml
# docker-compose.test.yml
version: '3.8'

services:
  mao-backend:
    build: ./backend
    environment:
      - DATABASE_URL=postgresql://test:test@db:5432/mao_test
      - DETECTION_MODE=sync
    depends_on:
      - db
    
  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=test
      - POSTGRES_PASSWORD=test
      - POSTGRES_DB=mao_test
    tmpfs:
      - /var/lib/postgresql/data

  fix-sandbox:
    build:
      context: ./backend
      dockerfile: Dockerfile.sandbox
    security_opt:
      - no-new-privileges:true
      - seccomp:unconfined
    read_only: true
    tmpfs:
      - /tmp:size=100M
    mem_limit: 512m
    cpus: 1
    network_mode: none
```

```dockerfile
# backend/Dockerfile.sandbox
FROM python:3.11-slim

RUN useradd -m -s /bin/bash sandbox
USER sandbox
WORKDIR /home/sandbox

COPY --chown=sandbox:sandbox requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

COPY --chown=sandbox:sandbox . .

CMD ["python", "-m", "pytest"]
```

---

## Phase 2: Framework Integration Tests (Week 2)

### 2.1 LangChain Integration
```python
# backend/tests/integration/test_langchain.py
import pytest
from mao_sdk import MAOTracer

class TestLangChainInfiniteLoop:
    
    @pytest.mark.vcr()
    async def test_detects_infinite_loop_in_react_agent(self, mao_tracer):
        """Agent calling same tool repeatedly triggers detection."""
        from langchain.agents import AgentExecutor, create_react_agent
        from langchain_openai import ChatOpenAI
        
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        agent = create_react_agent(llm, tools, prompt)
        executor = mao_tracer.wrap(AgentExecutor(agent=agent, tools=tools))
        
        result = await executor.ainvoke({
            "input": "Keep searching until you find the meaning of life"
        })
        
        detections = await mao_tracer.get_detections(result.trace_id)
        assert any(d.type == "infinite_loop" for d in detections)
    
    @pytest.mark.vcr()
    async def test_healthy_agent_no_false_positives(self, mao_tracer):
        """Normal execution should not trigger detection."""
        result = await executor.ainvoke({"input": "What is 2 + 2?"})
        
        detections = await mao_tracer.get_detections(result.trace_id)
        assert len(detections) == 0
```

---

## Phase 3: Fix Validation System (Week 3)

### 3.1 Sandboxed Fix Applicator
```python
# backend/app/fixes/sandbox.py
import docker
import tempfile
import json

class SandboxedFixValidator:
    """Run fix validation in isolated Docker container."""
    
    def __init__(self):
        self.client = docker.from_env()
    
    async def validate_fix(
        self, 
        original_code: str, 
        fix: FixSuggestion,
        test_input: dict,
        timeout: int = 30
    ) -> ValidationResult:
        """Apply fix and run in sandbox to verify it works."""
        
        fixed_code = self._apply_fix(original_code, fix)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write code to temp file
            code_path = f"{tmpdir}/agent.py"
            with open(code_path, 'w') as f:
                f.write(fixed_code)
            
            # Run in sandbox
            try:
                container = self.client.containers.run(
                    "mao/fix-sandbox:latest",
                    command=["python", "agent.py", json.dumps(test_input)],
                    volumes={tmpdir: {"bind": "/code", "mode": "ro"}},
                    mem_limit="512m",
                    cpu_period=100000,
                    cpu_quota=100000,
                    network_disabled=True,
                    read_only=True,
                    remove=True,
                    timeout=timeout
                )
                
                return ValidationResult(
                    success=True,
                    output=container.decode('utf-8')
                )
                
            except docker.errors.ContainerError as e:
                return ValidationResult(
                    success=False,
                    error=str(e)
                )
```

---

## Phase 4: Test Dashboard UI (Week 4)

### 4.1 Testing Dashboard with Trends
```tsx
// frontend/src/app/testing/page.tsx
'use client'

import { useState, useEffect } from 'react'
import { TrendingUp, TrendingDown, Minus, Play, RefreshCw } from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { Button } from '@/components/ui/Button'

interface AccuracyMetric {
  type: string
  value: number
  trend: 'up' | 'down' | 'stable'
  change: number
}

export default function TestingPage() {
  const [isLoading, setIsLoading] = useState(true)
  const [isRunning, setIsRunning] = useState(false)
  const [accuracy, setAccuracy] = useState<AccuracyMetric[]>([])
  const [fixEffectiveness, setFixEffectiveness] = useState<AccuracyMetric[]>([])
  const [integrations, setIntegrations] = useState([])
  const [recentRuns, setRecentRuns] = useState([])

  const TrendIcon = ({ trend }: { trend: string }) => {
    if (trend === 'up') return <TrendingUp className="text-emerald-400" size={16} />
    if (trend === 'down') return <TrendingDown className="text-red-400" size={16} />
    return <Minus className="text-slate-400" size={16} />
  }

  const runTests = async () => {
    setIsRunning(true)
    // API call to run tests
    setIsRunning(false)
  }

  if (isLoading) {
    return (
      <Layout>
        <div className="p-6 animate-pulse">
          <div className="h-8 w-48 bg-slate-700 rounded mb-6" />
          <div className="grid lg:grid-cols-2 gap-6">
            <div className="h-48 bg-slate-700 rounded-xl" />
            <div className="h-48 bg-slate-700 rounded-xl" />
          </div>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white">Testing Dashboard</h1>
            <p className="text-slate-400 text-sm mt-1">Last updated: 2 minutes ago</p>
          </div>
          <Button 
            onClick={runTests} 
            loading={isRunning}
            leftIcon={isRunning ? <RefreshCw className="animate-spin" size={16} /> : <Play size={16} />}
          >
            {isRunning ? 'Running...' : 'Run Tests'}
          </Button>
        </div>

        <div className="grid lg:grid-cols-2 gap-6 mb-6">
          {/* Detection Accuracy Card */}
          <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              🎯 Detection Accuracy
              <span className="text-xs text-slate-400 font-normal">(24hr avg)</span>
            </h2>
            <div className="space-y-3">
              {accuracy.map((metric) => (
                <div key={metric.type} className="flex items-center justify-between">
                  <span className="text-slate-300 capitalize">{metric.type}</span>
                  <div className="flex items-center gap-2">
                    <span className={`font-mono font-medium ${
                      metric.value >= 90 ? 'text-emerald-400' : 
                      metric.value >= 80 ? 'text-amber-400' : 'text-red-400'
                    }`}>
                      {metric.value.toFixed(1)}%
                    </span>
                    <TrendIcon trend={metric.trend} />
                    <span className="text-xs text-slate-500">
                      {metric.change > 0 ? '+' : ''}{metric.change.toFixed(1)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Fix Effectiveness Card */}
          <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
            <h2 className="text-lg font-semibold text-white mb-4">⚡ Fix Effectiveness</h2>
            <div className="space-y-3">
              {fixEffectiveness.map((metric) => (
                <div key={metric.type} className="flex items-center justify-between">
                  <span className="text-slate-300 font-mono text-sm">{metric.type}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-24 bg-slate-700 rounded-full h-2">
                      <div 
                        className={`h-2 rounded-full ${
                          metric.value >= 90 ? 'bg-emerald-500' : 
                          metric.value >= 80 ? 'bg-amber-500' : 'bg-red-500'
                        }`}
                        style={{ width: `${metric.value}%` }}
                      />
                    </div>
                    <span className="font-mono text-white w-12 text-right">
                      {metric.value}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Integration Status */}
        <div className="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6">
          <h2 className="text-lg font-semibold text-white mb-4">Integration Test Status</h2>
          <div className="space-y-2">
            {integrations.map((integration: any) => (
              <div 
                key={integration.name}
                className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <span className={integration.passed === integration.total ? 'text-emerald-400' : 'text-amber-400'}>
                    {integration.passed === integration.total ? '✅' : '⚠️'}
                  </span>
                  <span className="text-white font-medium">{integration.name}</span>
                  <span className="text-slate-400 text-sm">{integration.version}</span>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-slate-300">
                    {integration.passed}/{integration.total} passed
                  </span>
                  <Button variant="ghost" size="sm">View</Button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent Runs */}
        <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
          <h2 className="text-lg font-semibold text-white mb-4">Recent Test Runs</h2>
          <div className="space-y-2">
            {recentRuns.map((run: any) => (
              <div 
                key={run.id}
                className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <span className="text-slate-400 text-sm font-mono">{run.timestamp}</span>
                  <span className="text-white">{run.name}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={run.passed === run.total ? 'text-emerald-400' : 'text-amber-400'}>
                    {run.passed === run.total ? '✅' : '⚠️'}
                  </span>
                  <span className="text-slate-300">{run.passed}/{run.total}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Layout>
  )
}
```

### 4.2 Human Review Queue with Keyboard Shortcuts
```tsx
// frontend/src/app/review/page.tsx
'use client'

import { useState, useEffect, useCallback } from 'react'
import { CheckCircle2, XCircle, HelpCircle, SkipForward, Filter, ChevronLeft, ChevronRight } from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { Button } from '@/components/ui/Button'

interface Detection {
  id: string
  type: string
  traceId: string
  agentType: string
  pattern: string
  confidence: number
}

export default function ReviewPage() {
  const [detections, setDetections] = useState<Detection[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [filter, setFilter] = useState('all')
  const [reviewed, setReviewed] = useState(0)
  const [showFeedback, setShowFeedback] = useState<string | null>(null)

  const current = detections[currentIndex]
  const pending = detections.length - reviewed

  const handleLabel = useCallback(async (label: 'correct' | 'false_positive' | 'unclear' | 'skip') => {
    if (!current) return
    
    if (label !== 'skip') {
      await fetch(`/api/v1/detections/${current.id}/label`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ label })
      })
      setReviewed(r => r + 1)
    }
    
    // Show feedback
    const feedbackMap = {
      correct: '✅ Marked as correct',
      false_positive: '❌ Marked as false positive',
      unclear: '🤔 Marked as unclear',
      skip: '⏭️ Skipped'
    }
    setShowFeedback(feedbackMap[label])
    
    // Auto-advance after 1s
    setTimeout(() => {
      setShowFeedback(null)
      if (currentIndex < detections.length - 1) {
        setCurrentIndex(i => i + 1)
      }
    }, 1000)
  }, [current, currentIndex, detections.length])

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return
      
      switch (e.key.toLowerCase()) {
        case 'c': handleLabel('correct'); break
        case 'f': handleLabel('false_positive'); break
        case 'u': handleLabel('unclear'); break
        case 's': handleLabel('skip'); break
        case 'arrowleft': setCurrentIndex(i => Math.max(0, i - 1)); break
        case 'arrowright': setCurrentIndex(i => Math.min(detections.length - 1, i + 1)); break
      }
    }
    
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleLabel, detections.length])

  if (detections.length === 0) {
    return (
      <Layout>
        <div className="p-6 flex flex-col items-center justify-center h-[60vh]">
          <CheckCircle2 className="text-emerald-400 mb-4" size={64} />
          <h2 className="text-xl font-semibold text-white mb-2">All caught up!</h2>
          <p className="text-slate-400">No detections pending review.</p>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white">Detection Review Queue</h1>
            <p className="text-slate-400 text-sm mt-1">
              {reviewed} reviewed today · {pending} pending
            </p>
          </div>
          <div className="flex items-center gap-3">
            <select 
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white"
            >
              <option value="all">All Types</option>
              <option value="infinite_loop">Infinite Loop</option>
              <option value="state_corruption">State Corruption</option>
              <option value="persona_drift">Persona Drift</option>
              <option value="deadlock">Deadlock</option>
            </select>
            <Button variant="ghost" leftIcon={<Filter size={16} />}>
              High Confidence
            </Button>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="bg-slate-800 rounded-lg p-4 mb-6 border border-slate-700">
          <div className="flex items-center justify-between mb-2">
            <span className="text-slate-400 text-sm">Session Progress</span>
            <span className="text-white font-medium">{reviewed}/{detections.length}</span>
          </div>
          <div className="w-full bg-slate-700 rounded-full h-2">
            <div 
              className="bg-emerald-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${(reviewed / detections.length) * 100}%` }}
            />
          </div>
        </div>

        {/* Detection Card */}
        {current && (
          <div className="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h2 className="text-lg font-semibold text-white">
                  Detection #{current.id.slice(0, 8)} - {current.type.replace('_', ' ')}
                </h2>
                <p className="text-slate-400 text-sm mt-1">
                  Trace: {current.traceId.slice(0, 12)}... | Agent: {current.agentType}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Button 
                  variant="ghost" 
                  size="sm"
                  onClick={() => setCurrentIndex(i => Math.max(0, i - 1))}
                  disabled={currentIndex === 0}
                >
                  <ChevronLeft size={16} />
                </Button>
                <span className="text-slate-400 text-sm">
                  {currentIndex + 1} of {detections.length}
                </span>
                <Button 
                  variant="ghost" 
                  size="sm"
                  onClick={() => setCurrentIndex(i => Math.min(detections.length - 1, i + 1))}
                  disabled={currentIndex === detections.length - 1}
                >
                  <ChevronRight size={16} />
                </Button>
              </div>
            </div>

            <div className="bg-slate-700/50 rounded-lg p-4 mb-4">
              <p className="text-slate-300 mb-2">
                <strong>Pattern:</strong> {current.pattern}
              </p>
              <p className="text-slate-300">
                <strong>Confidence:</strong>{' '}
                <span className={current.confidence >= 90 ? 'text-emerald-400' : 'text-amber-400'}>
                  {current.confidence.toFixed(1)}%
                </span>
              </p>
            </div>

            <div className="flex items-center gap-3 mb-4">
              <Button variant="ghost" size="sm">View Trace</Button>
              <Button variant="ghost" size="sm">View Suggestion</Button>
            </div>

            {/* Feedback Toast */}
            {showFeedback && (
              <div className="bg-slate-700 rounded-lg p-3 mb-4 text-center animate-pulse">
                <span className="text-white">{showFeedback}</span>
                <span className="text-slate-400 text-sm ml-2">Auto-advancing...</span>
              </div>
            )}

            {/* Label Buttons */}
            <div className="border-t border-slate-700 pt-4">
              <p className="text-slate-400 text-sm mb-3">Was this detection correct?</p>
              <div className="flex items-center gap-3">
                <Button 
                  variant="success" 
                  onClick={() => handleLabel('correct')}
                  leftIcon={<CheckCircle2 size={16} />}
                >
                  Correct <kbd className="ml-2 text-xs opacity-60">C</kbd>
                </Button>
                <Button 
                  variant="danger" 
                  onClick={() => handleLabel('false_positive')}
                  leftIcon={<XCircle size={16} />}
                >
                  False Positive <kbd className="ml-2 text-xs opacity-60">F</kbd>
                </Button>
                <Button 
                  variant="secondary" 
                  onClick={() => handleLabel('unclear')}
                  leftIcon={<HelpCircle size={16} />}
                >
                  Unclear <kbd className="ml-2 text-xs opacity-60">U</kbd>
                </Button>
                <Button 
                  variant="ghost" 
                  onClick={() => handleLabel('skip')}
                  leftIcon={<SkipForward size={16} />}
                >
                  Skip <kbd className="ml-2 text-xs opacity-60">S</kbd>
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Keyboard Shortcuts Help */}
        <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
          <p className="text-slate-400 text-sm">
            <strong>Keyboard shortcuts:</strong>{' '}
            <kbd className="bg-slate-700 px-1.5 py-0.5 rounded text-xs">C</kbd> Correct{' '}
            <kbd className="bg-slate-700 px-1.5 py-0.5 rounded text-xs">F</kbd> False Positive{' '}
            <kbd className="bg-slate-700 px-1.5 py-0.5 rounded text-xs">U</kbd> Unclear{' '}
            <kbd className="bg-slate-700 px-1.5 py-0.5 rounded text-xs">S</kbd> Skip{' '}
            <kbd className="bg-slate-700 px-1.5 py-0.5 rounded text-xs">←/→</kbd> Navigate
          </p>
        </div>
      </div>
    </Layout>
  )
}
```

---

## Phase 5: Documentation (Week 4)

### 5.1 User Documentation
**Files to create:**
- `docs/user-guide/testing-your-agents.md`
- `docs/user-guide/reviewing-detections.md`
- `docs/user-guide/understanding-fix-suggestions.md`

### 5.2 Developer Documentation
**Files to create:**
- `docs/dev-guide/running-integration-tests.md`
- `docs/dev-guide/adding-framework-support.md`
- `docs/dev-guide/recording-vcr-cassettes.md`

---

## Phase 6: CI/CD Integration (Week 4)

### 6.1 GitHub Actions
```yaml
# .github/workflows/e2e-tests.yml
name: E2E Tests

on:
  push:
    branches: [main]
  pull_request:

jobs:
  golden-dataset:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Validate detection accuracy
        run: python scripts/validate_detections.py
      - name: Assert thresholds
        run: |
          python -c "
          import json
          results = json.load(open('detection_results.json'))
          for dtype, m in results.items():
              assert m['f1'] >= 0.85, f'{dtype} F1 {m[\"f1\"]} < 0.85'
          "

  integration-tests:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        framework: [langchain, crewai, autogen]
    steps:
      - uses: actions/checkout@v4
      - name: Run tests (replay mode)
        env:
          MAO_RECORD_MODE: none
        run: pytest tests/integration/test_${{ matrix.framework }}.py -v

  fix-validation:
    runs-on: ubuntu-latest
    services:
      docker:
        image: docker:dind
    steps:
      - uses: actions/checkout@v4
      - name: Build sandbox
        run: docker build -t mao/fix-sandbox -f Dockerfile.sandbox .
      - name: Run fix validation
        run: pytest tests/integration/test_fix_validation.py -v
```

---

## Deliverables Summary

| Component | Files | Priority | Status |
|-----------|-------|----------|--------|
| VCR Infrastructure | 3 | P0 | 🔜 |
| LangChain Tests | 3 | P0 | 🔜 |
| Fix Validation Sandbox | 4 | P0 | 🔜 |
| Test Dashboard UI | 2 | P1 | 🔜 |
| Review Queue UI | 2 | P1 | 🔜 |
| User Docs | 3 | P1 | 🔜 |
| CI/CD | 2 | P1 | 🔜 |

## Success Criteria

1. **Detection Accuracy**: ≥90% F1 on golden dataset
2. **Fix Effectiveness**: ≥85% success rate
3. **Framework Coverage**: LangChain, CrewAI, AutoGen all passing
4. **UI Usability**: Review detection in <30 seconds with keyboard
5. **Security**: All code execution sandboxed
6. **Documentation**: All features documented with examples
