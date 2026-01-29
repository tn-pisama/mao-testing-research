# N8N Data Summary - Complete Count

**Generated**: January 29, 2026
**Backend Status**: ✅ Healthy (Database & Redis restored)

---

## Production Database (mao-db.internal)

### Core N8N Tables

| Table | Count | Description |
|-------|-------|-------------|
| `n8n_workflows` | **1** | Registered workflows being monitored |
| `n8n_connections` | **1** | Active n8n instance connections |
| `traces` (framework='n8n') | **207** | Execution traces from n8n workflows |
| `states` (from n8n traces) | **42** | Node execution states across n8n traces |
| `detections` (from n8n traces) | **11** | Failure detections in n8n executions |

### Additional Context

**All Database Tables**:
- api_keys
- detections
- n8n_connections ✅
- n8n_workflows ✅
- states
- tenants
- traces
- users
- webhook_nonces

**Tables Not Yet Created** (per schema but no data):
- workflow_quality_assessments
- healing_records
- workflow_versions

### Overall Database Stats

| Metric | Count |
|--------|-------|
| Total Traces (all frameworks) | 207 |
| Total States (all frameworks) | 42 |
| Total Detections (all frameworks) | 11 |

**N8N Percentage**:
- 100% of traces are from n8n (207/207)
- 100% of states are from n8n (42/42)
- 100% of detections are from n8n (11/11)

---

## Local Workflow Files

### Test Workflows (`n8n-workflows/`)

**Total**: 92 JSON files

#### Main Test Workflows (8 files):
1. `01-loop-injection.json` - Loop failure test
2. `02-hallucination-injection.json` - Hallucination test
3. `03-coordination-failure.json` - Coordination test
4. `04-state-corruption.json` - State corruption test
5. `05-persona-drift.json` - Persona drift test
6. `hn-analyzer.json` - HackerNews Comment Analyzer
7. `news-aggregator.json` - Multi-Source News Aggregator
8. `fact-checker.json` - Real-Time Fact Checker

#### Subdirectories with Variants (84 files):
- `coordination/` - 18 coordination failure test variants
- `loop/` - 18 loop detection test variants
- `persona/` - 15 persona drift test variants
- `resource/` - 15 resource overflow test variants
- `state/` - 18 state corruption test variants

### Template Fixtures (`backend/fixtures/external/n8n/`)

**Total**: 11,650 JSON files

Sources:
- `zengfr-templates/` - Community workflow templates
- `zie619-workflows/` - Additional workflow examples

---

## Summary Statistics

### Production Data (Live)
- **Registered Workflows**: 1
- **Active Connections**: 1
- **Execution Traces**: 207
- **Node States**: 42
- **Failures Detected**: 11

### Test Data (Local Files)
- **Test Workflows**: 92
- **Template Library**: 11,650

### Grand Total
**11,743 n8n workflows** (1 live + 92 tests + 11,650 templates)

---

## Production Backend Health

```json
{
  "status": "healthy",
  "database": "healthy",
  "redis": "healthy",
  "version": "0.1.0"
}
```

**Fixed Issues**:
1. ✅ Redis created and connected (mao-redis)
2. ✅ PostgreSQL restarted and healthy
3. ✅ All health checks passing

---

## Data Collection Commands

To query this data yourself:

```bash
# Check backend health
curl https://mao-api.fly.dev/api/v1/health

# Count local workflows
find n8n-workflows -name "*.json" | wc -l

# Count templates
find backend/fixtures/external/n8n -name "*.json" | wc -l

# Query database (requires SSH access)
fly ssh console -a mao-api -C "python3 -c 'import asyncio; import asyncpg; ...'"
```

---

## Notes

- The production database contains only actual execution data (207 traces)
- Test workflows (92) are used for MAST benchmarking
- Template library (11,650) provides workflow examples for analysis
- Database schema supports quality assessments and self-healing but those tables are empty
