"""Cross-Database Integration Detection (DAB property i).

Detects failures when an agent queries across multiple databases:
- Schema mismatches between databases
- Ill-formatted join keys (bid_123 vs bref_123, trailing whitespace)
- Query dialect errors (PostgreSQL vs MongoDB vs SQLite syntax)
- Missing cross-database joins when task requires them
- Data type incompatibilities across systems

DAB found ALL 54 queries require multi-database integration, and
join key reconciliation is needed in 26/54 queries.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class IntegrationIssue:
    """A cross-database integration problem."""
    issue_type: str  # schema_mismatch, join_key_format, dialect_error, missing_join, type_incompatible
    severity: str
    description: str
    source_db: str = ""
    target_db: str = ""
    evidence: str = ""


@dataclass
class CrossDatabaseResult:
    """Result of cross-database integration analysis."""
    detected: bool
    confidence: float
    issues: List[IntegrationIssue] = field(default_factory=list)
    databases_involved: List[str] = field(default_factory=list)
    join_keys_found: List[Dict[str, str]] = field(default_factory=list)
    raw_score: Optional[float] = None


class CrossDatabaseDetector:
    """Detects cross-database integration failures.

    Analyzes agent traces that involve multiple databases for:
    1. Schema mismatches (same entity, different column names)
    2. Join key format differences (id_123 vs id-123 vs ID123)
    3. SQL dialect errors (PostgreSQL syntax in SQLite context)
    4. Missing joins when task requires cross-DB data
    5. Data type incompatibilities
    """

    # Known SQL dialect differences
    DIALECT_FEATURES = {
        "postgresql": {"ILIKE", "::text", "SERIAL", "RETURNING", "ON CONFLICT", "JSONB"},
        "sqlite": {"GLOB", "typeof()", "datetime()", "julianday()", "AUTOINCREMENT"},
        "mysql": {"LIMIT offset,count", "IFNULL", "AUTO_INCREMENT", "ENGINE="},
        "mongodb": {"$match", "$group", "$project", "$lookup", "$unwind", "ObjectId"},
        "duckdb": {"COPY", "PARQUET", "read_csv_auto", "STRUCT", "LIST"},
    }

    # Common join key format patterns
    JOIN_KEY_PATTERNS = [
        (r"\bid[_-]?\d+\b", "numeric_id"),  # id_123, id-123, id123
        (r"\b[a-z]+[_-]\d+\b", "prefixed_id"),  # user_123, order-456
        (r"\b\d+\b", "bare_number"),  # Just 123
        (r"\b[A-Z]{2,}_\d+\b", "code_id"),  # US_123, ORD_456
    ]

    def detect(
        self,
        queries: List[Dict[str, Any]],
        databases: List[Dict[str, Any]],
        task: str,
        agent_output: Optional[str] = None,
    ) -> CrossDatabaseResult:
        """Analyze cross-database integration quality.

        Args:
            queries: List of queries executed [{db, query, result}, ...]
            databases: List of database schemas [{name, type, tables, ...}, ...]
            task: The original task description
            agent_output: The agent's final answer
        """
        issues = []
        db_names = [d.get("name", d.get("db_name", "")) for d in databases]

        # Check 1: Missing cross-database join
        if len(databases) >= 2:
            join_issues = self._check_missing_joins(queries, databases, task)
            issues.extend(join_issues)

        # Check 2: Join key format mismatches
        key_issues, keys_found = self._check_join_key_formats(queries, databases)
        issues.extend(key_issues)

        # Check 3: SQL dialect errors
        dialect_issues = self._check_dialect_errors(queries, databases)
        issues.extend(dialect_issues)

        # Check 4: Schema mismatches
        schema_issues = self._check_schema_mismatches(databases)
        issues.extend(schema_issues)

        # Check 5: Data type incompatibilities
        type_issues = self._check_type_incompatibilities(queries)
        issues.extend(type_issues)

        if not issues:
            return CrossDatabaseResult(
                detected=False, confidence=0.0,
                databases_involved=db_names, join_keys_found=keys_found,
            )

        severity_weights = {"critical": 1.0, "high": 0.7, "medium": 0.4, "low": 0.2}
        max_sev = max(severity_weights.get(i.severity, 0.3) for i in issues)
        confidence = min(1.0, max_sev * (1 + 0.1 * (len(issues) - 1)))

        return CrossDatabaseResult(
            detected=True,
            confidence=round(confidence, 4),
            issues=issues,
            databases_involved=db_names,
            join_keys_found=keys_found,
            raw_score=confidence,
        )

    def _check_missing_joins(
        self, queries: List[Dict], databases: List[Dict], task: str
    ) -> List[IntegrationIssue]:
        """Check if task requires cross-DB data but agent doesn't join."""
        issues = []

        # Which databases were actually queried?
        queried_dbs = {q.get("db", q.get("db_name", "")) for q in queries}
        available_dbs = {d.get("name", d.get("db_name", "")) for d in databases}

        # If multiple DBs available but only one queried, might be missing integration
        if len(available_dbs) >= 2 and len(queried_dbs) <= 1:
            task_lower = task.lower()
            multi_source_keywords = ["across", "from both", "combine", "together", "join", "all databases", "compare"]
            if any(kw in task_lower for kw in multi_source_keywords):
                issues.append(IntegrationIssue(
                    issue_type="missing_join",
                    severity="high",
                    description=f"Task requires data from multiple sources but only {len(queried_dbs)} database(s) queried",
                    evidence=f"Available: {available_dbs}, Queried: {queried_dbs}",
                ))

        return issues

    def _check_join_key_formats(
        self, queries: List[Dict], databases: List[Dict]
    ) -> tuple:
        """Check for join key format mismatches between databases."""
        issues = []
        keys_found = []

        # Extract column names from schemas
        db_columns: Dict[str, Set[str]] = {}
        for db in databases:
            db_name = db.get("name", "")
            cols = set()
            for table in db.get("tables", []):
                if isinstance(table, dict):
                    for col in table.get("columns", []):
                        col_name = col if isinstance(col, str) else col.get("name", "")
                        cols.add(col_name.lower())
                elif isinstance(table, str):
                    cols.add(table.lower())
            db_columns[db_name] = cols

        # Check for similar-but-different column names across DBs
        all_dbs = list(db_columns.keys())
        for i, db1 in enumerate(all_dbs):
            for db2 in all_dbs[i+1:]:
                cols1 = db_columns.get(db1, set())
                cols2 = db_columns.get(db2, set())

                for c1 in cols1:
                    for c2 in cols2:
                        if c1 != c2 and self._are_similar_keys(c1, c2):
                            keys_found.append({"db1": db1, "col1": c1, "db2": db2, "col2": c2})
                            issues.append(IntegrationIssue(
                                issue_type="join_key_format",
                                severity="medium",
                                description=f"Potential join key mismatch: '{c1}' in {db1} vs '{c2}' in {db2}",
                                source_db=db1, target_db=db2,
                                evidence=f"These may refer to the same entity with different formatting",
                            ))

        return issues, keys_found

    def _are_similar_keys(self, key1: str, key2: str) -> bool:
        """Check if two column names likely refer to the same entity."""
        # Remove common prefixes/suffixes
        k1 = re.sub(r"[_\-\s]", "", key1.lower())
        k2 = re.sub(r"[_\-\s]", "", key2.lower())

        # Exact match after normalization
        if k1 == k2:
            return True

        # One is prefix of the other (book_id vs bookid)
        if k1.startswith(k2) or k2.startswith(k1):
            return True

        # Common entity words match (bid vs book_id)
        entities = {"id", "name", "key", "ref", "code", "num"}
        k1_parts = set(re.split(r"[_\-]", key1.lower()))
        k2_parts = set(re.split(r"[_\-]", key2.lower()))
        shared_entities = (k1_parts & k2_parts) - entities
        if shared_entities:
            return True

        return False

    def _check_dialect_errors(
        self, queries: List[Dict], databases: List[Dict]
    ) -> List[IntegrationIssue]:
        """Check for SQL dialect mismatches."""
        issues = []

        db_types = {d.get("name", ""): d.get("type", d.get("db_type", "")).lower() for d in databases}

        for q in queries:
            db_name = q.get("db", q.get("db_name", ""))
            query_text = q.get("query", "").upper()
            db_type = db_types.get(db_name, "")

            if not query_text or not db_type:
                continue

            # Check for wrong dialect features
            for dialect, features in self.DIALECT_FEATURES.items():
                if dialect == db_type:
                    continue  # Same dialect, skip
                for feature in features:
                    if feature.upper() in query_text:
                        issues.append(IntegrationIssue(
                            issue_type="dialect_error",
                            severity="high",
                            description=f"'{feature}' is a {dialect} feature but target database is {db_type}",
                            source_db=db_name,
                            evidence=f"Query contains {dialect}-specific syntax for {db_type} database",
                        ))

        return issues

    def _check_schema_mismatches(self, databases: List[Dict]) -> List[IntegrationIssue]:
        """Check for schema inconsistencies between databases."""
        issues = []

        # Check for tables with similar names but different schemas
        all_tables = {}
        for db in databases:
            db_name = db.get("name", "")
            for table in db.get("tables", []):
                table_name = table.get("name", "") if isinstance(table, dict) else str(table)
                if table_name:
                    all_tables.setdefault(table_name.lower(), []).append(db_name)

        # Tables that appear in multiple DBs (potential schema mismatch)
        for table, dbs in all_tables.items():
            if len(dbs) > 1:
                issues.append(IntegrationIssue(
                    issue_type="schema_mismatch",
                    severity="low",
                    description=f"Table '{table}' exists in multiple databases: {dbs}. Schemas may differ.",
                ))

        return issues

    def _check_type_incompatibilities(self, queries: List[Dict]) -> List[IntegrationIssue]:
        """Check for data type issues in cross-database operations."""
        issues = []

        for q in queries:
            query = q.get("query", "")
            # Implicit type coercion risks
            if re.search(r"CAST\s*\(", query, re.IGNORECASE) or re.search(r"::\w+", query):
                # Has explicit casting — good
                pass
            elif re.search(r"=\s*'\d+'", query):
                # Comparing number stored as string — potential issue
                issues.append(IntegrationIssue(
                    issue_type="type_incompatible",
                    severity="low",
                    description="Comparing numeric value as string — may need explicit type casting",
                    evidence=query[:100],
                ))

        return issues


# Singleton
cross_database_detector = CrossDatabaseDetector()
