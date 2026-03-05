"""Metrics export API endpoints."""

from fastapi import APIRouter, Depends, Response
from fastapi.responses import PlainTextResponse

from app.export.prometheus import prometheus_exporter, mao_metrics
from app.export.datadog import datadog_exporter
from app.core.auth import get_current_tenant

router = APIRouter(tags=["metrics"])


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics(tenant_id: str = Depends(get_current_tenant)):
    metrics_text = prometheus_exporter.export()
    return Response(
        content=metrics_text,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get("/metrics/json")
async def metrics_json(tenant_id: str = Depends(get_current_tenant)):
    return {
        "traces": dict(mao_metrics.traces_total.get_all()),
        "detections": dict(mao_metrics.detections_total.get_all()),
        "tokens": dict(mao_metrics.tokens_total.get_all()),
        "cost": dict(mao_metrics.cost_total.get_all()),
        "active_traces": dict(mao_metrics.active_traces.get_all()),
        "detector_f1": dict(mao_metrics.detector_f1.get_all()),
        "detector_threshold": dict(mao_metrics.detector_threshold.get_all()),
        "detector_ece": dict(mao_metrics.detector_ece.get_all()),
    }


@router.post("/metrics/datadog/flush")
async def flush_datadog(tenant_id: str = Depends(get_current_tenant)):
    success = await datadog_exporter.flush()
    return {"success": success}


@router.get("/metrics/datadog/dashboard")
async def get_datadog_dashboard(tenant_id: str = Depends(get_current_tenant)):
    return datadog_exporter.get_dashboard_json()
