"""Embedded server for MAO Healer CLI.

Runs a minimal FastAPI server to receive n8n webhooks.
"""

import asyncio
import logging
import signal
import sys
from typing import Any, Dict, Optional

import uvicorn
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse

from .config import HealerConfig

logger = logging.getLogger(__name__)

# Global server state
_server_state: Dict[str, Any] = {
    "healing_engine": None,
    "notification_router": None,
    "config": None,
    "stats": {
        "webhooks_received": 0,
        "detections": 0,
        "fixes_applied": 0,
        "fixes_failed": 0,
    },
}


def create_app(config: HealerConfig) -> FastAPI:
    """Create FastAPI app for webhook receiver."""
    app = FastAPI(
        title="MAO Healer",
        description="Self-healing agent for n8n workflows",
        version="0.1.0",
    )

    @app.get("/")
    async def root():
        """Health check endpoint."""
        return {
            "status": "running",
            "service": "mao-healer",
            "version": "0.1.0",
        }

    @app.get("/health")
    async def health():
        """Health check for monitoring."""
        return {"status": "healthy"}

    @app.get("/stats")
    async def stats():
        """Get server statistics."""
        engine = _server_state.get("healing_engine")
        if engine:
            healing_stats = engine.get_healing_stats()
            apply_results = engine.get_apply_results(limit=10)
            return {
                "server_stats": _server_state["stats"],
                "healing_stats": healing_stats,
                "recent_applies": [r.to_dict() for r in apply_results],
            }
        return {"server_stats": _server_state["stats"]}

    @app.post("/webhook/n8n")
    async def n8n_webhook(
        request: Request,
        x_n8n_signature: Optional[str] = Header(None, alias="x-n8n-signature"),
    ):
        """
        Receive n8n execution webhooks.

        This is the main entry point for n8n workflow events.
        """
        _server_state["stats"]["webhooks_received"] += 1

        try:
            body = await request.json()
        except Exception as e:
            logger.error(f"Failed to parse webhook body: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        # Verify webhook signature if configured
        if config.n8n.webhook_secret:
            if not x_n8n_signature:
                logger.warning("Missing webhook signature")
                raise HTTPException(status_code=401, detail="Missing signature")

            # Verify HMAC signature
            import hashlib
            import hmac

            raw_body = await request.body()
            expected_sig = hmac.new(
                config.n8n.webhook_secret.encode(),
                raw_body,
                hashlib.sha256,
            ).hexdigest()

            if not hmac.compare_digest(expected_sig, x_n8n_signature):
                logger.warning("Invalid webhook signature")
                raise HTTPException(status_code=401, detail="Invalid signature")

        # Process the webhook
        result = await process_webhook(body, config)

        return JSONResponse(content=result, status_code=200)

    @app.post("/test")
    async def test_endpoint(request: Request):
        """Test endpoint for manual testing."""
        body = await request.json()
        return {
            "received": body,
            "message": "Test successful",
        }

    return app


async def process_webhook(body: Dict[str, Any], config: HealerConfig) -> Dict[str, Any]:
    """
    Process n8n webhook and trigger healing if needed.

    Args:
        body: Webhook payload from n8n
        config: Healer configuration

    Returns:
        Response dict
    """
    execution_id = body.get("execution_id") or body.get("executionId")
    workflow_id = body.get("workflow_id") or body.get("workflowId")
    workflow_name = body.get("workflow_name") or body.get("workflowName", "Unknown")
    status = body.get("status", "").lower()

    logger.info(f"Received webhook: workflow={workflow_name} status={status}")

    # Only process failed executions
    if status not in ("error", "failed", "crashed"):
        return {
            "status": "ignored",
            "reason": f"Execution status '{status}' does not require healing",
        }

    # Get error details
    error_message = body.get("error_message") or body.get("errorMessage", "")
    error_node = body.get("error_node") or body.get("stoppedAt", "")

    # Run detection
    from backend.app.detection.patterns import run_all_detectors

    execution_data = body.get("data", {})
    detections = run_all_detectors(
        execution_data,
        enabled_modes=config.detection.enabled_modes,
    )

    _server_state["stats"]["detections"] += len(detections)

    if not detections:
        logger.info(f"No failures detected for workflow {workflow_name}")
        return {
            "status": "no_detection",
            "workflow": workflow_name,
        }

    # Get healing engine
    engine = _server_state.get("healing_engine")
    if not engine:
        logger.error("Healing engine not initialized")
        return {
            "status": "error",
            "message": "Healing engine not initialized",
        }

    # Heal the workflow
    from backend.app.integrations.n8n import N8nClient

    n8n_client = N8nClient(
        api_url=config.n8n.api_url,
        api_key=config.n8n.api_key,
    )

    # Take the highest confidence detection
    detection = max(detections, key=lambda d: d.get("confidence", 0))

    result = await engine.heal_n8n_workflow(
        detection=detection,
        workflow_id=workflow_id,
        n8n_client=n8n_client,
        trace=execution_data,
    )

    # Update stats
    if result.is_successful:
        _server_state["stats"]["fixes_applied"] += 1
    else:
        _server_state["stats"]["fixes_failed"] += 1

    # Send notification
    router = _server_state.get("notification_router")
    if router:
        await router.notify_healing_result(result, workflow_name)

    return {
        "status": "healed" if result.is_successful else "failed",
        "healing_id": result.id,
        "workflow": workflow_name,
        "failure_mode": detection.get("failure_mode"),
        "fixes_applied": len(result.applied_fixes),
        "error": result.error,
    }


async def initialize_services(config: HealerConfig) -> None:
    """Initialize healing engine and notification router."""
    # Initialize healing engine
    from backend.app.healing import (
        SelfHealingEngine,
        AutoApplyConfig as EngineAutoApplyConfig,
        GitBackupConfig,
        GitBackupService,
        AutoApplyService,
    )

    auto_apply_config = EngineAutoApplyConfig(
        enabled=config.auto_apply.enabled,
        max_fixes_per_hour=config.auto_apply.max_fixes_per_hour,
        require_git_backup=config.auto_apply.git_backup,
    )

    git_backup_service = None
    if config.auto_apply.git_backup:
        git_backup_config = GitBackupConfig(
            repo_path=config.auto_apply.git_repo,
        )
        git_backup_service = GitBackupService(git_backup_config)
        await git_backup_service.initialize()

    engine = SelfHealingEngine(
        auto_apply=config.auto_apply.enabled,
        auto_apply_config=auto_apply_config,
        git_backup_service=git_backup_service,
    )

    _server_state["healing_engine"] = engine
    _server_state["config"] = config

    # Initialize notification router
    from backend.app.notifications import NotificationRouter, NotifyConfig

    notify_config = NotifyConfig(
        discord_webhook=config.notifications.discord_webhook or None,
        slack_webhook=config.notifications.slack_webhook or None,
        email_enabled=bool(config.notifications.email_to),
        email_smtp_host=config.notifications.email_smtp_host,
        email_smtp_port=config.notifications.email_smtp_port,
        email_smtp_user=config.notifications.email_smtp_user or None,
        email_smtp_password=config.notifications.email_smtp_password or None,
        email_from=config.notifications.email_from,
        email_to=[config.notifications.email_to] if config.notifications.email_to else [],
    )

    _server_state["notification_router"] = NotificationRouter(notify_config)

    logger.info("Services initialized successfully")


def run_server(config: HealerConfig, host: str = "0.0.0.0", port: Optional[int] = None) -> None:
    """
    Run the MAO Healer server.

    Args:
        config: Healer configuration
        host: Server host
        port: Server port (defaults to config.server_port)
    """
    port = port or config.server_port

    # Set up logging
    log_level = config.log_level.upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create app
    app = create_app(config)

    # Initialize services on startup
    @app.on_event("startup")
    async def startup():
        await initialize_services(config)
        logger.info(f"MAO Healer started on {host}:{port}")

    @app.on_event("shutdown")
    async def shutdown():
        router = _server_state.get("notification_router")
        if router:
            await router.close()
        logger.info("MAO Healer shutting down")

    # Run server
    uvicorn.run(app, host=host, port=port, log_level=log_level.lower())
