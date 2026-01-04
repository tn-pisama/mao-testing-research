# PISAMA Claude Code Distribution Plan

## Executive Summary

Package and distribute PISAMA trace capture and failure detection for Claude Code users, enabling them to:
1. Capture all tool calls automatically
2. Detect MAST failure modes (F1-F16) locally
3. Optionally sync traces to MAO Testing platform for team analytics

---

## 1. Package Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Distribution Packages                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────┐  │
│  │  pisama-claude-code │  │    pisama-core      │  │  pisama-skills  │  │
│  │      (PyPI)         │  │      (PyPI)         │  │   (Optional)    │  │
│  │                     │  │                     │  │                 │  │
│  │  • CLI (pisama-cc)  │  │  • Span format      │  │  • /diagnose    │  │
│  │  • Hook installer   │  │  • Storage adapters │  │  • /fix         │  │
│  │  • Local detection  │  │  • Base detectors   │  │  • /config      │  │
│  │  • Cloud sync       │  │  • Converters       │  │  • /guardian    │  │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────┘  │
│           │                        │                        │           │
│           └────────────────────────┼────────────────────────┘           │
│                                    ▼                                     │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                     MAO Testing Platform                          │   │
│  │  • Dashboard  • Team Analytics  • AI Fix Suggestions  • Alerts   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Package Details

### pisama-claude-code (Primary Package)

**Purpose**: Main package for Claude Code users

**Installation**:
```bash
pip install pisama-claude-code
```

**Features**:
| Feature | Local (Free) | Cloud (Premium) |
|---------|--------------|-----------------|
| Trace capture | ✅ | ✅ |
| F4-F16 detection | ✅ | ✅ |
| Skill differentiation | ✅ | ✅ |
| Self-healing (loop break) | ✅ | ✅ |
| Export/share traces | ✅ | ✅ |
| Sync to platform | ❌ | ✅ |
| Team dashboard | ❌ | ✅ |
| Cross-session analytics | ❌ | ✅ |
| AI fix suggestions | ❌ | ✅ |

**CLI Commands**:
```
pisama-cc init          # Install hooks, create config
pisama-cc status        # Show connection status
pisama-cc analyze       # Run local detection
pisama-cc sync          # Upload to platform (requires API key)
pisama-cc export        # Export traces to file
pisama-cc connect       # Connect to MAO platform
pisama-cc disconnect    # Remove API key
```

**Dependencies**:
- click >= 8.0.0 (CLI framework)
- rich >= 13.0.0 (Pretty output)
- pydantic >= 2.0.0 (Data validation)
- httpx >= 0.25.0 (HTTP client)

**Optional Dependencies**:
- pisama-core (for advanced features)

---

## 3. Installation Flow

### First-Time User Experience

```
┌──────────────────────────────────────────────────────────────────┐
│  Step 1: Install                                                  │
│  $ pip install pisama-claude-code                                │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  Step 2: Initialize                                               │
│  $ pisama-cc init                                                │
│                                                                   │
│  ✅ Created ~/.claude/pisama/config.json                         │
│  ✅ Installed hooks in ~/.claude/settings.json                   │
│  ✅ Created trace storage directory                              │
│                                                                   │
│  Traces will now be captured automatically.                      │
│  Run 'pisama-cc analyze' to detect failures.                     │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  Step 3: Use Claude Code Normally                                 │
│  $ claude                                                        │
│                                                                   │
│  (All tool calls are captured in background)                     │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  Step 4: Analyze (Optional)                                       │
│  $ pisama-cc analyze --last 100                                  │
│                                                                   │
│  📊 Analysis Results                                              │
│  ✅ F4 Tool Misuse: OK                                           │
│  🟡 F6 Loop: 12 consecutive repeats detected                     │
│  ✅ F15 Grounding: OK                                            │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  Step 5: Connect to Platform (Optional)                          │
│  $ pisama-cc connect --api-key pk_live_xxx                       │
│                                                                   │
│  ✅ Connected to MAO Testing Platform                            │
│  📡 Auto-sync enabled                                            │
│  🔗 View dashboard: https://app.maotesting.com/traces            │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. Hook Installation

### What Gets Installed

**~/.claude/settings.json** (merged, not replaced):
```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "pisama-cc hook pre"
      }]
    }],
    "PostToolUse": [{
      "matcher": "*", 
      "hooks": [{
        "type": "command",
        "command": "pisama-cc hook post"
      }]
    }]
  }
}
```

### Safety Considerations

1. **Backup existing settings** before modifying
2. **Merge hooks** - don't replace user's existing hooks
3. **Fail gracefully** - hooks must not block Claude Code
4. **Timeout protection** - hooks have 5s max execution time

---

## 5. Data & Privacy

### What Is Captured

| Data | Captured | Synced to Cloud | Configurable |
|------|----------|-----------------|--------------|
| Tool names | ✅ | ✅ | No |
| Timestamps | ✅ | ✅ | No |
| Session IDs | ✅ | ✅ | No |
| Hook type (Pre/Post) | ✅ | ✅ | No |
| Working directory | ✅ | ✅ (anonymized) | Yes |
| Tool inputs | ✅ | ✅ (sanitized) | Yes |
| Tool outputs | ✅ | ⚙️ (opt-in) | Yes |
| File contents | ❌ | ❌ | - |
| Secrets/API keys | ❌ (redacted) | ❌ | - |

### Redaction Rules

1. **Environment variables**: Keys containing `SECRET`, `KEY`, `TOKEN`, `PASSWORD` → `[REDACTED]`
2. **File paths**: `/Users/name/...` → `~/...`
3. **Large outputs**: Truncated to 500 chars
4. **Credentials in commands**: Pattern-matched and removed

### Local-Only Mode

Users can run completely locally without any cloud sync:
```bash
pisama-cc init --local-only
```

---

## 6. Versioning Strategy

### Semantic Versioning

```
MAJOR.MINOR.PATCH

0.1.0  - Initial release
0.1.1  - Bug fixes
0.2.0  - New detection modes
1.0.0  - Stable API, production ready
```

### Compatibility Matrix

| pisama-claude-code | Claude Code | Python | MAO Platform API |
|--------------------|-------------|--------|------------------|
| 0.1.x | Any | 3.10+ | v1 |
| 0.2.x | Any | 3.10+ | v1 |
| 1.0.x | TBD | 3.10+ | v1, v2 |

---

## 7. Distribution Channels

### Phase 1: Private Beta (Now)
- GitHub releases only
- Manual pip install from repo
- Selected users

### Phase 2: Public Beta (Next)
- PyPI publication
- TestPyPI first for validation
- Documentation site

### Phase 3: General Availability
- Stable PyPI release
- Homebrew formula (optional)
- IDE extension hooks (VS Code, etc.)

---

## 8. Testing Strategy

### Unit Tests
```
tests/
├── test_cli.py           # CLI command tests
├── test_hooks.py         # Hook installation tests
├── test_detection.py     # Detection algorithm tests
├── test_sync.py          # Cloud sync tests
└── test_privacy.py       # Redaction tests
```

### Integration Tests
- Install on fresh system
- Run with real Claude Code session
- Verify trace capture
- Test sync to staging platform

### E2E Tests
- Full user journey: install → use → analyze → sync
- Cross-platform: macOS, Linux, Windows (WSL)

---

## 9. CI/CD Pipeline

```yaml
# .github/workflows/publish.yml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install build twine
      - run: python -m build
      - run: twine upload dist/*
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
```

---

## 10. Documentation

### README.md (PyPI)
- Quick start (3 commands)
- Feature overview
- Privacy statement
- Links to full docs

### docs.maotesting.com/claude-code/
- Installation guide
- Configuration reference
- CLI reference
- Troubleshooting
- FAQ

### In-CLI Help
```bash
pisama-cc --help
pisama-cc init --help
pisama-cc analyze --help
```

---

## 11. Pricing Model

### Free Tier
- Local trace capture (unlimited)
- Local detection (F4-F16)
- Export to file
- Self-healing (local)

### Pro Tier ($X/month per seat)
- Everything in Free
- Cloud sync
- Team dashboard
- 30-day trace retention
- Basic alerts

### Enterprise
- Everything in Pro
- Unlimited retention
- SSO/SAML
- Custom detection rules
- Priority support
- SLA

---

## 12. Implementation Phases

### Phase 1: Package Cleanup (This Week)
- [ ] Fix datetime deprecation warnings
- [ ] Add proper error handling
- [ ] Write unit tests
- [ ] Update README for PyPI
- [ ] Add LICENSE file

### Phase 2: PyPI Publication (Next Week)
- [ ] Test on TestPyPI
- [ ] Publish to PyPI
- [ ] Verify installation works
- [ ] Announce to beta users

### Phase 3: Platform Integration (Following Week)
- [ ] Deploy backend API to production
- [ ] Test cloud sync end-to-end
- [ ] Build basic dashboard view
- [ ] Enable team workspaces

### Phase 4: Skills & Self-Healing (Future)
- [ ] Package pisama-skills
- [ ] Auto-install skills on init
- [ ] Guardian real-time mode
- [ ] AI-powered fix suggestions

---

## 13. Success Metrics

### Adoption
- Package downloads (PyPI)
- Active installations (heartbeat)
- Connected accounts (cloud)

### Engagement
- Traces captured per user
- Analysis runs per week
- Detections per session

### Value
- Failures detected before impact
- Time saved via self-healing
- User satisfaction (NPS)

---

## 14. Open Questions

1. **Package name**: `pisama-claude-code` vs `mao-claude-code` vs `claude-code-testing`?
2. **Pricing**: What's the right price point for Pro tier?
3. **Skills distribution**: Separate package or bundled?
4. **Windows support**: Priority or later?
5. **IDE integration**: Worth the effort?

---

## 15. Next Actions

1. ✅ Create package structure
2. ✅ Implement CLI
3. ✅ Add cloud sync
4. ⏳ Fix deprecation warnings
5. ⏳ Write tests
6. ⏳ Update README
7. ⏳ Publish to TestPyPI
8. ⏳ Test installation
9. ⏳ Publish to PyPI
10. ⏳ Announce to users
