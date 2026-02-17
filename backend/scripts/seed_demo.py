#!/usr/bin/env python3
"""
Seed the database with demo data for presentations and testing.

Usage:
    python scripts/seed_demo.py

This creates:
- 1 demo tenant with API key
- 20 traces (mix of healthy and failing)
- States for each trace
- Detections for failing traces
"""

import asyncio
import hashlib
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
import random

import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.storage.models import Base, Tenant, Trace, State, Detection, ApiKey


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/mao_testing"
)

DEMO_TENANT_NAME = "Demo Organization"
DEMO_API_KEY = "mao_demo_key_12345"


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def random_choice(items):
    return random.choice(items)


def random_int(min_val, max_val):
    return random.randint(min_val, max_val)


def random_date(hours_ago: int = 48) -> datetime:
    delta = timedelta(hours=random.uniform(0, hours_ago))
    return datetime.now(timezone.utc) - delta


FRAMEWORKS = ["langgraph", "crewai", "n8n"]
AGENTS = ["researcher", "analyst", "writer", "coordinator", "validator"]
DETECTION_TYPES = ["infinite_loop", "state_corruption", "persona_drift", "coordination_deadlock"]
DETECTION_METHODS = ["structural_match", "hash_collision", "semantic_analysis", "embedding_cluster"]


def create_demo_tenant() -> Dict[str, Any]:
    tenant_id = uuid.uuid4()
    return {
        "id": tenant_id,
        "name": DEMO_TENANT_NAME,
        "api_key_hash": hash_key(DEMO_API_KEY),
        "settings": {"demo": True},
    }


def create_demo_api_key(tenant_id: uuid.UUID) -> Dict[str, Any]:
    return {
        "id": uuid.uuid4(),
        "tenant_id": tenant_id,
        "name": "Demo API Key",
        "key_hash": hash_key(DEMO_API_KEY),
        "key_prefix": DEMO_API_KEY[:8],
    }


def create_healthy_trace(tenant_id: uuid.UUID) -> Dict[str, Any]:
    created = random_date(48)
    completed = created + timedelta(seconds=random_int(2, 30))
    return {
        "id": uuid.uuid4(),
        "tenant_id": tenant_id,
        "session_id": f"session-{secrets.token_hex(8)}",
        "framework": random_choice(FRAMEWORKS),
        "status": "completed",
        "total_tokens": random_int(1000, 15000),
        "total_cost_cents": random_int(5, 50),
        "created_at": created,
        "completed_at": completed,
    }


def create_failing_trace(tenant_id: uuid.UUID, failure_type: str) -> Dict[str, Any]:
    created = random_date(48)
    duration = random_int(30, 300) if failure_type == "infinite_loop" else random_int(5, 60)
    return {
        "id": uuid.uuid4(),
        "tenant_id": tenant_id,
        "session_id": f"session-{secrets.token_hex(8)}",
        "framework": random_choice(FRAMEWORKS),
        "status": "failed",
        "total_tokens": random_int(10000, 100000) if failure_type == "infinite_loop" else random_int(2000, 20000),
        "total_cost_cents": random_int(50, 500) if failure_type == "infinite_loop" else random_int(10, 100),
        "created_at": created,
        "completed_at": created + timedelta(seconds=duration),
        "_failure_type": failure_type,
    }


def create_states_for_trace(trace: Dict[str, Any], count: int) -> List[Dict[str, Any]]:
    states = []
    base_time = trace["created_at"]
    
    for i in range(count):
        states.append({
            "id": uuid.uuid4(),
            "trace_id": trace["id"],
            "tenant_id": trace["tenant_id"],
            "sequence_num": i + 1,
            "agent_id": random_choice(AGENTS),
            "state_delta": {
                "action": random_choice(["query", "search", "analyze", "generate", "validate"]),
                "input": f"Input for step {i+1}",
                "output": f"Output from step {i+1}",
            },
            "state_hash": secrets.token_hex(32),
            "token_count": random_int(50, 500),
            "latency_ms": random_int(100, 2000),
            "created_at": base_time + timedelta(milliseconds=i * random_int(500, 3000)),
        })
    
    return states


def create_loop_states(trace: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Create states that show a loop pattern."""
    states = []
    base_time = trace["created_at"]
    loop_agents = ["researcher", "analyst"]
    loop_hash = secrets.token_hex(32)
    
    for i in range(15):
        agent = loop_agents[i % 2]
        states.append({
            "id": uuid.uuid4(),
            "trace_id": trace["id"],
            "tenant_id": trace["tenant_id"],
            "sequence_num": i + 1,
            "agent_id": agent,
            "state_delta": {
                "action": "handoff" if i > 0 else "start",
                "message": f"Processing iteration {i // 2 + 1}",
            },
            "state_hash": loop_hash if i > 4 else secrets.token_hex(32),
            "token_count": random_int(100, 300),
            "latency_ms": random_int(500, 1500),
            "created_at": base_time + timedelta(seconds=i * 2),
        })
    
    return states


def create_detection(trace: Dict[str, Any], state_id: uuid.UUID = None) -> Dict[str, Any]:
    failure_type = trace.get("_failure_type", random_choice(DETECTION_TYPES))
    
    details = {}
    if failure_type == "infinite_loop":
        details = {
            "loop_length": random_int(5, 15),
            "affected_agents": ["researcher", "analyst"],
            "iterations": random_int(7, 50),
            "severity": "high",
            "message": "Agents stuck in repetitive cycle",
        }
    elif failure_type == "state_corruption":
        details = {
            "corrupted_fields": ["response", "context"],
            "null_injection": True,
            "severity": "high",
            "message": "Data integrity violation detected",
        }
    elif failure_type == "persona_drift":
        details = {
            "agent_name": "writer",
            "expected_tone": "professional",
            "actual_tone": "casual",
            "drift_score": random_int(70, 95) / 100,
            "severity": "medium",
            "message": "Agent behavior diverged from specification",
        }
    else:
        details = {
            "waiting_agents": ["planner", "executor"],
            "wait_duration_ms": random_int(30000, 120000),
            "severity": "high",
            "message": "Circular dependency detected",
        }
    
    return {
        "id": uuid.uuid4(),
        "tenant_id": trace["tenant_id"],
        "trace_id": trace["id"],
        "state_id": state_id,
        "detection_type": failure_type,
        "confidence": random_int(75, 98),
        "method": random_choice(DETECTION_METHODS),
        "details": details,
        "validated": random.random() > 0.5,
        "false_positive": False,
        "created_at": trace["created_at"] + timedelta(seconds=random_int(1, 10)),
    }


async def seed_database():
    """Seed the database with demo data."""
    print("=" * 60)
    print("MAO Testing Platform - Database Seeder")
    print("=" * 60)
    
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        result = await session.execute(
            text("SELECT id FROM tenants WHERE name = :name"),
            {"name": DEMO_TENANT_NAME}
        )
        existing = result.scalar()
        
        if existing:
            print(f"\nDemo tenant already exists (id: {existing})")
            print("Clearing existing demo data...")
            
            await session.execute(
                text("DELETE FROM detections WHERE tenant_id = :tid"),
                {"tid": str(existing)}
            )
            await session.execute(
                text("DELETE FROM states WHERE tenant_id = :tid"),
                {"tid": str(existing)}
            )
            await session.execute(
                text("DELETE FROM traces WHERE tenant_id = :tid"),
                {"tid": str(existing)}
            )
            await session.commit()
            
            tenant_id = existing
            print("Cleared existing traces, states, and detections.")
        else:
            tenant_data = create_demo_tenant()
            tenant_id = tenant_data["id"]
            
            await session.execute(
                text("""
                    INSERT INTO tenants (id, name, api_key_hash, settings, plan, span_limit, created_at)
                    VALUES (:id, :name, :api_key_hash, :settings, 'free', 10000, NOW())
                """),
                {
                    "id": str(tenant_id),
                    "name": tenant_data["name"],
                    "api_key_hash": tenant_data["api_key_hash"],
                    "settings": "{}",
                }
            )
            
            api_key_data = create_demo_api_key(tenant_id)
            await session.execute(
                text("""
                    INSERT INTO api_keys (id, tenant_id, name, key_hash, key_prefix, created_at)
                    VALUES (:id, :tenant_id, :name, :key_hash, :key_prefix, NOW())
                """),
                {
                    "id": str(api_key_data["id"]),
                    "tenant_id": str(tenant_id),
                    "name": api_key_data["name"],
                    "key_hash": api_key_data["key_hash"],
                    "key_prefix": api_key_data["key_prefix"],
                }
            )
            await session.commit()
            print(f"\nCreated demo tenant: {tenant_id}")
        
        print("\nCreating demo traces...")
        
        traces = []
        for _ in range(12):
            traces.append(create_healthy_trace(tenant_id))
        
        for failure_type in DETECTION_TYPES:
            traces.append(create_failing_trace(tenant_id, failure_type))
            traces.append(create_failing_trace(tenant_id, failure_type))
        
        random.shuffle(traces)
        
        all_states = []
        all_detections = []
        
        for trace in traces:
            failure_type = trace.pop("_failure_type", None)
            
            await session.execute(
                text("""
                    INSERT INTO traces (id, tenant_id, session_id, framework, status, 
                                       total_tokens, total_cost_cents, created_at, completed_at)
                    VALUES (:id, :tenant_id, :session_id, :framework, :status,
                           :total_tokens, :total_cost_cents, :created_at, :completed_at)
                """),
                {
                    "id": str(trace["id"]),
                    "tenant_id": str(trace["tenant_id"]),
                    "session_id": trace["session_id"],
                    "framework": trace["framework"],
                    "status": trace["status"],
                    "total_tokens": trace["total_tokens"],
                    "total_cost_cents": trace["total_cost_cents"],
                    "created_at": trace["created_at"],
                    "completed_at": trace["completed_at"],
                }
            )
            
            if failure_type == "infinite_loop":
                states = create_loop_states({**trace, "_failure_type": failure_type})
            else:
                states = create_states_for_trace(trace, random_int(5, 20))
            
            for state in states:
                await session.execute(
                    text("""
                        INSERT INTO states (id, trace_id, tenant_id, sequence_num, agent_id,
                                           state_delta, state_hash, token_count, latency_ms, created_at)
                        VALUES (:id, :trace_id, :tenant_id, :sequence_num, :agent_id,
                               :state_delta, :state_hash, :token_count, :latency_ms, :created_at)
                    """),
                    {
                        "id": str(state["id"]),
                        "trace_id": str(state["trace_id"]),
                        "tenant_id": str(state["tenant_id"]),
                        "sequence_num": state["sequence_num"],
                        "agent_id": state["agent_id"],
                        "state_delta": json.dumps(state["state_delta"]),
                        "state_hash": state["state_hash"],
                        "token_count": state["token_count"],
                        "latency_ms": state["latency_ms"],
                        "created_at": state["created_at"],
                    }
                )
                all_states.append(state)
            
            if failure_type:
                trace["_failure_type"] = failure_type
                detection = create_detection(trace, states[-1]["id"] if states else None)
                await session.execute(
                    text("""
                        INSERT INTO detections (id, tenant_id, trace_id, state_id, detection_type,
                                               confidence, method, details, validated, false_positive, created_at)
                        VALUES (:id, :tenant_id, :trace_id, :state_id, :detection_type,
                               :confidence, :method, :details, :validated, :false_positive, :created_at)
                    """),
                    {
                        "id": str(detection["id"]),
                        "tenant_id": str(detection["tenant_id"]),
                        "trace_id": str(detection["trace_id"]),
                        "state_id": str(detection["state_id"]) if detection["state_id"] else None,
                        "detection_type": detection["detection_type"],
                        "confidence": detection["confidence"],
                        "method": detection["method"],
                        "details": json.dumps(detection["details"]),
                        "validated": detection["validated"],
                        "false_positive": detection["false_positive"],
                        "created_at": detection["created_at"],
                    }
                )
                all_detections.append(detection)
        
        await session.commit()
        
        print(f"\nDemo data created successfully!")
        print(f"  - Tenant ID: {tenant_id}")
        print(f"  - Traces: {len(traces)}")
        print(f"  - States: {len(all_states)}")
        print(f"  - Detections: {len(all_detections)}")
        print(f"\nDemo API Key: {DEMO_API_KEY}")
        print(f"\nUse this in your frontend/CLI configuration.")
        print("=" * 60)
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_database())
