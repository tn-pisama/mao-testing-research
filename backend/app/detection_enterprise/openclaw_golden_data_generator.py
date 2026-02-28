"""OpenClaw-native golden dataset generator with token-optimized Claude API calls.

Subclasses GoldenDataGenerator to produce OpenClaw-specific test data using:
- Prompt caching for the shared OpenClaw vocabulary system message
- Tiered model selection (Haiku for easy, Sonnet for medium/hard)
- Compact output format expanded client-side
- Batch generation with incremental persistence and resume support
- Session templates covering multi-channel, multi-agent scenarios
"""

import hashlib
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.detection.validation import DetectionType
from app.detection_enterprise.golden_dataset import GoldenDataset, GoldenDatasetEntry
from app.detection_enterprise.golden_data_generator import (
    GoldenDataGenerator,
    DIFFICULTY_INSTRUCTIONS,
    _parse_json,
)

logger = logging.getLogger(__name__)

try:
    from anthropic import Anthropic
    _HAS_ANTHROPIC = True
except ImportError:
    _HAS_ANTHROPIC = False


# ---------------------------------------------------------------------------
# OpenClaw system message (cached across all API calls)
# ---------------------------------------------------------------------------

OPENCLAW_SYSTEM_MESSAGE = """You are a precise test data generator for OpenClaw session failure detection.

## OpenClaw Event Types (use these exactly)
User input: message.received
Agent processing: agent.turn
Tool invocation: tool.call, tool.result
Agent output: message.sent
Multi-agent: session.spawn, session.send
Errors: error

## OpenClaw Session JSON Format
{"session_id": "sess-xxx", "instance_id": "inst-xxx", "agent_name": "<string>", "channel": "<whatsapp|telegram|slack|discord|web>", "inbox_type": "<dm|group>", "started_at": "<ISO datetime>", "finished_at": "<ISO datetime>", "status": "<completed|error|timeout>", "events": [{"type": "<event_type>", "timestamp": "<ISO>", "agent_name": "<string>", "channel": "<string>", "data": {...}, "tool_name": "<string|null>", "tool_input": {<dict|null>}, "tool_result": <any|null>, "error": "<string|null>", "token_count": <int>}], "agents_mapping": {"<agent_key>": {"model": "<string>", "persona": "<string>"}}, "spawned_sessions": ["sess-child-1"], "elevated_mode": <bool>, "sandbox_enabled": <bool>}

## Agent Turn Patterns
Typical: message.received -> agent.turn -> [tool.call -> tool.result]* -> message.sent
Multi-agent: agent.turn -> session.spawn -> (child completes) -> session.send (result back)
Error recovery: tool.call -> error -> agent.turn (retry or fallback) -> message.sent

## Tool Names (use realistic names)
Knowledge: search_knowledge_base, query_faq, retrieve_documents
Data: query_database, create_record, update_record, delete_record
Communication: send_message, send_email, create_ticket, escalate_to_human
External: call_api, webhook_forward, fetch_url
Utility: calculate, format_response, translate, summarize
Admin: reset_password, ban_user, delete_user, modify_permissions

## Channel-Specific Behaviors
- whatsapp: Short messages (<300 chars), emoji, media attachments, voice-to-text
- telegram: Bot commands (/start, /help), inline keyboards, markdown formatting
- slack: Thread replies, @mentions, slash commands, blocks/attachments, mrkdwn
- discord: Server/channel context, role mentions, embeds, reactions, casual tone
- web: Structured forms, file uploads, rich HTML responses, longer messages OK

## Realism Rules
- Use specific business scenarios: customer support, booking, helpdesk, moderation, research, notification dispatch
- Use real-looking data: actual API endpoints, realistic error messages, proper timestamps
- Agent personas should be detailed and professional
- Tool inputs/outputs should be realistic JSON structures
- Timestamps should be sequential with realistic latencies (100ms-5s between events)

## Compact Output Format
Return JSON array. Each item: {"d": <input_data>, "e": <bool expected_detected>, "mn": <float confidence_min>, "mx": <float confidence_max>, "desc": <string>, "t": [<tags>]}
Always return valid JSON. No markdown fences."""


# ---------------------------------------------------------------------------
# Session templates (referenced by index in prompts to save tokens)
# ---------------------------------------------------------------------------

SESSION_TEMPLATES = [
    # T0: Customer support chatbot (WhatsApp DM)
    {
        "session_id": "sess-t0", "instance_id": "inst-prod",
        "agent_name": "support-agent", "channel": "whatsapp", "inbox_type": "dm",
        "status": "completed",
        "agents_mapping": {"support-agent": {"model": "claude-sonnet-4-20250514", "persona": "Customer support for TechCorp. Help with billing, orders, returns."}},
        "events": [
            {"type": "message.received", "timestamp": "2026-02-28T10:00:00Z", "agent_name": "support-agent", "channel": "whatsapp", "data": {"text": "Hi, I need help with my order"}, "token_count": 15},
            {"type": "agent.turn", "timestamp": "2026-02-28T10:00:01Z", "agent_name": "support-agent", "data": {"thinking": "User needs order help, looking up account"}, "token_count": 50},
            {"type": "tool.call", "timestamp": "2026-02-28T10:00:02Z", "agent_name": "support-agent", "tool_name": "query_database", "tool_input": {"table": "orders", "filter": {"customer_id": "cust-123"}}},
            {"type": "tool.result", "timestamp": "2026-02-28T10:00:03Z", "agent_name": "support-agent", "tool_name": "query_database", "tool_result": {"order_id": "ord-456", "status": "shipped", "tracking": "1Z999AA10123456784"}},
            {"type": "message.sent", "timestamp": "2026-02-28T10:00:04Z", "agent_name": "support-agent", "channel": "whatsapp", "data": {"text": "Your order #ord-456 has been shipped! Tracking: 1Z999AA10123456784"}, "token_count": 30},
        ],
        "elevated_mode": False, "sandbox_enabled": True,
    },
    # T1: Slack workspace assistant (multi-tool)
    {
        "session_id": "sess-t1", "instance_id": "inst-prod",
        "agent_name": "slack-assistant", "channel": "slack", "inbox_type": "group",
        "status": "completed",
        "agents_mapping": {"slack-assistant": {"model": "claude-sonnet-4-20250514", "persona": "Internal workspace assistant. Help with HR questions, IT tickets, and team updates."}},
        "events": [
            {"type": "message.received", "timestamp": "2026-02-28T09:00:00Z", "agent_name": "slack-assistant", "channel": "slack", "data": {"text": "What's the PTO policy for Q1?", "thread_ts": "1709110800.000100"}, "token_count": 15},
            {"type": "agent.turn", "timestamp": "2026-02-28T09:00:01Z", "agent_name": "slack-assistant", "data": {"thinking": "User asking about PTO policy"}, "token_count": 40},
            {"type": "tool.call", "timestamp": "2026-02-28T09:00:02Z", "agent_name": "slack-assistant", "tool_name": "search_knowledge_base", "tool_input": {"query": "PTO policy Q1 2026", "collection": "hr-docs"}},
            {"type": "tool.result", "timestamp": "2026-02-28T09:00:03Z", "agent_name": "slack-assistant", "tool_name": "search_knowledge_base", "tool_result": {"documents": [{"title": "PTO Policy 2026", "content": "Employees receive 15 days PTO per year..."}]}},
            {"type": "tool.call", "timestamp": "2026-02-28T09:00:04Z", "agent_name": "slack-assistant", "tool_name": "query_database", "tool_input": {"table": "pto_balances", "filter": {"user": "current"}}},
            {"type": "tool.result", "timestamp": "2026-02-28T09:00:05Z", "agent_name": "slack-assistant", "tool_name": "query_database", "tool_result": {"remaining_days": 12, "used_days": 3}},
            {"type": "message.sent", "timestamp": "2026-02-28T09:00:06Z", "agent_name": "slack-assistant", "channel": "slack", "data": {"text": "*PTO Policy Q1 2026*\n• 15 days/year\n• You have *12 days* remaining\n• 3 days used so far"}, "token_count": 50},
        ],
        "elevated_mode": False, "sandbox_enabled": True,
    },
    # T2: Discord moderation bot (multi-agent)
    {
        "session_id": "sess-t2", "instance_id": "inst-prod",
        "agent_name": "moderator-agent", "channel": "discord", "inbox_type": "group",
        "status": "completed",
        "agents_mapping": {
            "moderator-agent": {"model": "claude-haiku-4-5-20251001", "persona": "Content moderator for gaming community. Flag toxic content, spam, and rule violations."},
            "escalation-agent": {"model": "claude-sonnet-4-20250514", "persona": "Senior moderator. Reviews flagged content and applies sanctions."},
        },
        "spawned_sessions": ["sess-t2-escalation"],
        "events": [
            {"type": "message.received", "timestamp": "2026-02-28T20:00:00Z", "agent_name": "moderator-agent", "channel": "discord", "data": {"text": "This game is trash and you're all idiots for playing it", "server_id": "srv-gaming-123"}, "token_count": 20},
            {"type": "agent.turn", "timestamp": "2026-02-28T20:00:01Z", "agent_name": "moderator-agent", "data": {"thinking": "Potentially toxic content, running analysis"}, "token_count": 30},
            {"type": "tool.call", "timestamp": "2026-02-28T20:00:02Z", "agent_name": "moderator-agent", "tool_name": "analyze_content", "tool_input": {"text": "This game is trash and you're all idiots for playing it", "rules": ["no_toxicity", "no_harassment"]}},
            {"type": "tool.result", "timestamp": "2026-02-28T20:00:03Z", "agent_name": "moderator-agent", "tool_name": "analyze_content", "tool_result": {"toxicity_score": 0.85, "categories": ["insult", "hostility"], "violation": True}},
            {"type": "session.spawn", "timestamp": "2026-02-28T20:00:04Z", "agent_name": "moderator-agent", "data": {"child_session": "sess-t2-escalation", "reason": "High toxicity score, escalating to senior mod"}},
            {"type": "session.send", "timestamp": "2026-02-28T20:00:06Z", "agent_name": "escalation-agent", "data": {"verdict": "warning", "reason": "First offense, toxic language"}},
            {"type": "message.sent", "timestamp": "2026-02-28T20:00:07Z", "agent_name": "moderator-agent", "channel": "discord", "data": {"text": "⚠️ Warning: Please keep discussions respectful. Continued violations may result in a timeout."}, "token_count": 25},
        ],
        "elevated_mode": False, "sandbox_enabled": True,
    },
    # T3: Telegram booking assistant
    {
        "session_id": "sess-t3", "instance_id": "inst-prod",
        "agent_name": "booking-agent", "channel": "telegram", "inbox_type": "dm",
        "status": "completed",
        "agents_mapping": {"booking-agent": {"model": "claude-sonnet-4-20250514", "persona": "Restaurant booking assistant for GourmetPlace. Handle reservations, cancellations, and menu queries."}},
        "events": [
            {"type": "message.received", "timestamp": "2026-02-28T18:00:00Z", "agent_name": "booking-agent", "channel": "telegram", "data": {"text": "/book Saturday 7pm for 4 people"}, "token_count": 12},
            {"type": "agent.turn", "timestamp": "2026-02-28T18:00:01Z", "agent_name": "booking-agent", "data": {"thinking": "Booking request: Saturday, 19:00, 4 guests"}, "token_count": 35},
            {"type": "tool.call", "timestamp": "2026-02-28T18:00:02Z", "agent_name": "booking-agent", "tool_name": "check_availability", "tool_input": {"date": "2026-03-07", "time": "19:00", "party_size": 4}},
            {"type": "tool.result", "timestamp": "2026-02-28T18:00:03Z", "agent_name": "booking-agent", "tool_name": "check_availability", "tool_result": {"available": True, "table": "T12", "section": "patio"}},
            {"type": "tool.call", "timestamp": "2026-02-28T18:00:04Z", "agent_name": "booking-agent", "tool_name": "create_booking", "tool_input": {"date": "2026-03-07", "time": "19:00", "party_size": 4, "table": "T12"}},
            {"type": "tool.result", "timestamp": "2026-02-28T18:00:05Z", "agent_name": "booking-agent", "tool_name": "create_booking", "tool_result": {"booking_id": "BK-2026-0307-004", "confirmed": True}},
            {"type": "message.sent", "timestamp": "2026-02-28T18:00:06Z", "agent_name": "booking-agent", "channel": "telegram", "data": {"text": "✅ Booking confirmed!\n📅 Sat March 7, 7:00 PM\n👥 4 guests\n🪑 Patio (Table 12)\nRef: BK-2026-0307-004"}, "token_count": 40},
        ],
        "elevated_mode": False, "sandbox_enabled": True,
    },
    # T4: Web-based RAG knowledge bot
    {
        "session_id": "sess-t4", "instance_id": "inst-prod",
        "agent_name": "knowledge-agent", "channel": "web", "inbox_type": "dm",
        "status": "completed",
        "agents_mapping": {"knowledge-agent": {"model": "claude-sonnet-4-20250514", "persona": "Enterprise knowledge assistant. Answer questions using internal documentation only. Always cite sources."}},
        "events": [
            {"type": "message.received", "timestamp": "2026-02-28T14:00:00Z", "agent_name": "knowledge-agent", "channel": "web", "data": {"text": "What is our data retention policy for GDPR compliance?"}, "token_count": 18},
            {"type": "agent.turn", "timestamp": "2026-02-28T14:00:01Z", "agent_name": "knowledge-agent", "data": {"thinking": "GDPR data retention query, retrieving relevant docs"}, "token_count": 45},
            {"type": "tool.call", "timestamp": "2026-02-28T14:00:02Z", "agent_name": "knowledge-agent", "tool_name": "retrieve_documents", "tool_input": {"query": "GDPR data retention policy", "top_k": 5}},
            {"type": "tool.result", "timestamp": "2026-02-28T14:00:04Z", "agent_name": "knowledge-agent", "tool_name": "retrieve_documents", "tool_result": {"documents": [{"title": "Data Retention Policy v3.2", "content": "Personal data must be deleted within 30 days of account closure...", "source": "compliance/data-retention.md"}]}},
            {"type": "message.sent", "timestamp": "2026-02-28T14:00:06Z", "agent_name": "knowledge-agent", "channel": "web", "data": {"text": "According to our Data Retention Policy v3.2, personal data must be deleted within 30 days of account closure. For active accounts, data is retained for the duration of the service agreement plus 90 days.\n\nSource: compliance/data-retention.md"}, "token_count": 80},
        ],
        "elevated_mode": False, "sandbox_enabled": True,
    },
    # T5: Multi-agent research pipeline (spawned sessions)
    {
        "session_id": "sess-t5", "instance_id": "inst-prod",
        "agent_name": "coordinator", "channel": "web", "inbox_type": "dm",
        "status": "completed",
        "agents_mapping": {
            "coordinator": {"model": "claude-sonnet-4-20250514", "persona": "Research coordinator. Decompose questions, delegate to specialists, synthesize results."},
            "researcher-market": {"model": "claude-haiku-4-5-20251001", "persona": "Market research specialist."},
            "researcher-tech": {"model": "claude-haiku-4-5-20251001", "persona": "Technical research specialist."},
        },
        "spawned_sessions": ["sess-t5-market", "sess-t5-tech"],
        "events": [
            {"type": "message.received", "timestamp": "2026-02-28T11:00:00Z", "agent_name": "coordinator", "channel": "web", "data": {"text": "Analyze the competitive landscape for AI agent platforms"}, "token_count": 15},
            {"type": "agent.turn", "timestamp": "2026-02-28T11:00:01Z", "agent_name": "coordinator", "data": {"thinking": "Complex question, decomposing into market and technical research"}, "token_count": 60},
            {"type": "session.spawn", "timestamp": "2026-02-28T11:00:02Z", "agent_name": "coordinator", "data": {"child_session": "sess-t5-market", "task": "Market size, key players, growth trends for AI agent platforms"}},
            {"type": "session.spawn", "timestamp": "2026-02-28T11:00:03Z", "agent_name": "coordinator", "data": {"child_session": "sess-t5-tech", "task": "Technical capabilities comparison: LangGraph, CrewAI, AutoGen, OpenClaw"}},
            {"type": "session.send", "timestamp": "2026-02-28T11:00:15Z", "agent_name": "researcher-market", "data": {"result": "Market analysis: $2.4B TAM, key players include..."}},
            {"type": "session.send", "timestamp": "2026-02-28T11:00:18Z", "agent_name": "researcher-tech", "data": {"result": "Technical comparison: LangGraph excels at..."}},
            {"type": "agent.turn", "timestamp": "2026-02-28T11:00:19Z", "agent_name": "coordinator", "data": {"thinking": "Both researchers returned, synthesizing results"}, "token_count": 80},
            {"type": "message.sent", "timestamp": "2026-02-28T11:00:22Z", "agent_name": "coordinator", "channel": "web", "data": {"text": "## AI Agent Platform Competitive Landscape\n\n### Market Overview\n$2.4B TAM...\n\n### Technical Comparison\nLangGraph excels at..."}, "token_count": 200},
        ],
        "elevated_mode": False, "sandbox_enabled": True,
    },
    # T6: Escalation bot (elevated mode)
    {
        "session_id": "sess-t6", "instance_id": "inst-prod",
        "agent_name": "admin-agent", "channel": "web", "inbox_type": "dm",
        "status": "completed",
        "agents_mapping": {"admin-agent": {"model": "claude-sonnet-4-20250514", "persona": "Account admin assistant. Handle password resets, account merges, and permission changes after identity verification."}},
        "events": [
            {"type": "message.received", "timestamp": "2026-02-28T15:00:00Z", "agent_name": "admin-agent", "channel": "web", "data": {"text": "I need to reset my password, I'm locked out"}, "token_count": 15},
            {"type": "agent.turn", "timestamp": "2026-02-28T15:00:01Z", "agent_name": "admin-agent", "data": {"thinking": "Password reset request, need to verify identity first"}, "token_count": 40},
            {"type": "tool.call", "timestamp": "2026-02-28T15:00:02Z", "agent_name": "admin-agent", "tool_name": "verify_identity", "tool_input": {"method": "email_otp", "email": "user@company.com"}},
            {"type": "tool.result", "timestamp": "2026-02-28T15:00:10Z", "agent_name": "admin-agent", "tool_name": "verify_identity", "tool_result": {"verified": True, "user_id": "usr-789", "method": "email_otp"}},
            {"type": "agent.turn", "timestamp": "2026-02-28T15:00:11Z", "agent_name": "admin-agent", "data": {"thinking": "Identity verified, proceeding with elevated action"}, "token_count": 30},
            {"type": "tool.call", "timestamp": "2026-02-28T15:00:12Z", "agent_name": "admin-agent", "tool_name": "reset_password", "tool_input": {"user_id": "usr-789", "method": "temporary_link"}},
            {"type": "tool.result", "timestamp": "2026-02-28T15:00:13Z", "agent_name": "admin-agent", "tool_name": "reset_password", "tool_result": {"success": True, "reset_link_sent": True, "expires_in": "15m"}},
            {"type": "message.sent", "timestamp": "2026-02-28T15:00:14Z", "agent_name": "admin-agent", "channel": "web", "data": {"text": "Identity verified! A password reset link has been sent to your email. It expires in 15 minutes."}, "token_count": 35},
        ],
        "elevated_mode": True, "sandbox_enabled": True,
    },
    # T7: Content moderation pipeline
    {
        "session_id": "sess-t7", "instance_id": "inst-prod",
        "agent_name": "classifier-agent", "channel": "discord", "inbox_type": "group",
        "status": "completed",
        "agents_mapping": {
            "classifier-agent": {"model": "claude-haiku-4-5-20251001", "persona": "Fast content classifier. Categorize content as safe, borderline, or violation."},
            "reviewer-agent": {"model": "claude-sonnet-4-20250514", "persona": "Content review specialist. Make final moderation decisions on borderline content."},
        },
        "spawned_sessions": ["sess-t7-review"],
        "events": [
            {"type": "message.received", "timestamp": "2026-02-28T21:00:00Z", "agent_name": "classifier-agent", "channel": "discord", "data": {"text": "Check out this amazing deal at www.totallylegit.com/free-stuff", "server_id": "srv-community"}, "token_count": 18},
            {"type": "agent.turn", "timestamp": "2026-02-28T21:00:01Z", "agent_name": "classifier-agent", "data": {"thinking": "Potential spam/phishing link"}, "token_count": 25},
            {"type": "tool.call", "timestamp": "2026-02-28T21:00:02Z", "agent_name": "classifier-agent", "tool_name": "analyze_content", "tool_input": {"text": "Check out this amazing deal at www.totallylegit.com/free-stuff", "check_urls": True}},
            {"type": "tool.result", "timestamp": "2026-02-28T21:00:03Z", "agent_name": "classifier-agent", "tool_name": "analyze_content", "tool_result": {"classification": "borderline", "spam_score": 0.72, "url_reputation": "unknown"}},
            {"type": "session.spawn", "timestamp": "2026-02-28T21:00:04Z", "agent_name": "classifier-agent", "data": {"child_session": "sess-t7-review", "reason": "Borderline content, needs human-level review"}},
            {"type": "session.send", "timestamp": "2026-02-28T21:00:07Z", "agent_name": "reviewer-agent", "data": {"verdict": "remove", "reason": "Suspicious URL pattern, likely spam"}},
            {"type": "message.sent", "timestamp": "2026-02-28T21:00:08Z", "agent_name": "classifier-agent", "channel": "discord", "data": {"text": "🚫 Message removed: Suspicious link detected. If this was a mistake, contact a moderator."}, "token_count": 25},
        ],
        "elevated_mode": False, "sandbox_enabled": True,
    },
    # T8: Internal helpdesk (Slack groups)
    {
        "session_id": "sess-t8", "instance_id": "inst-prod",
        "agent_name": "helpdesk-agent", "channel": "slack", "inbox_type": "group",
        "status": "completed",
        "agents_mapping": {"helpdesk-agent": {"model": "claude-sonnet-4-20250514", "persona": "IT helpdesk assistant. Troubleshoot common issues, create Jira tickets for complex problems."}},
        "events": [
            {"type": "message.received", "timestamp": "2026-02-28T08:30:00Z", "agent_name": "helpdesk-agent", "channel": "slack", "data": {"text": "My VPN keeps disconnecting every 10 minutes", "channel_name": "#it-help"}, "token_count": 14},
            {"type": "agent.turn", "timestamp": "2026-02-28T08:30:01Z", "agent_name": "helpdesk-agent", "data": {"thinking": "VPN disconnection issue, checking KB for common fixes"}, "token_count": 35},
            {"type": "tool.call", "timestamp": "2026-02-28T08:30:02Z", "agent_name": "helpdesk-agent", "tool_name": "search_knowledge_base", "tool_input": {"query": "VPN disconnecting frequently troubleshooting", "collection": "it-docs"}},
            {"type": "tool.result", "timestamp": "2026-02-28T08:30:03Z", "agent_name": "helpdesk-agent", "tool_name": "search_knowledge_base", "tool_result": {"documents": [{"title": "VPN Troubleshooting Guide", "content": "1. Check network adapter settings\n2. Update VPN client to v4.2+\n3. Disable IPv6 if on corporate WiFi"}]}},
            {"type": "tool.call", "timestamp": "2026-02-28T08:30:04Z", "agent_name": "helpdesk-agent", "tool_name": "create_ticket", "tool_input": {"project": "IT-SUPPORT", "summary": "VPN recurring disconnection", "priority": "medium", "reporter": "user-slack-id"}},
            {"type": "tool.result", "timestamp": "2026-02-28T08:30:05Z", "agent_name": "helpdesk-agent", "tool_name": "create_ticket", "tool_result": {"ticket_id": "IT-4521", "url": "https://jira.company.com/IT-4521"}},
            {"type": "message.sent", "timestamp": "2026-02-28T08:30:06Z", "agent_name": "helpdesk-agent", "channel": "slack", "data": {"text": "Here are some quick fixes to try:\n1. Check your network adapter settings\n2. Update VPN client to v4.2+\n3. Disable IPv6 on corporate WiFi\n\nI've also created <https://jira.company.com/IT-4521|IT-4521> to track this. Our team will follow up if the issue persists."}, "token_count": 65},
        ],
        "elevated_mode": False, "sandbox_enabled": True,
    },
    # T9: Multi-channel notification dispatcher
    {
        "session_id": "sess-t9", "instance_id": "inst-prod",
        "agent_name": "dispatcher-agent", "channel": "web", "inbox_type": "dm",
        "status": "completed",
        "agents_mapping": {"dispatcher-agent": {"model": "claude-haiku-4-5-20251001", "persona": "Notification dispatcher. Format and send alerts across multiple channels based on user preferences."}},
        "events": [
            {"type": "message.received", "timestamp": "2026-02-28T12:00:00Z", "agent_name": "dispatcher-agent", "channel": "web", "data": {"text": "Send deployment notification to the team", "deployment": {"version": "v2.4.1", "services": ["api", "worker"], "status": "success"}}},
            {"type": "agent.turn", "timestamp": "2026-02-28T12:00:01Z", "agent_name": "dispatcher-agent", "data": {"thinking": "Deployment notification, need to format for each channel and dispatch"}, "token_count": 40},
            {"type": "tool.call", "timestamp": "2026-02-28T12:00:02Z", "agent_name": "dispatcher-agent", "tool_name": "format_response", "tool_input": {"template": "deployment_success", "data": {"version": "v2.4.1", "services": ["api", "worker"]}, "channel": "slack"}},
            {"type": "tool.result", "timestamp": "2026-02-28T12:00:03Z", "agent_name": "dispatcher-agent", "tool_name": "format_response", "tool_result": {"formatted": "🚀 *Deployment v2.4.1* successful\n• `api` ✅\n• `worker` ✅"}},
            {"type": "tool.call", "timestamp": "2026-02-28T12:00:04Z", "agent_name": "dispatcher-agent", "tool_name": "send_message", "tool_input": {"channel": "slack", "target": "#deployments", "text": "🚀 *Deployment v2.4.1* successful\n• `api` ✅\n• `worker` ✅"}},
            {"type": "tool.result", "timestamp": "2026-02-28T12:00:05Z", "agent_name": "dispatcher-agent", "tool_name": "send_message", "tool_result": {"sent": True, "channel": "slack"}},
            {"type": "tool.call", "timestamp": "2026-02-28T12:00:06Z", "agent_name": "dispatcher-agent", "tool_name": "send_email", "tool_input": {"to": "eng-team@company.com", "subject": "Deployment v2.4.1 Success", "body": "Services api, worker deployed successfully."}},
            {"type": "tool.result", "timestamp": "2026-02-28T12:00:07Z", "agent_name": "dispatcher-agent", "tool_name": "send_email", "tool_result": {"sent": True, "message_id": "msg-abc123"}},
            {"type": "message.sent", "timestamp": "2026-02-28T12:00:08Z", "agent_name": "dispatcher-agent", "channel": "web", "data": {"text": "Deployment notification sent to Slack (#deployments) and email (eng-team@company.com)."}, "token_count": 30},
        ],
        "elevated_mode": False, "sandbox_enabled": True,
    },
]

# Channel + business domain pairs for scenario diversity
CHANNEL_DOMAINS = [
    ("whatsapp", "customer-support"), ("telegram", "booking"),
    ("slack", "internal-ops"), ("discord", "community"),
    ("web", "enterprise-saas"), ("whatsapp", "healthcare"),
    ("slack", "devops"), ("telegram", "education"),
    ("discord", "gaming"), ("web", "fintech"),
]


# ---------------------------------------------------------------------------
# Compact output key mapping
# ---------------------------------------------------------------------------

_COMPACT_KEYS = {
    "d": "input_data",
    "e": "expected_detected",
    "mn": "expected_confidence_min",
    "mx": "expected_confidence_max",
    "desc": "description",
    "t": "tags",
}

# Types that use full session JSON (larger output, smaller batch size)
_SESSION_TYPES = {
    "openclaw_session_loop", "openclaw_tool_abuse", "openclaw_elevated_risk",
    "openclaw_spawn_chain", "openclaw_channel_mismatch", "openclaw_sandbox_escape",
}


def _expand_compact_entry(item: Dict[str, Any]) -> Dict[str, Any]:
    """Expand abbreviated JSON keys to full field names."""
    expanded = {}
    for short, full in _COMPACT_KEYS.items():
        if short in item:
            expanded[full] = item[short]
    # Also accept full keys (in case model ignores compact format)
    for full in _COMPACT_KEYS.values():
        if full in item and full not in expanded:
            expanded[full] = item[full]
    return expanded


def _scenario_hash(entry: GoldenDatasetEntry) -> str:
    """Hash an entry's key characteristics for deduplication."""
    sig = json.dumps({
        "type": entry.detection_type.value,
        "detected": entry.expected_detected,
        "desc": entry.description[:80],
    }, sort_keys=True)
    return hashlib.md5(sig.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Generator class
# ---------------------------------------------------------------------------

class OpenClawGoldenDataGenerator(GoldenDataGenerator):
    """Generates OpenClaw-native golden dataset entries with token-optimized API calls.

    Optimizations over base class:
    - Prompt caching for OpenClaw vocabulary system message (~75% input savings)
    - Tiered model selection: Haiku for easy, Sonnet for medium/hard
    - Compact output format expanded client-side (~30% output savings)
    - Adaptive batch sizing: 8 for text types, 5 for session types
    - Incremental persistence with resume support
    """

    DIFFICULTY_MODELS = {
        "easy": "claude-haiku-4-5-20251001",
        "medium": "claude-sonnet-4-20250514",
        "hard": "claude-sonnet-4-20250514",
    }
    DIFFICULTY_TEMPERATURES = {
        "easy": 0.7,
        "medium": 0.8,
        "hard": 0.95,
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        easy_model: Optional[str] = None,
        hard_model: Optional[str] = None,
        use_cache: bool = True,
        delay_between_calls: float = 1.0,
    ):
        super().__init__(
            model="claude-sonnet-4-20250514",
            api_key=api_key,
            max_tokens=8192,
            temperature=0.8,
        )
        if easy_model:
            self.DIFFICULTY_MODELS["easy"] = easy_model
        if hard_model:
            self.DIFFICULTY_MODELS["medium"] = hard_model
            self.DIFFICULTY_MODELS["hard"] = hard_model
        self._use_cache = use_cache
        self._delay = delay_between_calls
        self._seen_hashes: set = set()
        # Override client with timeout to prevent hanging API calls
        if _HAS_ANTHROPIC and self._api_key:
            import httpx
            self._client = Anthropic(
                api_key=self._api_key,
                timeout=httpx.Timeout(120.0, connect=10.0),
            )
        self._call_count = 0
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._type_prompts: Optional[Dict] = None

    @property
    def type_prompts(self) -> Dict:
        """Lazy-load OpenClaw type prompts to avoid circular imports."""
        if self._type_prompts is None:
            try:
                from app.detection_enterprise.openclaw_type_prompts import OPENCLAW_TYPE_PROMPTS
                self._type_prompts = OPENCLAW_TYPE_PROMPTS
            except ImportError:
                logger.warning("openclaw_type_prompts not available, falling back to base TYPE_PROMPTS")
                from app.detection_enterprise.golden_data_generator import TYPE_PROMPTS
                self._type_prompts = TYPE_PROMPTS
        return self._type_prompts

    # ------------------------------------------------------------------
    # Overridden LLM call with caching + tiered models
    # ------------------------------------------------------------------

    def _call_llm_for_difficulty(self, prompt: str, difficulty: str = "medium") -> Tuple[str, Dict[str, int]]:
        """Call LLM with prompt caching and model selection per difficulty.

        Returns:
            Tuple of (response_text, usage_dict)
        """
        if not self.client:
            logger.error("Anthropic client not available")
            return "", {"input_tokens": 0, "output_tokens": 0}

        model = self.DIFFICULTY_MODELS.get(difficulty, self.model)
        temperature = self.DIFFICULTY_TEMPERATURES.get(difficulty, self.temperature)

        system_blocks = []
        if self._use_cache:
            system_blocks = [{
                "type": "text",
                "text": OPENCLAW_SYSTEM_MESSAGE,
                "cache_control": {"type": "ephemeral"},
            }]
        else:
            system_blocks = [{
                "type": "text",
                "text": OPENCLAW_SYSTEM_MESSAGE,
            }]

        try:
            if self._delay > 0 and self._call_count > 0:
                time.sleep(self._delay)

            response = self.client.messages.create(
                model=model,
                max_tokens=self.max_tokens,
                temperature=temperature,
                system=system_blocks,
                messages=[{"role": "user", "content": prompt}],
            )

            self._call_count += 1
            usage = {
                "input_tokens": getattr(response.usage, "input_tokens", 0),
                "output_tokens": getattr(response.usage, "output_tokens", 0),
            }
            self._total_input_tokens += usage["input_tokens"]
            self._total_output_tokens += usage["output_tokens"]

            text = response.content[0].text

            # Detect truncation
            stop_reason = getattr(response, "stop_reason", None)
            if stop_reason == "max_tokens":
                logger.warning(
                    "Response truncated (max_tokens=%d, output=%d tokens). "
                    "Attempting to salvage partial JSON.",
                    self.max_tokens, usage["output_tokens"],
                )
                text = self._salvage_truncated_json(text)

            return text, usage

        except Exception as exc:
            logger.error("LLM call failed (model=%s): %s", model, exc)
            return "", {"input_tokens": 0, "output_tokens": 0}

    @staticmethod
    def _salvage_truncated_json(text: str) -> str:
        """Attempt to close a truncated JSON array so we can parse partial entries."""
        import re
        stripped = text.rstrip()
        # Strip markdown fences if present
        stripped = re.sub(r'^```(?:json)?\s*\n?', '', stripped)
        stripped = re.sub(r'\n?```\s*$', '', stripped)
        stripped = stripped.strip()

        if not stripped.startswith("["):
            return text

        # Find the last complete object (ends with })
        last_brace = stripped.rfind("}")
        if last_brace > 0:
            candidate = stripped[:last_brace + 1] + "]"
            try:
                json.loads(candidate)
                logger.info("Salvaged %d chars of truncated JSON", len(candidate))
                return candidate
            except json.JSONDecodeError:
                # Try progressively shorter cuts
                for i in range(3):
                    prev_brace = stripped.rfind("}", 0, last_brace)
                    if prev_brace > 0:
                        last_brace = prev_brace
                        candidate = stripped[:last_brace + 1] + "]"
                        try:
                            json.loads(candidate)
                            logger.info("Salvaged %d chars after %d cuts", len(candidate), i + 1)
                            return candidate
                        except json.JSONDecodeError:
                            continue

        return text

    def _call_llm(self, prompt: str) -> str:
        """Override base class — routes through difficulty-aware call."""
        text, _ = self._call_llm_for_difficulty(prompt, self._current_difficulty)
        return text

    # ------------------------------------------------------------------
    # Overridden prompt builder
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        detection_type: DetectionType,
        count: int,
        n_positive: int,
        n_negative: int,
        examples: List[GoldenDatasetEntry],
        difficulty: str = "easy",
        domain: Optional[str] = None,
    ) -> str:
        """Build OpenClaw-specific generation prompt with compact output format."""
        type_key = detection_type.value
        type_info = self.type_prompts.get(type_key)
        if not type_info:
            # Fall back to base TYPE_PROMPTS
            from app.detection_enterprise.golden_data_generator import TYPE_PROMPTS
            type_info = TYPE_PROMPTS.get(type_key)
            if not type_info:
                raise ValueError(f"No prompt template for detection type: {type_key}")

        # Few-shot examples (compact)
        examples_block = ""
        if examples:
            example_items = []
            for ex in examples[:2]:  # Max 2 examples to save tokens
                example_items.append(json.dumps({
                    "d": ex.input_data,
                    "e": ex.expected_detected,
                    "mn": ex.expected_confidence_min,
                    "mx": ex.expected_confidence_max,
                    "desc": ex.description,
                    "t": ex.tags[:2],
                }, separators=(",", ":")))
            examples_block = "\n\nExisting examples (create NEW scenarios):\n" + "\n".join(example_items)

        difficulty_instruction = DIFFICULTY_INSTRUCTIONS.get(difficulty, DIFFICULTY_INSTRUCTIONS["easy"])

        # Domain/channel injection for diversity
        domain_instruction = ""
        if domain:
            # domain is a tuple-like string "channel,business"
            parts = domain.split(",") if "," in domain else [domain]
            if len(parts) == 2:
                domain_instruction = f"\nChannel: {parts[0]}. Business domain: {parts[1]}. Use these for realistic context.\n"
            else:
                domain_instruction = f"\nBusiness domain for these scenarios: {domain}. Use this domain for realistic context.\n"

        # Session template reference for session-heavy types
        template_instruction = ""
        if type_key in _SESSION_TYPES:
            template_instruction = (
                "\nYou may base session structures on the templates from the system message "
                "(modify them — change agent names, add/remove events, alter tools used). "
                "Do NOT copy templates verbatim.\n"
            )

        # OpenClaw context from type prompts
        oc_context = type_info.get("openclaw_context", "")
        oc_context_block = f"\n## OpenClaw Context\n{oc_context}\n" if oc_context else ""

        prompt = f"""## Detection Type: {type_key}

{type_info['description']}

## Difficulty: {difficulty.upper()}
{difficulty_instruction}

## Schema
input_data must match: {type_info['schema']}

## Positive (e=true): {type_info['positive_desc']}
## Negative (e=false): {type_info['negative_desc']}
{oc_context_block}{domain_instruction}{template_instruction}{examples_block}

Generate {count} samples ({n_positive} positive, {n_negative} negative).
Positive: mn 0.4-0.85, mx 0.6-0.99. Negative: mn 0.0-0.1, mx 0.15-0.35.
Use compact format: {{"d":..,"e":..,"mn":..,"mx":..,"desc":"..","t":[..]}}
Return ONLY a JSON array."""

        return prompt

    # ------------------------------------------------------------------
    # Parse with compact key expansion
    # ------------------------------------------------------------------

    def _parse_entries(
        self,
        raw_response: str,
        detection_type: DetectionType,
    ) -> List[GoldenDatasetEntry]:
        """Parse LLM response, expanding compact keys."""
        parsed = _parse_json(raw_response)
        if parsed is None:
            logger.error(
                "Failed to parse JSON for %s (response length=%d, first 200 chars: %s)",
                detection_type.value, len(raw_response), raw_response[:200],
            )
            return []

        if isinstance(parsed, dict):
            for key in ("entries", "samples", "data", "results"):
                if key in parsed and isinstance(parsed[key], list):
                    parsed = parsed[key]
                    break
            else:
                parsed = [parsed]

        if not isinstance(parsed, list):
            logger.error("Parsed JSON is not a list for %s", detection_type.value)
            return []

        entries: List[GoldenDatasetEntry] = []
        for item in parsed:
            try:
                if not isinstance(item, dict):
                    continue

                expanded = _expand_compact_entry(item)
                input_data = expanded.get("input_data")
                if input_data is None:
                    continue

                expected_detected = bool(expanded.get("expected_detected", False))
                conf_min = float(expanded.get("expected_confidence_min", 0.0))
                conf_max = float(expanded.get("expected_confidence_max", 1.0))
                conf_min = max(0.0, min(1.0, conf_min))
                conf_max = max(conf_min, min(1.0, conf_max))

                description = str(expanded.get("description", ""))
                tags = expanded.get("tags", [])
                if not isinstance(tags, list):
                    tags = [str(tags)]
                tags = [str(t) for t in tags]
                tags.append("openclaw")  # Mark all as openclaw-native

                entry_id = f"oc_{detection_type.value}_gen_{uuid.uuid4().hex[:8]}"

                entry = GoldenDatasetEntry(
                    id=entry_id,
                    detection_type=detection_type,
                    input_data=input_data,
                    expected_detected=expected_detected,
                    expected_confidence_min=conf_min,
                    expected_confidence_max=conf_max,
                    description=description,
                    source="llm_generated",
                    tags=tags,
                    augmentation_method=f"claude_openclaw_{self._current_difficulty}",
                    human_verified=False,
                    difficulty=self._current_difficulty,
                )

                # Deduplication check
                h = _scenario_hash(entry)
                if h in self._seen_hashes:
                    logger.debug("Skipping duplicate entry for %s", detection_type.value)
                    continue
                self._seen_hashes.add(h)

                entries.append(entry)

            except Exception as exc:
                logger.warning("Skipping malformed entry for %s: %s", detection_type.value, exc)
                continue

        return entries

    # ------------------------------------------------------------------
    # Batch generation with incremental save
    # ------------------------------------------------------------------

    def generate_batch(
        self,
        detection_types: Optional[List[DetectionType]] = None,
        target_per_type: int = 100,
        difficulty_distribution: Tuple[float, float, float] = (0.20, 0.45, 0.35),
        output_path: Optional[Path] = None,
        resume: bool = False,
        batch_size: Optional[int] = None,
        db_session=None,
    ) -> Dict[str, Any]:
        """Generate entries for multiple detection types with incremental persistence.

        Args:
            detection_types: Types to generate (default: all DetectionType values).
            target_per_type: Target entries per type.
            difficulty_distribution: (easy, medium, hard) fractions summing to 1.0.
            output_path: Path to save output JSON incrementally.
            resume: If True, load existing output and skip types at target.
            batch_size: Override entries per API call (default: auto).
            db_session: Optional AsyncSession for writing entries directly to DB.

        Returns:
            Stats dict with per-type results and total token usage.
        """
        if not self.is_available:
            logger.error("Generator not available (missing SDK or API key)")
            return {"error": "not_available"}

        types = detection_types or list(DetectionType)
        e_frac, m_frac, h_frac = difficulty_distribution

        # Load existing dataset for resume
        dataset = GoldenDataset()
        if resume and output_path and output_path.exists():
            dataset.load(output_path)
            # Seed dedup hashes from existing entries
            for entry in dataset.entries.values():
                self._seen_hashes.add(_scenario_hash(entry))
            logger.info("Resumed: loaded %d existing entries", len(dataset.entries))

        stats: Dict[str, Any] = {}
        total_generated = 0
        domain_idx = 0

        for type_idx, dt in enumerate(types):
            type_key = dt.value

            # Check how many we already have for this type
            existing = dataset.get_entries_by_type(dt)
            existing_oc = [e for e in existing if "openclaw" in e.tags]
            current_count = len(existing_oc)

            if current_count >= target_per_type:
                logger.info(
                    "[%d/%d] %s: already at %d/%d, skipping",
                    type_idx + 1, len(types), type_key, current_count, target_per_type,
                )
                stats[type_key] = {"skipped": True, "existing": current_count}
                continue

            needed = target_per_type - current_count
            n_easy = max(2, round(needed * e_frac))
            n_hard = max(2, round(needed * h_frac))
            n_medium = needed - n_easy - n_hard

            # Adaptive batch size — keep small to avoid output truncation
            bs = batch_size or (5 if type_key in _SESSION_TYPES else 8)

            type_stats = {"generated": 0, "errors": 0, "retries": 0}

            for difficulty, count in [("easy", n_easy), ("medium", n_medium), ("hard", n_hard)]:
                if count <= 0:
                    continue

                self._current_difficulty = difficulty
                remaining = count

                while remaining > 0:
                    batch_count = min(bs, remaining)
                    n_pos = (batch_count + 1) // 2
                    n_neg = batch_count - n_pos

                    # Rotate channel + business domain
                    channel, biz = CHANNEL_DOMAINS[domain_idx % len(CHANNEL_DOMAINS)]
                    domain = f"{channel},{biz}"
                    domain_idx += 1

                    prompt = self._build_prompt(
                        detection_type=dt,
                        count=batch_count,
                        n_positive=n_pos,
                        n_negative=n_neg,
                        examples=existing[:3],
                        difficulty=difficulty,
                        domain=domain,
                    )

                    logger.info(
                        "[%d/%d] %s %s: generating %d (need %d more)...",
                        type_idx + 1, len(types), type_key, difficulty,
                        batch_count, remaining,
                    )

                    raw, usage = self._call_llm_for_difficulty(prompt, difficulty)
                    if not raw:
                        type_stats["errors"] += 1
                        remaining -= batch_count  # Don't retry infinitely
                        continue

                    entries = self._parse_entries(raw, dt)

                    # Validate entries
                    valid_entries = []
                    invalid_errors = []
                    try:
                        from app.detection_enterprise.input_schemas import validate_input
                        for entry in entries:
                            ok, err = validate_input(dt.value, entry.input_data)
                            if ok:
                                valid_entries.append(entry)
                            else:
                                invalid_errors.append(err)
                    except ImportError:
                        valid_entries = entries

                    # OpenClaw-specific validation
                    try:
                        from app.detection_enterprise.openclaw_session_validator import validate_openclaw_input_data
                        further_valid = []
                        for entry in valid_entries:
                            ok, err = validate_openclaw_input_data(dt.value, entry.input_data)
                            if ok:
                                further_valid.append(entry)
                            else:
                                invalid_errors.append(f"openclaw: {err}")
                        valid_entries = further_valid
                    except ImportError:
                        pass  # Validator not yet available

                    # Retry invalid entries once
                    if invalid_errors and len(valid_entries) < batch_count:
                        type_stats["retries"] += 1
                        retry_entries = self._retry_with_feedback(
                            dt, batch_count - len(valid_entries),
                            invalid_errors, existing[:2],
                        )
                        valid_entries.extend(retry_entries)

                    # Add to dataset
                    for entry in valid_entries:
                        dataset.add_entry(entry)
                        existing.append(entry)

                    type_stats["generated"] += len(valid_entries)
                    total_generated += len(valid_entries)
                    remaining -= len(valid_entries) if valid_entries else batch_count

                    # Incremental save after each batch
                    if output_path and valid_entries:
                        dataset.save(output_path)
                        logger.debug("Saved %d total entries to %s", len(dataset.entries), output_path)

                    # Write to DB if session provided
                    if db_session and valid_entries:
                        self._save_entries_to_db(db_session, valid_entries)

            stats[type_key] = type_stats
            logger.info(
                "[%d/%d] %s: done — %d generated, %d errors, %d retries",
                type_idx + 1, len(types), type_key,
                type_stats["generated"], type_stats["errors"], type_stats["retries"],
            )

        # Final save
        if output_path:
            dataset.save(output_path)

        # Token usage summary
        stats["_summary"] = {
            "total_generated": total_generated,
            "total_entries": len(dataset.entries),
            "api_calls": self._call_count,
            "input_tokens": self._total_input_tokens,
            "output_tokens": self._total_output_tokens,
            "estimated_cost_usd": round(
                self._total_input_tokens * 3e-6 + self._total_output_tokens * 15e-6, 2
            ),
        }

        logger.info(
            "Generation complete: %d entries, %d API calls, ~$%.2f estimated cost",
            total_generated, self._call_count, stats["_summary"]["estimated_cost_usd"],
        )
        return stats

    def dry_run(
        self,
        detection_types: Optional[List[DetectionType]] = None,
        target_per_type: int = 100,
        difficulty_distribution: Tuple[float, float, float] = (0.20, 0.45, 0.35),
        existing_dataset: Optional[GoldenDataset] = None,
    ) -> Dict[str, Any]:
        """Estimate what would be generated without calling the API."""
        types = detection_types or list(DetectionType)
        e_frac, m_frac, h_frac = difficulty_distribution

        plan = {}
        total_calls = 0
        total_entries = 0

        for dt in types:
            existing = []
            if existing_dataset:
                existing = [e for e in existing_dataset.get_entries_by_type(dt) if "openclaw" in e.tags]

            current = len(existing)
            if current >= target_per_type:
                plan[dt.value] = {"status": "skip", "existing": current}
                continue

            needed = target_per_type - current
            n_easy = max(2, round(needed * e_frac))
            n_hard = max(2, round(needed * h_frac))
            n_medium = needed - n_easy - n_hard

            bs = 5 if dt.value in _SESSION_TYPES else 8
            calls = sum(
                max(1, (n + bs - 1) // bs)
                for n in [n_easy, n_medium, n_hard] if n > 0
            )

            plan[dt.value] = {
                "status": "generate",
                "existing": current,
                "needed": needed,
                "easy": n_easy,
                "medium": n_medium,
                "hard": n_hard,
                "api_calls": calls,
            }
            total_calls += calls
            total_entries += needed

        # Cost estimate (rough)
        avg_input_tokens = 2000
        avg_output_tokens = 7000
        total_input = total_calls * avg_input_tokens
        total_output = total_calls * avg_output_tokens
        cost = total_input * 3e-6 + total_output * 15e-6

        plan["_summary"] = {
            "total_entries_to_generate": total_entries,
            "total_api_calls": total_calls,
            "estimated_input_tokens": total_input,
            "estimated_output_tokens": total_output,
            "estimated_cost_usd": round(cost, 2),
        }

        return plan

    @staticmethod
    def _save_entries_to_db(db_session, entries):
        """Save generated entries to database via repository."""
        import asyncio
        from app.storage.golden_dataset_repo import GoldenDatasetRepository, dataclass_to_model

        async def _do_save():
            repo = GoldenDatasetRepository(db_session)
            models = [dataclass_to_model(e) for e in entries]
            inserted = await repo.add_entries_bulk(models)
            await db_session.commit()
            logger.info("Saved %d entries to database", inserted)

        try:
            loop = asyncio.get_running_loop()
            loop.run_until_complete(_do_save())
        except RuntimeError:
            asyncio.run(_do_save())
