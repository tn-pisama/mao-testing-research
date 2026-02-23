"""Golden dataset entries for n8n structural detectors."""

from typing import List

from app.detection.validation import DetectionType
from app.detection_enterprise.golden_dataset import GoldenDatasetEntry


def _n8n_schema_entries() -> List[GoldenDatasetEntry]:
    """10 entries for n8n_schema detector (5 positive, 5 negative)."""
    return [
        # --- POSITIVE: should detect schema mismatch ---
        GoldenDatasetEntry(
            id="n8n_schema_pos_001",
            detection_type=DetectionType.N8N_SCHEMA,
            input_data={"workflow_json": {
                "id": "wf-schema-p1",
                "name": "HTTP to Agent type mismatch",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [250, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Fetch Data", "type": "n8n-nodes-base.httpRequest", "position": [450, 300], "parameters": {"url": "https://api.example.com/data"}, "settings": {}},
                    {"id": "3", "name": "AI Agent", "type": "@n8n/n8n-nodes-langchain.agent", "position": [650, 300], "parameters": {"systemMessage": "Summarize"}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Fetch Data", "type": "main", "index": 0}]]},
                    "Fetch Data": {"main": [[{"node": "AI Agent", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=True,
            expected_confidence_min=0.6,
            expected_confidence_max=0.9,
            description="HTTP node outputs json but AI agent expects text input - type mismatch",
            tags=["n8n", "schema", "type_mismatch", "clear_positive"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_schema_pos_002",
            detection_type=DetectionType.N8N_SCHEMA,
            input_data={"workflow_json": {
                "id": "wf-schema-p2",
                "name": "Agent to Set type mismatch",
                "nodes": [
                    {"id": "1", "name": "Trigger", "type": "n8n-nodes-base.webhook", "position": [250, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Chat Agent", "type": "@n8n/n8n-nodes-langchain.agent", "position": [450, 300], "parameters": {"systemMessage": "Help user"}, "settings": {}},
                    {"id": "3", "name": "Format Output", "type": "n8n-nodes-base.set", "position": [650, 300], "parameters": {"values": {"string": [{"name": "result", "value": "={{ $json.response }}"}]}}, "settings": {}},
                ],
                "connections": {
                    "Trigger": {"main": [[{"node": "Chat Agent", "type": "main", "index": 0}]]},
                    "Chat Agent": {"main": [[{"node": "Format Output", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=True,
            expected_confidence_min=0.6,
            expected_confidence_max=0.9,
            description="Agent outputs text but Set node expects items - type mismatch",
            tags=["n8n", "schema", "type_mismatch"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_schema_pos_003",
            detection_type=DetectionType.N8N_SCHEMA,
            input_data={"workflow_json": {
                "id": "wf-schema-p3",
                "name": "Expression references nonexistent field",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [250, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "LLM Chain", "type": "@n8n/n8n-nodes-langchain.chainLlm", "position": [450, 300], "parameters": {"prompt": "Summarize this"}, "settings": {}},
                    {"id": "3", "name": "Code", "type": "n8n-nodes-base.code", "position": [650, 300], "parameters": {"jsCode": "return [{json: {name: $json.customerName, email: $json.customerEmail}}]"}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "LLM Chain", "type": "main", "index": 0}]]},
                    "LLM Chain": {"main": [[{"node": "Code", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=True,
            expected_confidence_min=0.6,
            expected_confidence_max=0.95,
            description="Code node references $json.customerName from LLM chain that outputs plain text",
            tags=["n8n", "schema", "expression_reference", "medium"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_schema_pos_004",
            detection_type=DetectionType.N8N_SCHEMA,
            input_data={"workflow_json": {
                "id": "wf-schema-p4",
                "name": "Multiple type mismatches in pipeline",
                "nodes": [
                    {"id": "1", "name": "Cron Trigger", "type": "n8n-nodes-base.cron", "position": [200, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "HTTP Request", "type": "n8n-nodes-base.httpRequest", "position": [400, 300], "parameters": {"url": "https://api.example.com/users"}, "settings": {}},
                    {"id": "3", "name": "Summarizer", "type": "@n8n/n8n-nodes-langchain.chainLlm", "position": [600, 300], "parameters": {"prompt": "Summarize users"}, "settings": {}},
                    {"id": "4", "name": "Save to DB", "type": "n8n-nodes-base.postgres", "position": [800, 300], "parameters": {"operation": "insert", "table": "summaries"}, "settings": {}},
                ],
                "connections": {
                    "Cron Trigger": {"main": [[{"node": "HTTP Request", "type": "main", "index": 0}]]},
                    "HTTP Request": {"main": [[{"node": "Summarizer", "type": "main", "index": 0}]]},
                    "Summarizer": {"main": [[{"node": "Save to DB", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=True,
            expected_confidence_min=0.7,
            expected_confidence_max=0.95,
            description="Chain of HTTP(json)->LLM(text)->Postgres(items) with two type mismatches",
            tags=["n8n", "schema", "type_mismatch", "multiple"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_schema_pos_005",
            detection_type=DetectionType.N8N_SCHEMA,
            input_data={"workflow_json": {
                "id": "wf-schema-p5",
                "name": "Orphan expression reference no upstream",
                "nodes": [
                    {"id": "1", "name": "Manual Trigger", "type": "n8n-nodes-base.manualTrigger", "position": [250, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Set Fields", "type": "n8n-nodes-base.set", "position": [450, 300], "parameters": {"values": {"string": [{"name": "greeting", "value": "Hello {{ $json.userName }}"}]}}, "settings": {}},
                ],
                "connections": {
                    "Manual Trigger": {"main": [[{"node": "Set Fields", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=True,
            expected_confidence_min=0.5,
            expected_confidence_max=0.85,
            description="Set node references $json.userName but manual trigger produces no structured data - borderline",
            tags=["n8n", "schema", "expression_reference", "borderline"],
            difficulty="hard",
        ),
        # --- NEGATIVE: should NOT detect schema mismatch ---
        GoldenDatasetEntry(
            id="n8n_schema_neg_001",
            detection_type=DetectionType.N8N_SCHEMA,
            input_data={"workflow_json": {
                "id": "wf-schema-n1",
                "name": "Compatible HTTP to Set pipeline",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [250, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Get Users", "type": "n8n-nodes-base.httpRequest", "position": [450, 300], "parameters": {"url": "https://api.example.com/users"}, "settings": {}},
                    {"id": "3", "name": "Transform", "type": "n8n-nodes-base.code", "position": [650, 300], "parameters": {"jsCode": "return items.map(i => ({json: {name: i.json.name}}))"}, "settings": {}},
                    {"id": "4", "name": "Set Status", "type": "n8n-nodes-base.set", "position": [850, 300], "parameters": {"values": {"string": [{"name": "status", "value": "processed"}]}}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Get Users", "type": "main", "index": 0}]]},
                    "Get Users": {"main": [[{"node": "Transform", "type": "main", "index": 0}]]},
                    "Transform": {"main": [[{"node": "Set Status", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.3,
            description="HTTP->Code->Set pipeline with compatible types (code accepts any, set accepts items)",
            tags=["n8n", "schema", "compatible", "clear_negative"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_schema_neg_002",
            detection_type=DetectionType.N8N_SCHEMA,
            input_data={"workflow_json": {
                "id": "wf-schema-n2",
                "name": "Items-only pipeline",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [250, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Postgres Read", "type": "n8n-nodes-base.postgres", "position": [450, 300], "parameters": {"operation": "select", "table": "orders"}, "settings": {}},
                    {"id": "3", "name": "Filter", "type": "n8n-nodes-base.if", "position": [650, 300], "parameters": {"conditions": {"number": [{"value1": "={{ $json.amount }}", "operation": "larger", "value2": 100}]}}, "settings": {}},
                    {"id": "4", "name": "Send Email", "type": "n8n-nodes-base.set", "position": [850, 300], "parameters": {"values": {"string": [{"name": "to", "value": "admin@example.com"}]}}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Postgres Read", "type": "main", "index": 0}]]},
                    "Postgres Read": {"main": [[{"node": "Filter", "type": "main", "index": 0}]]},
                    "Filter": {"main": [[{"node": "Send Email", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.3,
            description="Postgres->IF->Set all use items type - fully compatible",
            tags=["n8n", "schema", "compatible", "clear_negative"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_schema_neg_003",
            detection_type=DetectionType.N8N_SCHEMA,
            input_data={"workflow_json": {
                "id": "wf-schema-n3",
                "name": "Code node as universal adapter",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [250, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "AI Agent", "type": "@n8n/n8n-nodes-langchain.agent", "position": [450, 300], "parameters": {"systemMessage": "Extract data"}, "settings": {}},
                    {"id": "3", "name": "Parse Response", "type": "n8n-nodes-base.code", "position": [650, 300], "parameters": {"jsCode": "const parsed = JSON.parse($json.output); return [{json: parsed}]"}, "settings": {}},
                    {"id": "4", "name": "Save", "type": "n8n-nodes-base.postgres", "position": [850, 300], "parameters": {"operation": "insert", "table": "results"}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "AI Agent", "type": "main", "index": 0}]]},
                    "AI Agent": {"main": [[{"node": "Parse Response", "type": "main", "index": 0}]]},
                    "Parse Response": {"main": [[{"node": "Save", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.3,
            description="Code node accepts any input type and can output items - acts as adapter between agent and DB",
            tags=["n8n", "schema", "code_adapter", "clear_negative"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_schema_neg_004",
            detection_type=DetectionType.N8N_SCHEMA,
            input_data={"workflow_json": {
                "id": "wf-schema-n4",
                "name": "Merge items from two sources",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [250, 200], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Get Orders", "type": "n8n-nodes-base.postgres", "position": [450, 100], "parameters": {"operation": "select", "table": "orders"}, "settings": {}},
                    {"id": "3", "name": "Get Customers", "type": "n8n-nodes-base.mysql", "position": [450, 300], "parameters": {"operation": "select", "table": "customers"}, "settings": {}},
                    {"id": "4", "name": "Combine", "type": "n8n-nodes-base.merge", "position": [650, 200], "parameters": {"mode": "append"}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Get Orders", "type": "main", "index": 0}], [{"node": "Get Customers", "type": "main", "index": 0}]]},
                    "Get Orders": {"main": [[{"node": "Combine", "type": "main", "index": 0}]]},
                    "Get Customers": {"main": [[{"node": "Combine", "type": "main", "index": 1}]]},
                },
                "settings": {},
            }},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.3,
            description="Two DB nodes (items) merging into Merge node (items) - fully compatible types",
            tags=["n8n", "schema", "merge", "compatible"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_schema_neg_005",
            detection_type=DetectionType.N8N_SCHEMA,
            input_data={"workflow_json": {
                "id": "wf-schema-n5",
                "name": "Simple two-node webhook to code",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [250, 300], "parameters": {"path": "/api/process"}, "settings": {}},
                    {"id": "2", "name": "Process", "type": "n8n-nodes-base.code", "position": [450, 300], "parameters": {"jsCode": "return items;"}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Process", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.2,
            description="Minimal webhook to code node - code accepts any type",
            tags=["n8n", "schema", "minimal", "clear_negative"],
            difficulty="easy",
        ),
    ]


def _n8n_cycle_entries() -> List[GoldenDatasetEntry]:
    """10 entries for n8n_cycle detector (5 positive, 5 negative)."""
    return [
        # --- POSITIVE: should detect graph cycles ---
        GoldenDatasetEntry(
            id="n8n_cycle_pos_001",
            detection_type=DetectionType.N8N_CYCLE,
            input_data={"workflow_json": {
                "id": "wf-cycle-p1",
                "name": "Simple A-B-C-A cycle",
                "nodes": [
                    {"id": "1", "name": "Fetch", "type": "n8n-nodes-base.httpRequest", "position": [250, 300], "parameters": {"url": "https://api.example.com/tasks"}, "settings": {}},
                    {"id": "2", "name": "Process", "type": "n8n-nodes-base.code", "position": [450, 300], "parameters": {"jsCode": "return items;"}, "settings": {}},
                    {"id": "3", "name": "Validate", "type": "n8n-nodes-base.code", "position": [650, 300], "parameters": {"jsCode": "return items;"}, "settings": {}},
                ],
                "connections": {
                    "Fetch": {"main": [[{"node": "Process", "type": "main", "index": 0}]]},
                    "Process": {"main": [[{"node": "Validate", "type": "main", "index": 0}]]},
                    "Validate": {"main": [[{"node": "Fetch", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=True,
            expected_confidence_min=0.7,
            expected_confidence_max=0.95,
            description="Direct 3-node cycle Fetch->Process->Validate->Fetch with no break condition",
            tags=["n8n", "cycle", "graph_cycle", "clear_positive"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_cycle_pos_002",
            detection_type=DetectionType.N8N_CYCLE,
            input_data={"workflow_json": {
                "id": "wf-cycle-p2",
                "name": "Self-loop on retry node",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [250, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Call API", "type": "n8n-nodes-base.httpRequest", "position": [450, 300], "parameters": {"url": "https://api.example.com/submit"}, "settings": {}},
                    {"id": "3", "name": "Done", "type": "n8n-nodes-base.set", "position": [650, 300], "parameters": {}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Call API", "type": "main", "index": 0}]]},
                    "Call API": {"main": [[{"node": "Call API", "type": "main", "index": 0}], [{"node": "Done", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=True,
            expected_confidence_min=0.7,
            expected_confidence_max=0.95,
            description="Self-loop: Call API node connected to itself for retry without break condition",
            tags=["n8n", "cycle", "self_loop", "clear_positive"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_cycle_pos_003",
            detection_type=DetectionType.N8N_CYCLE,
            input_data={"workflow_json": {
                "id": "wf-cycle-p3",
                "name": "Complex cycle with 5 nodes no IF exit",
                "nodes": [
                    {"id": "1", "name": "Start", "type": "n8n-nodes-base.webhook", "position": [100, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Fetch Batch", "type": "n8n-nodes-base.httpRequest", "position": [300, 300], "parameters": {"url": "https://api.example.com/batch"}, "settings": {}},
                    {"id": "3", "name": "Transform", "type": "n8n-nodes-base.code", "position": [500, 300], "parameters": {"jsCode": "return items;"}, "settings": {}},
                    {"id": "4", "name": "Enrich", "type": "n8n-nodes-base.httpRequest", "position": [700, 300], "parameters": {"url": "https://api.example.com/enrich"}, "settings": {}},
                    {"id": "5", "name": "Store", "type": "n8n-nodes-base.postgres", "position": [900, 300], "parameters": {"operation": "insert", "table": "results"}, "settings": {}},
                    {"id": "6", "name": "Queue Next", "type": "n8n-nodes-base.code", "position": [1100, 300], "parameters": {"jsCode": "return items;"}, "settings": {}},
                ],
                "connections": {
                    "Start": {"main": [[{"node": "Fetch Batch", "type": "main", "index": 0}]]},
                    "Fetch Batch": {"main": [[{"node": "Transform", "type": "main", "index": 0}]]},
                    "Transform": {"main": [[{"node": "Enrich", "type": "main", "index": 0}]]},
                    "Enrich": {"main": [[{"node": "Store", "type": "main", "index": 0}]]},
                    "Store": {"main": [[{"node": "Queue Next", "type": "main", "index": 0}]]},
                    "Queue Next": {"main": [[{"node": "Fetch Batch", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=True,
            expected_confidence_min=0.7,
            expected_confidence_max=0.95,
            description="5-node cycle with no IF/Switch to break out - potentially infinite",
            tags=["n8n", "cycle", "graph_cycle", "potentially_infinite"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_cycle_pos_004",
            detection_type=DetectionType.N8N_CYCLE,
            input_data={"workflow_json": {
                "id": "wf-cycle-p4",
                "name": "Two independent cycles",
                "nodes": [
                    {"id": "1", "name": "Trigger", "type": "n8n-nodes-base.webhook", "position": [100, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "A", "type": "n8n-nodes-base.code", "position": [300, 200], "parameters": {"jsCode": "return items;"}, "settings": {}},
                    {"id": "3", "name": "B", "type": "n8n-nodes-base.code", "position": [500, 200], "parameters": {"jsCode": "return items;"}, "settings": {}},
                    {"id": "4", "name": "C", "type": "n8n-nodes-base.code", "position": [300, 400], "parameters": {"jsCode": "return items;"}, "settings": {}},
                    {"id": "5", "name": "D", "type": "n8n-nodes-base.code", "position": [500, 400], "parameters": {"jsCode": "return items;"}, "settings": {}},
                ],
                "connections": {
                    "Trigger": {"main": [[{"node": "A", "type": "main", "index": 0}], [{"node": "C", "type": "main", "index": 0}]]},
                    "A": {"main": [[{"node": "B", "type": "main", "index": 0}]]},
                    "B": {"main": [[{"node": "A", "type": "main", "index": 0}]]},
                    "C": {"main": [[{"node": "D", "type": "main", "index": 0}]]},
                    "D": {"main": [[{"node": "C", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=True,
            expected_confidence_min=0.8,
            expected_confidence_max=0.95,
            description="Two separate 2-node cycles (A<->B and C<->D) - both infinite",
            tags=["n8n", "cycle", "multiple_cycles"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_cycle_pos_005",
            detection_type=DetectionType.N8N_CYCLE,
            input_data={"workflow_json": {
                "id": "wf-cycle-p5",
                "name": "Cycle with IF but no exit branch",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [200, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Fetch Page", "type": "n8n-nodes-base.httpRequest", "position": [400, 300], "parameters": {"url": "https://api.example.com/page"}, "settings": {}},
                    {"id": "3", "name": "Check More", "type": "n8n-nodes-base.if", "position": [600, 300], "parameters": {"conditions": {"boolean": [{"value1": "={{ $json.hasMore }}", "value2": True}]}}, "settings": {}},
                    {"id": "4", "name": "Accumulate", "type": "n8n-nodes-base.code", "position": [800, 300], "parameters": {"jsCode": "return items;"}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Fetch Page", "type": "main", "index": 0}]]},
                    "Fetch Page": {"main": [[{"node": "Check More", "type": "main", "index": 0}]]},
                    "Check More": {"main": [[{"node": "Accumulate", "type": "main", "index": 0}], [{"node": "Accumulate", "type": "main", "index": 0}]]},
                    "Accumulate": {"main": [[{"node": "Fetch Page", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=True,
            expected_confidence_min=0.6,
            expected_confidence_max=0.9,
            description="IF node inside cycle but both branches lead back into the cycle - no exit path",
            tags=["n8n", "cycle", "no_exit", "borderline"],
            difficulty="hard",
        ),
        # --- NEGATIVE: should NOT detect graph cycles ---
        GoldenDatasetEntry(
            id="n8n_cycle_neg_001",
            detection_type=DetectionType.N8N_CYCLE,
            input_data={"workflow_json": {
                "id": "wf-cycle-n1",
                "name": "Linear 4-node pipeline",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [200, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Fetch Data", "type": "n8n-nodes-base.httpRequest", "position": [400, 300], "parameters": {"url": "https://api.example.com/data"}, "settings": {}},
                    {"id": "3", "name": "Transform", "type": "n8n-nodes-base.code", "position": [600, 300], "parameters": {"jsCode": "return items;"}, "settings": {}},
                    {"id": "4", "name": "Respond", "type": "n8n-nodes-base.set", "position": [800, 300], "parameters": {}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Fetch Data", "type": "main", "index": 0}]]},
                    "Fetch Data": {"main": [[{"node": "Transform", "type": "main", "index": 0}]]},
                    "Transform": {"main": [[{"node": "Respond", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.3,
            description="Simple linear pipeline with no back-edges - no cycles possible",
            tags=["n8n", "cycle", "linear", "clear_negative"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_cycle_neg_002",
            detection_type=DetectionType.N8N_CYCLE,
            input_data={"workflow_json": {
                "id": "wf-cycle-n2",
                "name": "Branching workflow with IF",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [200, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Check", "type": "n8n-nodes-base.if", "position": [400, 300], "parameters": {"conditions": {"number": [{"value1": "={{ $json.amount }}", "operation": "larger", "value2": 100}]}}, "settings": {}},
                    {"id": "3", "name": "High Value", "type": "n8n-nodes-base.set", "position": [600, 200], "parameters": {}, "settings": {}},
                    {"id": "4", "name": "Low Value", "type": "n8n-nodes-base.set", "position": [600, 400], "parameters": {}, "settings": {}},
                    {"id": "5", "name": "Log", "type": "n8n-nodes-base.code", "position": [800, 300], "parameters": {"jsCode": "return items;"}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Check", "type": "main", "index": 0}]]},
                    "Check": {"main": [[{"node": "High Value", "type": "main", "index": 0}], [{"node": "Low Value", "type": "main", "index": 0}]]},
                    "High Value": {"main": [[{"node": "Log", "type": "main", "index": 0}]]},
                    "Low Value": {"main": [[{"node": "Log", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.3,
            description="IF branching into two paths that converge - DAG, no cycles",
            tags=["n8n", "cycle", "branching", "clear_negative"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_cycle_neg_003",
            detection_type=DetectionType.N8N_CYCLE,
            input_data={"workflow_json": {
                "id": "wf-cycle-n3",
                "name": "Parallel branches with merge",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [200, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Get Users", "type": "n8n-nodes-base.postgres", "position": [400, 200], "parameters": {"operation": "select"}, "settings": {}},
                    {"id": "3", "name": "Get Orders", "type": "n8n-nodes-base.mysql", "position": [400, 400], "parameters": {"operation": "select"}, "settings": {}},
                    {"id": "4", "name": "Merge", "type": "n8n-nodes-base.merge", "position": [600, 300], "parameters": {"mode": "append"}, "settings": {}},
                    {"id": "5", "name": "Output", "type": "n8n-nodes-base.set", "position": [800, 300], "parameters": {}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Get Users", "type": "main", "index": 0}], [{"node": "Get Orders", "type": "main", "index": 0}]]},
                    "Get Users": {"main": [[{"node": "Merge", "type": "main", "index": 0}]]},
                    "Get Orders": {"main": [[{"node": "Merge", "type": "main", "index": 1}]]},
                    "Merge": {"main": [[{"node": "Output", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.2,
            description="Two parallel branches merging - diamond DAG pattern, no cycles",
            tags=["n8n", "cycle", "parallel_merge", "clear_negative"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_cycle_neg_004",
            detection_type=DetectionType.N8N_CYCLE,
            input_data={"workflow_json": {
                "id": "wf-cycle-n4",
                "name": "Loop with proper IF exit",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [200, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Fetch Page", "type": "n8n-nodes-base.httpRequest", "position": [400, 300], "parameters": {"url": "https://api.example.com/page"}, "settings": {}},
                    {"id": "3", "name": "Has More", "type": "n8n-nodes-base.if", "position": [600, 300], "parameters": {"conditions": {"boolean": [{"value1": "={{ $json.hasMore }}", "value2": True}]}}, "settings": {}},
                    {"id": "4", "name": "Done", "type": "n8n-nodes-base.set", "position": [800, 200], "parameters": {}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Fetch Page", "type": "main", "index": 0}]]},
                    "Fetch Page": {"main": [[{"node": "Has More", "type": "main", "index": 0}]]},
                    "Has More": {"main": [[{"node": "Fetch Page", "type": "main", "index": 0}], [{"node": "Done", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.4,
            description="Cycle exists but IF node has exit branch leading outside - has break condition",
            tags=["n8n", "cycle", "controlled_loop", "has_break"],
            difficulty="hard",
        ),
        GoldenDatasetEntry(
            id="n8n_cycle_neg_005",
            detection_type=DetectionType.N8N_CYCLE,
            input_data={"workflow_json": {
                "id": "wf-cycle-n5",
                "name": "Deep linear chain",
                "nodes": [
                    {"id": "1", "name": "Trigger", "type": "n8n-nodes-base.webhook", "position": [100, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Step 1", "type": "n8n-nodes-base.set", "position": [250, 300], "parameters": {}, "settings": {}},
                    {"id": "3", "name": "Step 2", "type": "n8n-nodes-base.code", "position": [400, 300], "parameters": {"jsCode": "return items;"}, "settings": {}},
                    {"id": "4", "name": "Step 3", "type": "n8n-nodes-base.httpRequest", "position": [550, 300], "parameters": {"url": "https://api.example.com"}, "settings": {}},
                    {"id": "5", "name": "Step 4", "type": "n8n-nodes-base.if", "position": [700, 300], "parameters": {}, "settings": {}},
                    {"id": "6", "name": "Step 5", "type": "n8n-nodes-base.set", "position": [850, 300], "parameters": {}, "settings": {}},
                    {"id": "7", "name": "End", "type": "n8n-nodes-base.code", "position": [1000, 300], "parameters": {"jsCode": "return items;"}, "settings": {}},
                ],
                "connections": {
                    "Trigger": {"main": [[{"node": "Step 1", "type": "main", "index": 0}]]},
                    "Step 1": {"main": [[{"node": "Step 2", "type": "main", "index": 0}]]},
                    "Step 2": {"main": [[{"node": "Step 3", "type": "main", "index": 0}]]},
                    "Step 3": {"main": [[{"node": "Step 4", "type": "main", "index": 0}]]},
                    "Step 4": {"main": [[{"node": "Step 5", "type": "main", "index": 0}]]},
                    "Step 5": {"main": [[{"node": "End", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.2,
            description="Long linear chain of 7 nodes with no back-edges",
            tags=["n8n", "cycle", "linear", "deep_chain"],
            difficulty="easy",
        ),
    ]


def _generate_large_workflow(node_count: int, branching_nodes: int = 0) -> dict:
    """Helper to generate a large workflow with many nodes."""
    nodes = [{"id": "1", "name": "Trigger", "type": "n8n-nodes-base.webhook", "position": [100, 300], "parameters": {}, "settings": {}}]
    connections = {}
    prev_name = "Trigger"
    branch_idx = 0
    for i in range(2, node_count + 1):
        name = f"Node {i}"
        if branch_idx < branching_nodes and i % (node_count // max(branching_nodes, 1)) == 0:
            node_type = "n8n-nodes-base.if"
            branch_idx += 1
        elif i % 5 == 0:
            node_type = "n8n-nodes-base.httpRequest"
        elif i % 3 == 0:
            node_type = "n8n-nodes-base.code"
        else:
            node_type = "n8n-nodes-base.set"
        nodes.append({"id": str(i), "name": name, "type": node_type, "position": [100 + i * 150, 300], "parameters": {}, "settings": {}})
        connections[prev_name] = {"main": [[{"node": name, "type": "main", "index": 0}]]}
        prev_name = name
    return {"id": f"wf-large-{node_count}", "name": f"Large workflow {node_count} nodes", "nodes": nodes, "connections": connections, "settings": {}}


def _n8n_complexity_entries() -> List[GoldenDatasetEntry]:
    """10 entries for n8n_complexity detector (5 positive, 5 negative)."""
    return [
        # --- POSITIVE: should detect complexity issues ---
        GoldenDatasetEntry(
            id="n8n_complexity_pos_001",
            detection_type=DetectionType.N8N_COMPLEXITY,
            input_data={"workflow_json": _generate_large_workflow(55, branching_nodes=3)},
            expected_detected=True,
            expected_confidence_min=0.6,
            expected_confidence_max=0.95,
            description="55-node workflow exceeds 50-node threshold with IF branches",
            tags=["n8n", "complexity", "excessive_nodes", "clear_positive"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_complexity_pos_002",
            detection_type=DetectionType.N8N_COMPLEXITY,
            input_data={"workflow_json": _generate_large_workflow(65, branching_nodes=8)},
            expected_detected=True,
            expected_confidence_min=0.7,
            expected_confidence_max=0.95,
            description="65-node workflow with 8 IF branches - excessive nodes and high branching",
            tags=["n8n", "complexity", "excessive_nodes", "branching"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_complexity_pos_003",
            detection_type=DetectionType.N8N_COMPLEXITY,
            input_data={"workflow_json": {
                "id": "wf-complex-p3",
                "name": "Deeply nested IF branches",
                "nodes": [
                    {"id": "1", "name": "Trigger", "type": "n8n-nodes-base.webhook", "position": [100, 300], "parameters": {}, "settings": {}},
                ] + [
                    {"id": str(i + 2), "name": f"IF Level {i+1}", "type": "n8n-nodes-base.if", "position": [200 + i * 150, 300], "parameters": {"conditions": {"number": [{"value1": "={{ $json.val }}", "operation": "larger", "value2": i}]}}, "settings": {}}
                    for i in range(12)
                ] + [
                    {"id": "15", "name": "End", "type": "n8n-nodes-base.set", "position": [2000, 300], "parameters": {}, "settings": {}},
                ],
                "connections": {
                    "Trigger": {"main": [[{"node": "IF Level 1", "type": "main", "index": 0}]]},
                    **{f"IF Level {i+1}": {"main": [[{"node": f"IF Level {i+2}", "type": "main", "index": 0}]]} for i in range(11)},
                    "IF Level 12": {"main": [[{"node": "End", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=True,
            expected_confidence_min=0.6,
            expected_confidence_max=0.95,
            description="12 levels of nested IF branches exceeding depth threshold of 10",
            tags=["n8n", "complexity", "deep_branching"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_complexity_pos_004",
            detection_type=DetectionType.N8N_COMPLEXITY,
            input_data={"workflow_json": _generate_large_workflow(80, branching_nodes=15)},
            expected_detected=True,
            expected_confidence_min=0.8,
            expected_confidence_max=0.95,
            description="80-node monolith with 15 branching points - all thresholds exceeded",
            tags=["n8n", "complexity", "monolith", "all_thresholds"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_complexity_pos_005",
            detection_type=DetectionType.N8N_COMPLEXITY,
            input_data={"workflow_json": {
                "id": "wf-complex-p5",
                "name": "Multi-concern workflow",
                "nodes": [
                    {"id": "1", "name": "Trigger", "type": "n8n-nodes-base.webhook", "position": [100, 300], "parameters": {}, "settings": {}},
                ] + [
                    {"id": str(i + 2), "name": f"HTTP {i+1}", "type": "n8n-nodes-base.httpRequest", "position": [200 + i * 100, 200], "parameters": {"url": f"https://api{i+1}.example.com"}, "settings": {}}
                    for i in range(10)
                ] + [
                    {"id": str(i + 12), "name": f"DB {i+1}", "type": "n8n-nodes-base.postgres", "position": [200 + i * 100, 400], "parameters": {"operation": "insert"}, "settings": {}}
                    for i in range(10)
                ] + [
                    {"id": str(i + 22), "name": f"AI {i+1}", "type": "@n8n/n8n-nodes-langchain.agent", "position": [200 + i * 100, 600], "parameters": {"systemMessage": "process"}, "settings": {}}
                    for i in range(10)
                ] + [
                    {"id": str(i + 32), "name": f"Email {i+1}", "type": "n8n-nodes-base.set", "position": [200 + i * 100, 800], "parameters": {}, "settings": {}}
                    for i in range(10)
                ] + [
                    {"id": str(i + 42), "name": f"Branch {i+1}", "type": "n8n-nodes-base.if", "position": [200 + i * 100, 1000], "parameters": {}, "settings": {}}
                    for i in range(12)
                ],
                "connections": {
                    "Trigger": {"main": [[{"node": "HTTP 1", "type": "main", "index": 0}]]},
                    **{f"HTTP {i+1}": {"main": [[{"node": f"HTTP {i+2}", "type": "main", "index": 0}]]} for i in range(9)},
                    "HTTP 10": {"main": [[{"node": "DB 1", "type": "main", "index": 0}]]},
                    **{f"DB {i+1}": {"main": [[{"node": f"DB {i+2}", "type": "main", "index": 0}]]} for i in range(9)},
                    "DB 10": {"main": [[{"node": "AI 1", "type": "main", "index": 0}]]},
                    **{f"AI {i+1}": {"main": [[{"node": f"AI {i+2}", "type": "main", "index": 0}]]} for i in range(9)},
                    "AI 10": {"main": [[{"node": "Email 1", "type": "main", "index": 0}]]},
                    **{f"Email {i+1}": {"main": [[{"node": f"Email {i+2}", "type": "main", "index": 0}]]} for i in range(9)},
                    "Email 10": {"main": [[{"node": "Branch 1", "type": "main", "index": 0}]]},
                    **{f"Branch {i+1}": {"main": [[{"node": f"Branch {i+2}", "type": "main", "index": 0}]]} for i in range(11)},
                },
                "settings": {},
            }},
            expected_detected=True,
            expected_confidence_min=0.7,
            expected_confidence_max=0.95,
            description="53-node workflow with HTTP, DB, AI, email, and branching concerns all in one",
            tags=["n8n", "complexity", "multiple_concerns", "monolith"],
            difficulty="hard",
        ),
        # --- NEGATIVE: should NOT detect complexity issues ---
        GoldenDatasetEntry(
            id="n8n_complexity_neg_001",
            detection_type=DetectionType.N8N_COMPLEXITY,
            input_data={"workflow_json": {
                "id": "wf-complex-n1",
                "name": "Simple 5-node workflow",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [200, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Fetch", "type": "n8n-nodes-base.httpRequest", "position": [400, 300], "parameters": {"url": "https://api.example.com"}, "settings": {}},
                    {"id": "3", "name": "Transform", "type": "n8n-nodes-base.code", "position": [600, 300], "parameters": {"jsCode": "return items;"}, "settings": {}},
                    {"id": "4", "name": "Check", "type": "n8n-nodes-base.if", "position": [800, 300], "parameters": {}, "settings": {}},
                    {"id": "5", "name": "Respond", "type": "n8n-nodes-base.set", "position": [1000, 300], "parameters": {}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Fetch", "type": "main", "index": 0}]]},
                    "Fetch": {"main": [[{"node": "Transform", "type": "main", "index": 0}]]},
                    "Transform": {"main": [[{"node": "Check", "type": "main", "index": 0}]]},
                    "Check": {"main": [[{"node": "Respond", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.2,
            description="Simple 5-node linear workflow well within all thresholds",
            tags=["n8n", "complexity", "simple", "clear_negative"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_complexity_neg_002",
            detection_type=DetectionType.N8N_COMPLEXITY,
            input_data={"workflow_json": {
                "id": "wf-complex-n2",
                "name": "Moderate 15-node pipeline",
                "nodes": [
                    {"id": "1", "name": "Trigger", "type": "n8n-nodes-base.webhook", "position": [100, 300], "parameters": {}, "settings": {}},
                ] + [
                    {"id": str(i + 2), "name": f"Step {i+1}", "type": "n8n-nodes-base.code" if i % 2 == 0 else "n8n-nodes-base.set", "position": [200 + i * 120, 300], "parameters": {} if i % 2 != 0 else {"jsCode": "return items;"}, "settings": {}}
                    for i in range(14)
                ],
                "connections": {
                    "Trigger": {"main": [[{"node": "Step 1", "type": "main", "index": 0}]]},
                    **{f"Step {i+1}": {"main": [[{"node": f"Step {i+2}", "type": "main", "index": 0}]]} for i in range(13)},
                },
                "settings": {},
            }},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.2,
            description="15-node workflow with no branching - within all thresholds",
            tags=["n8n", "complexity", "moderate", "clear_negative"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_complexity_neg_003",
            detection_type=DetectionType.N8N_COMPLEXITY,
            input_data={"workflow_json": {
                "id": "wf-complex-n3",
                "name": "Workflow with 3 IF branches",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [100, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Fetch", "type": "n8n-nodes-base.httpRequest", "position": [250, 300], "parameters": {"url": "https://api.example.com"}, "settings": {}},
                    {"id": "3", "name": "Check Type", "type": "n8n-nodes-base.if", "position": [400, 300], "parameters": {}, "settings": {}},
                    {"id": "4", "name": "TypeA", "type": "n8n-nodes-base.code", "position": [550, 200], "parameters": {"jsCode": "return items;"}, "settings": {}},
                    {"id": "5", "name": "TypeB", "type": "n8n-nodes-base.code", "position": [550, 400], "parameters": {"jsCode": "return items;"}, "settings": {}},
                    {"id": "6", "name": "Check Size", "type": "n8n-nodes-base.if", "position": [700, 200], "parameters": {}, "settings": {}},
                    {"id": "7", "name": "Small", "type": "n8n-nodes-base.set", "position": [850, 150], "parameters": {}, "settings": {}},
                    {"id": "8", "name": "Large", "type": "n8n-nodes-base.set", "position": [850, 250], "parameters": {}, "settings": {}},
                    {"id": "9", "name": "Check Valid", "type": "n8n-nodes-base.if", "position": [700, 400], "parameters": {}, "settings": {}},
                    {"id": "10", "name": "Valid", "type": "n8n-nodes-base.set", "position": [850, 350], "parameters": {}, "settings": {}},
                    {"id": "11", "name": "Invalid", "type": "n8n-nodes-base.set", "position": [850, 450], "parameters": {}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Fetch", "type": "main", "index": 0}]]},
                    "Fetch": {"main": [[{"node": "Check Type", "type": "main", "index": 0}]]},
                    "Check Type": {"main": [[{"node": "TypeA", "type": "main", "index": 0}], [{"node": "TypeB", "type": "main", "index": 0}]]},
                    "TypeA": {"main": [[{"node": "Check Size", "type": "main", "index": 0}]]},
                    "TypeB": {"main": [[{"node": "Check Valid", "type": "main", "index": 0}]]},
                    "Check Size": {"main": [[{"node": "Small", "type": "main", "index": 0}], [{"node": "Large", "type": "main", "index": 0}]]},
                    "Check Valid": {"main": [[{"node": "Valid", "type": "main", "index": 0}], [{"node": "Invalid", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.3,
            description="11-node workflow with 3 IF branches - reasonable complexity",
            tags=["n8n", "complexity", "moderate_branching"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_complexity_neg_004",
            detection_type=DetectionType.N8N_COMPLEXITY,
            input_data={"workflow_json": _generate_large_workflow(45, branching_nodes=2)},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.4,
            description="45-node workflow just under the 50-node threshold with minimal branching",
            tags=["n8n", "complexity", "borderline", "under_threshold"],
            difficulty="hard",
        ),
        GoldenDatasetEntry(
            id="n8n_complexity_neg_005",
            detection_type=DetectionType.N8N_COMPLEXITY,
            input_data={"workflow_json": {
                "id": "wf-complex-n5",
                "name": "Minimal 3-node workflow",
                "nodes": [
                    {"id": "1", "name": "Cron", "type": "n8n-nodes-base.cron", "position": [200, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Fetch", "type": "n8n-nodes-base.httpRequest", "position": [400, 300], "parameters": {"url": "https://api.example.com/health"}, "settings": {}},
                    {"id": "3", "name": "Log", "type": "n8n-nodes-base.code", "position": [600, 300], "parameters": {"jsCode": "console.log('ok'); return items;"}, "settings": {}},
                ],
                "connections": {
                    "Cron": {"main": [[{"node": "Fetch", "type": "main", "index": 0}]]},
                    "Fetch": {"main": [[{"node": "Log", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.1,
            description="Minimal 3-node health check workflow",
            tags=["n8n", "complexity", "minimal", "clear_negative"],
            difficulty="easy",
        ),
    ]


def _n8n_error_entries() -> List[GoldenDatasetEntry]:
    """10 entries for n8n_error detector (5 positive, 5 negative)."""
    return [
        # --- POSITIVE: should detect error handling issues ---
        GoldenDatasetEntry(
            id="n8n_error_pos_001",
            detection_type=DetectionType.N8N_ERROR,
            input_data={"workflow_json": {
                "id": "wf-error-p1",
                "name": "AI agent without error handling",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [250, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "AI Agent", "type": "@n8n/n8n-nodes-langchain.agent", "position": [450, 300], "parameters": {"systemMessage": "You are a helpful assistant"}, "settings": {}},
                    {"id": "3", "name": "Respond", "type": "n8n-nodes-base.set", "position": [650, 300], "parameters": {}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "AI Agent", "type": "main", "index": 0}]]},
                    "AI Agent": {"main": [[{"node": "Respond", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=True,
            expected_confidence_min=0.7,
            expected_confidence_max=0.95,
            description="AI agent node without continueOnFail or error trigger - highest risk",
            tags=["n8n", "error", "unprotected_ai", "clear_positive"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_error_pos_002",
            detection_type=DetectionType.N8N_ERROR,
            input_data={"workflow_json": {
                "id": "wf-error-p2",
                "name": "No error trigger in workflow",
                "nodes": [
                    {"id": "1", "name": "Cron", "type": "n8n-nodes-base.cron", "position": [200, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Fetch Users", "type": "n8n-nodes-base.httpRequest", "position": [400, 300], "parameters": {"url": "https://api.example.com/users"}, "settings": {}},
                    {"id": "3", "name": "Process", "type": "n8n-nodes-base.code", "position": [600, 300], "parameters": {"jsCode": "return items;"}, "settings": {}},
                    {"id": "4", "name": "Save", "type": "n8n-nodes-base.postgres", "position": [800, 300], "parameters": {"operation": "insert", "table": "users"}, "settings": {}},
                ],
                "connections": {
                    "Cron": {"main": [[{"node": "Fetch Users", "type": "main", "index": 0}]]},
                    "Fetch Users": {"main": [[{"node": "Process", "type": "main", "index": 0}]]},
                    "Process": {"main": [[{"node": "Save", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=True,
            expected_confidence_min=0.6,
            expected_confidence_max=0.9,
            description="Multi-node workflow with no errorTrigger node and no error handling on any node",
            tags=["n8n", "error", "missing_error_trigger", "no_handling"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_error_pos_003",
            detection_type=DetectionType.N8N_ERROR,
            input_data={"workflow_json": {
                "id": "wf-error-p3",
                "name": "continueOnFail feeding into database",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [200, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Fetch External", "type": "n8n-nodes-base.httpRequest", "position": [400, 300], "parameters": {"url": "https://unreliable-api.example.com"}, "settings": {"continueOnFail": True}},
                    {"id": "3", "name": "Save to DB", "type": "n8n-nodes-base.postgres", "position": [600, 300], "parameters": {"operation": "insert", "table": "records"}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Fetch External", "type": "main", "index": 0}]]},
                    "Fetch External": {"main": [[{"node": "Save to DB", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=True,
            expected_confidence_min=0.7,
            expected_confidence_max=0.95,
            description="HTTP with continueOnFail feeds directly into Postgres - data integrity risk",
            tags=["n8n", "error", "continue_on_fail", "data_integrity"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_error_pos_004",
            detection_type=DetectionType.N8N_ERROR,
            input_data={"workflow_json": {
                "id": "wf-error-p4",
                "name": "Multiple unprotected AI nodes",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [200, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Classifier", "type": "@n8n/n8n-nodes-langchain.agent", "position": [400, 300], "parameters": {"systemMessage": "Classify input"}, "settings": {}},
                    {"id": "3", "name": "Summarizer", "type": "@n8n/n8n-nodes-langchain.chainLlm", "position": [600, 300], "parameters": {"prompt": "Summarize"}, "settings": {}},
                    {"id": "4", "name": "Writer", "type": "@n8n/n8n-nodes-langchain.agent", "position": [800, 300], "parameters": {"systemMessage": "Write response"}, "settings": {}},
                    {"id": "5", "name": "Output", "type": "n8n-nodes-base.set", "position": [1000, 300], "parameters": {}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Classifier", "type": "main", "index": 0}]]},
                    "Classifier": {"main": [[{"node": "Summarizer", "type": "main", "index": 0}]]},
                    "Summarizer": {"main": [[{"node": "Writer", "type": "main", "index": 0}]]},
                    "Writer": {"main": [[{"node": "Output", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=True,
            expected_confidence_min=0.8,
            expected_confidence_max=0.95,
            description="Three AI nodes in sequence all without error handling - severe risk",
            tags=["n8n", "error", "multiple_ai", "no_handling"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_error_pos_005",
            detection_type=DetectionType.N8N_ERROR,
            input_data={"workflow_json": {
                "id": "wf-error-p5",
                "name": "continueOnFail feeding AI node",
                "nodes": [
                    {"id": "1", "name": "Trigger", "type": "n8n-nodes-base.webhook", "position": [200, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Parse Input", "type": "n8n-nodes-base.code", "position": [400, 300], "parameters": {"jsCode": "return items;"}, "settings": {"continueOnFail": True}},
                    {"id": "3", "name": "Agent", "type": "@n8n/n8n-nodes-langchain.agent", "position": [600, 300], "parameters": {"systemMessage": "Process"}, "settings": {}},
                ],
                "connections": {
                    "Trigger": {"main": [[{"node": "Parse Input", "type": "main", "index": 0}]]},
                    "Parse Input": {"main": [[{"node": "Agent", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=True,
            expected_confidence_min=0.7,
            expected_confidence_max=0.95,
            description="Code node with continueOnFail feeds into AI agent - null data could cause hallucination",
            tags=["n8n", "error", "continue_on_fail", "feeds_ai"],
            difficulty="hard",
        ),
        # --- NEGATIVE: should NOT detect error handling issues ---
        GoldenDatasetEntry(
            id="n8n_error_neg_001",
            detection_type=DetectionType.N8N_ERROR,
            input_data={"workflow_json": {
                "id": "wf-error-n1",
                "name": "All nodes with error handling",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [200, 300], "parameters": {}, "settings": {"continueOnFail": True}},
                    {"id": "2", "name": "AI Agent", "type": "@n8n/n8n-nodes-langchain.agent", "position": [400, 300], "parameters": {"systemMessage": "Help user"}, "settings": {"continueOnFail": True}},
                    {"id": "3", "name": "Respond", "type": "n8n-nodes-base.set", "position": [600, 300], "parameters": {}, "settings": {"continueOnFail": True}},
                    {"id": "4", "name": "Error Handler", "type": "n8n-nodes-base.errorTrigger", "position": [400, 500], "parameters": {}, "settings": {}},
                    {"id": "5", "name": "Notify Admin", "type": "n8n-nodes-base.set", "position": [600, 500], "parameters": {}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "AI Agent", "type": "main", "index": 0}]]},
                    "AI Agent": {"main": [[{"node": "Respond", "type": "main", "index": 0}]]},
                    "Error Handler": {"main": [[{"node": "Notify Admin", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.3,
            description="All nodes have continueOnFail and workflow has errorTrigger with notification",
            tags=["n8n", "error", "fully_protected", "clear_negative"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_error_neg_002",
            detection_type=DetectionType.N8N_ERROR,
            input_data={"workflow_json": {
                "id": "wf-error-n2",
                "name": "AI with onError and error trigger",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [200, 300], "parameters": {}, "settings": {"continueOnFail": True}},
                    {"id": "2", "name": "Agent", "type": "@n8n/n8n-nodes-langchain.agent", "position": [400, 300], "parameters": {"systemMessage": "Analyze"}, "settings": {"continueOnFail": True, "onError": "continueRegularOutput"}},
                    {"id": "3", "name": "Format", "type": "n8n-nodes-base.code", "position": [600, 300], "parameters": {"jsCode": "return items;"}, "settings": {"continueOnFail": True}},
                    {"id": "4", "name": "Error Trigger", "type": "n8n-nodes-base.errorTrigger", "position": [400, 500], "parameters": {}, "settings": {}},
                    {"id": "5", "name": "Log Error", "type": "n8n-nodes-base.code", "position": [600, 500], "parameters": {"jsCode": "console.error($json); return items;"}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Agent", "type": "main", "index": 0}]]},
                    "Agent": {"main": [[{"node": "Format", "type": "main", "index": 0}]]},
                    "Error Trigger": {"main": [[{"node": "Log Error", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.3,
            description="AI node with explicit onError setting plus global error trigger",
            tags=["n8n", "error", "protected_ai", "clear_negative"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_error_neg_003",
            detection_type=DetectionType.N8N_ERROR,
            input_data={"workflow_json": {
                "id": "wf-error-n3",
                "name": "Simple non-AI workflow with error trigger",
                "nodes": [
                    {"id": "1", "name": "Cron", "type": "n8n-nodes-base.cron", "position": [200, 300], "parameters": {}, "settings": {"continueOnFail": True}},
                    {"id": "2", "name": "Check Health", "type": "n8n-nodes-base.httpRequest", "position": [400, 300], "parameters": {"url": "https://api.example.com/health"}, "settings": {"continueOnFail": True}},
                    {"id": "3", "name": "Log", "type": "n8n-nodes-base.code", "position": [600, 300], "parameters": {"jsCode": "return items;"}, "settings": {"continueOnFail": True}},
                    {"id": "4", "name": "Error Handler", "type": "n8n-nodes-base.errorTrigger", "position": [400, 500], "parameters": {}, "settings": {}},
                ],
                "connections": {
                    "Cron": {"main": [[{"node": "Check Health", "type": "main", "index": 0}]]},
                    "Check Health": {"main": [[{"node": "Log", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.2,
            description="Health check with all nodes protected and error trigger present",
            tags=["n8n", "error", "health_check", "protected"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_error_neg_004",
            detection_type=DetectionType.N8N_ERROR,
            input_data={"workflow_json": {
                "id": "wf-error-n4",
                "name": "Pipeline with proper error boundaries",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [200, 300], "parameters": {}, "settings": {"continueOnFail": True}},
                    {"id": "2", "name": "Validate", "type": "n8n-nodes-base.if", "position": [400, 300], "parameters": {}, "settings": {"continueOnFail": True}},
                    {"id": "3", "name": "Process", "type": "n8n-nodes-base.code", "position": [600, 300], "parameters": {"jsCode": "return items;"}, "settings": {"continueOnFail": True}},
                    {"id": "4", "name": "Save", "type": "n8n-nodes-base.postgres", "position": [800, 300], "parameters": {"operation": "insert"}, "settings": {"continueOnFail": True}},
                    {"id": "5", "name": "Error Trigger", "type": "n8n-nodes-base.errorTrigger", "position": [400, 500], "parameters": {}, "settings": {}},
                    {"id": "6", "name": "Alert", "type": "n8n-nodes-base.set", "position": [600, 500], "parameters": {}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Validate", "type": "main", "index": 0}]]},
                    "Validate": {"main": [[{"node": "Process", "type": "main", "index": 0}]]},
                    "Process": {"main": [[{"node": "Save", "type": "main", "index": 0}]]},
                    "Error Trigger": {"main": [[{"node": "Alert", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.3,
            description="DB pipeline with all nodes protected and error trigger for alerting",
            tags=["n8n", "error", "db_pipeline", "protected"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_error_neg_005",
            detection_type=DetectionType.N8N_ERROR,
            input_data={"workflow_json": {
                "id": "wf-error-n5",
                "name": "AI chain with full error handling",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [200, 300], "parameters": {}, "settings": {"continueOnFail": True}},
                    {"id": "2", "name": "Classifier", "type": "@n8n/n8n-nodes-langchain.agent", "position": [400, 300], "parameters": {"systemMessage": "Classify"}, "settings": {"continueOnFail": True, "onError": "continueRegularOutput"}},
                    {"id": "3", "name": "Writer", "type": "@n8n/n8n-nodes-langchain.chainLlm", "position": [600, 300], "parameters": {"prompt": "Write"}, "settings": {"continueOnFail": True, "onError": "continueRegularOutput"}},
                    {"id": "4", "name": "Output", "type": "n8n-nodes-base.set", "position": [800, 300], "parameters": {}, "settings": {"continueOnFail": True}},
                    {"id": "5", "name": "Error Trigger", "type": "n8n-nodes-base.errorTrigger", "position": [400, 500], "parameters": {}, "settings": {}},
                    {"id": "6", "name": "Fallback", "type": "n8n-nodes-base.set", "position": [600, 500], "parameters": {}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Classifier", "type": "main", "index": 0}]]},
                    "Classifier": {"main": [[{"node": "Writer", "type": "main", "index": 0}]]},
                    "Writer": {"main": [[{"node": "Output", "type": "main", "index": 0}]]},
                    "Error Trigger": {"main": [[{"node": "Fallback", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.3,
            description="Two AI nodes both with continueOnFail, onError, and global error trigger",
            tags=["n8n", "error", "ai_chain", "fully_protected"],
            difficulty="hard",
        ),
    ]


def _n8n_resource_entries() -> List[GoldenDatasetEntry]:
    """10 entries for n8n_resource detector (5 positive, 5 negative)."""
    return [
        # --- POSITIVE: should detect resource issues ---
        GoldenDatasetEntry(
            id="n8n_resource_pos_001",
            detection_type=DetectionType.N8N_RESOURCE,
            input_data={"workflow_json": {
                "id": "wf-resource-p1",
                "name": "AI node without maxTokens",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [250, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "AI Agent", "type": "@n8n/n8n-nodes-langchain.agent", "position": [450, 300], "parameters": {"systemMessage": "Summarize the full document"}, "settings": {}},
                    {"id": "3", "name": "Output", "type": "n8n-nodes-base.set", "position": [650, 300], "parameters": {}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "AI Agent", "type": "main", "index": 0}]]},
                    "AI Agent": {"main": [[{"node": "Output", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=True,
            expected_confidence_min=0.6,
            expected_confidence_max=0.9,
            description="AI agent without maxTokens - could consume full context window",
            tags=["n8n", "resource", "unbounded_tokens", "clear_positive"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_resource_pos_002",
            detection_type=DetectionType.N8N_RESOURCE,
            input_data={"workflow_json": {
                "id": "wf-resource-p2",
                "name": "SplitInBatches without limits",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [200, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Get All Records", "type": "n8n-nodes-base.httpRequest", "position": [400, 300], "parameters": {"url": "https://api.example.com/records"}, "settings": {}},
                    {"id": "3", "name": "Split", "type": "n8n-nodes-base.splitInBatches", "position": [600, 300], "parameters": {}, "settings": {}},
                    {"id": "4", "name": "Process Each", "type": "n8n-nodes-base.code", "position": [800, 300], "parameters": {"jsCode": "return items;"}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Get All Records", "type": "main", "index": 0}]]},
                    "Get All Records": {"main": [[{"node": "Split", "type": "main", "index": 0}]]},
                    "Split": {"main": [[{"node": "Process Each", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=True,
            expected_confidence_min=0.6,
            expected_confidence_max=0.9,
            description="SplitInBatches without maxIterations or batchSize - could process unlimited items",
            tags=["n8n", "resource", "unbounded_loop", "clear_positive"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_resource_pos_003",
            detection_type=DetectionType.N8N_RESOURCE,
            input_data={"workflow_json": {
                "id": "wf-resource-p3",
                "name": "HTTP request without timeout",
                "nodes": [
                    {"id": "1", "name": "Cron", "type": "n8n-nodes-base.cron", "position": [200, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Fetch Report", "type": "n8n-nodes-base.httpRequest", "position": [400, 300], "parameters": {"url": "https://slow-api.example.com/generate-report", "method": "POST"}, "settings": {}},
                    {"id": "3", "name": "Save", "type": "n8n-nodes-base.postgres", "position": [600, 300], "parameters": {"operation": "insert", "table": "reports"}, "settings": {}},
                ],
                "connections": {
                    "Cron": {"main": [[{"node": "Fetch Report", "type": "main", "index": 0}]]},
                    "Fetch Report": {"main": [[{"node": "Save", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=True,
            expected_confidence_min=0.5,
            expected_confidence_max=0.85,
            description="HTTP request to potentially slow endpoint without timeout setting",
            tags=["n8n", "resource", "http_no_timeout"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_resource_pos_004",
            detection_type=DetectionType.N8N_RESOURCE,
            input_data={"workflow_json": {
                "id": "wf-resource-p4",
                "name": "Sequential AI nodes without data reduction",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [200, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Expand", "type": "@n8n/n8n-nodes-langchain.agent", "position": [400, 300], "parameters": {"systemMessage": "Expand this into a full document"}, "settings": {}},
                    {"id": "3", "name": "Refine", "type": "@n8n/n8n-nodes-langchain.chainLlm", "position": [600, 300], "parameters": {"prompt": "Refine and improve"}, "settings": {}},
                    {"id": "4", "name": "Translate", "type": "@n8n/n8n-nodes-langchain.agent", "position": [800, 300], "parameters": {"systemMessage": "Translate to all languages"}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Expand", "type": "main", "index": 0}]]},
                    "Expand": {"main": [[{"node": "Refine", "type": "main", "index": 0}]]},
                    "Refine": {"main": [[{"node": "Translate", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=True,
            expected_confidence_min=0.7,
            expected_confidence_max=0.95,
            description="Three sequential AI nodes without maxTokens and no data reduction between them",
            tags=["n8n", "resource", "sequential_ai", "token_explosion"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_resource_pos_005",
            detection_type=DetectionType.N8N_RESOURCE,
            input_data={"workflow_json": {
                "id": "wf-resource-p5",
                "name": "Multiple unbounded resources",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [200, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Fetch All", "type": "n8n-nodes-base.httpRequest", "position": [400, 300], "parameters": {"url": "https://api.example.com/all"}, "settings": {}},
                    {"id": "3", "name": "Loop", "type": "n8n-nodes-base.splitInBatches", "position": [600, 300], "parameters": {}, "settings": {}},
                    {"id": "4", "name": "Enrich", "type": "@n8n/n8n-nodes-langchain.agent", "position": [800, 300], "parameters": {"systemMessage": "Enrich each record"}, "settings": {}},
                    {"id": "5", "name": "Store", "type": "n8n-nodes-base.postgres", "position": [1000, 300], "parameters": {"operation": "insert"}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Fetch All", "type": "main", "index": 0}]]},
                    "Fetch All": {"main": [[{"node": "Loop", "type": "main", "index": 0}]]},
                    "Loop": {"main": [[{"node": "Enrich", "type": "main", "index": 0}]]},
                    "Enrich": {"main": [[{"node": "Store", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=True,
            expected_confidence_min=0.7,
            expected_confidence_max=0.95,
            description="HTTP without timeout + unbounded loop + AI without maxTokens - triple resource risk",
            tags=["n8n", "resource", "multiple_issues", "severe"],
            difficulty="hard",
        ),
        # --- NEGATIVE: should NOT detect resource issues ---
        GoldenDatasetEntry(
            id="n8n_resource_neg_001",
            detection_type=DetectionType.N8N_RESOURCE,
            input_data={"workflow_json": {
                "id": "wf-resource-n1",
                "name": "AI with maxTokens set",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [250, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "AI Agent", "type": "@n8n/n8n-nodes-langchain.agent", "position": [450, 300], "parameters": {"systemMessage": "Help user", "maxTokens": 2000}, "settings": {}},
                    {"id": "3", "name": "Output", "type": "n8n-nodes-base.set", "position": [650, 300], "parameters": {}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "AI Agent", "type": "main", "index": 0}]]},
                    "AI Agent": {"main": [[{"node": "Output", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.3,
            description="AI agent with explicit maxTokens limit - properly bounded",
            tags=["n8n", "resource", "bounded_tokens", "clear_negative"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_resource_neg_002",
            detection_type=DetectionType.N8N_RESOURCE,
            input_data={"workflow_json": {
                "id": "wf-resource-n2",
                "name": "Loop with batch size and iteration limit",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [200, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Fetch", "type": "n8n-nodes-base.httpRequest", "position": [400, 300], "parameters": {"url": "https://api.example.com/items", "options": {"timeout": 30000}}, "settings": {}},
                    {"id": "3", "name": "Batch Process", "type": "n8n-nodes-base.splitInBatches", "position": [600, 300], "parameters": {"batchSize": 50, "options": {"maxIterations": 100}}, "settings": {}},
                    {"id": "4", "name": "Transform", "type": "n8n-nodes-base.code", "position": [800, 300], "parameters": {"jsCode": "return items;"}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Fetch", "type": "main", "index": 0}]]},
                    "Fetch": {"main": [[{"node": "Batch Process", "type": "main", "index": 0}]]},
                    "Batch Process": {"main": [[{"node": "Transform", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.3,
            description="SplitInBatches with batchSize and maxIterations, HTTP with timeout",
            tags=["n8n", "resource", "bounded_loop", "clear_negative"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_resource_neg_003",
            detection_type=DetectionType.N8N_RESOURCE,
            input_data={"workflow_json": {
                "id": "wf-resource-n3",
                "name": "HTTP with explicit timeout",
                "nodes": [
                    {"id": "1", "name": "Cron", "type": "n8n-nodes-base.cron", "position": [200, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Health Check", "type": "n8n-nodes-base.httpRequest", "position": [400, 300], "parameters": {"url": "https://api.example.com/health", "options": {"timeout": 10000}}, "settings": {}},
                    {"id": "3", "name": "Log", "type": "n8n-nodes-base.code", "position": [600, 300], "parameters": {"jsCode": "return items;"}, "settings": {}},
                ],
                "connections": {
                    "Cron": {"main": [[{"node": "Health Check", "type": "main", "index": 0}]]},
                    "Health Check": {"main": [[{"node": "Log", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.2,
            description="Simple health check with explicit 10s timeout on HTTP",
            tags=["n8n", "resource", "http_timeout", "clear_negative"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_resource_neg_004",
            detection_type=DetectionType.N8N_RESOURCE,
            input_data={"workflow_json": {
                "id": "wf-resource-n4",
                "name": "AI with options.maxTokens",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [200, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Summarize", "type": "@n8n/n8n-nodes-langchain.chainLlm", "position": [400, 300], "parameters": {"prompt": "Summarize", "options": {"maxTokens": 1000}}, "settings": {}},
                    {"id": "3", "name": "Format", "type": "n8n-nodes-base.set", "position": [600, 300], "parameters": {}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Summarize", "type": "main", "index": 0}]]},
                    "Summarize": {"main": [[{"node": "Format", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.3,
            description="LLM chain with maxTokens in options - properly bounded",
            tags=["n8n", "resource", "options_max_tokens"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_resource_neg_005",
            detection_type=DetectionType.N8N_RESOURCE,
            input_data={"workflow_json": {
                "id": "wf-resource-n5",
                "name": "Non-AI workflow with no resource concerns",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [200, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Set Data", "type": "n8n-nodes-base.set", "position": [400, 300], "parameters": {"values": {"string": [{"name": "status", "value": "ok"}]}}, "settings": {}},
                    {"id": "3", "name": "Check", "type": "n8n-nodes-base.if", "position": [600, 300], "parameters": {}, "settings": {}},
                    {"id": "4", "name": "Done", "type": "n8n-nodes-base.set", "position": [800, 300], "parameters": {}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Set Data", "type": "main", "index": 0}]]},
                    "Set Data": {"main": [[{"node": "Check", "type": "main", "index": 0}]]},
                    "Check": {"main": [[{"node": "Done", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.1,
            description="Workflow with no AI nodes, no loops, no HTTP - no resource risks",
            tags=["n8n", "resource", "no_risk", "clear_negative"],
            difficulty="easy",
        ),
    ]


def _n8n_timeout_entries() -> List[GoldenDatasetEntry]:
    """10 entries for n8n_timeout detector (5 positive, 5 negative)."""
    return [
        # --- POSITIVE: should detect timeout issues ---
        GoldenDatasetEntry(
            id="n8n_timeout_pos_001",
            detection_type=DetectionType.N8N_TIMEOUT,
            input_data={"workflow_json": {
                "id": "wf-timeout-p1",
                "name": "No workflow timeout",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [250, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Process", "type": "n8n-nodes-base.code", "position": [450, 300], "parameters": {"jsCode": "return items;"}, "settings": {}},
                    {"id": "3", "name": "Save", "type": "n8n-nodes-base.postgres", "position": [650, 300], "parameters": {"operation": "insert"}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Process", "type": "main", "index": 0}]]},
                    "Process": {"main": [[{"node": "Save", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=True,
            expected_confidence_min=0.6,
            expected_confidence_max=0.9,
            description="Workflow has no executionTimeout in settings - could run indefinitely",
            tags=["n8n", "timeout", "missing_workflow_timeout", "clear_positive"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_timeout_pos_002",
            detection_type=DetectionType.N8N_TIMEOUT,
            input_data={"workflow_json": {
                "id": "wf-timeout-p2",
                "name": "Webhook without response timeout",
                "nodes": [
                    {"id": "1", "name": "Incoming Hook", "type": "n8n-nodes-base.webhook", "position": [250, 300], "parameters": {"path": "/process", "responseMode": "lastNode"}, "settings": {}},
                    {"id": "2", "name": "Heavy Processing", "type": "n8n-nodes-base.code", "position": [450, 300], "parameters": {"jsCode": "// long computation\nreturn items;"}, "settings": {}},
                    {"id": "3", "name": "Respond", "type": "n8n-nodes-base.set", "position": [650, 300], "parameters": {}, "settings": {}},
                ],
                "connections": {
                    "Incoming Hook": {"main": [[{"node": "Heavy Processing", "type": "main", "index": 0}]]},
                    "Heavy Processing": {"main": [[{"node": "Respond", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=True,
            expected_confidence_min=0.6,
            expected_confidence_max=0.9,
            description="Webhook trigger without responseTimeout - callers may wait indefinitely",
            tags=["n8n", "timeout", "webhook_no_timeout", "clear_positive"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_timeout_pos_003",
            detection_type=DetectionType.N8N_TIMEOUT,
            input_data={"workflow_json": {
                "id": "wf-timeout-p3",
                "name": "AI node without timeout",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [200, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Analyze", "type": "@n8n/n8n-nodes-langchain.agent", "position": [400, 300], "parameters": {"systemMessage": "Analyze deeply"}, "settings": {}},
                    {"id": "3", "name": "Report", "type": "n8n-nodes-base.set", "position": [600, 300], "parameters": {}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Analyze", "type": "main", "index": 0}]]},
                    "Analyze": {"main": [[{"node": "Report", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=True,
            expected_confidence_min=0.6,
            expected_confidence_max=0.9,
            description="AI agent without timeout config - LLM calls can hang on provider outages",
            tags=["n8n", "timeout", "ai_no_timeout"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_timeout_pos_004",
            detection_type=DetectionType.N8N_TIMEOUT,
            input_data={"workflow_json": {
                "id": "wf-timeout-p4",
                "name": "HTTP node without timeout",
                "nodes": [
                    {"id": "1", "name": "Cron", "type": "n8n-nodes-base.cron", "position": [200, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Fetch Slow API", "type": "n8n-nodes-base.httpRequest", "position": [400, 300], "parameters": {"url": "https://slow-service.example.com/report", "method": "GET"}, "settings": {}},
                    {"id": "3", "name": "Parse", "type": "n8n-nodes-base.code", "position": [600, 300], "parameters": {"jsCode": "return items;"}, "settings": {}},
                ],
                "connections": {
                    "Cron": {"main": [[{"node": "Fetch Slow API", "type": "main", "index": 0}]]},
                    "Fetch Slow API": {"main": [[{"node": "Parse", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=True,
            expected_confidence_min=0.5,
            expected_confidence_max=0.85,
            description="HTTP request without timeout - slow endpoint could stall workflow",
            tags=["n8n", "timeout", "http_no_timeout"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_timeout_pos_005",
            detection_type=DetectionType.N8N_TIMEOUT,
            input_data={"workflow_json": {
                "id": "wf-timeout-p5",
                "name": "Merge waitForAll without timeout",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [200, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Fast Path", "type": "n8n-nodes-base.set", "position": [400, 200], "parameters": {}, "settings": {}},
                    {"id": "3", "name": "Slow Path", "type": "n8n-nodes-base.httpRequest", "position": [400, 400], "parameters": {"url": "https://api.example.com/slow"}, "settings": {}},
                    {"id": "4", "name": "Wait For All", "type": "n8n-nodes-base.merge", "position": [600, 300], "parameters": {"mode": "waitForAllBranches"}, "settings": {}},
                    {"id": "5", "name": "Continue", "type": "n8n-nodes-base.code", "position": [800, 300], "parameters": {"jsCode": "return items;"}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Fast Path", "type": "main", "index": 0}], [{"node": "Slow Path", "type": "main", "index": 0}]]},
                    "Fast Path": {"main": [[{"node": "Wait For All", "type": "main", "index": 0}]]},
                    "Slow Path": {"main": [[{"node": "Wait For All", "type": "main", "index": 1}]]},
                    "Wait For All": {"main": [[{"node": "Continue", "type": "main", "index": 0}]]},
                },
                "settings": {},
            }},
            expected_detected=True,
            expected_confidence_min=0.6,
            expected_confidence_max=0.9,
            description="Merge node in waitForAllBranches mode without timeout - stall risk if one branch fails",
            tags=["n8n", "timeout", "merge_stall", "waitForAll"],
            difficulty="hard",
        ),
        # --- NEGATIVE: should NOT detect timeout issues ---
        GoldenDatasetEntry(
            id="n8n_timeout_neg_001",
            detection_type=DetectionType.N8N_TIMEOUT,
            input_data={"workflow_json": {
                "id": "wf-timeout-n1",
                "name": "Fully configured timeouts",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [200, 300], "parameters": {"options": {"responseTimeout": 30000}}, "settings": {}},
                    {"id": "2", "name": "Fetch", "type": "n8n-nodes-base.httpRequest", "position": [400, 300], "parameters": {"url": "https://api.example.com/data", "options": {"timeout": 15000}}, "settings": {}},
                    {"id": "3", "name": "AI", "type": "@n8n/n8n-nodes-langchain.agent", "position": [600, 300], "parameters": {"systemMessage": "Help", "options": {"timeout": 60000}}, "settings": {}},
                    {"id": "4", "name": "Output", "type": "n8n-nodes-base.set", "position": [800, 300], "parameters": {}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Fetch", "type": "main", "index": 0}]]},
                    "Fetch": {"main": [[{"node": "AI", "type": "main", "index": 0}]]},
                    "AI": {"main": [[{"node": "Output", "type": "main", "index": 0}]]},
                },
                "settings": {"executionTimeout": 300},
            }},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.3,
            description="All timeouts configured: workflow, webhook, HTTP, and AI node",
            tags=["n8n", "timeout", "fully_configured", "clear_negative"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_timeout_neg_002",
            detection_type=DetectionType.N8N_TIMEOUT,
            input_data={"workflow_json": {
                "id": "wf-timeout-n2",
                "name": "Workflow with execution timeout",
                "nodes": [
                    {"id": "1", "name": "Cron", "type": "n8n-nodes-base.cron", "position": [200, 300], "parameters": {}, "settings": {}},
                    {"id": "2", "name": "Process", "type": "n8n-nodes-base.code", "position": [400, 300], "parameters": {"jsCode": "return items;"}, "settings": {}},
                    {"id": "3", "name": "Save", "type": "n8n-nodes-base.set", "position": [600, 300], "parameters": {}, "settings": {}},
                ],
                "connections": {
                    "Cron": {"main": [[{"node": "Process", "type": "main", "index": 0}]]},
                    "Process": {"main": [[{"node": "Save", "type": "main", "index": 0}]]},
                },
                "settings": {"executionTimeout": 120},
            }},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.2,
            description="Simple workflow with execution timeout set - no webhook/HTTP/AI risk nodes",
            tags=["n8n", "timeout", "simple_with_timeout", "clear_negative"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_timeout_neg_003",
            detection_type=DetectionType.N8N_TIMEOUT,
            input_data={"workflow_json": {
                "id": "wf-timeout-n3",
                "name": "HTTP with timeout in parameters",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [200, 300], "parameters": {"options": {"responseTimeout": 20000}}, "settings": {}},
                    {"id": "2", "name": "Call API", "type": "n8n-nodes-base.httpRequest", "position": [400, 300], "parameters": {"url": "https://api.example.com", "timeout": 10000}, "settings": {}},
                    {"id": "3", "name": "Respond", "type": "n8n-nodes-base.set", "position": [600, 300], "parameters": {}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Call API", "type": "main", "index": 0}]]},
                    "Call API": {"main": [[{"node": "Respond", "type": "main", "index": 0}]]},
                },
                "settings": {"executionTimeout": 60},
            }},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.2,
            description="HTTP timeout in parameters (not options) - still properly configured",
            tags=["n8n", "timeout", "param_timeout"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_timeout_neg_004",
            detection_type=DetectionType.N8N_TIMEOUT,
            input_data={"workflow_json": {
                "id": "wf-timeout-n4",
                "name": "AI with requestTimeout",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [200, 300], "parameters": {"options": {"responseTimeout": 30000}}, "settings": {}},
                    {"id": "2", "name": "Agent", "type": "@n8n/n8n-nodes-langchain.agent", "position": [400, 300], "parameters": {"systemMessage": "Assist", "requestTimeout": 90000}, "settings": {}},
                    {"id": "3", "name": "Done", "type": "n8n-nodes-base.set", "position": [600, 300], "parameters": {}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Agent", "type": "main", "index": 0}]]},
                    "Agent": {"main": [[{"node": "Done", "type": "main", "index": 0}]]},
                },
                "settings": {"executionTimeout": 300},
            }},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.3,
            description="AI node with requestTimeout parameter - alternative timeout config",
            tags=["n8n", "timeout", "request_timeout", "ai"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_timeout_neg_005",
            detection_type=DetectionType.N8N_TIMEOUT,
            input_data={"workflow_json": {
                "id": "wf-timeout-n5",
                "name": "Merge with timeout configured",
                "nodes": [
                    {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "position": [200, 300], "parameters": {"options": {"responseTimeout": 30000}}, "settings": {}},
                    {"id": "2", "name": "Branch A", "type": "n8n-nodes-base.set", "position": [400, 200], "parameters": {}, "settings": {}},
                    {"id": "3", "name": "Branch B", "type": "n8n-nodes-base.httpRequest", "position": [400, 400], "parameters": {"url": "https://api.example.com", "options": {"timeout": 15000}}, "settings": {}},
                    {"id": "4", "name": "Combine", "type": "n8n-nodes-base.merge", "position": [600, 300], "parameters": {"mode": "waitForAllBranches", "options": {"timeout": 30000}}, "settings": {}},
                    {"id": "5", "name": "End", "type": "n8n-nodes-base.set", "position": [800, 300], "parameters": {}, "settings": {}},
                ],
                "connections": {
                    "Webhook": {"main": [[{"node": "Branch A", "type": "main", "index": 0}], [{"node": "Branch B", "type": "main", "index": 0}]]},
                    "Branch A": {"main": [[{"node": "Combine", "type": "main", "index": 0}]]},
                    "Branch B": {"main": [[{"node": "Combine", "type": "main", "index": 1}]]},
                    "Combine": {"main": [[{"node": "End", "type": "main", "index": 0}]]},
                },
                "settings": {"executionTimeout": 120},
            }},
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.3,
            description="Merge waitForAll with timeout, HTTP with timeout, webhook with timeout, workflow timeout",
            tags=["n8n", "timeout", "merge_with_timeout", "fully_configured"],
            difficulty="hard",
        ),
    ]


def create_n8n_golden_entries() -> List[GoldenDatasetEntry]:
    """Create all 60 n8n golden dataset entries (10 per detector)."""
    entries: List[GoldenDatasetEntry] = []
    entries.extend(_n8n_schema_entries())
    entries.extend(_n8n_cycle_entries())
    entries.extend(_n8n_complexity_entries())
    entries.extend(_n8n_error_entries())
    entries.extend(_n8n_resource_entries())
    entries.extend(_n8n_timeout_entries())
    return entries
