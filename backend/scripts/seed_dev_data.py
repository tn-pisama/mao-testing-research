#!/usr/bin/env python3
"""Seed development database with test workflow quality assessments."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from uuid import uuid4
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config import get_settings
from app.storage.models import WorkflowQualityAssessment, Tenant
from sqlalchemy import select
from datetime import datetime, timezone

async def seed_data():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Get the first tenant
        result = await session.execute(select(Tenant).limit(1))
        tenant = result.scalar_one()
        
        print(f"Seeding data for tenant: {tenant.name} ({tenant.id})")

        # Create sample workflow assessments
        workflows = [
            WorkflowQualityAssessment(
                id=uuid4(),
                tenant_id=tenant.id,
                workflow_id="wf-sequential-001",
                workflow_name="Customer Onboarding Flow",
                overall_score=85,
                overall_grade="B+",
                agent_scores=[
                    {
                        "agent_id": "agent_validator",
                        "agent_name": "Input Validator",
                        "score": 0.90,
                        "grade": "A",
                        "dimensions": {
                            "role_clarity": 0.92,
                            "tool_usage": 0.88,
                            "error_handling": 0.90
                        }
                    },
                    {
                        "agent_id": "agent_processor",
                        "agent_name": "Data Processor",
                        "score": 0.82,
                        "grade": "B+",
                        "dimensions": {
                            "role_clarity": 0.85,
                            "tool_usage": 0.80,
                            "output_consistency": 0.82
                        }
                    }
                ],
                orchestration_score={
                    "detected_pattern": "sequential",
                    "score": 0.83,
                    "dimensions": [
                        {"dimension": "data_flow_clarity", "score": 0.88},
                        {"dimension": "complexity_management", "score": 0.85},
                        {"dimension": "state_management", "score": 0.80}
                    ]
                },
                improvements=[
                    {
                        "category": "error_handling",
                        "priority": "medium",
                        "suggestion": "Add timeout handling for external API calls",
                        "impact": "Improves reliability"
                    },
                    {
                        "category": "observability",
                        "priority": "low",
                        "suggestion": "Add structured logging for key decision points",
                        "impact": "Easier debugging"
                    }
                ],
                total_issues=3,
                critical_issues_count=0,
                source="api",
                summary="Well-structured sequential workflow with clear data flow and minimal complexity.",
                created_at=datetime.now(timezone.utc)
            ),
            WorkflowQualityAssessment(
                id=uuid4(),
                tenant_id=tenant.id,
                workflow_id="wf-fanout-002",
                workflow_name="Parallel Report Generator",
                overall_score=72,
                overall_grade="B",
                agent_scores=[
                    {
                        "agent_id": "agent_splitter",
                        "agent_name": "Task Splitter",
                        "score": 0.78,
                        "grade": "B",
                        "dimensions": {
                            "role_clarity": 0.80,
                            "tool_usage": 0.75,
                            "error_handling": 0.79
                        }
                    },
                    {
                        "agent_id": "agent_worker1",
                        "agent_name": "Report Worker 1",
                        "score": 0.70,
                        "grade": "B",
                        "dimensions": {
                            "role_clarity": 0.72,
                            "output_consistency": 0.68,
                            "error_handling": 0.70
                        }
                    },
                    {
                        "agent_id": "agent_aggregator",
                        "agent_name": "Results Aggregator",
                        "score": 0.68,
                        "grade": "B-",
                        "dimensions": {
                            "role_clarity": 0.70,
                            "output_consistency": 0.65,
                            "error_handling": 0.69
                        }
                    }
                ],
                orchestration_score={
                    "detected_pattern": "fan-out",
                    "score": 0.68,
                    "dimensions": [
                        {"dimension": "agent_coupling", "score": 0.65},
                        {"dimension": "best_practices", "score": 0.72},
                        {"dimension": "error_propagation", "score": 0.66}
                    ]
                },
                improvements=[
                    {
                        "category": "architecture",
                        "priority": "high",
                        "suggestion": "Reduce agent coupling by using shared state manager",
                        "impact": "Improves maintainability and testability"
                    },
                    {
                        "category": "error_handling",
                        "priority": "high",
                        "suggestion": "Implement proper error propagation from workers to aggregator",
                        "impact": "Prevents silent failures"
                    },
                    {
                        "category": "performance",
                        "priority": "medium",
                        "suggestion": "Add result caching to avoid redundant processing",
                        "impact": "Reduces latency"
                    }
                ],
                total_issues=5,
                critical_issues_count=1,
                source="manual",
                summary="Parallel execution pattern with some agent coupling issues and error handling concerns.",
                created_at=datetime.now(timezone.utc)
            ),
            WorkflowQualityAssessment(
                id=uuid4(),
                tenant_id=tenant.id,
                workflow_id="wf-loop-003",
                workflow_name="Data Validation Loop",
                overall_score=91,
                overall_grade="A",
                agent_scores=[
                    {
                        "agent_id": "agent_validator",
                        "agent_name": "Data Validator",
                        "score": 0.93,
                        "grade": "A",
                        "dimensions": {
                            "role_clarity": 0.95,
                            "tool_usage": 0.92,
                            "error_handling": 0.92
                        }
                    },
                    {
                        "agent_id": "agent_corrector",
                        "agent_name": "Error Corrector",
                        "score": 0.89,
                        "grade": "A-",
                        "dimensions": {
                            "role_clarity": 0.90,
                            "error_handling": 0.88,
                            "output_consistency": 0.89
                        }
                    }
                ],
                orchestration_score={
                    "detected_pattern": "loop",
                    "score": 0.91,
                    "dimensions": [
                        {"dimension": "loop_termination", "score": 0.95},
                        {"dimension": "state_management", "score": 0.90},
                        {"dimension": "progress_tracking", "score": 0.88}
                    ]
                },
                improvements=[
                    {
                        "category": "observability",
                        "priority": "low",
                        "suggestion": "Add metrics for iteration count and success rate",
                        "impact": "Better monitoring"
                    }
                ],
                total_issues=1,
                critical_issues_count=0,
                source="api",
                summary="Excellent loop implementation with proper termination conditions and state management.",
                created_at=datetime.now(timezone.utc)
            )
        ]

        for wf in workflows:
            session.add(wf)

        await session.commit()
        print(f"✅ Seeded {len(workflows)} workflow assessments")
        print("\nWorkflows:")
        for wf in workflows:
            print(f"  - {wf.workflow_name} ({wf.overall_grade})")

if __name__ == "__main__":
    asyncio.run(seed_data())
