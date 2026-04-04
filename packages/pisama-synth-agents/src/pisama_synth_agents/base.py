"""SyntheticCustomer base class — shared bootstrap, HTTP client, and reporting."""

import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class Assertion:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class AgentReport:
    agent_name: str
    tenant_id: str | None = None
    steps_run: int = 0
    assertions: list[Assertion] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_s: float = 0.0

    @property
    def passed(self) -> int:
        return sum(1 for a in self.assertions if a.passed)

    @property
    def failed(self) -> int:
        return sum(1 for a in self.assertions if not a.passed)

    @property
    def ok(self) -> bool:
        return self.failed == 0 and not self.errors


class SyntheticCustomer:
    """Base class for synthetic customer agents.

    Each agent creates its own tenant, authenticates, runs its scenario,
    and reports results. Subclasses implement `run_scenario()`.
    """

    name: str = "base"
    description: str = "Base synthetic customer"

    def __init__(self, base_url: str, api_key: str | None = None, tenant_id: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.jwt: str | None = None
        self._client: httpx.AsyncClient | None = None
        self._report = AgentReport(agent_name=self.name)

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self.jwt:
                headers["Authorization"] = f"Bearer {self.jwt}"
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=30.0,
            )
        return self._client

    async def setup(self) -> None:
        """Create tenant and authenticate. If api_key is pre-set, skip creation."""
        if not self.api_key:
            await self._create_tenant()
        await self._authenticate()
        # Recreate client with JWT
        if self._client:
            await self._client.aclose()
            self._client = None
        await self._ensure_client()

    async def _create_tenant(self) -> None:
        ts = int(time.time())
        tenant_name = f"synth-{self.name}-{ts}"
        client = await self._ensure_client()
        resp = await client.post("/api/v1/auth/tenants", json={"name": tenant_name})
        resp.raise_for_status()
        data = resp.json()
        self.api_key = data["api_key"]
        self.tenant_id = str(data["id"])
        logger.info("[%s] Created tenant %s (id=%s)", self.name, tenant_name, self.tenant_id)

    async def _authenticate(self) -> None:
        client = await self._ensure_client()
        resp = await client.post("/api/v1/auth/token", json={"api_key": self.api_key})
        resp.raise_for_status()
        self.jwt = resp.json()["access_token"]
        logger.info("[%s] Authenticated (tenant=%s)", self.name, self.tenant_id)

    async def run(self) -> AgentReport:
        """Full lifecycle: setup -> scenario -> teardown."""
        start = time.monotonic()
        try:
            await self.setup()
            await self.run_scenario()
        except Exception as exc:
            self._report.errors.append(f"{type(exc).__name__}: {exc}")
            logger.exception("[%s] Agent failed", self.name)
        finally:
            self._report.duration_s = time.monotonic() - start
            self._report.tenant_id = self.tenant_id
            await self.teardown()
        return self._report

    async def run_scenario(self) -> None:
        """Override in subclasses with the agent's specific test scenario."""
        raise NotImplementedError

    async def teardown(self) -> None:
        """Cleanup HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    # --- Path helpers ---

    def tenant_path(self, path: str) -> str:
        """Prefix a path with /api/v1/tenants/{tenant_id} for tenant-scoped endpoints."""
        return f"/api/v1/tenants/{self.tenant_id}{path}"

    # --- HTTP helpers ---

    async def _request_with_retry(
        self, method: str, path: str, max_retries: int = 3, **kwargs: Any,
    ) -> httpx.Response:
        """Execute HTTP request with retry on 503 (backpressure) and exponential backoff."""
        client = await self._ensure_client()
        for attempt in range(max_retries + 1):
            resp = await getattr(client, method)(path, **kwargs)
            if resp.status_code != 503 or attempt == max_retries:
                return resp
            wait = 1.0 * (2 ** attempt)  # 1s, 2s, 4s
            logger.info("[%s] 503 backpressure on %s, retrying in %.0fs", self.name, path, wait)
            await asyncio.sleep(wait)
        return resp  # unreachable, but satisfies type checker

    async def post(self, path: str, json: dict | list | None = None, **kwargs: Any) -> dict:
        resp = await self._request_with_retry("post", path, json=json, **kwargs)
        self._report.steps_run += 1
        resp.raise_for_status()
        return resp.json()

    async def get(self, path: str, params: dict | None = None, **kwargs: Any) -> dict:
        resp = await self._request_with_retry("get", path, params=params, **kwargs)
        self._report.steps_run += 1
        resp.raise_for_status()
        return resp.json()

    # --- Assertion helpers ---

    def assert_true(self, name: str, condition: bool, detail: str = "") -> bool:
        self._report.assertions.append(Assertion(name=name, passed=condition, detail=detail))
        if not condition:
            logger.warning("[%s] FAIL: %s — %s", self.name, name, detail)
        return condition

    def assert_eq(self, name: str, actual: Any, expected: Any) -> bool:
        passed = actual == expected
        detail = f"expected={expected}, got={actual}" if not passed else ""
        return self.assert_true(name, passed, detail)

    def assert_in(self, name: str, item: Any, collection: Any) -> bool:
        passed = item in collection
        detail = f"{item!r} not in {collection!r}" if not passed else ""
        return self.assert_true(name, passed, detail)

    def assert_gt(self, name: str, actual: float | int, threshold: float | int) -> bool:
        passed = actual > threshold
        detail = f"{actual} <= {threshold}" if not passed else ""
        return self.assert_true(name, passed, detail)

    def assert_gte(self, name: str, actual: float | int, threshold: float | int) -> bool:
        passed = actual >= threshold
        detail = f"{actual} < {threshold}" if not passed else ""
        return self.assert_true(name, passed, detail)

    def assert_lt(self, name: str, actual: float | int, threshold: float | int) -> bool:
        passed = actual < threshold
        detail = f"{actual} >= {threshold}" if not passed else ""
        return self.assert_true(name, passed, detail)
