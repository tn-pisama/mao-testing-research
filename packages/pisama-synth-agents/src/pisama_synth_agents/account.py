"""AccountManager — create, reuse, and cleanup synthetic tenant accounts."""

import asyncio
import json
import logging
import time
from pathlib import Path
from dataclasses import dataclass, asdict

import httpx

logger = logging.getLogger(__name__)

STATE_FILE = ".synth-state.json"
TENANT_CREATE_DELAY_S = 2.0  # Stagger to avoid burst rate limiting


@dataclass
class TenantCredentials:
    name: str
    tenant_id: str
    api_key: str
    created_at: float


class AccountManager:
    """Manages synthetic tenant accounts with optional persistence for reuse."""

    def __init__(self, base_url: str, state_path: Path | None = None):
        self.base_url = base_url.rstrip("/")
        self.state_path = state_path or Path(STATE_FILE)
        self._accounts: dict[str, TenantCredentials] = {}
        self._load_state()

    def _load_state(self) -> None:
        if self.state_path.exists():
            try:
                data = json.loads(self.state_path.read_text())
                for agent_name, cred in data.get("accounts", {}).items():
                    self._accounts[agent_name] = TenantCredentials(**cred)
                logger.info("Loaded %d saved accounts from %s", len(self._accounts), self.state_path)
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                logger.warning("Failed to load state file: %s", exc)

    def _save_state(self) -> None:
        data = {"accounts": {k: asdict(v) for k, v in self._accounts.items()}}
        self.state_path.write_text(json.dumps(data, indent=2))

    def get_existing(self, agent_name: str) -> TenantCredentials | None:
        return self._accounts.get(agent_name)

    async def create_account(self, agent_name: str) -> TenantCredentials:
        """Create a new tenant account via the API."""
        ts = int(time.time())
        tenant_name = f"synth-{agent_name}-{ts}"

        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            resp = await client.post(
                "/api/v1/auth/tenants",
                json={"name": tenant_name},
            )
            resp.raise_for_status()
            data = resp.json()

        creds = TenantCredentials(
            name=tenant_name,
            tenant_id=str(data["id"]),
            api_key=data["api_key"],
            created_at=time.time(),
        )
        self._accounts[agent_name] = creds
        self._save_state()
        logger.info("Created tenant %s for agent %s", tenant_name, agent_name)
        return creds

    async def ensure_accounts(
        self, agent_names: list[str], reuse: bool = False
    ) -> dict[str, TenantCredentials]:
        """Create accounts for all agents, with optional reuse of existing ones."""
        result: dict[str, TenantCredentials] = {}

        for name in agent_names:
            if reuse:
                existing = self.get_existing(name)
                if existing:
                    # Verify the account still works
                    if await self._verify_account(existing):
                        result[name] = existing
                        logger.info("Reusing account for %s (tenant=%s)", name, existing.tenant_id)
                        continue
                    logger.info("Saved account for %s is stale, creating new", name)

            creds = await self.create_account(name)
            result[name] = creds

            # Stagger to respect rate limits (5 creates/hour/IP)
            if name != agent_names[-1]:
                await asyncio.sleep(TENANT_CREATE_DELAY_S)

        return result

    async def _verify_account(self, creds: TenantCredentials) -> bool:
        """Check if saved credentials still authenticate successfully."""
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=10.0) as client:
                resp = await client.post(
                    "/api/v1/auth/token",
                    json={"api_key": creds.api_key},
                )
                return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def cleanup(self, max_age_hours: float = 24.0) -> int:
        """Remove accounts older than max_age_hours. Returns count removed."""
        cutoff = time.time() - (max_age_hours * 3600)
        removed = 0
        to_remove = []

        for name, creds in self._accounts.items():
            if creds.created_at < cutoff:
                to_remove.append(name)

        for name in to_remove:
            # Try to delete via API if endpoint exists
            creds = self._accounts[name]
            try:
                async with httpx.AsyncClient(base_url=self.base_url, timeout=10.0) as client:
                    # Authenticate first
                    token_resp = await client.post(
                        "/api/v1/auth/token",
                        json={"api_key": creds.api_key},
                    )
                    if token_resp.status_code == 200:
                        jwt = token_resp.json()["access_token"]
                        await client.delete(
                            f"/api/v1/auth/tenants/{creds.tenant_id}",
                            headers={"Authorization": f"Bearer {jwt}"},
                        )
            except httpx.HTTPError:
                pass  # Endpoint may not exist yet; just remove from state

            del self._accounts[name]
            removed += 1
            logger.info("Cleaned up account %s (tenant=%s)", name, creds.tenant_id)

        if removed:
            self._save_state()

        return removed
