#!/usr/bin/env python3
"""Import real n8n workflow fixtures, execute them, and create golden entries
from n8n's OWN execution results (not Pisama detector output).

Labels are derived independently:
  - n8n status="error" -> n8n_error positive
  - n8n execution duration vs timeout -> n8n_timeout positive/negative
  - node count / connection density -> n8n_complexity positive/negative
  - graph cycle detection on workflow JSON -> n8n_cycle positive/negative
  - schema violations in node types/connections -> n8n_schema positive/negative
  - resource usage (many nodes attempted, large payloads) -> n8n_resource positive/negative

Usage:
    python -m scripts.capture_n8n_executions
    python -m scripts.capture_n8n_executions --dry-run
    python -m scripts.capture_n8n_executions --n8n-host https://custom:5678
"""

import argparse
import hashlib
import json
import logging
import os
import random
import sys
import time
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import requests

# Setup path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("JWT_SECRET", "xK9mPqL2vN7wR4tY8uJ3hB6gF5dC0aZS")

from app.detection.validation import DetectionType
from app.detection_enterprise.golden_dataset import GoldenDataset, GoldenDatasetEntry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("capture_n8n")

# Output path
OUTPUT_PATH = BACKEND_DIR / "data" / "golden_dataset_n8n_execution.json"

# Fixture directories (in priority order)
FIXTURE_DIRS = [
    BACKEND_DIR / "fixtures" / "external" / "n8n" / "ai-templates",
    BACKEND_DIR / "fixtures" / "external" / "n8n" / "zie619-workflows",
    BACKEND_DIR / "fixtures" / "external" / "n8n" / "marvomatic-seo",
    BACKEND_DIR / "fixtures" / "external" / "n8n" / "zengfr-templates",
]

# Thresholds for independent labeling
COMPLEXITY_NODE_THRESHOLD = 15  # workflows with >= 15 nodes are "complex"
COMPLEXITY_CONN_DENSITY_THRESHOLD = 2.0  # avg connections per node
TIMEOUT_DURATION_MS = 30_000  # 30s execution = timeout-like
RESOURCE_NODE_ATTEMPTS_THRESHOLD = 10  # >= 10 nodes attempted in execution


def parse_args():
    parser = argparse.ArgumentParser(
        description="Import, execute, and label n8n workflows for golden dataset",
    )
    parser.add_argument(
        "--n8n-host",
        type=str,
        default="http://localhost:5678",
        help="n8n host URL (default: http://localhost:5678)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="n8n API key (default: from N8N_LOCAL_API_KEY env or auto-detect)",
    )
    parser.add_argument(
        "--session-cookie",
        type=str,
        default=None,
        help="n8n session cookie for REST API execution (auto-detect if not set)",
    )
    parser.add_argument(
        "--n8n-email",
        type=str,
        default="test@pisama.ai",
        help="n8n user email for login (default: test@pisama.ai)",
    )
    parser.add_argument(
        "--n8n-password",
        type=str,
        default="pisama2026",
        help="n8n user password for login (default: pisama2026)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=20,
        help="Number of workflows to import (default: 20)",
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed (default: 42)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Select and analyze workflows without importing/executing",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help=f"Output JSON path (default: {OUTPUT_PATH})",
    )
    parser.add_argument(
        "--exec-timeout",
        type=int,
        default=15,
        help="Seconds to wait for execution to complete (default: 15)",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete imported workflows after capturing traces",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# n8n API helpers
# ---------------------------------------------------------------------------

class N8nClient:
    """Thin wrapper around n8n Public API + REST API."""

    def __init__(self, host: str, api_key: str, session_cookie: str | None = None):
        self.host = host.rstrip("/")
        self.api_headers = {
            "X-N8N-API-KEY": api_key,
            "Content-Type": "application/json",
        }
        self.session_cookie = session_cookie
        self.cookies = {"n8n-auth": session_cookie} if session_cookie else {}

    # -- Public API v1 --

    def list_workflows(self) -> list[dict]:
        r = requests.get(f"{self.host}/api/v1/workflows", headers=self.api_headers)
        r.raise_for_status()
        return r.json().get("data", [])

    def create_workflow(self, workflow_json: dict) -> dict:
        payload = {
            "name": workflow_json.get("name", "unnamed"),
            "nodes": workflow_json.get("nodes", []),
            "connections": workflow_json.get("connections", {}),
            "settings": workflow_json.get("settings", {}),
        }
        r = requests.post(
            f"{self.host}/api/v1/workflows",
            json=payload,
            headers=self.api_headers,
        )
        r.raise_for_status()
        return r.json()

    def get_workflow(self, wf_id: str) -> dict:
        r = requests.get(
            f"{self.host}/api/v1/workflows/{wf_id}",
            headers=self.api_headers,
        )
        r.raise_for_status()
        return r.json()

    def delete_workflow(self, wf_id: str) -> None:
        r = requests.delete(
            f"{self.host}/api/v1/workflows/{wf_id}",
            headers=self.api_headers,
        )
        r.raise_for_status()

    def get_execution(self, exec_id: str) -> dict:
        r = requests.get(
            f"{self.host}/api/v1/executions/{exec_id}?includeData=true",
            headers=self.api_headers,
        )
        r.raise_for_status()
        return r.json()

    def list_executions(self, workflow_id: str | None = None) -> list[dict]:
        url = f"{self.host}/api/v1/executions"
        params = {}
        if workflow_id:
            params["workflowId"] = workflow_id
        r = requests.get(url, headers=self.api_headers, params=params)
        r.raise_for_status()
        return r.json().get("data", [])

    # -- REST API (needs session cookie) --

    def execute_workflow(self, wf_id: str, wf_data: dict) -> str | None:
        """Execute a workflow via the REST API. Returns execution ID or None."""
        if not self.session_cookie:
            logger.warning("No session cookie -- cannot execute workflows via REST API")
            return None

        # Find a trigger node to start from
        trigger_node = self._find_trigger_node(wf_data)

        # Pin empty data on trigger to avoid waiting for webhook
        wf_data_copy = dict(wf_data)
        if trigger_node:
            wf_data_copy["pinData"] = {
                trigger_node: [{"json": {"test": True, "body": {"message": "pisama test input"}}}],
            }
            payload = {
                "workflowData": wf_data_copy,
                "triggerToStartFrom": {"name": trigger_node},
            }
        else:
            # No trigger found -- try destinationNode approach
            first_node = self._find_first_non_sticky_node(wf_data)
            if not first_node:
                logger.warning("No usable start node in workflow %s", wf_id)
                return None
            wf_data_copy["pinData"] = {}
            payload = {
                "workflowData": wf_data_copy,
                "destinationNode": {"nodeName": first_node},
                "runData": {},
            }

        try:
            r = requests.post(
                f"{self.host}/rest/workflows/{wf_id}/run",
                json=payload,
                cookies=self.cookies,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            if r.status_code == 200:
                data = r.json()
                exec_id = data.get("data", {}).get("executionId")
                if exec_id:
                    return str(exec_id)
                # Sometimes returns waitingForWebhook
                if data.get("data", {}).get("waitingForWebhook"):
                    logger.info("Workflow %s waiting for webhook -- skipping", wf_id)
                    return None
            logger.warning(
                "Execute failed for %s: %s %s",
                wf_id, r.status_code, r.text[:200],
            )
        except requests.exceptions.RequestException as e:
            logger.warning("Execute request failed for %s: %s", wf_id, e)
        return None

    def login(self, email: str, password: str) -> str | None:
        """Login and return session cookie."""
        try:
            r = requests.post(
                f"{self.host}/rest/login",
                json={"emailOrLdapLoginId": email, "password": password},
            )
            if r.status_code == 200:
                cookie = r.cookies.get("n8n-auth")
                if cookie:
                    self.session_cookie = cookie
                    self.cookies = {"n8n-auth": cookie}
                    return cookie
            logger.warning("Login failed: %s", r.text[:200])
        except requests.exceptions.RequestException as e:
            logger.warning("Login request failed: %s", e)
        return None

    @staticmethod
    def _find_trigger_node(wf_data: dict) -> str | None:
        for n in wf_data.get("nodes", []):
            t = n.get("type", "").lower()
            if "trigger" in t or "webhook" in t or "cron" in t or "schedule" in t:
                return n["name"]
        return None

    @staticmethod
    def _find_first_non_sticky_node(wf_data: dict) -> str | None:
        for n in wf_data.get("nodes", []):
            if "stickyNote" not in n.get("type", ""):
                return n["name"]
        return None


# ---------------------------------------------------------------------------
# Workflow selection
# ---------------------------------------------------------------------------

def collect_all_workflows() -> list[dict]:
    """Scan fixture directories and return metadata for each valid workflow."""
    results = []
    for d in FIXTURE_DIRS:
        if not d.exists():
            continue
        for f in d.rglob("*.json"):
            try:
                with open(f) as fh:
                    data = json.load(fh)
                if "nodes" not in data or "connections" not in data:
                    continue
                nodes = data.get("nodes", [])
                if len(nodes) < 3:
                    continue

                node_types = [n.get("type", "") for n in nodes]
                conns = data.get("connections", {})
                has_trigger = any(
                    "trigger" in t.lower() or "webhook" in t.lower()
                    for t in node_types
                )
                has_branching = any(
                    "if" in t.lower() or "switch" in t.lower()
                    for t in node_types
                )

                # Check for graph cycles
                has_cycle = _detect_cycle_in_connections(conns)

                results.append({
                    "path": str(f),
                    "name": data.get("name", f.stem),
                    "node_count": len(nodes),
                    "conn_count": len(conns),
                    "has_trigger": has_trigger,
                    "has_branching": has_branching,
                    "has_cycle": has_cycle,
                    "source_dir": d.name,
                })
            except (json.JSONDecodeError, OSError):
                pass
    return results


def _detect_cycle_in_connections(connections: dict) -> bool:
    """Check if the n8n connection graph contains a cycle (DFS)."""
    # Build adjacency list from n8n connections format
    graph: dict[str, set[str]] = defaultdict(set)
    for src_name, src_conns in connections.items():
        if not isinstance(src_conns, dict):
            continue
        for conn_type, target_lists in src_conns.items():
            if not isinstance(target_lists, list):
                continue
            for target_list in target_lists:
                if not isinstance(target_list, list):
                    continue
                for target in target_list:
                    if isinstance(target, dict) and "node" in target:
                        graph[src_name].add(target["node"])

    # DFS cycle detection
    WHITE, GRAY, BLACK = 0, 1, 2
    color = defaultdict(int)

    def dfs(node: str) -> bool:
        color[node] = GRAY
        for neighbor in graph.get(node, set()):
            if color[neighbor] == GRAY:
                return True  # back edge = cycle
            if color[neighbor] == WHITE and dfs(neighbor):
                return True
        color[node] = BLACK
        return False

    all_nodes = set(graph.keys())
    for targets in graph.values():
        all_nodes |= targets

    for node in all_nodes:
        if color[node] == WHITE:
            if dfs(node):
                return True
    return False


def select_diverse_workflows(all_wfs: list[dict], count: int, seed: int) -> list[dict]:
    """Select a diverse set of workflows across complexity categories."""
    rng = random.Random(seed)

    simple = [w for w in all_wfs if w["node_count"] <= 7]
    medium = [w for w in all_wfs if 8 <= w["node_count"] <= 15]
    complex_ = [w for w in all_wfs if w["node_count"] > 15]
    issues = [w for w in all_wfs if w["has_cycle"] or not w["has_trigger"] or w["has_branching"]]

    rng.shuffle(simple)
    rng.shuffle(medium)
    rng.shuffle(complex_)
    rng.shuffle(issues)

    per_cat = max(count // 4, 1)
    selected = []
    seen_paths = set()

    def pick(pool: list, category: str, limit: int):
        for w in pool:
            if len([s for s in selected if s.get("_category") == category]) >= limit:
                break
            if w["path"] not in seen_paths:
                w["_category"] = category
                selected.append(w)
                seen_paths.add(w["path"])

    pick(simple, "simple", per_cat)
    pick(medium, "medium", per_cat)
    pick(complex_, "complex", per_cat)
    pick(issues, "issues", count - len(selected))

    # If we still need more, fill from medium/complex
    remaining = count - len(selected)
    if remaining > 0:
        extras = [w for w in medium + complex_ if w["path"] not in seen_paths]
        rng.shuffle(extras)
        for w in extras[:remaining]:
            w["_category"] = "extra"
            selected.append(w)

    return selected[:count]


# ---------------------------------------------------------------------------
# Independent labeling (NOT using Pisama detectors)
# ---------------------------------------------------------------------------

def label_from_execution(
    workflow_json: dict,
    execution_data: dict | None,
    execution_meta: dict,
) -> list[dict]:
    """Generate independent labels based on n8n's own execution outcome.

    Returns a list of {detection_type, expected_detected, confidence_min,
    confidence_max, description, difficulty, tags} dicts.
    """
    labels = []
    node_count = len(workflow_json.get("nodes", []))
    connections = workflow_json.get("connections", {})
    exec_status = execution_meta.get("status", "unknown")
    exec_finished = execution_meta.get("finished", False)
    started_at = execution_meta.get("startedAt")
    stopped_at = execution_meta.get("stoppedAt")

    # Compute execution duration
    duration_ms = None
    if started_at and stopped_at:
        try:
            t_start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            t_stop = datetime.fromisoformat(stopped_at.replace("Z", "+00:00"))
            duration_ms = (t_stop - t_start).total_seconds() * 1000
        except (ValueError, TypeError):
            pass

    # Parse run data for node-level info
    run_data = {}
    node_errors = []
    nodes_attempted = 0
    if execution_data:
        rd = execution_data.get("resultData", {}).get("runData", {})
        run_data = rd
        nodes_attempted = len(rd)
        for node_name, runs in rd.items():
            for run in runs if isinstance(runs, list) else []:
                if run.get("error"):
                    error_msg = ""
                    err = run["error"]
                    if isinstance(err, dict):
                        error_msg = err.get("message", str(err))
                    else:
                        error_msg = str(err)
                    node_errors.append((node_name, error_msg))

    final_error = None
    if execution_data:
        fe = execution_data.get("resultData", {}).get("error")
        if fe:
            final_error = fe.get("message", str(fe)) if isinstance(fe, dict) else str(fe)

    # ---- n8n_error ----
    is_error = (
        exec_status in ("error", "crashed", "import_failed")
        or bool(node_errors)
        or bool(final_error)
    )
    if is_error:
        error_desc = final_error or (node_errors[0][1] if node_errors else "execution error")
        labels.append({
            "detection_type": DetectionType.N8N_ERROR,
            "expected_detected": True,
            "confidence_min": 0.7,
            "confidence_max": 1.0,
            "description": f"n8n execution error: {error_desc[:120]}",
            "difficulty": "easy" if final_error else "medium",
            "tags": ["n8n_execution_real", "positive", "n8n_error"],
        })
    else:
        labels.append({
            "detection_type": DetectionType.N8N_ERROR,
            "expected_detected": False,
            "confidence_min": 0.0,
            "confidence_max": 0.3,
            "description": f"n8n execution succeeded (status={exec_status})",
            "difficulty": "easy",
            "tags": ["n8n_execution_real", "negative", "n8n_error"],
        })

    # ---- n8n_timeout ----
    # Only label timeout based on actual execution behavior, not import/exec failures
    is_timeout = False
    non_execution_statuses = {"import_failed", "not_executed", "unknown"}
    if exec_status not in non_execution_statuses:
        if duration_ms is not None and duration_ms >= TIMEOUT_DURATION_MS:
            is_timeout = True
        elif exec_status == "waiting":
            is_timeout = True

    labels.append({
        "detection_type": DetectionType.N8N_TIMEOUT,
        "expected_detected": is_timeout,
        "confidence_min": 0.6 if is_timeout else 0.0,
        "confidence_max": 1.0 if is_timeout else 0.3,
        "description": (
            f"n8n execution {'timed out' if is_timeout else 'completed'} "
            f"(duration={duration_ms:.0f}ms)" if duration_ms else
            f"n8n execution status={exec_status}, finished={exec_finished}"
        ),
        "difficulty": "medium" if is_timeout else "easy",
        "tags": ["n8n_execution_real", "positive" if is_timeout else "negative", "n8n_timeout"],
    })

    # ---- n8n_complexity ----
    # Count total connections
    total_connections = 0
    for src, conn_types in connections.items():
        if isinstance(conn_types, dict):
            for ct, target_lists in conn_types.items():
                if isinstance(target_lists, list):
                    for tl in target_lists:
                        if isinstance(tl, list):
                            total_connections += len(tl)

    conn_density = total_connections / max(node_count, 1)
    is_complex = node_count >= COMPLEXITY_NODE_THRESHOLD or conn_density >= COMPLEXITY_CONN_DENSITY_THRESHOLD

    labels.append({
        "detection_type": DetectionType.N8N_COMPLEXITY,
        "expected_detected": is_complex,
        "confidence_min": 0.6 if is_complex else 0.0,
        "confidence_max": 1.0 if is_complex else 0.4,
        "description": (
            f"n8n workflow complexity: {node_count} nodes, {total_connections} connections "
            f"(density={conn_density:.2f})"
        ),
        "difficulty": "easy" if node_count > 20 or node_count < 8 else "medium",
        "tags": ["n8n_execution_real", "positive" if is_complex else "negative", "n8n_complexity"],
    })

    # ---- n8n_cycle ----
    has_cycle = _detect_cycle_in_connections(connections)
    labels.append({
        "detection_type": DetectionType.N8N_CYCLE,
        "expected_detected": has_cycle,
        "confidence_min": 0.8 if has_cycle else 0.0,
        "confidence_max": 1.0 if has_cycle else 0.2,
        "description": (
            f"n8n workflow {'has' if has_cycle else 'has no'} cycle in connection graph"
        ),
        "difficulty": "easy" if not has_cycle else "medium",
        "tags": ["n8n_execution_real", "positive" if has_cycle else "negative", "n8n_cycle"],
    })

    # ---- n8n_schema ----
    # Check for schema issues: nodes with missing types, malformed connections
    schema_issues = []
    for node in workflow_json.get("nodes", []):
        if not node.get("type"):
            schema_issues.append(f"node '{node.get('name', '?')}' missing type")
        if not node.get("id"):
            schema_issues.append(f"node '{node.get('name', '?')}' missing id")

    # Check for connections referencing non-existent nodes
    node_names = {n.get("name") for n in workflow_json.get("nodes", [])}
    for src, conn_types in connections.items():
        if src not in node_names:
            schema_issues.append(f"connection source '{src}' not in nodes")
        if isinstance(conn_types, dict):
            for ct, target_lists in conn_types.items():
                if isinstance(target_lists, list):
                    for tl in target_lists:
                        if isinstance(tl, list):
                            for t in tl:
                                if isinstance(t, dict):
                                    tgt = t.get("node", "")
                                    if tgt and tgt not in node_names:
                                        schema_issues.append(
                                            f"connection target '{tgt}' not in nodes"
                                        )

    has_schema_issue = len(schema_issues) > 0
    labels.append({
        "detection_type": DetectionType.N8N_SCHEMA,
        "expected_detected": has_schema_issue,
        "confidence_min": 0.7 if has_schema_issue else 0.0,
        "confidence_max": 1.0 if has_schema_issue else 0.3,
        "description": (
            f"n8n schema issues: {'; '.join(schema_issues[:3])}"
            if has_schema_issue
            else "n8n workflow schema is valid"
        ),
        "difficulty": "easy" if not has_schema_issue else "medium",
        "tags": ["n8n_execution_real", "positive" if has_schema_issue else "negative", "n8n_schema"],
    })

    # ---- n8n_resource ----
    is_resource_heavy = nodes_attempted >= RESOURCE_NODE_ATTEMPTS_THRESHOLD
    labels.append({
        "detection_type": DetectionType.N8N_RESOURCE,
        "expected_detected": is_resource_heavy,
        "confidence_min": 0.5 if is_resource_heavy else 0.0,
        "confidence_max": 1.0 if is_resource_heavy else 0.4,
        "description": (
            f"n8n execution attempted {nodes_attempted} nodes "
            f"({'resource-heavy' if is_resource_heavy else 'lightweight'})"
        ),
        "difficulty": "medium",
        "tags": ["n8n_execution_real", "positive" if is_resource_heavy else "negative", "n8n_resource"],
    })

    return labels


# ---------------------------------------------------------------------------
# Golden entry creation
# ---------------------------------------------------------------------------

def make_entry_id(det_type: DetectionType, workflow_name: str, detected: bool) -> str:
    """Create a deterministic entry ID."""
    label = "pos" if detected else "neg"
    name_hash = hashlib.sha256(workflow_name.encode()).hexdigest()[:10]
    return f"n8n_exec_{det_type.value}_{label}_{name_hash}"


def create_golden_entries(
    workflow_json: dict,
    execution_data: dict | None,
    execution_meta: dict,
    workflow_path: str,
    n8n_workflow_id: str,
    n8n_execution_id: str | None,
) -> list[GoldenDatasetEntry]:
    """Create golden entries from one workflow's execution results."""
    labels = label_from_execution(workflow_json, execution_data, execution_meta)
    entries = []
    wf_name = workflow_json.get("name", "unknown")

    for label_info in labels:
        det_type = label_info["detection_type"]
        detected = label_info["expected_detected"]
        entry_id = make_entry_id(det_type, wf_name, detected)

        # Build input_data with the workflow JSON (what detectors expect)
        input_data = {"workflow_json": workflow_json}

        # For error detector, also include execution trace
        if det_type == DetectionType.N8N_ERROR and execution_data:
            input_data["execution_data"] = {
                "status": execution_meta.get("status"),
                "finished": execution_meta.get("finished"),
                "startedAt": execution_meta.get("startedAt"),
                "stoppedAt": execution_meta.get("stoppedAt"),
            }
            # Include node-level error info
            rd = execution_data.get("resultData", {}).get("runData", {})
            node_results = {}
            for node_name, runs in rd.items():
                for run in (runs if isinstance(runs, list) else []):
                    node_results[node_name] = {
                        "status": run.get("executionStatus", "unknown"),
                        "error": (
                            run["error"].get("message", "")
                            if isinstance(run.get("error"), dict)
                            else str(run.get("error", ""))
                        ) if run.get("error") else None,
                    }
            input_data["execution_data"]["node_results"] = node_results

        entry = GoldenDatasetEntry(
            id=entry_id,
            detection_type=det_type,
            input_data=input_data,
            expected_detected=detected,
            expected_confidence_min=label_info["confidence_min"],
            expected_confidence_max=label_info["confidence_max"],
            description=label_info["description"],
            source="n8n_execution_real",
            tags=label_info["tags"],
            source_workflow_id=n8n_workflow_id,
            source_trace_id=n8n_execution_id,
            difficulty=label_info["difficulty"],
            split="test",
        )
        entries.append(entry)

    return entries


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    logger.info("=== n8n Execution Capture ===")
    logger.info("Host: %s", args.n8n_host)
    logger.info("Count: %d workflows", args.count)

    # Step 0: Collect all fixture workflows
    logger.info("Scanning fixture directories...")
    all_wfs = collect_all_workflows()
    logger.info("Found %d valid workflow fixtures", len(all_wfs))

    if not all_wfs:
        logger.error("No workflow fixtures found. Check FIXTURE_DIRS.")
        sys.exit(1)

    # Step 1: Select diverse set
    selected = select_diverse_workflows(all_wfs, args.count, args.seed)
    logger.info("Selected %d diverse workflows:", len(selected))
    for w in selected:
        logger.info(
            "  [%s] %s (%d nodes, trigger=%s, branch=%s, cycle=%s)",
            w.get("_category", "?"),
            w["name"],
            w["node_count"],
            w["has_trigger"],
            w["has_branching"],
            w["has_cycle"],
        )

    if args.dry_run:
        logger.info("DRY RUN -- would import and execute %d workflows", len(selected))

        # Still generate labels from workflow JSON alone (no execution data)
        all_entries = []
        for wf_info in selected:
            with open(wf_info["path"]) as f:
                wf_json = json.load(f)
            entries = create_golden_entries(
                workflow_json=wf_json,
                execution_data=None,
                execution_meta={"status": "unknown", "finished": False},
                workflow_path=wf_info["path"],
                n8n_workflow_id="dry-run",
                n8n_execution_id=None,
            )
            all_entries.extend(entries)

        # Summary
        by_type = defaultdict(lambda: {"pos": 0, "neg": 0})
        for e in all_entries:
            key = "pos" if e.expected_detected else "neg"
            by_type[e.detection_type.value][key] += 1

        logger.info("\nDry-run label distribution:")
        for dt, counts in sorted(by_type.items()):
            logger.info("  %s: %d positive, %d negative", dt, counts["pos"], counts["neg"])

        return

    # Step 2: Connect to n8n
    api_key = args.api_key or os.environ.get("N8N_LOCAL_API_KEY", "")
    if not api_key:
        logger.error(
            "No API key provided. Set --api-key or N8N_LOCAL_API_KEY env var.\n"
            "Create one in n8n Settings > API Keys, or see script comments."
        )
        sys.exit(1)

    client = N8nClient(args.n8n_host, api_key, args.session_cookie)

    # Login if no session cookie provided
    if not client.session_cookie:
        logger.info("Logging in to n8n as %s...", args.n8n_email)
        cookie = client.login(args.n8n_email, args.n8n_password)
        if cookie:
            logger.info("Login successful")
        else:
            logger.warning("Login failed -- will import but cannot execute workflows")

    # Verify connectivity
    try:
        existing = client.list_workflows()
        logger.info("Connected to n8n (found %d existing workflows)", len(existing))
    except requests.exceptions.RequestException as e:
        logger.error("Cannot connect to n8n at %s: %s", args.n8n_host, e)
        sys.exit(1)

    # Step 3: Import, execute, capture
    all_entries: list[GoldenDatasetEntry] = []
    imported_ids: list[str] = []

    for i, wf_info in enumerate(selected):
        wf_path = wf_info["path"]
        wf_name = wf_info["name"]
        logger.info("\n--- [%d/%d] %s ---", i + 1, len(selected), wf_name)

        # Load workflow JSON
        try:
            with open(wf_path) as f:
                wf_json = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Cannot load %s: %s", wf_path, e)
            continue

        # Import to n8n
        try:
            created = client.create_workflow(wf_json)
            wf_id = created["id"]
            imported_ids.append(wf_id)
            logger.info("Imported as workflow %s", wf_id)
        except requests.exceptions.RequestException as e:
            logger.warning("Import failed for %s: %s", wf_name, e)
            # Still create entries from workflow JSON alone
            entries = create_golden_entries(
                wf_json, None,
                {"status": "import_failed", "finished": False},
                wf_path, "import_failed", None,
            )
            all_entries.extend(entries)
            continue

        # Get full workflow data (with id set by n8n)
        try:
            wf_data = client.get_workflow(wf_id)
        except requests.exceptions.RequestException:
            wf_data = created

        # Execute
        exec_id = client.execute_workflow(wf_id, wf_data)
        execution_data = None
        execution_meta = {"status": "not_executed", "finished": False}

        if exec_id:
            logger.info("Execution started: %s", exec_id)
            # Wait for completion
            for wait_sec in range(args.exec_timeout):
                time.sleep(1)
                try:
                    exec_result = client.get_execution(exec_id)
                    status = exec_result.get("status", "running")
                    if status in ("success", "error", "crashed", "waiting"):
                        execution_meta = {
                            "status": status,
                            "finished": exec_result.get("finished", False),
                            "startedAt": exec_result.get("startedAt"),
                            "stoppedAt": exec_result.get("stoppedAt"),
                        }
                        execution_data = exec_result.get("data")
                        logger.info(
                            "Execution %s: status=%s, finished=%s",
                            exec_id, status, exec_result.get("finished"),
                        )
                        break
                except requests.exceptions.RequestException:
                    pass
            else:
                logger.info("Execution %s did not complete in %ds", exec_id, args.exec_timeout)
                # Fetch whatever we have
                try:
                    exec_result = client.get_execution(exec_id)
                    execution_meta = {
                        "status": exec_result.get("status", "timeout"),
                        "finished": exec_result.get("finished", False),
                        "startedAt": exec_result.get("startedAt"),
                        "stoppedAt": exec_result.get("stoppedAt"),
                    }
                    execution_data = exec_result.get("data")
                except requests.exceptions.RequestException:
                    pass
        else:
            logger.info("Could not execute workflow %s", wf_id)

        # Create golden entries
        entries = create_golden_entries(
            wf_json, execution_data, execution_meta,
            wf_path, wf_id, exec_id,
        )
        all_entries.extend(entries)
        logger.info("Created %d golden entries", len(entries))

    # Step 4: Cleanup imported workflows if requested
    if args.cleanup and imported_ids:
        logger.info("\nCleaning up %d imported workflows...", len(imported_ids))
        for wf_id in imported_ids:
            try:
                client.delete_workflow(wf_id)
            except requests.exceptions.RequestException:
                pass

    # Step 5: Save results
    logger.info("\n=== Results ===")
    logger.info("Total golden entries: %d", len(all_entries))

    # Summary by type
    by_type = defaultdict(lambda: {"pos": 0, "neg": 0})
    for e in all_entries:
        key = "pos" if e.expected_detected else "neg"
        by_type[e.detection_type.value][key] += 1

    logger.info("Label distribution:")
    for dt, counts in sorted(by_type.items()):
        logger.info("  %s: %d positive, %d negative", dt, counts["pos"], counts["neg"])

    # Save
    output_path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing if present
    existing_entries = {}
    if output_path.exists():
        try:
            with open(output_path) as f:
                existing = json.load(f)
            for e in existing:
                existing_entries[e["id"]] = e
            logger.info("Loaded %d existing entries from %s", len(existing_entries), output_path)
        except (json.JSONDecodeError, OSError):
            pass

    # Merge
    for entry in all_entries:
        existing_entries[entry.id] = asdict(entry)
        # Convert DetectionType enum to string
        existing_entries[entry.id]["detection_type"] = entry.detection_type.value

    merged = list(existing_entries.values())

    with open(output_path, "w") as f:
        json.dump(merged, f, indent=2, default=str)

    logger.info("Saved %d entries to %s", len(merged), output_path)

    # Also merge into golden_dataset_external.json if it exists
    external_path = BACKEND_DIR / "data" / "golden_dataset_external.json"
    if external_path.exists():
        try:
            with open(external_path) as f:
                ext_raw = json.load(f)

            # Handle both wrapped {version, entries} and flat list formats
            if isinstance(ext_raw, dict) and "entries" in ext_raw:
                ext_entries = ext_raw["entries"]
                ext_wrapper = ext_raw  # preserve wrapper
            elif isinstance(ext_raw, list):
                ext_entries = ext_raw
                ext_wrapper = None
            else:
                logger.warning("Unexpected external dataset format: %s", type(ext_raw))
                ext_entries = []
                ext_wrapper = None

            ext_by_id = {e["id"]: e for e in ext_entries if isinstance(e, dict)}

            # Remove old n8n_real entries (tautological) but keep n8n_execution_real
            removed = [
                eid for eid, e in ext_by_id.items()
                if e.get("source") == "n8n_real"
            ]
            for eid in removed:
                del ext_by_id[eid]
            if removed:
                logger.info("Removed %d tautological n8n_real entries", len(removed))

            # Add new entries
            added = 0
            for entry in all_entries:
                entry_dict = asdict(entry)
                entry_dict["detection_type"] = entry.detection_type.value
                if entry.id not in ext_by_id:
                    ext_by_id[entry.id] = entry_dict
                    added += 1

            # Write back in same format
            merged_entries = list(ext_by_id.values())
            if ext_wrapper is not None:
                ext_wrapper["entries"] = merged_entries
                output_data = ext_wrapper
            else:
                output_data = merged_entries

            with open(external_path, "w") as f:
                json.dump(output_data, f, indent=2, default=str)

            logger.info(
                "Merged %d new entries into %s (total: %d)",
                added, external_path, len(ext_by_id),
            )
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Could not merge into %s: %s", external_path, e)


if __name__ == "__main__":
    main()
