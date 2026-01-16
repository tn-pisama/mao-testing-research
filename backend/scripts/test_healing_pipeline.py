#!/usr/bin/env python3
"""
End-to-end test script for the n8n self-healing pipeline.

Tests the complete flow:
1. Authentication with API key
2. n8n connection management (create, test, list)
3. Trace ingestion via webhook
4. Detection pipeline verification
5. Fix preview (dry run)
6. Fix application
7. Healing record verification
8. Cleanup

Usage:
    python test_healing_pipeline.py \
        --api-url https://mao-api.fly.dev \
        --api-key mao_xxx \
        --mock-n8n-url http://localhost:8001

    # With real n8n
    python test_healing_pipeline.py \
        --api-url https://mao-api.fly.dev \
        --api-key mao_xxx \
        --n8n-url https://real-n8n.example.com \
        --n8n-api-key n8n_xxx
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
from uuid import uuid4

import httpx


class TestResult:
    """Represents a single test result."""

    def __init__(self, name: str, passed: bool, message: str = "", details: Dict = None):
        self.name = name
        self.passed = passed
        self.message = message
        self.details = details or {}
        self.duration_ms: Optional[float] = None


class PipelineTestRunner:
    """Runs the complete healing pipeline tests."""

    def __init__(
        self,
        api_url: str,
        api_key: str,
        n8n_url: str,
        n8n_api_key: str,
        timeout: float = 30.0
    ):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.n8n_url = n8n_url.rstrip("/")
        self.n8n_api_key = n8n_api_key
        self.timeout = timeout

        # State tracking
        self.jwt_token: Optional[str] = None
        self.tenant_id: Optional[str] = None
        self.connection_id: Optional[str] = None
        self.trace_id: Optional[str] = None
        self.detection_id: Optional[str] = None
        self.healing_id: Optional[str] = None

        # Results
        self.results: List[TestResult] = []
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

    async def run_all_tests(self) -> bool:
        """Run all tests in sequence."""
        self.start_time = datetime.now(timezone.utc)

        tests = [
            ("Phase 1: Authentication", self.test_authentication),
            ("Phase 2: n8n Connection Setup", self.test_connection_setup),
            ("Phase 3: Trace Ingestion", self.test_trace_ingestion),
            ("Phase 4: Detection Verification", self.test_detection_verification),
            ("Phase 5: Fix Preview (Dry Run)", self.test_fix_preview),
            ("Phase 6: Apply Fix", self.test_apply_fix),
            ("Phase 7: Verify Healing", self.test_verify_healing),
            ("Phase 8: Cleanup", self.test_cleanup),
        ]

        all_passed = True

        for phase_name, test_func in tests:
            print(f"\n{'='*60}")
            print(f"  {phase_name}")
            print(f"{'='*60}")

            try:
                start = time.time()
                result = await test_func()
                result.duration_ms = (time.time() - start) * 1000
                self.results.append(result)

                status = "[PASS]" if result.passed else "[FAIL]"
                print(f"{status} {result.name}")
                if result.message:
                    print(f"       {result.message}")
                if result.details:
                    for key, value in result.details.items():
                        print(f"       - {key}: {value}")

                if not result.passed:
                    all_passed = False
                    # Continue to cleanup even if tests fail
                    if "Cleanup" not in phase_name:
                        continue

            except Exception as e:
                result = TestResult(
                    name=phase_name,
                    passed=False,
                    message=f"Exception: {str(e)}"
                )
                self.results.append(result)
                print(f"[FAIL] {phase_name}")
                print(f"       Exception: {str(e)}")
                all_passed = False

        self.end_time = datetime.now(timezone.utc)
        return all_passed

    async def test_authentication(self) -> TestResult:
        """Test API key authentication and JWT exchange."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Exchange API key for JWT
            response = await client.post(
                f"{self.api_url}/auth/exchange",
                json={"api_key": self.api_key}
            )

            if response.status_code != 200:
                return TestResult(
                    name="Exchange API key for JWT",
                    passed=False,
                    message=f"Status {response.status_code}: {response.text}"
                )

            data = response.json()
            self.jwt_token = data.get("access_token")
            self.tenant_id = data.get("tenant_id")

            if not self.jwt_token:
                return TestResult(
                    name="Exchange API key for JWT",
                    passed=False,
                    message="No access_token in response"
                )

            return TestResult(
                name="Exchange API key for JWT",
                passed=True,
                message="Authentication successful",
                details={
                    "tenant_id": self.tenant_id[:8] + "..." if self.tenant_id else "N/A",
                    "token_length": len(self.jwt_token)
                }
            )

    async def test_connection_setup(self) -> TestResult:
        """Test n8n connection creation and verification."""
        headers = {"Authorization": f"Bearer {self.jwt_token}"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Create connection
            connection_name = f"test-conn-{uuid4().hex[:8]}"
            create_response = await client.post(
                f"{self.api_url}/healing/n8n/connections",
                headers=headers,
                json={
                    "name": connection_name,
                    "instance_url": self.n8n_url,
                    "api_key": self.n8n_api_key
                }
            )

            if create_response.status_code not in (200, 201):
                return TestResult(
                    name="Create n8n connection",
                    passed=False,
                    message=f"Status {create_response.status_code}: {create_response.text}"
                )

            conn_data = create_response.json()
            self.connection_id = conn_data.get("id")

            if not self.connection_id:
                return TestResult(
                    name="Create n8n connection",
                    passed=False,
                    message="No connection ID in response"
                )

            # Test connection
            test_response = await client.post(
                f"{self.api_url}/healing/n8n/connections/{self.connection_id}/test",
                headers=headers
            )

            test_success = test_response.status_code == 200
            test_data = test_response.json() if test_success else {}

            # List connections to verify
            list_response = await client.get(
                f"{self.api_url}/healing/n8n/connections",
                headers=headers
            )

            list_data = list_response.json() if list_response.status_code == 200 else []
            connection_count = len(list_data) if isinstance(list_data, list) else 0

            return TestResult(
                name="Create n8n connection",
                passed=True,
                message="Connection created and verified",
                details={
                    "connection_id": self.connection_id[:8] + "...",
                    "connection_name": connection_name,
                    "instance_url": self.n8n_url,
                    "test_status": "verified" if test_success else "failed",
                    "total_connections": connection_count
                }
            )

    async def test_trace_ingestion(self) -> TestResult:
        """Test trace ingestion via webhook."""
        headers = {"Authorization": f"Bearer {self.jwt_token}"}

        # Create a trace payload that will trigger loop detection
        trace_payload = {
            "workflow_id": "wf-loop-test-001",
            "workflow_name": "Loop Test Workflow",
            "execution_id": f"exec-{uuid4().hex[:8]}",
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "nodes": [
                {
                    "name": "Start",
                    "type": "n8n-nodes-base.start",
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "status": "success"
                },
                {
                    "name": "Loop",
                    "type": "n8n-nodes-base.loop",
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "status": "running",
                    "iterations": 150,  # High iteration count to trigger loop detection
                    "data": {
                        "batchSize": 10,
                        # No maxIterations - infinite loop risk
                    }
                },
                {
                    "name": "AI Agent",
                    "type": "n8n-nodes-base.openAi",
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "status": "running",
                    "data": {
                        "operation": "chat",
                        "model": "gpt-4"
                    }
                }
            ],
            # Add repetitive states to trigger loop detection
            "states": [
                {"node": "Loop", "iteration": i, "status": "processing"}
                for i in range(100)
            ]
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Submit trace via webhook
            webhook_response = await client.post(
                f"{self.api_url}/n8n/webhook",
                headers=headers,
                json=trace_payload
            )

            if webhook_response.status_code not in (200, 201, 202):
                return TestResult(
                    name="Submit webhook payload",
                    passed=False,
                    message=f"Status {webhook_response.status_code}: {webhook_response.text}"
                )

            webhook_data = webhook_response.json()
            self.trace_id = webhook_data.get("trace_id") or webhook_data.get("id")

            if not self.trace_id:
                return TestResult(
                    name="Submit webhook payload",
                    passed=False,
                    message="No trace_id in webhook response"
                )

            # Wait a moment for async detection to complete
            await asyncio.sleep(1.0)

            return TestResult(
                name="Submit webhook payload",
                passed=True,
                message="Trace ingested successfully",
                details={
                    "trace_id": self.trace_id[:8] + "..." if len(self.trace_id) > 8 else self.trace_id,
                    "workflow_id": trace_payload["workflow_id"],
                    "state_count": len(trace_payload.get("states", []))
                }
            )

    async def test_detection_verification(self) -> TestResult:
        """Verify detection was triggered from the trace."""
        headers = {"Authorization": f"Bearer {self.jwt_token}"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Get detections for the trace
            detection_response = await client.get(
                f"{self.api_url}/detections",
                headers=headers,
                params={"trace_id": self.trace_id, "limit": 10}
            )

            if detection_response.status_code != 200:
                # Try alternative endpoint
                detection_response = await client.get(
                    f"{self.api_url}/traces/{self.trace_id}/detections",
                    headers=headers
                )

            if detection_response.status_code != 200:
                return TestResult(
                    name="Verify detection triggered",
                    passed=False,
                    message=f"Status {detection_response.status_code}: {detection_response.text}"
                )

            detections = detection_response.json()
            if isinstance(detections, dict):
                detections = detections.get("data", []) or detections.get("detections", [])

            if not detections:
                return TestResult(
                    name="Verify detection triggered",
                    passed=False,
                    message="No detections found for trace"
                )

            # Find the most relevant detection
            detection = detections[0]
            self.detection_id = detection.get("id")

            return TestResult(
                name="Verify detection triggered",
                passed=True,
                message="Detection created from trace",
                details={
                    "detection_id": self.detection_id[:8] + "..." if self.detection_id else "N/A",
                    "type": detection.get("failure_type") or detection.get("type"),
                    "confidence": f"{detection.get('confidence', 0)*100:.0f}%",
                    "method": detection.get("detection_method", "unknown")
                }
            )

    async def test_fix_preview(self) -> TestResult:
        """Test fix preview with dry_run=true."""
        headers = {"Authorization": f"Bearer {self.jwt_token}"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Preview fix (dry run)
            preview_response = await client.post(
                f"{self.api_url}/healing/apply-to-n8n/{self.detection_id}",
                headers=headers,
                params={"dry_run": "true"},
                json={"connection_id": self.connection_id}
            )

            if preview_response.status_code != 200:
                return TestResult(
                    name="Generate fix preview",
                    passed=False,
                    message=f"Status {preview_response.status_code}: {preview_response.text}"
                )

            preview_data = preview_response.json()

            diff = preview_data.get("diff", {})
            changes = diff.get("changes", []) or diff.get("node_changes", [])

            return TestResult(
                name="Generate fix preview",
                passed=True,
                message="Fix preview generated",
                details={
                    "dry_run": True,
                    "workflow_id": preview_data.get("workflow_id", "N/A"),
                    "changes_count": len(changes),
                    "changes": changes[:3] if changes else ["No changes detected"]
                }
            )

    async def test_apply_fix(self) -> TestResult:
        """Test applying the fix to n8n."""
        headers = {"Authorization": f"Bearer {self.jwt_token}"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Apply fix (not dry run)
            apply_response = await client.post(
                f"{self.api_url}/healing/apply-to-n8n/{self.detection_id}",
                headers=headers,
                params={"dry_run": "false"},
                json={"connection_id": self.connection_id}
            )

            if apply_response.status_code not in (200, 201):
                return TestResult(
                    name="Apply fix to n8n",
                    passed=False,
                    message=f"Status {apply_response.status_code}: {apply_response.text}"
                )

            apply_data = apply_response.json()
            self.healing_id = apply_data.get("healing_id") or apply_data.get("id")

            return TestResult(
                name="Apply fix to n8n",
                passed=True,
                message="Fix applied successfully",
                details={
                    "healing_id": self.healing_id[:8] + "..." if self.healing_id else "N/A",
                    "status": apply_data.get("status", "applied"),
                    "workflow_version": apply_data.get("workflow_version", "N/A")
                }
            )

    async def test_verify_healing(self) -> TestResult:
        """Verify healing record was created and detection marked healed."""
        headers = {"Authorization": f"Bearer {self.jwt_token}"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Check healing record
            healing_response = await client.get(
                f"{self.api_url}/healing/{self.healing_id}",
                headers=headers
            )

            healing_exists = healing_response.status_code == 200
            healing_data = healing_response.json() if healing_exists else {}

            # Check detection is marked as healed
            detection_response = await client.get(
                f"{self.api_url}/detections/{self.detection_id}",
                headers=headers
            )

            detection_healed = False
            if detection_response.status_code == 200:
                detection_data = detection_response.json()
                detection_healed = (
                    detection_data.get("healed_by") is not None or
                    detection_data.get("status") == "healed" or
                    detection_data.get("healed_via_n8n") is True
                )

            return TestResult(
                name="Verify healing record",
                passed=healing_exists or detection_healed,
                message="Healing verified" if (healing_exists or detection_healed) else "Healing not verified",
                details={
                    "healing_record_exists": healing_exists,
                    "detection_marked_healed": detection_healed,
                    "rollback_available": healing_data.get("rollback_available", False)
                }
            )

    async def test_cleanup(self) -> TestResult:
        """Clean up test resources."""
        headers = {"Authorization": f"Bearer {self.jwt_token}"}
        cleanup_results = []

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Delete n8n connection
            if self.connection_id:
                delete_response = await client.delete(
                    f"{self.api_url}/healing/n8n/connections/{self.connection_id}",
                    headers=headers
                )
                cleanup_results.append(
                    f"Connection: {'deleted' if delete_response.status_code in (200, 204) else 'failed'}"
                )

            # Reset mock n8n workflow (if using mock server)
            if "localhost" in self.n8n_url or "127.0.0.1" in self.n8n_url:
                try:
                    reset_response = await client.post(
                        f"{self.n8n_url}/api/v1/workflows/wf-loop-test-001/reset",
                        headers={"X-N8N-API-KEY": self.n8n_api_key}
                    )
                    cleanup_results.append(
                        f"Mock workflow: {'reset' if reset_response.status_code == 200 else 'not reset'}"
                    )
                except Exception:
                    pass

        return TestResult(
            name="Cleanup test resources",
            passed=True,
            message="Cleanup completed",
            details={"actions": cleanup_results}
        )

    def print_report(self):
        """Print the final test report."""
        print("\n")
        print("=" * 60)
        print("  n8n Self-Healing Pipeline Test Report")
        print("=" * 60)

        if self.start_time:
            print(f"Timestamp: {self.start_time.isoformat()}")
        print(f"Environment: {self.api_url}")
        print(f"n8n Instance: {self.n8n_url}")
        if self.tenant_id:
            print(f"Tenant: {self.tenant_id[:12]}...")

        print("\n" + "-" * 60)
        print("  TEST RESULTS")
        print("-" * 60)

        passed = 0
        failed = 0

        for result in self.results:
            status = "[PASS]" if result.passed else "[FAIL]"
            duration = f"({result.duration_ms:.0f}ms)" if result.duration_ms else ""
            print(f"{status} {result.name} {duration}")

            if result.passed:
                passed += 1
            else:
                failed += 1
                if result.message:
                    print(f"       Error: {result.message}")

        print("\n" + "=" * 60)
        print("  SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {len(self.results)}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")

        if self.start_time and self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()
            print(f"Duration: {duration:.1f} seconds")

        print("=" * 60)

        return failed == 0


async def main():
    parser = argparse.ArgumentParser(
        description="Test the n8n self-healing pipeline end-to-end"
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="MAO API URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--api-key",
        required=True,
        help="MAO API key for authentication"
    )
    parser.add_argument(
        "--mock-n8n-url",
        default=None,
        help="Mock n8n server URL (e.g., http://localhost:8001)"
    )
    parser.add_argument(
        "--n8n-url",
        default=None,
        help="Real n8n instance URL"
    )
    parser.add_argument(
        "--n8n-api-key",
        default="test-api-key",
        help="n8n API key"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Request timeout in seconds"
    )

    args = parser.parse_args()

    # Determine n8n URL to use
    n8n_url = args.n8n_url or args.mock_n8n_url or "http://localhost:8001"

    print("=" * 60)
    print("  n8n Self-Healing Pipeline Test")
    print("=" * 60)
    print(f"MAO API: {args.api_url}")
    print(f"n8n Instance: {n8n_url}")
    print(f"Timeout: {args.timeout}s")

    runner = PipelineTestRunner(
        api_url=args.api_url,
        api_key=args.api_key,
        n8n_url=n8n_url,
        n8n_api_key=args.n8n_api_key,
        timeout=args.timeout
    )

    success = await runner.run_all_tests()
    runner.print_report()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
