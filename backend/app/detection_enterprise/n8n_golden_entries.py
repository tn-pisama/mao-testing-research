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
    """Create all 90 n8n golden dataset entries (10 per detector)."""
    entries: List[GoldenDatasetEntry] = []
    entries.extend(_n8n_schema_entries())
    entries.extend(_n8n_cycle_entries())
    entries.extend(_n8n_complexity_entries())
    entries.extend(_n8n_error_entries())
    entries.extend(_n8n_resource_entries())
    entries.extend(_n8n_timeout_entries())
    # Core detectors (Task 7)
    entries.extend(_n8n_core_loop_entries())
    entries.extend(_n8n_core_corruption_entries())
    entries.extend(_n8n_core_overflow_entries())
    return entries


# Alias so callers can use either name
get_n8n_golden_entries = create_n8n_golden_entries


# ---------------------------------------------------------------------------
# Core detector golden entries (Task 7)
# ---------------------------------------------------------------------------

def _n8n_core_loop_entries() -> List[GoldenDatasetEntry]:
    """10 entries for infinite_loop / LOOP detection (5 positive, 5 negative).

    Positive cases model n8n execution traces where the same agent_id
    appears 20+ times with near-identical state_delta, or two agents
    ping-pong between each other indefinitely.

    Negative cases model healthy multi-step workflows with batch
    processing, legitimate retries, and multi-agent coordination.
    """
    return [
        # --- POSITIVE: should detect infinite loop ---
        GoldenDatasetEntry(
            id="n8n_core_loop_pos_001",
            detection_type=DetectionType.LOOP,
            input_data={
                "trace": {
                    "trace_id": "trace-loop-p1",
                    "workflow_id": "wf-core-lp1",
                    "spans": [
                        {
                            "span_id": f"span-lp1-{i:03d}",
                            "agent_id": "agent-summarizer",
                            "node_name": "Summarize",
                            "timestamp_ms": 1000 * i,
                            "state_delta": {"summary_length": 142 + (i % 3), "retry": True},
                            "token_count": 200,
                        }
                        for i in range(25)
                    ],
                },
            },
            expected_detected=True,
            expected_confidence_min=0.75,
            expected_confidence_max=0.98,
            description="Same agent_id runs 25 times with near-identical state_delta — clear infinite loop",
            tags=["n8n", "core", "loop", "repeated_agent", "clear_positive"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_core_loop_pos_002",
            detection_type=DetectionType.LOOP,
            input_data={
                "trace": {
                    "trace_id": "trace-loop-p2",
                    "workflow_id": "wf-core-lp2",
                    "spans": [
                        {
                            "span_id": f"span-lp2-{i:03d}",
                            "agent_id": "agent-a" if i % 2 == 0 else "agent-b",
                            "node_name": "Planner" if i % 2 == 0 else "Executor",
                            "timestamp_ms": 500 * i,
                            "state_delta": {"task": "parse_report", "status": "pending" if i % 2 == 0 else "rejected"},
                            "token_count": 180,
                        }
                        for i in range(30)
                    ],
                },
            },
            expected_detected=True,
            expected_confidence_min=0.70,
            expected_confidence_max=0.95,
            description="Ping-pong between Planner (agent-a) and Executor (agent-b) — 30 alternating spans",
            tags=["n8n", "core", "loop", "ping_pong", "clear_positive"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_core_loop_pos_003",
            detection_type=DetectionType.LOOP,
            input_data={
                "trace": {
                    "trace_id": "trace-loop-p3",
                    "workflow_id": "wf-core-lp3",
                    "spans": [
                        {
                            "span_id": f"span-lp3-{i:03d}",
                            "agent_id": "agent-validator",
                            "node_name": "Validate Output",
                            "timestamp_ms": 800 * i,
                            "state_delta": {"valid": False, "error_code": "E_FORMAT", "attempt": i + 1},
                            "token_count": 250,
                        }
                        for i in range(22)
                    ],
                },
            },
            expected_detected=True,
            expected_confidence_min=0.70,
            expected_confidence_max=0.95,
            description="Validator agent fails 22 times with same error code, never breaks out",
            tags=["n8n", "core", "loop", "stuck_validator", "clear_positive"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_core_loop_pos_004",
            detection_type=DetectionType.LOOP,
            input_data={
                "trace": {
                    "trace_id": "trace-loop-p4",
                    "workflow_id": "wf-core-lp4",
                    "spans": [
                        {
                            "span_id": f"span-lp4-{i:03d}",
                            "agent_id": "agent-refiner" if i % 3 != 2 else "agent-critic",
                            "node_name": "Refine" if i % 3 != 2 else "Critique",
                            "timestamp_ms": 600 * i,
                            "state_delta": {"draft_version": (i // 3) + 1, "score": 0.42 + 0.001 * (i % 5)},
                            "token_count": 300,
                        }
                        for i in range(33)
                    ],
                },
            },
            expected_detected=True,
            expected_confidence_min=0.65,
            expected_confidence_max=0.90,
            description="Refiner-Critic loop with negligible score improvement over 33 spans (11 cycles)",
            tags=["n8n", "core", "loop", "refiner_critic", "marginal_improvement"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_core_loop_pos_005",
            detection_type=DetectionType.LOOP,
            input_data={
                "trace": {
                    "trace_id": "trace-loop-p5",
                    "workflow_id": "wf-core-lp5",
                    "spans": (
                        # Normal preamble
                        [
                            {"span_id": "span-lp5-init", "agent_id": "agent-init", "node_name": "Init", "timestamp_ms": 0, "state_delta": {"phase": "setup"}, "token_count": 100},
                        ]
                        +
                        # Looping tail
                        [
                            {
                                "span_id": f"span-lp5-loop-{i:03d}",
                                "agent_id": "agent-fetch",
                                "node_name": "Fetch Data",
                                "timestamp_ms": 1000 + 400 * i,
                                "state_delta": {"rows_fetched": 0, "retry": True},
                                "token_count": 150,
                            }
                            for i in range(24)
                        ]
                    ),
                },
            },
            expected_detected=True,
            expected_confidence_min=0.70,
            expected_confidence_max=0.95,
            description="Normal init then 24 repeated fetch attempts returning 0 rows — loop after setup",
            tags=["n8n", "core", "loop", "fetch_loop", "late_onset"],
            difficulty="hard",
        ),
        # --- NEGATIVE: should NOT detect infinite loop ---
        GoldenDatasetEntry(
            id="n8n_core_loop_neg_001",
            detection_type=DetectionType.LOOP,
            input_data={
                "trace": {
                    "trace_id": "trace-loop-n1",
                    "workflow_id": "wf-core-ln1",
                    "spans": [
                        {"span_id": "span-ln1-001", "agent_id": "agent-ingest", "node_name": "Ingest", "timestamp_ms": 0, "state_delta": {"records": 500}, "token_count": 400},
                        {"span_id": "span-ln1-002", "agent_id": "agent-transform", "node_name": "Transform", "timestamp_ms": 2000, "state_delta": {"records": 500, "format": "parquet"}, "token_count": 350},
                        {"span_id": "span-ln1-003", "agent_id": "agent-validate", "node_name": "Validate", "timestamp_ms": 4000, "state_delta": {"valid_records": 498, "invalid": 2}, "token_count": 300},
                        {"span_id": "span-ln1-004", "agent_id": "agent-load", "node_name": "Load", "timestamp_ms": 6000, "state_delta": {"loaded": 498}, "token_count": 200},
                        {"span_id": "span-ln1-005", "agent_id": "agent-notify", "node_name": "Notify", "timestamp_ms": 7000, "state_delta": {"notified": True}, "token_count": 100},
                    ],
                },
            },
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.25,
            description="Normal ETL pipeline: Ingest->Transform->Validate->Load->Notify, 5 distinct agents",
            tags=["n8n", "core", "loop", "normal_pipeline", "clear_negative"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_core_loop_neg_002",
            detection_type=DetectionType.LOOP,
            input_data={
                "trace": {
                    "trace_id": "trace-loop-n2",
                    "workflow_id": "wf-core-ln2",
                    "spans": [
                        {
                            "span_id": f"span-ln2-{i:03d}",
                            "agent_id": "agent-batch-proc",
                            "node_name": "Process Batch",
                            "timestamp_ms": 3000 * i,
                            "state_delta": {"batch_idx": i, "rows_processed": 1000, "total_processed": 1000 * (i + 1)},
                            "token_count": 250,
                        }
                        for i in range(15)
                    ],
                },
            },
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.30,
            description="Batch processing: same agent runs 15 times but batch_idx increments and total grows",
            tags=["n8n", "core", "loop", "batch_processing", "clear_negative"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_core_loop_neg_003",
            detection_type=DetectionType.LOOP,
            input_data={
                "trace": {
                    "trace_id": "trace-loop-n3",
                    "workflow_id": "wf-core-ln3",
                    "spans": [
                        {"span_id": "span-ln3-001", "agent_id": "agent-api", "node_name": "Call API", "timestamp_ms": 0, "state_delta": {"status": 503}, "token_count": 100},
                        {"span_id": "span-ln3-002", "agent_id": "agent-api", "node_name": "Call API", "timestamp_ms": 2000, "state_delta": {"status": 503}, "token_count": 100},
                        {"span_id": "span-ln3-003", "agent_id": "agent-api", "node_name": "Call API", "timestamp_ms": 6000, "state_delta": {"status": 200, "body": "ok"}, "token_count": 150},
                        {"span_id": "span-ln3-004", "agent_id": "agent-parse", "node_name": "Parse Response", "timestamp_ms": 7000, "state_delta": {"parsed": True}, "token_count": 120},
                    ],
                },
            },
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.20,
            description="Legitimate retry: 2 failures then success (exponential backoff visible in timestamps)",
            tags=["n8n", "core", "loop", "legitimate_retry", "clear_negative"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_core_loop_neg_004",
            detection_type=DetectionType.LOOP,
            input_data={
                "trace": {
                    "trace_id": "trace-loop-n4",
                    "workflow_id": "wf-core-ln4",
                    "spans": [
                        {"span_id": "span-ln4-001", "agent_id": "agent-planner", "node_name": "Plan", "timestamp_ms": 0, "state_delta": {"tasks": ["research", "draft", "review"]}, "token_count": 400},
                        {"span_id": "span-ln4-002", "agent_id": "agent-researcher", "node_name": "Research", "timestamp_ms": 2000, "state_delta": {"findings": 5}, "token_count": 800},
                        {"span_id": "span-ln4-003", "agent_id": "agent-drafter", "node_name": "Draft", "timestamp_ms": 5000, "state_delta": {"word_count": 1200}, "token_count": 1500},
                        {"span_id": "span-ln4-004", "agent_id": "agent-reviewer", "node_name": "Review", "timestamp_ms": 8000, "state_delta": {"score": 0.65, "suggestions": 3}, "token_count": 600},
                        {"span_id": "span-ln4-005", "agent_id": "agent-drafter", "node_name": "Draft", "timestamp_ms": 10000, "state_delta": {"word_count": 1350}, "token_count": 1200},
                        {"span_id": "span-ln4-006", "agent_id": "agent-reviewer", "node_name": "Review", "timestamp_ms": 13000, "state_delta": {"score": 0.88, "suggestions": 0}, "token_count": 500},
                        {"span_id": "span-ln4-007", "agent_id": "agent-publisher", "node_name": "Publish", "timestamp_ms": 14000, "state_delta": {"published": True}, "token_count": 150},
                    ],
                },
            },
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.25,
            description="Multi-agent coordination: Plan->Research->Draft->Review->Draft->Review->Publish with improving scores",
            tags=["n8n", "core", "loop", "multi_agent_coordination", "clear_negative"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_core_loop_neg_005",
            detection_type=DetectionType.LOOP,
            input_data={
                "trace": {
                    "trace_id": "trace-loop-n5",
                    "workflow_id": "wf-core-ln5",
                    "spans": [
                        {
                            "span_id": f"span-ln5-{i:03d}",
                            "agent_id": f"agent-worker-{i % 4}",
                            "node_name": f"Worker {i % 4}",
                            "timestamp_ms": 1500 * i,
                            "state_delta": {"chunk_id": i, "status": "completed", "output_size": 200 + i * 30},
                            "token_count": 300,
                        }
                        for i in range(12)
                    ],
                },
            },
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.25,
            description="Fan-out parallelism: 4 distinct workers processing 12 chunks with growing output_size",
            tags=["n8n", "core", "loop", "fan_out", "clear_negative"],
            difficulty="medium",
        ),
    ]


def _n8n_core_corruption_entries() -> List[GoldenDatasetEntry]:
    """10 entries for state_corruption / CORRUPTION detection (5 positive, 5 negative).

    Positive cases show state deltas with sign flips, extreme value jumps
    (>5x magnitude), field disappearances, and type changes.

    Negative cases show normal state transitions, valid updates, and
    expected value changes.
    """
    return [
        # --- POSITIVE: should detect state corruption ---
        GoldenDatasetEntry(
            id="n8n_core_corrupt_pos_001",
            detection_type=DetectionType.CORRUPTION,
            input_data={
                "trace": {
                    "trace_id": "trace-corrupt-p1",
                    "workflow_id": "wf-core-cp1",
                    "spans": [
                        {"span_id": "span-cp1-001", "agent_id": "agent-balance", "node_name": "Update Balance", "timestamp_ms": 0, "state_delta": {"balance": 1500.00, "currency": "USD"}, "token_count": 100},
                        {"span_id": "span-cp1-002", "agent_id": "agent-balance", "node_name": "Update Balance", "timestamp_ms": 2000, "state_delta": {"balance": 1480.00, "currency": "USD"}, "token_count": 100},
                        {"span_id": "span-cp1-003", "agent_id": "agent-balance", "node_name": "Update Balance", "timestamp_ms": 4000, "state_delta": {"balance": -1480.00, "currency": "USD"}, "token_count": 100},
                    ],
                },
            },
            expected_detected=True,
            expected_confidence_min=0.70,
            expected_confidence_max=0.95,
            description="Sign flip: balance goes from +1480 to -1480 in a single step",
            tags=["n8n", "core", "corruption", "sign_flip", "clear_positive"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_core_corrupt_pos_002",
            detection_type=DetectionType.CORRUPTION,
            input_data={
                "trace": {
                    "trace_id": "trace-corrupt-p2",
                    "workflow_id": "wf-core-cp2",
                    "spans": [
                        {"span_id": "span-cp2-001", "agent_id": "agent-score", "node_name": "Compute Score", "timestamp_ms": 0, "state_delta": {"score": 0.72, "items_evaluated": 50}, "token_count": 150},
                        {"span_id": "span-cp2-002", "agent_id": "agent-score", "node_name": "Compute Score", "timestamp_ms": 3000, "state_delta": {"score": 0.74, "items_evaluated": 55}, "token_count": 150},
                        {"span_id": "span-cp2-003", "agent_id": "agent-score", "node_name": "Compute Score", "timestamp_ms": 6000, "state_delta": {"score": 847.3, "items_evaluated": 56}, "token_count": 150},
                    ],
                },
            },
            expected_detected=True,
            expected_confidence_min=0.75,
            expected_confidence_max=0.98,
            description="Extreme value jump: score leaps from 0.74 to 847.3 (>1000x magnitude change)",
            tags=["n8n", "core", "corruption", "extreme_value", "clear_positive"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_core_corrupt_pos_003",
            detection_type=DetectionType.CORRUPTION,
            input_data={
                "trace": {
                    "trace_id": "trace-corrupt-p3",
                    "workflow_id": "wf-core-cp3",
                    "spans": [
                        {"span_id": "span-cp3-001", "agent_id": "agent-profile", "node_name": "Build Profile", "timestamp_ms": 0, "state_delta": {"user_name": "Alice", "email": "alice@example.com", "role": "admin", "active": True}, "token_count": 200},
                        {"span_id": "span-cp3-002", "agent_id": "agent-profile", "node_name": "Build Profile", "timestamp_ms": 3000, "state_delta": {"user_name": "Alice", "active": True}, "token_count": 120},
                    ],
                },
            },
            expected_detected=True,
            expected_confidence_min=0.60,
            expected_confidence_max=0.90,
            description="Field disappearance: email and role fields vanish between consecutive state deltas",
            tags=["n8n", "core", "corruption", "field_disappearance", "clear_positive"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_core_corrupt_pos_004",
            detection_type=DetectionType.CORRUPTION,
            input_data={
                "trace": {
                    "trace_id": "trace-corrupt-p4",
                    "workflow_id": "wf-core-cp4",
                    "spans": [
                        {"span_id": "span-cp4-001", "agent_id": "agent-config", "node_name": "Load Config", "timestamp_ms": 0, "state_delta": {"max_retries": 3, "timeout_sec": 30, "enabled": True}, "token_count": 80},
                        {"span_id": "span-cp4-002", "agent_id": "agent-config", "node_name": "Load Config", "timestamp_ms": 2000, "state_delta": {"max_retries": "three", "timeout_sec": "thirty", "enabled": "yes"}, "token_count": 80},
                    ],
                },
            },
            expected_detected=True,
            expected_confidence_min=0.70,
            expected_confidence_max=0.95,
            description="Type change: int->str for max_retries and timeout_sec, bool->str for enabled",
            tags=["n8n", "core", "corruption", "type_change", "clear_positive"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_core_corrupt_pos_005",
            detection_type=DetectionType.CORRUPTION,
            input_data={
                "trace": {
                    "trace_id": "trace-corrupt-p5",
                    "workflow_id": "wf-core-cp5",
                    "spans": [
                        {"span_id": "span-cp5-001", "agent_id": "agent-inventory", "node_name": "Check Stock", "timestamp_ms": 0, "state_delta": {"stock_count": 120, "warehouse": "A", "last_audit": "2025-06-01"}, "token_count": 100},
                        {"span_id": "span-cp5-002", "agent_id": "agent-inventory", "node_name": "Check Stock", "timestamp_ms": 2000, "state_delta": {"stock_count": 115, "warehouse": "A", "last_audit": "2025-06-01"}, "token_count": 100},
                        {"span_id": "span-cp5-003", "agent_id": "agent-inventory", "node_name": "Check Stock", "timestamp_ms": 4000, "state_delta": {"stock_count": -780, "warehouse": "A"}, "token_count": 100},
                    ],
                },
            },
            expected_detected=True,
            expected_confidence_min=0.75,
            expected_confidence_max=0.98,
            description="Combined corruption: sign flip (115 -> -780), >5x magnitude change, and field disappearance (last_audit gone)",
            tags=["n8n", "core", "corruption", "combined", "clear_positive"],
            difficulty="hard",
        ),
        # --- NEGATIVE: should NOT detect state corruption ---
        GoldenDatasetEntry(
            id="n8n_core_corrupt_neg_001",
            detection_type=DetectionType.CORRUPTION,
            input_data={
                "trace": {
                    "trace_id": "trace-corrupt-n1",
                    "workflow_id": "wf-core-cn1",
                    "spans": [
                        {"span_id": "span-cn1-001", "agent_id": "agent-counter", "node_name": "Count Items", "timestamp_ms": 0, "state_delta": {"count": 0, "status": "running"}, "token_count": 80},
                        {"span_id": "span-cn1-002", "agent_id": "agent-counter", "node_name": "Count Items", "timestamp_ms": 1000, "state_delta": {"count": 50, "status": "running"}, "token_count": 80},
                        {"span_id": "span-cn1-003", "agent_id": "agent-counter", "node_name": "Count Items", "timestamp_ms": 2000, "state_delta": {"count": 100, "status": "running"}, "token_count": 80},
                        {"span_id": "span-cn1-004", "agent_id": "agent-counter", "node_name": "Count Items", "timestamp_ms": 3000, "state_delta": {"count": 150, "status": "complete"}, "token_count": 80},
                    ],
                },
            },
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.20,
            description="Normal monotonic counter: count increases steadily from 0 to 150",
            tags=["n8n", "core", "corruption", "normal_counter", "clear_negative"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_core_corrupt_neg_002",
            detection_type=DetectionType.CORRUPTION,
            input_data={
                "trace": {
                    "trace_id": "trace-corrupt-n2",
                    "workflow_id": "wf-core-cn2",
                    "spans": [
                        {"span_id": "span-cn2-001", "agent_id": "agent-temp", "node_name": "Read Sensor", "timestamp_ms": 0, "state_delta": {"temperature_c": 22.1, "humidity": 45.0}, "token_count": 60},
                        {"span_id": "span-cn2-002", "agent_id": "agent-temp", "node_name": "Read Sensor", "timestamp_ms": 60000, "state_delta": {"temperature_c": 22.3, "humidity": 44.8}, "token_count": 60},
                        {"span_id": "span-cn2-003", "agent_id": "agent-temp", "node_name": "Read Sensor", "timestamp_ms": 120000, "state_delta": {"temperature_c": 21.9, "humidity": 45.2}, "token_count": 60},
                    ],
                },
            },
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.15,
            description="Normal sensor readings: small fluctuations in temperature and humidity",
            tags=["n8n", "core", "corruption", "sensor_readings", "clear_negative"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_core_corrupt_neg_003",
            detection_type=DetectionType.CORRUPTION,
            input_data={
                "trace": {
                    "trace_id": "trace-corrupt-n3",
                    "workflow_id": "wf-core-cn3",
                    "spans": [
                        {"span_id": "span-cn3-001", "agent_id": "agent-order", "node_name": "Process Order", "timestamp_ms": 0, "state_delta": {"order_id": "ORD-001", "total": 99.99, "status": "pending"}, "token_count": 120},
                        {"span_id": "span-cn3-002", "agent_id": "agent-order", "node_name": "Process Order", "timestamp_ms": 3000, "state_delta": {"order_id": "ORD-001", "total": 99.99, "status": "confirmed", "confirmation_id": "CONF-XY7"}, "token_count": 120},
                        {"span_id": "span-cn3-003", "agent_id": "agent-ship", "node_name": "Ship Order", "timestamp_ms": 6000, "state_delta": {"order_id": "ORD-001", "total": 99.99, "status": "shipped", "tracking": "TRK123456"}, "token_count": 100},
                    ],
                },
            },
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.20,
            description="Normal order lifecycle: pending->confirmed->shipped with new fields added",
            tags=["n8n", "core", "corruption", "normal_lifecycle", "clear_negative"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_core_corrupt_neg_004",
            detection_type=DetectionType.CORRUPTION,
            input_data={
                "trace": {
                    "trace_id": "trace-corrupt-n4",
                    "workflow_id": "wf-core-cn4",
                    "spans": [
                        {"span_id": "span-cn4-001", "agent_id": "agent-resize", "node_name": "Resize Pool", "timestamp_ms": 0, "state_delta": {"pool_size": 5, "active_workers": 5, "pending_tasks": 200}, "token_count": 90},
                        {"span_id": "span-cn4-002", "agent_id": "agent-resize", "node_name": "Resize Pool", "timestamp_ms": 10000, "state_delta": {"pool_size": 20, "active_workers": 20, "pending_tasks": 180}, "token_count": 90},
                        {"span_id": "span-cn4-003", "agent_id": "agent-resize", "node_name": "Resize Pool", "timestamp_ms": 20000, "state_delta": {"pool_size": 20, "active_workers": 18, "pending_tasks": 50}, "token_count": 90},
                    ],
                },
            },
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.25,
            description="Valid scale-up: pool_size 5->20 is a 4x change but expected for autoscaling",
            tags=["n8n", "core", "corruption", "valid_scaleup", "clear_negative"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_core_corrupt_neg_005",
            detection_type=DetectionType.CORRUPTION,
            input_data={
                "trace": {
                    "trace_id": "trace-corrupt-n5",
                    "workflow_id": "wf-core-cn5",
                    "spans": [
                        {"span_id": "span-cn5-001", "agent_id": "agent-ml", "node_name": "Train Model", "timestamp_ms": 0, "state_delta": {"epoch": 1, "loss": 2.45, "accuracy": 0.35}, "token_count": 200},
                        {"span_id": "span-cn5-002", "agent_id": "agent-ml", "node_name": "Train Model", "timestamp_ms": 30000, "state_delta": {"epoch": 2, "loss": 1.12, "accuracy": 0.62}, "token_count": 200},
                        {"span_id": "span-cn5-003", "agent_id": "agent-ml", "node_name": "Train Model", "timestamp_ms": 60000, "state_delta": {"epoch": 3, "loss": 0.54, "accuracy": 0.81}, "token_count": 200},
                        {"span_id": "span-cn5-004", "agent_id": "agent-ml", "node_name": "Train Model", "timestamp_ms": 90000, "state_delta": {"epoch": 4, "loss": 0.31, "accuracy": 0.89}, "token_count": 200},
                    ],
                },
            },
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.20,
            description="Normal ML training: loss decreases, accuracy increases — large relative changes but expected convergence",
            tags=["n8n", "core", "corruption", "ml_training", "clear_negative"],
            difficulty="medium",
        ),
    ]


def _n8n_core_overflow_entries() -> List[GoldenDatasetEntry]:
    """10 entries for context_overflow / OVERFLOW detection (5 positive, 5 negative).

    Positive cases show traces with very high token counts (>100K total)
    and many spans accumulating context without windowing.

    Negative cases show normal token usage (<10K total) with proper
    context management.
    """
    return [
        # --- POSITIVE: should detect context overflow ---
        GoldenDatasetEntry(
            id="n8n_core_overflow_pos_001",
            detection_type=DetectionType.OVERFLOW,
            input_data={
                "trace": {
                    "trace_id": "trace-overflow-p1",
                    "workflow_id": "wf-core-op1",
                    "spans": [
                        {
                            "span_id": f"span-op1-{i:03d}",
                            "agent_id": "agent-summarizer",
                            "node_name": "Summarize Documents",
                            "timestamp_ms": 5000 * i,
                            "state_delta": {"docs_processed": i + 1},
                            "token_count": 12000,
                            "cumulative_tokens": 12000 * (i + 1),
                        }
                        for i in range(12)
                    ],
                },
            },
            expected_detected=True,
            expected_confidence_min=0.75,
            expected_confidence_max=0.98,
            description="144K tokens total across 12 spans at 12K each — far exceeds 100K threshold",
            tags=["n8n", "core", "overflow", "high_token_count", "clear_positive"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_core_overflow_pos_002",
            detection_type=DetectionType.OVERFLOW,
            input_data={
                "trace": {
                    "trace_id": "trace-overflow-p2",
                    "workflow_id": "wf-core-op2",
                    "spans": [
                        {
                            "span_id": f"span-op2-{i:03d}",
                            "agent_id": "agent-chat",
                            "node_name": "Chat Turn",
                            "timestamp_ms": 3000 * i,
                            "state_delta": {"turn": i + 1, "history_tokens": 2500 * (i + 1)},
                            "token_count": 2500,
                            "cumulative_tokens": 2500 * (i + 1),
                        }
                        for i in range(50)
                    ],
                },
            },
            expected_detected=True,
            expected_confidence_min=0.80,
            expected_confidence_max=0.99,
            description="50-turn conversation accumulating 125K tokens with no context windowing",
            tags=["n8n", "core", "overflow", "chat_accumulation", "clear_positive"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_core_overflow_pos_003",
            detection_type=DetectionType.OVERFLOW,
            input_data={
                "trace": {
                    "trace_id": "trace-overflow-p3",
                    "workflow_id": "wf-core-op3",
                    "spans": (
                        [
                            {"span_id": "span-op3-init", "agent_id": "agent-loader", "node_name": "Load Corpus", "timestamp_ms": 0, "state_delta": {"corpus_size_mb": 15}, "token_count": 80000, "cumulative_tokens": 80000},
                        ]
                        +
                        [
                            {
                                "span_id": f"span-op3-qa-{i:03d}",
                                "agent_id": "agent-qa",
                                "node_name": "Answer Question",
                                "timestamp_ms": 10000 + 2000 * i,
                                "state_delta": {"question_idx": i + 1},
                                "token_count": 5000,
                                "cumulative_tokens": 80000 + 5000 * (i + 1),
                            }
                            for i in range(8)
                        ]
                    ),
                },
            },
            expected_detected=True,
            expected_confidence_min=0.70,
            expected_confidence_max=0.95,
            description="80K token corpus load then 8 QA spans adding 5K each — 120K total",
            tags=["n8n", "core", "overflow", "large_corpus", "clear_positive"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_core_overflow_pos_004",
            detection_type=DetectionType.OVERFLOW,
            input_data={
                "trace": {
                    "trace_id": "trace-overflow-p4",
                    "workflow_id": "wf-core-op4",
                    "spans": [
                        {
                            "span_id": f"span-op4-{i:03d}",
                            "agent_id": f"agent-analyst-{i % 5}",
                            "node_name": f"Analyst {i % 5}",
                            "timestamp_ms": 4000 * i,
                            "state_delta": {"report_section": i + 1, "findings": i * 2},
                            "token_count": 8000,
                            "cumulative_tokens": 8000 * (i + 1),
                        }
                        for i in range(18)
                    ],
                },
            },
            expected_detected=True,
            expected_confidence_min=0.75,
            expected_confidence_max=0.98,
            description="5 analysts contributing 18 spans at 8K each = 144K tokens, shared context grows unbounded",
            tags=["n8n", "core", "overflow", "multi_agent_overflow", "clear_positive"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_core_overflow_pos_005",
            detection_type=DetectionType.OVERFLOW,
            input_data={
                "trace": {
                    "trace_id": "trace-overflow-p5",
                    "workflow_id": "wf-core-op5",
                    "spans": [
                        {
                            "span_id": f"span-op5-{i:03d}",
                            "agent_id": "agent-code-review",
                            "node_name": "Review File",
                            "timestamp_ms": 6000 * i,
                            "state_delta": {"file_idx": i + 1, "issues_found": i * 3, "context_window_pct": min(100, 15 + i * 7)},
                            "token_count": 3000 + i * 1500,
                            "cumulative_tokens": sum(3000 + j * 1500 for j in range(i + 1)),
                        }
                        for i in range(15)
                    ],
                },
            },
            expected_detected=True,
            expected_confidence_min=0.70,
            expected_confidence_max=0.95,
            description="Code review with growing file sizes: 15 files, tokens per span increase, total ~210K",
            tags=["n8n", "core", "overflow", "growing_context", "clear_positive"],
            difficulty="hard",
        ),
        # --- NEGATIVE: should NOT detect context overflow ---
        GoldenDatasetEntry(
            id="n8n_core_overflow_neg_001",
            detection_type=DetectionType.OVERFLOW,
            input_data={
                "trace": {
                    "trace_id": "trace-overflow-n1",
                    "workflow_id": "wf-core-on1",
                    "spans": [
                        {"span_id": "span-on1-001", "agent_id": "agent-greet", "node_name": "Greeting", "timestamp_ms": 0, "state_delta": {"step": "greet"}, "token_count": 200, "cumulative_tokens": 200},
                        {"span_id": "span-on1-002", "agent_id": "agent-classify", "node_name": "Classify Intent", "timestamp_ms": 1000, "state_delta": {"intent": "order_status"}, "token_count": 350, "cumulative_tokens": 550},
                        {"span_id": "span-on1-003", "agent_id": "agent-lookup", "node_name": "Lookup Order", "timestamp_ms": 2000, "state_delta": {"order_id": "ORD-999"}, "token_count": 400, "cumulative_tokens": 950},
                        {"span_id": "span-on1-004", "agent_id": "agent-respond", "node_name": "Respond", "timestamp_ms": 3000, "state_delta": {"response_sent": True}, "token_count": 300, "cumulative_tokens": 1250},
                    ],
                },
            },
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.15,
            description="Simple chatbot flow: 4 spans, 1.25K tokens total — well under threshold",
            tags=["n8n", "core", "overflow", "simple_flow", "clear_negative"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_core_overflow_neg_002",
            detection_type=DetectionType.OVERFLOW,
            input_data={
                "trace": {
                    "trace_id": "trace-overflow-n2",
                    "workflow_id": "wf-core-on2",
                    "spans": [
                        {
                            "span_id": f"span-on2-{i:03d}",
                            "agent_id": "agent-chat-windowed",
                            "node_name": "Chat Turn",
                            "timestamp_ms": 3000 * i,
                            "state_delta": {"turn": i + 1, "window_start": max(0, i - 4)},
                            "token_count": 800,
                            "cumulative_tokens": min(4000, 800 * (i + 1)),
                        }
                        for i in range(12)
                    ],
                },
            },
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.25,
            description="12-turn chat with sliding window of 5 turns — cumulative stays at 4K",
            tags=["n8n", "core", "overflow", "windowed_chat", "clear_negative"],
            difficulty="medium",
        ),
        GoldenDatasetEntry(
            id="n8n_core_overflow_neg_003",
            detection_type=DetectionType.OVERFLOW,
            input_data={
                "trace": {
                    "trace_id": "trace-overflow-n3",
                    "workflow_id": "wf-core-on3",
                    "spans": [
                        {"span_id": "span-on3-001", "agent_id": "agent-ingest", "node_name": "Ingest Data", "timestamp_ms": 0, "state_delta": {"rows": 10000}, "token_count": 1500, "cumulative_tokens": 1500},
                        {"span_id": "span-on3-002", "agent_id": "agent-transform", "node_name": "Transform", "timestamp_ms": 5000, "state_delta": {"rows": 10000, "format": "normalized"}, "token_count": 2000, "cumulative_tokens": 3500},
                        {"span_id": "span-on3-003", "agent_id": "agent-analyze", "node_name": "Analyze", "timestamp_ms": 10000, "state_delta": {"insights": 12}, "token_count": 3000, "cumulative_tokens": 6500},
                        {"span_id": "span-on3-004", "agent_id": "agent-report", "node_name": "Generate Report", "timestamp_ms": 15000, "state_delta": {"report_pages": 5}, "token_count": 2500, "cumulative_tokens": 9000},
                    ],
                },
            },
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.20,
            description="Data pipeline: 4 stages totaling 9K tokens — normal usage",
            tags=["n8n", "core", "overflow", "normal_pipeline", "clear_negative"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_core_overflow_neg_004",
            detection_type=DetectionType.OVERFLOW,
            input_data={
                "trace": {
                    "trace_id": "trace-overflow-n4",
                    "workflow_id": "wf-core-on4",
                    "spans": [
                        {
                            "span_id": f"span-on4-{i:03d}",
                            "agent_id": f"agent-worker-{i}",
                            "node_name": f"Worker {i}",
                            "timestamp_ms": 1000 * i,
                            "state_delta": {"chunk": i, "result": f"summary_{i}"},
                            "token_count": 900,
                            "cumulative_tokens": 900 * (i + 1),
                        }
                        for i in range(8)
                    ],
                },
            },
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.20,
            description="8 independent workers processing chunks — 7.2K total tokens, each isolated",
            tags=["n8n", "core", "overflow", "isolated_workers", "clear_negative"],
            difficulty="easy",
        ),
        GoldenDatasetEntry(
            id="n8n_core_overflow_neg_005",
            detection_type=DetectionType.OVERFLOW,
            input_data={
                "trace": {
                    "trace_id": "trace-overflow-n5",
                    "workflow_id": "wf-core-on5",
                    "spans": [
                        {"span_id": "span-on5-001", "agent_id": "agent-rag", "node_name": "Retrieve", "timestamp_ms": 0, "state_delta": {"chunks_retrieved": 5}, "token_count": 4000, "cumulative_tokens": 4000},
                        {"span_id": "span-on5-002", "agent_id": "agent-rag", "node_name": "Generate Answer", "timestamp_ms": 3000, "state_delta": {"answer_length": 250}, "token_count": 2500, "cumulative_tokens": 6500},
                        {"span_id": "span-on5-003", "agent_id": "agent-rag", "node_name": "Retrieve", "timestamp_ms": 6000, "state_delta": {"chunks_retrieved": 3}, "token_count": 2400, "cumulative_tokens": 8900},
                        {"span_id": "span-on5-004", "agent_id": "agent-rag", "node_name": "Generate Answer", "timestamp_ms": 9000, "state_delta": {"answer_length": 180}, "token_count": 1100, "cumulative_tokens": 10000},
                    ],
                },
            },
            expected_detected=False,
            expected_confidence_min=0.0,
            expected_confidence_max=0.30,
            description="RAG pipeline: 2 retrieve-generate cycles, 10K tokens total — borderline but within bounds",
            tags=["n8n", "core", "overflow", "rag_pipeline", "clear_negative"],
            difficulty="hard",
        ),
    ]
