#!/usr/bin/env python3
"""
Seed demo workflow quality assessments and groups.

Creates:
- 2 workflow groups (Production Data, Platform Demo)
- 17 comprehensive quality assessments in Platform Demo group
- Auto-assignment of existing workflows to Production Data group

Usage:
    python scripts/seed_demo_quality_groups.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from datetime import datetime, timezone, timedelta
from uuid import uuid4, UUID
import random

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.config import get_settings
from app.storage.models import (
    Tenant, WorkflowGroup, WorkflowGroupAssignment,
    WorkflowQualityAssessment
)


# Workflow specifications with realistic variety
DEMO_WORKFLOWS = [
    # Customer Support (3 workflows)
    {
        "name": "Automated Ticket Triage",
        "pattern": "sequential",
        "grade_range": (85, 95),  # A/A-
        "agent_count": 3,
        "complexity": "low",
        "critical_issues": 0,
    },
    {
        "name": "Multilingual Support Bot",
        "pattern": "fan-out",
        "grade_range": (70, 80),  # B+/B
        "agent_count": 5,
        "complexity": "high",
        "critical_issues": 1,
    },
    {
        "name": "Escalation Router",
        "pattern": "conditional",
        "grade_range": (60, 70),  # C+/C
        "agent_count": 4,
        "complexity": "medium",
        "critical_issues": 2,
    },

    # Sales & Marketing (4 workflows)
    {
        "name": "Lead Qualification Pipeline",
        "pattern": "sequential",
        "grade_range": (80, 90),  # A-/B+
        "agent_count": 4,
        "complexity": "medium",
        "critical_issues": 0,
    },
    {
        "name": "Content Generator",
        "pattern": "parallel",
        "grade_range": (75, 85),  # B+/B
        "agent_count": 3,
        "complexity": "low",
        "critical_issues": 1,
    },
    {
        "name": "Email Campaign Personalizer",
        "pattern": "sequential",
        "grade_range": (88, 95),  # A/A+
        "agent_count": 2,
        "complexity": "low",
        "critical_issues": 0,
    },
    {
        "name": "Social Media Scheduler",
        "pattern": "fan-out",
        "grade_range": (65, 75),  # B/C+
        "agent_count": 4,
        "complexity": "medium",
        "critical_issues": 1,
    },

    # Data Processing (4 workflows)
    {
        "name": "Invoice Parser & Validator",
        "pattern": "sequential",
        "grade_range": (82, 92),  # A-/B+
        "agent_count": 3,
        "complexity": "medium",
        "critical_issues": 0,
    },
    {
        "name": "Data Quality Checker",
        "pattern": "loop",
        "grade_range": (90, 98),  # A/A+
        "agent_count": 2,
        "complexity": "low",
        "critical_issues": 0,
    },
    {
        "name": "Report Aggregator",
        "pattern": "parallel",
        "grade_range": (55, 65),  # C/D
        "agent_count": 6,
        "complexity": "very_high",
        "critical_issues": 3,
    },
    {
        "name": "ETL Pipeline Orchestrator",
        "pattern": "hierarchical",
        "grade_range": (70, 80),  # B/B-
        "agent_count": 5,
        "complexity": "high",
        "critical_issues": 1,
    },

    # Research & Analysis (3 workflows)
    {
        "name": "Competitive Analysis Agent",
        "pattern": "fan-out",
        "grade_range": (78, 88),  # B+/A-
        "agent_count": 4,
        "complexity": "medium",
        "critical_issues": 0,
    },
    {
        "name": "Market Research Bot",
        "pattern": "sequential",
        "grade_range": (85, 95),  # A/A-
        "agent_count": 3,
        "complexity": "medium",
        "critical_issues": 0,
    },
    {
        "name": "Sentiment Analyzer",
        "pattern": "parallel",
        "grade_range": (72, 82),  # B/B+
        "agent_count": 3,
        "complexity": "low",
        "critical_issues": 1,
    },

    # Operations (3 workflows)
    {
        "name": "Inventory Manager",
        "pattern": "conditional",
        "grade_range": (80, 90),  # B+/A-
        "agent_count": 3,
        "complexity": "medium",
        "critical_issues": 0,
    },
    {
        "name": "Order Fulfillment Workflow",
        "pattern": "sequential",
        "grade_range": (92, 98),  # A/A+
        "agent_count": 4,
        "complexity": "medium",
        "critical_issues": 0,
    },
    {
        "name": "Anomaly Detector",
        "pattern": "loop",
        "grade_range": (68, 78),  # B-/C+
        "agent_count": 2,
        "complexity": "low",
        "critical_issues": 2,
    },

    # Development & QA (2 workflows)
    {
        "name": "Code Review Assistant",
        "pattern": "sequential",
        "grade_range": (88, 96),  # A/A+
        "agent_count": 3,
        "complexity": "medium",
        "critical_issues": 0,
    },
    {
        "name": "Bug Triager",
        "pattern": "conditional",
        "grade_range": (75, 85),  # B+/B
        "agent_count": 4,
        "complexity": "medium",
        "critical_issues": 1,
    },
]

# Agent name templates (realistic role names)
AGENT_NAMES = [
    "Coordinator", "Router", "Validator", "Processor", "Analyzer",
    "Researcher", "Writer", "Aggregator", "Classifier", "Monitor",
    "Planner", "Executor", "Quality Checker", "Summarizer", "Enricher"
]

# Improvement suggestion templates by category
IMPROVEMENT_TEMPLATES = {
    "efficiency": [
        "Reduce token usage by caching repeated context",
        "Parallelize independent operations",
        "Optimize database query patterns",
        "Add result caching for expensive operations",
        "Reduce redundant API calls",
    ],
    "reliability": [
        "Add retry logic with exponential backoff",
        "Implement circuit breaker pattern",
        "Add timeout handling for external services",
        "Improve error recovery mechanisms",
        "Add health check endpoints",
    ],
    "safety": [
        "Add input validation for user queries",
        "Implement rate limiting per user",
        "Add content filtering for harmful output",
        "Enable audit logging for sensitive operations",
        "Add PII detection and tokenization",
    ],
    "architecture": [
        "Reduce agent coupling through shared state",
        "Simplify conditional branching logic",
        "Extract common patterns into reusable components",
        "Improve state management clarity",
        "Refactor complex orchestration pattern",
    ],
    "observability": [
        "Add structured logging for key decisions",
        "Implement distributed tracing",
        "Add metrics for success/failure rates",
        "Enable performance monitoring",
        "Add alerting for critical failures",
    ],
}


def score_to_grade(score: int) -> str:
    """Convert 0-100 score to letter grade."""
    if score >= 97: return 'A+'
    if score >= 93: return 'A'
    if score >= 90: return 'A-'
    if score >= 87: return 'B+'
    if score >= 83: return 'B'
    if score >= 80: return 'B-'
    if score >= 77: return 'C+'
    if score >= 73: return 'C'
    if score >= 70: return 'C-'
    if score >= 60: return 'D'
    return 'F'


def generate_agent_scores(agent_count: int, base_score: int) -> list:
    """Generate realistic agent quality scores with variance."""
    scores = []

    for i in range(agent_count):
        # Add variance: ±10 points from base score
        agent_score = max(0, min(100, base_score + random.randint(-10, 10)))

        scores.append({
            "agent_id": f"agent-{i+1}",
            "agent_name": random.choice(AGENT_NAMES),
            "agent_type": random.choice(["coordinator", "worker", "specialist", "validator"]),
            "overall_score": agent_score / 100,  # Convert to 0-1 range
            "grade": score_to_grade(agent_score),
            "dimensions": [
                {
                    "dimension": "Reliability",
                    "score": max(0, min(1, (agent_score + random.randint(-5, 5)) / 100)),
                    "weight": 0.2,
                    "issues": [] if agent_score >= 70 else ["Low reliability score"],
                    "evidence": {"sample_count": random.randint(10, 50)},
                    "suggestions": [] if agent_score >= 80 else ["Improve error handling"],
                },
                {
                    "dimension": "Efficiency",
                    "score": max(0, min(1, (agent_score + random.randint(-5, 5)) / 100)),
                    "weight": 0.2,
                    "issues": [],
                    "evidence": {"token_usage": random.randint(500, 2000)},
                    "suggestions": [],
                },
                {
                    "dimension": "Safety",
                    "score": max(0, min(1, (agent_score + random.randint(-5, 5)) / 100)),
                    "weight": 0.2,
                    "issues": [],
                    "evidence": {},
                    "suggestions": [],
                },
                {
                    "dimension": "Accuracy",
                    "score": max(0, min(1, (agent_score + random.randint(-5, 5)) / 100)),
                    "weight": 0.2,
                    "issues": [],
                    "evidence": {},
                    "suggestions": [],
                },
                {
                    "dimension": "Robustness",
                    "score": max(0, min(1, (agent_score + random.randint(-5, 5)) / 100)),
                    "weight": 0.2,
                    "issues": [],
                    "evidence": {},
                    "suggestions": [],
                },
            ],
            "issues_count": max(0, random.randint(0, 5) - (agent_score // 20)),
            "critical_issues": [] if agent_score >= 70 else ["Critical issue detected"],
        })

    return scores


def generate_orchestration_score(pattern: str, base_score: int) -> dict:
    """Generate orchestration score matching the detected pattern."""
    orch_score = max(0, min(100, base_score + random.randint(-5, 5)))

    # Pattern-specific complexity
    complexity_map = {
        "sequential": {"cyclomatic": random.randint(3, 8), "coupling": 0.3},
        "fan-out": {"cyclomatic": random.randint(8, 15), "coupling": 0.6},
        "parallel": {"cyclomatic": random.randint(10, 20), "coupling": 0.4},
        "conditional": {"cyclomatic": random.randint(12, 25), "coupling": 0.5},
        "loop": {"cyclomatic": random.randint(8, 15), "coupling": 0.4},
        "hierarchical": {"cyclomatic": random.randint(15, 30), "coupling": 0.7},
    }

    complexity = complexity_map.get(pattern, {"cyclomatic": 10, "coupling": 0.5})

    return {
        "workflow_id": f"wf-{uuid4().hex[:8]}",
        "workflow_name": "Demo Workflow",
        "overall_score": orch_score / 100,
        "grade": score_to_grade(orch_score),
        "dimensions": [
            {
                "dimension": "Coordination",
                "score": max(0, min(1, (orch_score + random.randint(-8, 8)) / 100)),
                "weight": 0.25,
                "issues": [],
                "evidence": {"handoff_count": random.randint(5, 20)},
                "suggestions": [],
            },
            {
                "dimension": "Flow Efficiency",
                "score": max(0, min(1, (orch_score + random.randint(-8, 8)) / 100)),
                "weight": 0.25,
                "issues": [],
                "evidence": {},
                "suggestions": [],
            },
            {
                "dimension": "Error Handling",
                "score": max(0, min(1, (orch_score + random.randint(-8, 8)) / 100)),
                "weight": 0.25,
                "issues": [],
                "evidence": {},
                "suggestions": [],
            },
            {
                "dimension": "Resource Utilization",
                "score": max(0, min(1, (orch_score + random.randint(-8, 8)) / 100)),
                "weight": 0.25,
                "issues": [],
                "evidence": {},
                "suggestions": [],
            },
        ],
        "complexity_metrics": {
            "node_count": random.randint(5, 30),
            "agent_count": random.randint(2, 6),
            "connection_count": random.randint(4, 20),
            "max_depth": random.randint(3, 10),
            "cyclomatic_complexity": complexity["cyclomatic"],
            "coupling_ratio": complexity["coupling"],
            "ai_node_ratio": random.randint(50, 90) / 100,
            "parallel_branches": random.randint(0, 5),
            "conditional_branches": random.randint(2, 15),
        },
        "issues_count": max(0, random.randint(0, 5) - (orch_score // 25)),
        "critical_issues": [] if orch_score >= 65 else ["Critical orchestration issue"],
        "detected_pattern": pattern,
    }


def generate_improvements(improvement_focus: dict, severity: str) -> list:
    """Generate realistic improvement suggestions."""
    if not improvement_focus:
        # Default mix
        improvement_focus = {
            "efficiency": 2,
            "reliability": 2,
            "safety": 1,
        }

    improvements = []

    for category, count in improvement_focus.items():
        templates = IMPROVEMENT_TEMPLATES.get(category, [])
        for _ in range(count):
            if not templates:
                break

            template = random.choice(templates)
            improvements.append({
                "id": f"improvement-{uuid4().hex[:8]}",
                "target_type": random.choice(["agent", "orchestration"]),
                "target_id": f"target-{uuid4().hex[:8]}",
                "severity": severity if improvements else "medium",
                "category": category,
                "title": template,
                "description": template,
                "rationale": f"Implementing {template.lower()} would improve {category}",
                "suggested_change": f"Update configuration to {template.lower()}",
                "code_example": f"// Example: {template}",
                "estimated_impact": random.choice([
                    "Reduce costs by 20%",
                    "Improve reliability to 99.9%",
                    "Decrease latency by 30%",
                    "Enhance security posture",
                    "Better observability",
                ]),
                "effort": random.choice(["low", "medium", "high"]),
            })

    return improvements


async def seed_demo_quality_groups():
    """Main seeding function."""
    print("=" * 60)
    print("PISAMA - Demo Quality Data Seeder")
    print("=" * 60)

    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 1. Get or create demo tenant
        result = await session.execute(select(Tenant).limit(1))
        tenant = result.scalar_one_or_none()

        if not tenant:
            print("\n❌ No tenant found. Please run database migrations first.")
            return

        print(f"\nUsing tenant: {tenant.name} ({tenant.id})")

        # 2. Check if groups already exist
        existing_groups_result = await session.execute(
            select(WorkflowGroup).filter(
                WorkflowGroup.tenant_id == tenant.id,
                WorkflowGroup.name.in_(["Production Data", "Platform Demo"])
            )
        )
        existing_groups = existing_groups_result.scalars().all()

        if existing_groups:
            print(f"\n⚠️  Found {len(existing_groups)} existing workflow groups with matching names.")
            print("    Skipping group creation. Delete existing groups first if you want to recreate.")

            production_group = next((g for g in existing_groups if g.name == "Production Data"), None)
            demo_group = next((g for g in existing_groups if g.name == "Platform Demo"), None)

            if not production_group:
                production_group = WorkflowGroup(
                    id=uuid4(),
                    tenant_id=tenant.id,
                    name="Production Data",
                    description="Live production workflows and real data",
                    color="#3b82f6",  # Blue
                    icon="database",
                    is_default=False,
                    auto_detect_rules=None,
                )
                session.add(production_group)

            if not demo_group:
                demo_group = WorkflowGroup(
                    id=uuid4(),
                    tenant_id=tenant.id,
                    name="Platform Demo",
                    description="Showcase workflows demonstrating platform capabilities",
                    color="#10b981",  # Green
                    icon="presentation",
                    is_default=False,
                    auto_detect_rules=None,
                )
                session.add(demo_group)

            if not production_group or not demo_group:
                await session.commit()
        else:
            # Create workflow groups
            production_group = WorkflowGroup(
                id=uuid4(),
                tenant_id=tenant.id,
                name="Production Data",
                description="Live production workflows and real data",
                color="#3b82f6",  # Blue
                icon="database",
                is_default=False,
                auto_detect_rules=None,
            )

            demo_group = WorkflowGroup(
                id=uuid4(),
                tenant_id=tenant.id,
                name="Platform Demo",
                description="Showcase workflows demonstrating platform capabilities",
                color="#10b981",  # Green
                icon="presentation",
                is_default=False,
                auto_detect_rules=None,
            )

            session.add(production_group)
            session.add(demo_group)
            await session.commit()

            print(f"\n✅ Created workflow groups:")
            print(f"   - {production_group.name} (id: {production_group.id})")
            print(f"   - {demo_group.name} (id: {demo_group.id})")

        # 3. Assign existing workflows to Production Data group
        existing_result = await session.execute(
            select(WorkflowQualityAssessment).filter(
                WorkflowQualityAssessment.tenant_id == tenant.id,
                ~WorkflowQualityAssessment.workflow_id.like('demo-wf-%')
            )
        )
        existing_workflows = existing_result.scalars().all()

        # Check which are already assigned
        assigned_count = 0
        for wf in existing_workflows:
            existing_assignment_result = await session.execute(
                select(WorkflowGroupAssignment).filter(
                    WorkflowGroupAssignment.workflow_id == wf.workflow_id,
                    WorkflowGroupAssignment.group_id == production_group.id
                )
            )
            existing_assignment = existing_assignment_result.scalar_one_or_none()

            if not existing_assignment:
                assignment = WorkflowGroupAssignment(
                    workflow_id=wf.workflow_id,
                    group_id=production_group.id,
                    assignment_type="manual",
                    assigned_by=None,
                )
                session.add(assignment)
                assigned_count += 1

        if assigned_count > 0:
            await session.commit()
            print(f"\n✅ Assigned {assigned_count} existing workflows to Production Data")
        else:
            print(f"\n✅ {len(existing_workflows)} existing workflows already in Production Data")

        # 4. Create demo quality assessments
        print(f"\n📊 Creating {len(DEMO_WORKFLOWS)} demo quality assessments...")

        demo_assessments = []

        for spec in DEMO_WORKFLOWS:
            # Generate realistic scores based on spec
            base_score = random.randint(*spec["grade_range"])

            assessment = WorkflowQualityAssessment(
                id=uuid4(),
                tenant_id=tenant.id,
                workflow_id=f"demo-wf-{uuid4().hex[:8]}",
                workflow_name=spec["name"],
                overall_score=base_score,
                overall_grade=score_to_grade(base_score),
                agent_scores=generate_agent_scores(
                    spec["agent_count"],
                    base_score
                ),
                orchestration_score=generate_orchestration_score(
                    spec["pattern"],
                    base_score
                ),
                improvements=generate_improvements(
                    spec.get("improvement_focus", {}),
                    "high" if spec["critical_issues"] > 0 else "medium"
                ),
                complexity_metrics={
                    "node_count": random.randint(5, 30),
                    "agent_count": spec["agent_count"],
                    "connection_count": spec["agent_count"] * random.randint(2, 4),
                    "max_depth": random.randint(3, 10),
                    "cyclomatic_complexity": random.randint(5, 25),
                },
                total_issues=random.randint(2, 10),
                critical_issues_count=spec["critical_issues"],
                source="api",
                summary=f"Quality assessment for {spec['name']} ({spec['pattern']} pattern)",
                created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30)),
            )

            demo_assessments.append(assessment)
            session.add(assessment)

            # Assign to Platform Demo group
            assignment = WorkflowGroupAssignment(
                workflow_id=assessment.workflow_id,
                group_id=demo_group.id,
                assignment_type="manual",
                assigned_by=None,
            )
            session.add(assignment)

        await session.commit()

        print(f"\n✅ Created {len(demo_assessments)} demo quality assessments:")
        for assessment in sorted(demo_assessments, key=lambda a: a.overall_score, reverse=True):
            print(f"   [{assessment.overall_grade:3}] {assessment.workflow_name}")

        print(f"\n🎉 Demo data setup complete!")
        print(f"   - Production Data group: {len(existing_workflows)} workflows")
        print(f"   - Platform Demo group: {len(demo_assessments)} workflows")
        print("\n" + "=" * 60)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_demo_quality_groups())
