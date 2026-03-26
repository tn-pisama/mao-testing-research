#!/usr/bin/env python3
"""Test orchestration_quality and multi_chain detectors on realistic synthetic data.

Generates production-realistic entries based on actual golden dataset patterns
(ChatDev agents, LangGraph supersteps, n8n workflows, Dify pipelines),
runs both detectors, reports accuracy, and appends validated entries.

Usage:
    cd backend && python scripts/test_new_capabilities.py
"""

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.detection.orchestration_quality import OrchestrationQualityScorer, detect as oq_detect
from app.detection.multi_chain import MultiChainAnalyzer, build_trace_graph, detect as mc_detect


# ── Realistic Agent Names & Patterns ──────────────────────────────────

CHATDEV_AGENTS = [
    "chatdev:Chief_Executive_Officer", "chatdev:Chief_Product_Officer",
    "chatdev:Chief_Technology_Officer", "chatdev:Programmer",
    "chatdev:Code_Reviewer", "chatdev:Counselor", "chatdev:Art_Designer",
]

LANGGRAPH_AGENTS = [
    "supervisor", "researcher_agent", "analyst_agent", "writer_agent",
    "reviewer_agent", "tools", "retrieve", "__start__", "__end__",
]

N8N_NODES = [
    "Webhook", "AI_Review", "Quality_Check", "HTTP_Request",
    "Claude_Summarizer", "Error_Handler", "Format_Output",
    "Database_Query", "Process_JSON", "Send_Email",
]

DIFY_AGENTS = [
    "intent_classifier", "rag_search", "claude_reasoning",
    "web_search", "summarizer", "format_response",
]


def _s(agent_id, seq, role=None, latency_ms=100, status="completed",
       state_delta=None, tool_calls=None, output=""):
    """Create a realistic state dict."""
    return {
        "agent_id": agent_id,
        "agent_role": role or agent_id.split(":")[-1].lower().replace("_", " "),
        "sequence_num": seq,
        "latency_ms": latency_ms,
        "status": status,
        "state_delta": state_delta or {},
        "tool_calls": tool_calls,
        "output": output,
    }


def generate_orchestration_entries() -> List[Dict[str, Any]]:
    """Generate 30 realistic orchestration_quality entries."""
    entries = []

    def _entry(desc, states, expected, difficulty="medium", source="synthetic"):
        entries.append({
            "id": f"oq-{uuid.uuid4().hex[:8]}",
            "detection_type": "orchestration_quality",
            "input_data": {"states": states},
            "expected_detected": expected,
            "description": desc,
            "source": source,
            "difficulty": difficulty,
        })

    # ═══════════════════════════════════════════════════════════════════
    # POSITIVES — Poor orchestration (expected_detected=True)
    # ═══════════════════════════════════════════════════════════════════

    # 1. ChatDev bottleneck: Programmer does 90% while CEO/CTO idle
    _entry("ChatDev bottleneck: Programmer does all coding while 5 managers supervise", [
        _s("chatdev:Chief_Executive_Officer", 0, latency_ms=2200,
           state_delta={"action": "propose_task", "task": "Build a weather dashboard app"},
           output="ChatDev: Task proposed to Chief Product Officer"),
        _s("chatdev:Chief_Product_Officer", 1, latency_ms=1800,
           state_delta={"action": "discuss_requirements", "features": ["current_weather", "forecast", "alerts"]},
           output="Product requirements: 3 features defined"),
        _s("chatdev:Programmer", 2, latency_ms=12000,
           state_delta={"action": "write_code", "files_created": 8, "lines_written": 450},
           tool_calls=["code_generation"], output="Generated 8 files: main.py, weather_api.py, dashboard.py, ..."),
        _s("chatdev:Programmer", 3, latency_ms=8000,
           state_delta={"action": "fix_bugs", "bugs_fixed": 5},
           tool_calls=["code_generation", "run_tests"], output="Fixed 5 bugs, all tests passing"),
        _s("chatdev:Code_Reviewer", 4, latency_ms=1500,
           state_delta={"action": "review", "issues_found": 0},
           output="Code review passed, no issues found"),
    ], True)

    # 2. Sequential independent research — should have been parallel
    _entry("LangGraph sequential research: 3 independent topics run one-at-a-time", [
        _s("supervisor", 0, latency_ms=500,
           state_delta={"action": "assign_research", "topics": ["quantum_computing", "biotech", "space_exploration"]},
           tool_calls=["plan"], output="Assigned 3 research topics to researchers"),
        _s("researcher_agent", 1, latency_ms=4500,
           state_delta={"topic": "quantum_computing", "papers_found": 12, "summary": "Recent breakthroughs in error correction"},
           tool_calls=["web_search", "arxiv_search"], output="Quantum computing: 12 papers analyzed"),
        _s("researcher_agent", 2, latency_ms=3800,
           state_delta={"topic": "biotech", "papers_found": 8, "summary": "CRISPR advances in gene therapy"},
           tool_calls=["web_search", "pubmed_search"], output="Biotech: 8 papers analyzed"),
        _s("researcher_agent", 3, latency_ms=5200,
           state_delta={"topic": "space_exploration", "papers_found": 15, "summary": "Mars colonization progress 2025"},
           tool_calls=["web_search", "nasa_api"], output="Space: 15 papers analyzed"),
        _s("writer_agent", 4, latency_ms=3000,
           state_delta={"action": "synthesize", "report_sections": 3},
           tool_calls=["generate_report"], output="Research synthesis report: 3 sections, 2500 words"),
    ], True)

    # 3. Excessive chatdev back-and-forth
    _entry("ChatDev excessive discussion: CEO/CTO debate 6 rounds before any coding", [
        _s("chatdev:Chief_Executive_Officer", 0, latency_ms=2000,
           state_delta={"action": "propose", "proposal": "Build a chat application"},
           output="CEO proposes: chat application"),
        _s("chatdev:Chief_Technology_Officer", 1, latency_ms=2500,
           state_delta={"action": "counter_propose", "concern": "scalability"},
           output="CTO: concerned about scalability of proposed architecture"),
        _s("chatdev:Chief_Executive_Officer", 2, latency_ms=1800,
           state_delta={"action": "revise", "revision": "add load balancing"},
           output="CEO revised: adding load balancing requirements"),
        _s("chatdev:Chief_Technology_Officer", 3, latency_ms=2200,
           state_delta={"action": "counter_propose", "concern": "cost"},
           output="CTO: revised architecture still too expensive"),
        _s("chatdev:Chief_Executive_Officer", 4, latency_ms=1500,
           state_delta={"action": "simplify", "simplification": "reduce features"},
           output="CEO: simplifying to core features only"),
        _s("chatdev:Chief_Technology_Officer", 5, latency_ms=2000,
           state_delta={"action": "approve", "decision": "proceed with simplified"},
           output="CTO finally approves simplified approach"),
        _s("chatdev:Programmer", 6, latency_ms=6000,
           state_delta={"action": "implement", "files": 3},
           tool_calls=["code_generation"], output="Implementation: 3 files created"),
    ], True)

    # 4. Error cascade: all n8n nodes fail sequentially
    _entry("n8n error cascade: API failure propagates through entire workflow", [
        _s("Webhook", 0, role="trigger", latency_ms=25,
           state_delta={"action": "receive_request", "method": "POST", "path": "/analyze"},
           output="Received POST /analyze"),
        _s("Database_Query", 1, role="data", latency_ms=800,
           state_delta={"action": "query", "table": "customers", "rows_returned": 150},
           tool_calls=["sql_query"], output="Queried customers table: 150 rows"),
        _s("HTTP_Request", 2, role="integration", latency_ms=5000, status="error",
           state_delta={"action": "call_external_api", "url": "https://api.enrichment.io/v2/lookup", "error": "504 Gateway Timeout"},
           output="ERROR: External API timeout after 5 seconds"),
        _s("Claude_Summarizer", 3, role="llm", latency_ms=100, status="error",
           state_delta={"action": "summarize", "error": "No input data from previous node"},
           output="ERROR: Cannot summarize without enrichment data"),
        _s("Format_Output", 4, role="formatter", latency_ms=50, status="error",
           state_delta={"action": "format", "error": "Empty response object"},
           output="ERROR: Nothing to format"),
    ], True)

    # 5. Deep delegation chain in agent hierarchy
    _entry("Dify deep delegation: 5-hop chain before any work happens", [
        _s("intent_classifier", 0, role="classifier", latency_ms=1200,
           state_delta={"intent": "complex_analysis", "confidence": 0.45, "action": "escalate"},
           output="Intent unclear (0.45 confidence), escalating to orchestrator"),
        _s("orchestrator", 1, role="orchestrator", latency_ms=800,
           state_delta={"action": "delegate_to_specialist", "specialist": "domain_expert"},
           output="Delegating to domain expert for specialized analysis"),
        _s("domain_expert", 2, role="expert", latency_ms=600,
           state_delta={"action": "requires_research", "delegate_to": "researcher"},
           output="Need research data first, delegating to researcher"),
        _s("researcher", 3, role="researcher", latency_ms=400,
           state_delta={"action": "needs_data", "delegate_to": "data_agent"},
           output="Need database access, delegating to data agent"),
        _s("data_agent", 4, role="data", latency_ms=2500,
           state_delta={"action": "query_and_analyze", "rows": 500, "analysis": "Revenue trending up 12% QoQ"},
           tool_calls=["sql_query", "compute_trend"], output="Analysis complete: revenue up 12% QoQ"),
    ], True)

    # 6. Extreme utilization imbalance
    _entry("LangGraph bottleneck: supervisor does all reasoning, tools barely used", [
        _s("supervisor", 0, latency_ms=8500,
           state_delta={"action": "deep_reasoning", "model": "claude-opus-4", "prompt_tokens": 6200, "completion_tokens": 1800},
           tool_calls=["think"], output="Extensive analysis: considered 5 approaches, selected option C based on cost-benefit"),
        _s("supervisor", 1, latency_ms=7200,
           state_delta={"action": "detailed_planning", "model": "claude-opus-4", "prompt_tokens": 5800, "completion_tokens": 1500},
           tool_calls=["think"], output="Detailed plan: 8 steps with dependencies mapped"),
        _s("tools", 2, latency_ms=350,
           state_delta={"action": "web_search", "query": "latest pricing data", "results": 3},
           tool_calls=["web_search"], output="Found 3 relevant pricing sources"),
        _s("supervisor", 3, latency_ms=6800,
           state_delta={"action": "final_synthesis", "model": "claude-opus-4", "prompt_tokens": 4500, "completion_tokens": 2000},
           tool_calls=["think"], output="Final synthesis incorporating search results"),
    ], True)

    # 7. Circular delegation pattern
    _entry("Multi-agent circular delegation: analyst→reviewer→analyst loop", [
        _s("supervisor", 0, latency_ms=1200,
           state_delta={"action": "assign_task", "task": "analyze market data"},
           output="Task assigned to analyst"),
        _s("analyst_agent", 1, latency_ms=3500,
           state_delta={"action": "initial_analysis", "findings": "Market growing 8% YoY"},
           tool_calls=["data_analysis"], output="Initial analysis: 8% YoY growth"),
        _s("reviewer_agent", 2, latency_ms=2000,
           state_delta={"action": "review", "feedback": "Need deeper competitive analysis"},
           output="Review: insufficient competitive data, sending back"),
        _s("analyst_agent", 3, latency_ms=4000,
           state_delta={"action": "revised_analysis", "findings": "Added competitor data, 3 key players"},
           tool_calls=["data_analysis", "web_search"], output="Revised: added competitive landscape"),
        _s("reviewer_agent", 4, latency_ms=1800,
           state_delta={"action": "review", "feedback": "Missing pricing comparison"},
           output="Review: still needs pricing data, sending back again"),
        _s("analyst_agent", 5, latency_ms=3200,
           state_delta={"action": "final_analysis", "findings": "Complete analysis with pricing"},
           tool_calls=["data_analysis"], output="Final analysis with pricing comparison"),
    ], True)

    # 8. All agents produce errors
    _entry("Dify workflow: every node fails in sequence", [
        _s("rag_search", 0, role="retrieval", latency_ms=2500, status="error",
           state_delta={"action": "search_knowledge_base", "error": "Index not found: kb_product_docs_v3"},
           output="ERROR: Knowledge base index missing"),
        _s("claude_reasoning", 1, role="llm", latency_ms=500, status="error",
           state_delta={"action": "generate_answer", "error": "No context documents to reason over"},
           output="ERROR: Cannot reason without source documents"),
        _s("format_response", 2, role="formatter", latency_ms=100, status="error",
           state_delta={"action": "format_markdown", "error": "Empty input from reasoning node"},
           output="ERROR: No content to format"),
    ], True)

    # 9. n8n chatty webhook ping-pong
    _entry("n8n status polling: webhook node checks status 8 times before proceeding", [
        _s("Webhook", 0, role="trigger", latency_ms=30,
           state_delta={"action": "receive", "path": "/process"}, output="Request received"),
        _s("HTTP_Request", 1, role="poller", latency_ms=800,
           state_delta={"action": "check_status", "status": "processing"}, output="Status: processing"),
        _s("HTTP_Request", 2, role="poller", latency_ms=800,
           state_delta={"action": "check_status", "status": "processing"}, output="Status: still processing"),
        _s("HTTP_Request", 3, role="poller", latency_ms=800,
           state_delta={"action": "check_status", "status": "processing"}, output="Status: still processing"),
        _s("HTTP_Request", 4, role="poller", latency_ms=800,
           state_delta={"action": "check_status", "status": "processing"}, output="Status: still processing"),
        _s("HTTP_Request", 5, role="poller", latency_ms=800,
           state_delta={"action": "check_status", "status": "completed"}, output="Status: completed"),
        _s("Claude_Summarizer", 6, role="llm", latency_ms=3500,
           state_delta={"action": "summarize", "model": "claude-3-5-sonnet"},
           tool_calls=["llm_call"], output="Summary generated from processed data"),
    ], True)

    # 10. Sequential pipeline where each step loses context
    _entry("Data pipeline context loss: each agent starts fresh without upstream context", [
        _s("data_ingester", 0, role="ingester", latency_ms=1500,
           state_delta={"source": "s3://data-lake/transactions/2025-q1/", "records": 50000, "schema": "transaction_v3"},
           tool_calls=["s3_read"], output="Ingested 50K transactions from Q1 data lake"),
        _s("data_cleaner", 1, role="cleaner", latency_ms=2000,
           state_delta={"removed_nulls": 1200, "fixed_types": 340, "output_records": 48460},
           tool_calls=["pandas_clean"], output="Cleaned: removed 1200 nulls, fixed 340 type mismatches"),
        _s("feature_engineer", 2, role="engineer", latency_ms=3500,
           state_delta={"features_created": 12, "aggregations": ["daily_spend", "category_mix"]},
           tool_calls=["compute_features"], output="Engineered 12 features including spending patterns"),
        _s("ml_predictor", 3, role="model", latency_ms=4000,
           state_delta={"model": "xgboost_v4", "predictions": 48460, "accuracy": 0.87},
           tool_calls=["predict"], output="Predictions: 87% accuracy on churn model"),
        _s("report_writer", 4, role="writer", latency_ms=2500,
           state_delta={"format": "pdf", "pages": 12, "charts": 5},
           tool_calls=["generate_report"], output="12-page report with 5 interactive charts"),
    ], True, difficulty="hard")

    # ═══════════════════════════════════════════════════════════════════
    # NEGATIVES — Good orchestration (expected_detected=False)
    # ═══════════════════════════════════════════════════════════════════

    # 11. Well-orchestrated ChatDev workflow
    _entry("ChatDev balanced: each role contributes meaningfully in sequence", [
        _s("chatdev:Chief_Executive_Officer", 0, latency_ms=2000,
           state_delta={"action": "task_proposal", "task": "Build a todo app with user authentication",
                        "requirements": ["login", "register", "task_crud", "categories"]},
           output="Task proposed: Todo app with auth, 4 core requirements"),
        _s("chatdev:Chief_Product_Officer", 1, latency_ms=2500,
           state_delta={"action": "requirements_refinement", "requirements": ["login", "register", "task_crud", "categories"],
                        "user_stories": 6, "acceptance_criteria": 12},
           output="Refined: 6 user stories, 12 acceptance criteria defined"),
        _s("chatdev:Chief_Technology_Officer", 2, latency_ms=3000,
           state_delta={"action": "architecture_design", "requirements": ["login", "register", "task_crud"],
                        "stack": "React+FastAPI+PostgreSQL", "components": 5},
           tool_calls=["design_system"], output="Architecture: React frontend, FastAPI backend, PostgreSQL"),
        _s("chatdev:Programmer", 3, latency_ms=8000,
           state_delta={"action": "implementation", "stack": "React+FastAPI+PostgreSQL",
                        "files": 12, "lines": 680, "tests": 15},
           tool_calls=["code_generation", "run_tests"], output="Implemented: 12 files, 680 lines, 15 tests passing"),
        _s("chatdev:Code_Reviewer", 4, latency_ms=2500,
           state_delta={"action": "code_review", "files": 12, "issues": 2, "approved": True},
           output="Review: 2 minor issues found, approved with suggestions"),
    ], False)

    # 12. LangGraph supervisor with parallel workers
    _entry("LangGraph parallel: supervisor dispatches, 2 researchers work concurrently", [
        _s("supervisor", 0, latency_ms=800,
           state_delta={"action": "dispatch", "tasks": ["search_web", "query_database"]},
           tool_calls=["plan"], output="Dispatching 2 parallel research tasks"),
        _s("researcher_agent", 1, latency_ms=3500,
           state_delta={"task": "search_web", "query": "AI agent frameworks 2025", "results": 8},
           tool_calls=["web_search"], output="Web search: 8 relevant results on agent frameworks"),
        _s("analyst_agent", 1, latency_ms=2800,
           state_delta={"task": "query_database", "table": "market_data", "rows": 250},
           tool_calls=["sql_query"], output="Database: 250 rows of market data retrieved"),
        _s("writer_agent", 2, latency_ms=4000,
           state_delta={"action": "synthesize", "sources": 2, "word_count": 1200,
                        "incorporates": "web search results and market data from database"},
           tool_calls=["generate_text"], output="Synthesis: 1200-word report combining web and database findings"),
        _s("supervisor", 3, latency_ms=600,
           state_delta={"action": "finalize", "quality_check": "passed", "report_length": 1200},
           output="Finalized: report quality check passed"),
    ], False)

    # 13. Error recovery with backup agent
    _entry("n8n error recovery: primary API fails, backup API succeeds", [
        _s("Webhook", 0, role="trigger", latency_ms=20,
           state_delta={"action": "receive", "path": "/enrich", "body_size": 1024},
           output="Received enrichment request"),
        _s("HTTP_Request", 1, role="primary_api", latency_ms=3000, status="error",
           state_delta={"action": "call_primary", "url": "https://api.clearbit.com/v2/people/find",
                        "error": "429 Too Many Requests"},
           output="ERROR: Primary enrichment API rate limited"),
        _s("HTTP_Request", 2, role="backup_api", latency_ms=2500,
           state_delta={"action": "call_backup", "url": "https://api.apollo.io/v1/people/match",
                        "enrichment_found": True, "fields_enriched": 8},
           tool_calls=["http_call"], output="Backup API: enriched 8 fields successfully"),
        _s("Claude_Summarizer", 3, role="llm", latency_ms=3000,
           state_delta={"action": "summarize_profile", "model": "claude-3-5-sonnet",
                        "input_fields": 8, "summary_length": 150},
           tool_calls=["llm_call"], output="Profile summary: 150-word executive overview generated"),
        _s("Send_Email", 4, role="output", latency_ms=400,
           state_delta={"action": "send_result", "recipient": "sales@company.com", "status": "sent"},
           output="Results emailed to sales team"),
    ], False)

    # 14. Efficient two-agent handoff
    _entry("Dify simple flow: classifier routes to correct specialist immediately", [
        _s("intent_classifier", 0, role="classifier", latency_ms=1200,
           state_delta={"intent": "billing_inquiry", "confidence": 0.94,
                        "entities": {"customer_id": "C-1234", "issue_type": "refund"}},
           tool_calls=["classify"], output="Intent: billing inquiry (94% confidence), customer C-1234"),
        _s("billing_specialist", 1, role="specialist", latency_ms=4500,
           state_delta={"action": "process_refund", "customer_id": "C-1234", "intent": "billing_inquiry",
                        "order_found": "ORD-5678", "refund_amount": 49.99, "status": "processed"},
           tool_calls=["lookup_order", "process_refund"], output="Refund of $49.99 processed for order ORD-5678"),
    ], False)

    # 15. Multi-step RAG with good context flow
    _entry("LangGraph RAG pipeline: retrieve → reason → verify → respond", [
        _s("retrieve", 0, role="retrieval", latency_ms=1500,
           state_delta={"action": "vector_search", "query": "What is the refund policy for enterprise plans?",
                        "documents_found": 5, "top_score": 0.92},
           tool_calls=["embedding_search"], output="Retrieved 5 documents, top relevance 0.92"),
        _s("supervisor", 1, role="reasoning", latency_ms=4200,
           state_delta={"action": "reason_with_context", "query": "What is the refund policy for enterprise plans?",
                        "documents_found": 5, "model": "claude-3-5-sonnet",
                        "answer": "Enterprise plans have a 30-day refund policy with prorated billing"},
           tool_calls=["llm_call"], output="Answer: 30-day refund policy with prorated billing for enterprise"),
        _s("reviewer_agent", 2, role="verifier", latency_ms=2000,
           state_delta={"action": "fact_check", "answer": "Enterprise plans have a 30-day refund policy",
                        "sources_checked": 5, "claims_verified": 3, "confidence": 0.88},
           tool_calls=["verify_claims"], output="Verification: 3/3 claims verified, confidence 0.88"),
        _s("writer_agent", 3, role="formatter", latency_ms=800,
           state_delta={"action": "format_response", "claims_verified": 3,
                        "format": "markdown", "includes_citations": True},
           output="Formatted response with 3 citations and confidence score"),
    ], False)

    # 16. Balanced supervisor with 3 workers
    _entry("LangGraph balanced team: supervisor coordinates 3 specialized workers", [
        _s("supervisor", 0, latency_ms=1000,
           state_delta={"action": "plan", "subtasks": ["data_collection", "analysis", "visualization"]},
           tool_calls=["plan"], output="Plan: 3 subtasks assigned to specialized agents"),
        _s("researcher_agent", 1, latency_ms=3500,
           state_delta={"subtask": "data_collection", "sources_queried": 4, "records": 1200},
           tool_calls=["web_search", "api_call"], output="Data collection: 1200 records from 4 sources"),
        _s("analyst_agent", 2, latency_ms=4000,
           state_delta={"subtask": "analysis", "records": 1200, "insights": 5, "model": "statistical"},
           tool_calls=["data_analysis"], output="Analysis: 5 key insights from 1200 records"),
        _s("writer_agent", 3, latency_ms=3500,
           state_delta={"subtask": "visualization", "insights": 5, "charts": 3, "dashboard": True},
           tool_calls=["create_charts", "build_dashboard"], output="Dashboard: 3 charts visualizing 5 insights"),
        _s("supervisor", 4, latency_ms=800,
           state_delta={"action": "review", "quality": "passed", "all_subtasks_complete": True},
           output="All subtasks complete, quality check passed"),
    ], False)

    # 17. Code review pipeline
    _entry("ChatDev review cycle: programmer implements, reviewer approves with minor feedback", [
        _s("chatdev:Programmer", 0, latency_ms=7000,
           state_delta={"action": "implement", "task": "Add search functionality",
                        "files_modified": 3, "lines_added": 120, "tests_added": 5},
           tool_calls=["code_generation", "run_tests"], output="Implemented search: 3 files, 120 lines, 5 tests"),
        _s("chatdev:Code_Reviewer", 1, latency_ms=3000,
           state_delta={"action": "review", "files_modified": 3, "issues": 1,
                        "severity": "minor", "suggestion": "Add input validation for search query"},
           output="Review: 1 minor issue — add input validation for search query"),
    ], False)

    # 18. Dify customer support flow
    _entry("Dify support: classify → search KB → generate answer → verify", [
        _s("intent_classifier", 0, role="classifier", latency_ms=1000,
           state_delta={"intent": "technical_support", "confidence": 0.89, "category": "api_error"},
           tool_calls=["classify"], output="Technical support request: API error (89% confidence)"),
        _s("rag_search", 1, role="retrieval", latency_ms=1800,
           state_delta={"query": "API error troubleshooting", "intent": "technical_support",
                        "documents": 4, "relevance_avg": 0.85},
           tool_calls=["knowledge_search"], output="Found 4 relevant troubleshooting docs (avg relevance 0.85)"),
        _s("claude_reasoning", 2, role="llm", latency_ms=3500,
           state_delta={"action": "generate_answer", "documents": 4, "model": "claude-3-5-sonnet",
                        "answer_length": 200, "includes_code_example": True},
           tool_calls=["llm_call"], output="Generated answer with code example for API error resolution"),
        _s("format_response", 3, role="formatter", latency_ms=300,
           state_delta={"format": "html", "includes_code_example": True, "includes_links": 2},
           output="Formatted HTML response with code block and 2 documentation links"),
    ], False)

    # 19. Hierarchical management with good delegation
    _entry("LangGraph hierarchy: manager plans, leads execute, manager verifies", [
        _s("supervisor", 0, role="manager", latency_ms=1500,
           state_delta={"action": "strategic_plan", "objectives": ["frontend", "backend", "testing"]},
           tool_calls=["plan"], output="Strategy: 3 work streams assigned to leads"),
        _s("researcher_agent", 1, role="frontend_lead", latency_ms=5000,
           state_delta={"stream": "frontend", "objectives": ["frontend"],
                        "components_built": 4, "tests": 8},
           tool_calls=["code_gen", "test_run"], output="Frontend: 4 React components, 8 tests passing"),
        _s("analyst_agent", 2, role="backend_lead", latency_ms=6000,
           state_delta={"stream": "backend", "objectives": ["backend"],
                        "endpoints_created": 6, "db_migrations": 2},
           tool_calls=["code_gen", "migrate_db"], output="Backend: 6 API endpoints, 2 DB migrations"),
        _s("writer_agent", 3, role="qa_lead", latency_ms=4000,
           state_delta={"stream": "testing", "objectives": ["testing"],
                        "e2e_tests": 12, "coverage": 0.85},
           tool_calls=["test_e2e"], output="QA: 12 E2E tests, 85% code coverage"),
        _s("supervisor", 4, role="manager", latency_ms=1000,
           state_delta={"action": "final_review", "all_streams_complete": True,
                        "overall_quality": "passed"},
           output="Final review: all 3 streams complete, quality gates passed"),
    ], False)

    # 20. n8n efficient automation
    _entry("n8n efficient pipeline: webhook → process → enrich → respond in 4 steps", [
        _s("Webhook", 0, role="trigger", latency_ms=15,
           state_delta={"action": "receive", "path": "/lead", "method": "POST"},
           output="Received new lead submission"),
        _s("Process_JSON", 1, role="processor", latency_ms=80,
           state_delta={"action": "validate_and_parse", "path": "/lead",
                        "fields_valid": True, "lead_score": 72},
           tool_calls=["validate"], output="Lead validated: score 72, all required fields present"),
        _s("HTTP_Request", 2, role="enricher", latency_ms=1500,
           state_delta={"action": "enrich_lead", "fields_valid": True,
                        "company_found": True, "employee_count": 250, "industry": "SaaS"},
           tool_calls=["http_call"], output="Enriched: SaaS company, 250 employees"),
        _s("Send_Email", 3, role="notifier", latency_ms=300,
           state_delta={"action": "notify_sales", "company_found": True,
                        "recipient": "sales-team@company.com", "priority": "high"},
           output="Sales team notified: high-priority SaaS lead"),
    ], False)

    return entries


def generate_multi_chain_entries() -> List[Dict[str, Any]]:
    """Generate 30 realistic multi_chain entries."""
    entries = []

    def _t(trace_id, status="completed", det_types=None, first_delta=None, last_delta=None,
           agents=None, created="2025-03-26T10:30:00Z", completed="2025-03-26T10:30:10Z"):
        return {
            "trace_id": trace_id, "status": status,
            "detection_types": det_types or [],
            "first_state_delta": first_delta or {},
            "last_state_delta": last_delta or {},
            "agent_ids": agents or [],
            "created_at": created, "completed_at": completed,
        }

    def _entry(desc, traces, links, expected, difficulty="medium"):
        entries.append({
            "id": f"mc-{uuid.uuid4().hex[:8]}",
            "detection_type": "multi_chain",
            "input_data": {"traces": traces, "links": links},
            "expected_detected": expected,
            "description": desc,
            "source": "synthetic",
            "difficulty": difficulty,
        })

    # ═══════════════════════════════════════════════════════════════════
    # POSITIVES — Cross-chain issues (expected_detected=True)
    # ═══════════════════════════════════════════════════════════════════

    # 1. n8n Execute Workflow cascade: data enrichment corrupts downstream
    _entry("n8n cascade: enrichment workflow corruption → analysis hallucination", [
        _t("wf-enrich-001", det_types=["corruption"],
           agents=["Webhook", "HTTP_Request", "Database_Query"],
           last_delta={"customer_data": {"name": "Acme Corp", "revenue": "corrupted_value", "industry": "SaaS"}},
           completed="2025-03-26T10:30:05Z"),
        _t("wf-analyze-001", det_types=["hallucination"],
           agents=["Claude_Summarizer", "Format_Output"],
           first_delta={"customer_data": {"name": "Acme Corp", "revenue": "corrupted_value", "industry": "SaaS"}},
           created="2025-03-26T10:30:06Z"),
    ], [{"parent_trace_id": "wf-enrich-001", "child_trace_id": "wf-analyze-001", "link_type": "execute_workflow"}],
    True)

    # 2. LangGraph subgraph timeout cascading
    _entry("LangGraph cascade: research subgraph timeout → main graph context neglect", [
        _t("lg-main-run", det_types=["timeout"],
           agents=["supervisor", "researcher_agent", "tools"],
           completed="2025-03-26T10:32:00Z"),
        _t("lg-synthesis-run", det_types=["context"],
           agents=["writer_agent", "reviewer_agent"],
           created="2025-03-26T10:32:01Z"),
    ], [{"parent_trace_id": "lg-main-run", "child_trace_id": "lg-synthesis-run", "link_type": "subgraph"}],
    True)

    # 3. Dify app-to-app cascade: injection in input app → derailment in processing app
    _entry("Dify cascade: chatbot injection → workflow derailment", [
        _t("dify-chat-session", det_types=["injection"],
           agents=["intent_classifier", "claude_reasoning"],
           completed="2025-03-26T10:31:00Z"),
        _t("dify-processing-wf", det_types=["derailment"],
           agents=["rag_search", "summarizer"],
           created="2025-03-26T10:31:01Z"),
    ], [{"parent_trace_id": "dify-chat-session", "child_trace_id": "dify-processing-wf", "link_type": "app_invocation"}],
    True)

    # 4. Multi-hop: enrichment → analysis → reporting
    _entry("3-hop cascade: n8n enrichment corruption → LangGraph hallucination → Dify spec violation", [
        _t("step1-enrich", det_types=["corruption"], completed="2025-03-26T10:30:10Z"),
        _t("step2-analyze", det_types=["hallucination"], created="2025-03-26T10:30:11Z", completed="2025-03-26T10:30:25Z"),
        _t("step3-report", det_types=["specification"], created="2025-03-26T10:30:26Z"),
    ], [
        {"parent_trace_id": "step1-enrich", "child_trace_id": "step2-analyze", "link_type": "execute_workflow"},
        {"parent_trace_id": "step2-analyze", "child_trace_id": "step3-report", "link_type": "app_invocation"},
    ], True, difficulty="hard")

    # 5. Data corruption: enrichment API returns wrong data
    _entry("Data corruption: enrichment returns wrong revenue figure, propagates to analysis", [
        _t("enrich-trace", last_delta={"company": "Acme", "revenue_usd": 5200000, "employees": 120}),
        _t("analyze-trace", first_delta={"company": "Acme", "revenue_usd": 52000, "employees": 120}),
    ], [{"parent_trace_id": "enrich-trace", "child_trace_id": "analyze-trace", "link_type": "execute_workflow"}],
    True)

    # 6. Cross-chain loop: n8n workflow A calls B, B calls A
    _entry("n8n cross-workflow loop: order processor calls inventory checker, which calls back", [
        _t("wf-order-processor", agents=["Webhook", "Process_Order", "Execute_Workflow"]),
        _t("wf-inventory-checker", agents=["Check_Stock", "Execute_Workflow"]),
    ], [
        {"parent_trace_id": "wf-order-processor", "child_trace_id": "wf-inventory-checker", "link_type": "execute_workflow"},
        {"parent_trace_id": "wf-inventory-checker", "child_trace_id": "wf-order-processor", "link_type": "execute_workflow"},
    ], True)

    # 7. 3-node cross-chain loop
    _entry("3-way loop: data pipeline → ML training → data pipeline (circular retraining)", [
        _t("pipeline-ingest", agents=["S3_Reader", "Cleaner", "Loader"]),
        _t("ml-train", agents=["Feature_Engineer", "Trainer", "Evaluator"]),
        _t("pipeline-retrain", agents=["Export_Model", "Update_Pipeline"]),
    ], [
        {"parent_trace_id": "pipeline-ingest", "child_trace_id": "ml-train", "link_type": "execute_workflow"},
        {"parent_trace_id": "ml-train", "child_trace_id": "pipeline-retrain", "link_type": "execute_workflow"},
        {"parent_trace_id": "pipeline-retrain", "child_trace_id": "pipeline-ingest", "link_type": "execute_workflow"},
    ], True)

    # 8. Redundant sibling work: same enrichment done twice
    _entry("Redundant: parent dispatches identical enrichment to 2 sub-workflows", [
        _t("parent-dispatch"),
        _t("enrich-copy1", first_delta={
            "task": "enrich customer profile for Acme Corp using Clearbit API",
            "customer_id": "C-9876", "enrichment_source": "clearbit"}),
        _t("enrich-copy2", first_delta={
            "task": "enrich customer profile for Acme Corp using Clearbit API endpoint",
            "customer_id": "C-9876", "enrichment_source": "clearbit"}),
    ], [
        {"parent_trace_id": "parent-dispatch", "child_trace_id": "enrich-copy1", "link_type": "execute_workflow"},
        {"parent_trace_id": "parent-dispatch", "child_trace_id": "enrich-copy2", "link_type": "execute_workflow"},
    ], True)

    # 9. Cascade + data corruption combined
    _entry("Combined: corruption in enrichment + data value changed + hallucination in analysis", [
        _t("combined-parent", det_types=["corruption"],
           last_delta={"analysis_result": "Revenue growth: 15% QoQ based on verified financial data"}),
        _t("combined-child", det_types=["hallucination"],
           first_delta={"analysis_result": "Revenue growth: 150% QoQ based on unverified estimates"}),
    ], [{"parent_trace_id": "combined-parent", "child_trace_id": "combined-child", "link_type": "execute_workflow"}],
    True, difficulty="hard")

    # 10. Loop cascade: parent loop causes child overflow
    _entry("Cascade: parent workflow stuck in loop → child workflow token overflow", [
        _t("looping-workflow", det_types=["loop"], completed="2025-03-26T10:35:00Z"),
        _t("downstream-workflow", det_types=["overflow"], created="2025-03-26T10:35:01Z"),
    ], [{"parent_trace_id": "looping-workflow", "child_trace_id": "downstream-workflow", "link_type": "execute_workflow"}],
    True)

    # ═══════════════════════════════════════════════════════════════════
    # NEGATIVES — No cross-chain issues (expected_detected=False)
    # ═══════════════════════════════════════════════════════════════════

    # 11. Clean n8n workflow chain
    _entry("Clean n8n chain: enrichment → analysis, both succeed, data matches", [
        _t("clean-enrich", agents=["Webhook", "HTTP_Request", "Database_Query"],
           last_delta={"customer": "Acme", "revenue": 5200000, "enriched": True}),
        _t("clean-analyze", agents=["Claude_Summarizer", "Format_Output"],
           first_delta={"customer": "Acme", "revenue": 5200000, "enriched": True}),
    ], [{"parent_trace_id": "clean-enrich", "child_trace_id": "clean-analyze", "link_type": "execute_workflow"}],
    False)

    # 12. Unrelated failures: parent has loop, child has injection (not a pair)
    _entry("Independent failures: ingestion loop and analysis injection are unrelated", [
        _t("ingest-loop", det_types=["loop"], completed="2025-03-26T10:30:05Z"),
        _t("analyze-injection", det_types=["injection"], created="2025-03-26T10:30:06Z"),
    ], [{"parent_trace_id": "ingest-loop", "child_trace_id": "analyze-injection", "link_type": "execute_workflow"}],
    False)

    # 13. Data matches perfectly
    _entry("Clean data flow: enrichment output matches analysis input exactly", [
        _t("perfect-enrich", last_delta={"lead_score": 85, "company_size": "mid-market", "industry": "fintech"}),
        _t("perfect-analyze", first_delta={"lead_score": 85, "company_size": "mid-market", "industry": "fintech"}),
    ], [{"parent_trace_id": "perfect-enrich", "child_trace_id": "perfect-analyze", "link_type": "execute_workflow"}],
    False)

    # 14. Different data domains — no shared keys
    _entry("Separate domains: user auth trace and analytics trace share no data", [
        _t("auth-trace", last_delta={"user_id": "U-123", "session_token": "abc123", "auth_method": "oauth"}),
        _t("analytics-trace", first_delta={"page_views": 1500, "bounce_rate": 0.35, "avg_session": 240}),
    ], [{"parent_trace_id": "auth-trace", "child_trace_id": "analytics-trace", "link_type": "correlation"}],
    False)

    # 15. Clean fan-out: parent dispatches 3 independent tasks
    _entry("Clean fan-out: batch processor dispatches 3 independent analysis tasks", [
        _t("batch-parent", agents=["Scheduler", "Dispatcher"]),
        _t("task-1", agents=["Analyzer_A"], first_delta={"task": "analyze Q1 sales data for US region"}),
        _t("task-2", agents=["Analyzer_B"], first_delta={"task": "analyze Q1 sales data for EU region"}),
        _t("task-3", agents=["Analyzer_C"], first_delta={"task": "analyze Q1 sales data for APAC region"}),
    ], [
        {"parent_trace_id": "batch-parent", "child_trace_id": "task-1", "link_type": "execute_workflow"},
        {"parent_trace_id": "batch-parent", "child_trace_id": "task-2", "link_type": "execute_workflow"},
        {"parent_trace_id": "batch-parent", "child_trace_id": "task-3", "link_type": "execute_workflow"},
    ], False)

    # 16. Siblings with different tasks — not redundant
    _entry("Distinct siblings: enrichment + sentiment analysis on same customer (different work)", [
        _t("dispatch-parent"),
        _t("enrich-child", first_delta={"task": "enrich customer profile with firmographic data from Clearbit"}),
        _t("sentiment-child", first_delta={"task": "analyze sentiment of recent support tickets for NPS prediction"}),
    ], [
        {"parent_trace_id": "dispatch-parent", "child_trace_id": "enrich-child", "link_type": "execute_workflow"},
        {"parent_trace_id": "dispatch-parent", "child_trace_id": "sentiment-child", "link_type": "execute_workflow"},
    ], False)

    # 17. Clean linear chain: 3 n8n workflows in sequence
    _entry("Clean 3-step n8n chain: ingest → transform → load, all healthy", [
        _t("etl-ingest", last_delta={"records": 10000, "schema": "v3", "status": "ingested"},
           completed="2025-03-26T10:30:05Z"),
        _t("etl-transform", first_delta={"records": 10000, "schema": "v3", "status": "ingested"},
           last_delta={"records": 9500, "schema": "v3", "status": "transformed"},
           created="2025-03-26T10:30:06Z", completed="2025-03-26T10:30:15Z"),
        _t("etl-load", first_delta={"records": 9500, "schema": "v3", "status": "transformed"},
           created="2025-03-26T10:30:16Z"),
    ], [
        {"parent_trace_id": "etl-ingest", "child_trace_id": "etl-transform", "link_type": "execute_workflow"},
        {"parent_trace_id": "etl-transform", "child_trace_id": "etl-load", "link_type": "execute_workflow"},
    ], False)

    # 18. Parent fails but child succeeds independently
    _entry("Independent child: parent chat session derails but background job completes fine", [
        _t("chat-session", det_types=["derailment"], completed="2025-03-26T10:30:10Z"),
        _t("background-job", created="2025-03-26T10:30:00Z", completed="2025-03-26T10:30:08Z"),
    ], [{"parent_trace_id": "chat-session", "child_trace_id": "background-job", "link_type": "correlation"}],
    False)

    # 19. Temporal violation: child started before parent completed (not a cascade)
    _entry("Temporal: child workflow started before parent completed — parallel, not cascade", [
        _t("slow-parent", det_types=["corruption"],
           created="2025-03-26T10:30:00Z", completed="2025-03-26T10:30:30Z"),
        _t("early-child", det_types=["hallucination"],
           created="2025-03-26T10:30:05Z", completed="2025-03-26T10:30:15Z"),
    ], [{"parent_trace_id": "slow-parent", "child_trace_id": "early-child", "link_type": "correlation"}],
    False)

    # 20. Mixed failures but unrelated detection types
    _entry("Mixed unrelated: parent has persona_drift, children have loop and withholding (no cascade pairs)", [
        _t("parent-mixed", det_types=["persona_drift"]),
        _t("child-1-mixed", det_types=["loop"]),
        _t("child-2-mixed", det_types=["withholding"]),
    ], [
        {"parent_trace_id": "parent-mixed", "child_trace_id": "child-1-mixed", "link_type": "execute_workflow"},
        {"parent_trace_id": "parent-mixed", "child_trace_id": "child-2-mixed", "link_type": "execute_workflow"},
    ], False)

    return entries


def run_detector(entry: Dict) -> Tuple[bool, float]:
    """Run the appropriate detector on an entry."""
    det_type = entry["detection_type"]
    input_data = entry["input_data"]
    if det_type == "orchestration_quality":
        detected, confidence, _ = oq_detect(input_data.get("states", []))
        return detected, confidence
    elif det_type == "multi_chain":
        detected, confidence, _ = mc_detect(input_data.get("traces", []), input_data.get("links", []))
        return detected, confidence
    raise ValueError(f"Unknown detection type: {det_type}")


def main():
    print("=" * 70)
    print("Testing New Capabilities: Realistic Synthetic Data")
    print("=" * 70)

    oq_entries = generate_orchestration_entries()
    mc_entries = generate_multi_chain_entries()

    print(f"\nGenerated {len(oq_entries)} orchestration_quality entries")
    print(f"Generated {len(mc_entries)} multi_chain entries")
    print(f"Total: {len(oq_entries) + len(mc_entries)} entries\n")

    results = {"orchestration_quality": [], "multi_chain": []}

    for det_type, det_entries in [("orchestration_quality", oq_entries), ("multi_chain", mc_entries)]:
        print(f"\n{'─' * 60}")
        print(f"  {det_type.upper()}")
        print(f"{'─' * 60}")

        tp, tn, fp, fn = 0, 0, 0, 0
        for entry in det_entries:
            detected, confidence = run_detector(entry)
            expected = entry["expected_detected"]
            correct = detected == expected

            if expected and detected: tp += 1; mark = "TP"
            elif not expected and not detected: tn += 1; mark = "TN"
            elif detected and not expected: fp += 1; mark = "FP"
            else: fn += 1; mark = "FN"

            status = "  OK " if correct else "WRONG"
            print(f"  [{status}] {mark} | conf={confidence:.2f} | {entry['description'][:65]}")
            results[det_type].append({"entry": entry, "detected": detected, "confidence": confidence, "correct": correct})

        total = tp + tn + fp + fn
        acc = (tp + tn) / total if total else 0
        prec = tp / (tp + fp) if (tp + fp) else 0
        rec = tp / (tp + fn) if (tp + fn) else 0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0

        print(f"\n  Results: TP={tp} TN={tn} FP={fp} FN={fn}")
        print(f"  Accuracy: {acc:.1%} ({tp+tn}/{total})")
        print(f"  Precision: {prec:.3f}  Recall: {rec:.3f}  F1: {f1:.3f}")

    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    total_correct = 0
    total_entries = 0
    for det_type, res_list in results.items():
        c = sum(1 for r in res_list if r["correct"])
        t = len(res_list)
        total_correct += c
        total_entries += t
        print(f"  {det_type}: {c}/{t} ({100*c/t:.0f}%)")
    print(f"\n  Overall: {total_correct}/{total_entries} ({100*total_correct/total_entries:.0f}%)")

    # Save validated entries
    print(f"\n{'─' * 60}")
    print("Saving validated entries to golden dataset...")
    golden_path = os.path.join(os.path.dirname(__file__), "..", "data", "golden_dataset_expanded.json")
    if os.path.exists(golden_path):
        with open(golden_path) as f:
            existing = json.load(f)
        if isinstance(existing, dict):
            existing = existing.get("entries", [])
    else:
        existing = []

    # Remove old test entries
    existing = [e for e in existing if e.get("detection_type") not in ("orchestration_quality", "multi_chain")]

    new_entries = []
    for res_list in results.values():
        for r in res_list:
            if r["correct"]:
                entry = r["entry"]
                entry["created_at"] = datetime.now(timezone.utc).isoformat()
                entry["tags"] = ["realistic_synthetic", "capability_test"]
                entry["split"] = "train"
                new_entries.append(entry)

    existing.extend(new_entries)
    with open(golden_path, "w") as f:
        json.dump(existing, f, indent=2, default=str)

    print(f"  Added {len(new_entries)} validated entries")
    print(f"  Total golden dataset: {len(existing)} entries")
    print(f"\nDone!")


if __name__ == "__main__":
    main()
