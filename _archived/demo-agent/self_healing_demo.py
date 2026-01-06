"""
MAO Testing Platform - Self-Healing Demo

Demonstrates the complete self-healing pipeline:
1. Detection → Analyze failure
2. Diagnosis → Identify root cause
3. Fix Generation → Create fix suggestions
4. Fix Application → Apply fixes to workflow
5. Validation → Verify fixes work

Usage:
    python self_healing_demo.py --mode loop
    python self_healing_demo.py --mode corruption
    python self_healing_demo.py --mode drift
    python self_healing_demo.py --mode all
    python self_healing_demo.py --mode all --auto-apply
"""

import os
import sys
import json
import asyncio
import argparse
import secrets
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdk"))

from app.healing import (
    SelfHealingEngine,
    HealingStatus,
)
from app.healing.models import FailureCategory


def create_loop_detection() -> Dict[str, Any]:
    """Create a simulated infinite loop detection."""
    return {
        "id": f"det_{secrets.token_hex(6)}",
        "detection_type": "infinite_loop",
        "confidence": 0.92,
        "method": "structural",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": {
            "loop_length": 7,
            "affected_agents": ["researcher", "analyst"],
            "message": "Node sequence [researcher, analyst] cycles detected. State hash repeated 7 times.",
            "iteration_count": 7,
            "max_iterations": 3,
        },
    }


def create_corruption_detection() -> Dict[str, Any]:
    """Create a simulated state corruption detection."""
    return {
        "id": f"det_{secrets.token_hex(6)}",
        "detection_type": "state_corruption",
        "confidence": 0.88,
        "method": "hash_comparison",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": {
            "corrupted_fields": ["research_notes", "analysis"],
            "null_injection": True,
            "data_loss": True,
            "message": "Original response was destroyed. Null values injected into state.",
            "node_name": "corrupted_processor",
        },
    }


def create_drift_detection() -> Dict[str, Any]:
    """Create a simulated persona drift detection."""
    return {
        "id": f"det_{secrets.token_hex(6)}",
        "detection_type": "persona_drift",
        "confidence": 0.85,
        "method": "style_analysis",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": {
            "drift_score": 0.85,
            "expected_tone": "professional",
            "actual_tone": "casual_unprofessional",
            "emojis_detected": True,
            "slang_detected": True,
            "message": "Tone mismatch detected. Expected professional, got casual with emojis and slang.",
            "agent_name": "writer",
        },
    }


def create_sample_workflow() -> Dict[str, Any]:
    """Create a sample workflow configuration."""
    return {
        "name": "Research Assistant Workflow",
        "framework": "langgraph",
        "nodes": [
            {
                "id": "researcher",
                "name": "Researcher",
                "type": "llm",
                "parameters": {
                    "model": "gpt-4o-mini",
                    "messages": {
                        "values": [
                            {"role": "system", "content": "You are a research assistant."}
                        ]
                    }
                }
            },
            {
                "id": "analyst",
                "name": "Analyst",
                "type": "llm",
                "parameters": {
                    "model": "gpt-4o-mini",
                }
            },
            {
                "id": "writer",
                "name": "Writer",
                "type": "llm",
                "parameters": {
                    "model": "gpt-4o-mini",
                    "messages": {
                        "values": [
                            {"role": "system", "content": "You are a professional writer."}
                        ]
                    }
                }
            },
        ],
        "connections": {
            "researcher": [{"node": "analyst"}],
            "analyst": [{"node": "writer"}],
        },
        "settings": {},
    }


def print_header(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def print_section(title: str):
    print(f"\n--- {title} ---")


def print_detection(detection: Dict[str, Any]):
    print_section("DETECTION")
    print(f"  ID: {detection['id']}")
    print(f"  Type: {detection['detection_type']}")
    print(f"  Confidence: {detection['confidence']:.0%}")
    print(f"  Method: {detection['method']}")
    
    details = detection.get("details", {})
    print(f"  Details:")
    for key, value in details.items():
        if key != "message":
            print(f"    - {key}: {value}")
    if "message" in details:
        print(f"  Message: {details['message']}")


def print_failure_signature(sig):
    print_section("FAILURE ANALYSIS")
    print(f"  Category: {sig.category.value}")
    print(f"  Pattern: {sig.pattern}")
    print(f"  Confidence: {sig.confidence:.0%}")
    print(f"  Root Cause: {sig.root_cause}")
    if sig.indicators:
        print(f"  Indicators:")
        for ind in sig.indicators:
            print(f"    - {ind}")
    if sig.affected_components:
        print(f"  Affected: {', '.join(sig.affected_components)}")


def print_fix_suggestions(suggestions: List[Dict[str, Any]]):
    print_section("FIX SUGGESTIONS")
    for i, fix in enumerate(suggestions, 1):
        print(f"  {i}. [{fix['confidence'].upper()}] {fix['type']}")
        print(f"     ID: {fix['id']}")


def print_applied_fixes(fixes):
    print_section("APPLIED FIXES")
    for i, fix in enumerate(fixes, 1):
        print(f"  {i}. {fix.fix_type}")
        print(f"     Target: {fix.target_component}")
        print(f"     Applied: {fix.applied_at.strftime('%H:%M:%S')}")
        print(f"     Rollback: {'Available' if fix.rollback_available else 'N/A'}")


def print_validation_results(results):
    print_section("VALIDATION RESULTS")
    for result in results:
        status = "PASS" if result.success else "FAIL"
        print(f"  [{status}] {result.validation_type}")
        if result.error_message:
            print(f"       Error: {result.error_message}")
        for key, value in result.details.items():
            if isinstance(value, bool):
                print(f"       - {key}: {'Yes' if value else 'No'}")
            elif isinstance(value, (int, float)):
                print(f"       - {key}: {value}")


def print_healing_result(result):
    print_section("HEALING RESULT")
    
    status_icons = {
        HealingStatus.SUCCESS: "SUCCESS",
        HealingStatus.PARTIAL_SUCCESS: "PARTIAL",
        HealingStatus.FAILED: "FAILED",
        HealingStatus.PENDING: "PENDING",
    }
    
    print(f"  ID: {result.id}")
    print(f"  Status: {status_icons.get(result.status, result.status.value)}")
    print(f"  Duration: {(result.completed_at - result.started_at).total_seconds():.2f}s")
    
    if result.error:
        print(f"  Error: {result.error}")
    
    if result.applied_fixes:
        print(f"  Fixes Applied: {len(result.applied_fixes)}")
    
    validations_passed = sum(1 for v in result.validation_results if v.success)
    validations_total = len(result.validation_results)
    if validations_total > 0:
        print(f"  Validations: {validations_passed}/{validations_total} passed")


def print_config_diff(original: Dict, modified: Dict):
    print_section("CONFIGURATION CHANGES")
    
    orig_settings = original.get("settings", {})
    mod_settings = modified.get("settings", {})
    
    new_settings = set(mod_settings.keys()) - set(orig_settings.keys())
    if new_settings:
        print("  New Settings Added:")
        for key in new_settings:
            value = mod_settings[key]
            if isinstance(value, dict) and value.get("enabled"):
                print(f"    + {key}: ENABLED")
                for k, v in value.items():
                    if k != "enabled":
                        print(f"        {k}: {v}")
            else:
                print(f"    + {key}: {value}")


async def run_healing_demo(mode: str, auto_apply: bool = False):
    """Run the self-healing demo for a specific mode."""
    
    mode_map = {
        "loop": ("Infinite Loop", create_loop_detection),
        "corruption": ("State Corruption", create_corruption_detection),
        "drift": ("Persona Drift", create_drift_detection),
    }
    
    if mode not in mode_map:
        print(f"Unknown mode: {mode}")
        return None
    
    title, create_detection = mode_map[mode]
    
    print_header(f"SELF-HEALING DEMO: {title}")
    
    detection = create_detection()
    workflow = create_sample_workflow()
    
    print_detection(detection)
    
    engine = SelfHealingEngine(
        auto_apply=auto_apply,
        max_fix_attempts=3,
        validation_timeout=30.0,
    )
    
    result = await engine.heal(
        detection=detection,
        workflow_config=workflow,
    )
    
    if result.failure_signature:
        print_failure_signature(result.failure_signature)
    
    if "fix_suggestions" in result.metadata:
        print_fix_suggestions(result.metadata["fix_suggestions"])
    
    if result.applied_fixes:
        print_applied_fixes(result.applied_fixes)
        
        original = result.applied_fixes[0].original_state
        modified = result.applied_fixes[-1].modified_state
        print_config_diff(original, modified)
    
    if result.validation_results:
        print_validation_results(result.validation_results)
    
    print_healing_result(result)
    
    return result


async def run_all_demos(auto_apply: bool = False):
    """Run all healing demos."""
    modes = ["loop", "corruption", "drift"]
    results = []
    
    for mode in modes:
        result = await run_healing_demo(mode, auto_apply)
        if result:
            results.append(result)
    
    print_header("SUMMARY")
    
    for result in results:
        category = result.failure_signature.category.value if result.failure_signature else "unknown"
        status = "PASS" if result.status in (HealingStatus.SUCCESS, HealingStatus.PARTIAL_SUCCESS) else "FAIL"
        fixes = len(result.applied_fixes)
        validations = sum(1 for v in result.validation_results if v.success)
        
        print(f"  [{status}] {category:20} | Fixes: {fixes} | Validations: {validations}/{len(result.validation_results)}")
    
    success_count = sum(
        1 for r in results 
        if r.status in (HealingStatus.SUCCESS, HealingStatus.PARTIAL_SUCCESS)
    )
    print(f"\n  Total: {success_count}/{len(results)} healing operations successful")


def main():
    parser = argparse.ArgumentParser(description="MAO Self-Healing Demo")
    parser.add_argument(
        "--mode",
        choices=["loop", "corruption", "drift", "all"],
        default="all",
        help="Failure mode to demonstrate",
    )
    parser.add_argument(
        "--auto-apply",
        action="store_true",
        help="Automatically apply fixes (otherwise just suggest)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    
    args = parser.parse_args()
    
    print(f"""
================================================================================
             MAO TESTING PLATFORM - SELF-HEALING DEMONSTRATION
                         {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
================================================================================
Mode: {args.mode.upper()}
Auto-Apply: {'ENABLED' if args.auto_apply else 'DISABLED (suggestion only)'}
""")
    
    if args.mode == "all":
        asyncio.run(run_all_demos(args.auto_apply))
    else:
        result = asyncio.run(run_healing_demo(args.mode, args.auto_apply))
        
        if args.json and result:
            print("\n" + json.dumps(result.to_dict(), indent=2, default=str))


if __name__ == "__main__":
    main()
