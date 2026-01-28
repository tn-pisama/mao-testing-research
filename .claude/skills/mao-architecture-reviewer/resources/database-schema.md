# PISAMA Database Schema Reference

This document defines the database schema, migration rules, and indexing strategy for the PISAMA platform.

---

## Core Tables

### traces
Stores ingested trace data from OTEL, n8n, and custom sources.

```sql
CREATE TABLE traces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    duration_ms INTEGER,
    status VARCHAR(50),
    source VARCHAR(50), -- 'otel', 'n8n', 'custom'
    user_id UUID REFERENCES users(id),
    project_id UUID REFERENCES projects(id),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_traces_trace_id ON traces(trace_id);
CREATE INDEX idx_traces_user_project ON traces(user_id, project_id);
CREATE INDEX idx_traces_start_time ON traces(start_time DESC);
CREATE INDEX idx_traces_metadata ON traces USING gin(metadata);
```

---

### spans
Stores individual spans within traces.

```sql
CREATE TABLE spans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    span_id VARCHAR(255) NOT NULL,
    trace_id UUID REFERENCES traces(id) ON DELETE CASCADE,
    parent_span_id VARCHAR(255),
    name VARCHAR(255),
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    duration_ms INTEGER,
    attributes JSONB,
    events JSONB,
    status VARCHAR(50),
    embedding vector(384), -- for semantic similarity (pgvector)
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_spans_trace_id ON spans(trace_id);
CREATE INDEX idx_spans_span_id ON spans(span_id);
CREATE INDEX idx_spans_start_time ON spans(start_time);
CREATE INDEX idx_spans_attributes ON spans USING gin(attributes);

-- pgvector index for semantic search
CREATE INDEX idx_spans_embedding ON spans USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

---

### detections
Stores failure detections found by the detection engine.

```sql
CREATE TABLE detections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id UUID REFERENCES traces(id) ON DELETE CASCADE,
    detection_type VARCHAR(100) NOT NULL, -- 'loop', 'corruption', 'persona', etc.
    failure_code VARCHAR(50), -- 'LOOP-001', 'STATE-004', etc.
    severity VARCHAR(50), -- 'low', 'medium', 'high', 'critical'
    confidence FLOAT, -- 0.0 to 1.0
    span_ids JSONB, -- array of affected span IDs
    evidence JSONB,
    root_cause TEXT,
    tier INTEGER, -- 1-5 (which detection tier found it)
    cost_usd DECIMAL(10, 6), -- detection cost
    detected_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'active', -- 'active', 'resolved', 'false_positive'
    resolved_at TIMESTAMP,
    resolved_by UUID REFERENCES users(id)
);

CREATE INDEX idx_detections_trace_id ON detections(trace_id);
CREATE INDEX idx_detections_type ON detections(detection_type);
CREATE INDEX idx_detections_severity ON detections(severity);
CREATE INDEX idx_detections_detected_at ON detections(detected_at DESC);
CREATE INDEX idx_detections_status ON detections(status);
```

---

### fixes
Stores AI-generated fix suggestions for detections.

```sql
CREATE TABLE fixes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    detection_id UUID REFERENCES detections(id) ON DELETE CASCADE,
    fix_type VARCHAR(100), -- 'prompt', 'state', 'coordination', 'resource'
    title VARCHAR(255),
    description TEXT,
    code_suggestion TEXT,
    confidence FLOAT,
    playbook_id UUID, -- if fix is from a playbook
    ai_generated BOOLEAN DEFAULT true,
    approval_required BOOLEAN DEFAULT false,
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMP,
    applied_at TIMESTAMP,
    rollback_checkpoint JSONB,
    feedback JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_fixes_detection_id ON fixes(detection_id);
CREATE INDEX idx_fixes_type ON fixes(fix_type);
CREATE INDEX idx_fixes_approval_required ON fixes(approval_required);
```

---

### users
User accounts and authentication.

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'developer', -- 'developer', 'admin', 'viewer'
    auth_provider VARCHAR(50), -- 'clerk', 'oauth', 'api_key'
    auth_provider_id VARCHAR(255),
    feature_flags JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    last_login_at TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_auth_provider ON users(auth_provider, auth_provider_id);
```

---

### projects
Organizational grouping for traces.

```sql
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    owner_id UUID REFERENCES users(id),
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_projects_owner_id ON projects(owner_id);
```

---

### mast_embeddings
Pre-computed embeddings for MAST benchmark traces (few-shot learning).

```sql
CREATE TABLE mast_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id VARCHAR(255),
    span_text TEXT,
    embedding vector(384),
    failure_type VARCHAR(100),
    failure_code VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_mast_embeddings_failure_type ON mast_embeddings(failure_type);
CREATE INDEX idx_mast_embeddings_embedding ON mast_embeddings USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 50);
```

---

## Migration Rules

### 1. Backward Compatibility
- **NEVER** drop columns without a deprecation period (minimum 2 releases)
- Mark deprecated columns in migration comments
- Add new columns as `NULL` or with `DEFAULT` values

### 2. Index Strategy
- Every foreign key MUST have an index
- JSONB columns queried in WHERE clauses need GIN indexes
- Add indexes CONCURRENTLY in production:
  ```sql
  CREATE INDEX CONCURRENTLY idx_name ON table(column);
  ```

### 3. pgvector Columns
- Dimension MUST be 384 (sentence-transformers/all-MiniLM-L6-v2)
- Always use `ivfflat` index with `vector_cosine_ops`
- Set `lists` parameter based on table size:
  - Small (<10k rows): lists = 50
  - Medium (10k-100k rows): lists = 100
  - Large (>100k rows): lists = sqrt(rows)

### 4. Migration Checklist
- [ ] Migration is reversible (include DOWN migration)
- [ ] Indexes added CONCURRENTLY (production safety)
- [ ] No breaking changes to existing columns
- [ ] Default values provided for new NOT NULL columns
- [ ] Updated SQLAlchemy models in `backend/app/storage/models.py`
- [ ] Updated Alembic migration in `backend/app/storage/migrations/versions/`

---

## Common Schema Patterns

### Adding a New Detection Type

When adding a new detection algorithm:

1. **No schema change needed** - detections table is generic
2. Update `detection_type` enum in application code
3. Ensure detector outputs match `detections` table structure:
   ```python
   detection = {
       "detection_type": "new_detector",
       "failure_code": "CUSTOM-001",
       "severity": "medium",
       "confidence": 0.85,
       "span_ids": ["span1", "span2"],
       "evidence": {"pattern": "...", "metrics": {}},
       "tier": 2,
       "cost_usd": 0.0001
   }
   ```

### Adding Semantic Search

When adding a new semantic similarity feature:

1. Add `embedding vector(384)` column
2. Create ivfflat index:
   ```sql
   CREATE INDEX CONCURRENTLY idx_table_embedding 
   ON table USING ivfflat (embedding vector_cosine_ops)
   WITH (lists = 100);
   ```
3. Use cosine similarity in queries:
   ```sql
   SELECT id, 1 - (embedding <=> query_vector) AS similarity
   FROM table
   WHERE 1 - (embedding <=> query_vector) > 0.8
   ORDER BY embedding <=> query_vector
   LIMIT 10;
   ```

### Adding Feature Flags

Feature flags are stored in `users.feature_flags` JSONB:

```python
user.feature_flags = {
    "ml_detection": True,
    "advanced_evals": False,
    "beta_features": ["tiered_detection", "llm_judge"]
}
```

Check feature flags in code:
```python
if user.feature_flags.get("ml_detection"):
    # Use enterprise ML detector
else:
    # Use ICP detectors only
```

---

## Performance Considerations

### Query Optimization
- Use `EXPLAIN ANALYZE` for slow queries
- Avoid `SELECT *` - specify columns
- Use pagination for large result sets
- Leverage JSONB indexes for metadata queries

### Connection Pooling
- Max pool size: 20 connections (asyncpg)
- Connection timeout: 30s
- Use async/await patterns consistently

### Batch Operations
- Bulk insert traces/spans in batches of 100-500
- Use `COPY` for large data imports
- Batch embedding computations before DB insert

---

## Breaking Change Examples

### ❌ DO NOT DO THIS:
```sql
-- Dropping a column without deprecation
ALTER TABLE traces DROP COLUMN metadata;

-- Changing column type incompatibly
ALTER TABLE spans ALTER COLUMN embedding TYPE vector(512);

-- Adding NOT NULL without DEFAULT
ALTER TABLE detections ADD COLUMN new_field VARCHAR NOT NULL;
```

### ✅ DO THIS INSTEAD:
```sql
-- Deprecate column first (add comment, log warnings)
-- In next release, drop it
ALTER TABLE traces DROP COLUMN old_metadata; -- deprecated in v1.2

-- Add new column, migrate data, deprecate old column
ALTER TABLE spans ADD COLUMN embedding_v2 vector(512);
-- Migration script updates embedding_v2
-- In next release, drop embedding

-- Add with DEFAULT or NULL
ALTER TABLE detections ADD COLUMN new_field VARCHAR DEFAULT 'default_value';
```

---

## Monitoring Queries

### Table Sizes
```sql
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Index Usage
```sql
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY schemaname, tablename;
```

### Slow Queries
```sql
SELECT 
    query,
    calls,
    total_time,
    mean_time,
    max_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 20;
```
