"""
Regression Alerts - Alert management for model regression.

Provides:
- Alert generation from drift results
- Alert routing and prioritization
- Weekly regression reports
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

from .drift import DriftResult, DriftSeverity, DriftType

logger = logging.getLogger(__name__)


class AlertType(str, Enum):
    DRIFT_DETECTED = "drift_detected"
    MODEL_UPDATE = "model_update"
    THRESHOLD_BREACH = "threshold_breach"
    BASELINE_STALE = "baseline_stale"
    REGRESSION_SUMMARY = "regression_summary"


class AlertPriority(str, Enum):
    P1 = "p1"
    P2 = "p2"
    P3 = "p3"
    P4 = "p4"


class AlertStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


@dataclass
class RegressionAlert:
    id: str
    alert_type: AlertType
    priority: AlertPriority
    status: AlertStatus
    
    title: str
    message: str
    
    tenant_id: str
    agent_name: Optional[str] = None
    model: Optional[str] = None
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    
    drift_results: list[DriftResult] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_drift(
        cls,
        drift: DriftResult,
        tenant_id: str,
        agent_name: Optional[str] = None,
        model: Optional[str] = None,
    ) -> "RegressionAlert":
        priority = cls._severity_to_priority(drift.severity)
        
        return cls(
            id=str(uuid.uuid4()),
            alert_type=AlertType.DRIFT_DETECTED,
            priority=priority,
            status=AlertStatus.OPEN,
            title=f"{drift.drift_type.value.title()} Drift Detected",
            message=drift.explanation,
            tenant_id=tenant_id,
            agent_name=agent_name,
            model=model,
            drift_results=[drift],
            metadata={
                "similarity": drift.similarity_score,
                "suggested_action": drift.suggested_action,
            },
        )

    @staticmethod
    def _severity_to_priority(severity: DriftSeverity) -> AlertPriority:
        mapping = {
            DriftSeverity.CRITICAL: AlertPriority.P1,
            DriftSeverity.HIGH: AlertPriority.P2,
            DriftSeverity.MEDIUM: AlertPriority.P3,
            DriftSeverity.LOW: AlertPriority.P4,
            DriftSeverity.NONE: AlertPriority.P4,
        }
        return mapping.get(severity, AlertPriority.P3)


class AlertManager:
    """
    Manages regression alerts.
    """
    
    def __init__(self):
        self.alerts: dict[str, RegressionAlert] = {}
        self.by_tenant: dict[str, list[str]] = {}
        self.suppressed_patterns: list[dict] = []

    def create_alert(
        self,
        alert_type: AlertType,
        priority: AlertPriority,
        title: str,
        message: str,
        tenant_id: str,
        agent_name: Optional[str] = None,
        model: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> RegressionAlert:
        if self._is_suppressed(tenant_id, agent_name, model, alert_type):
            logger.info(f"Alert suppressed: {title}")
            return None
        
        alert = RegressionAlert(
            id=str(uuid.uuid4()),
            alert_type=alert_type,
            priority=priority,
            status=AlertStatus.OPEN,
            title=title,
            message=message,
            tenant_id=tenant_id,
            agent_name=agent_name,
            model=model,
            metadata=metadata or {},
        )
        
        self.alerts[alert.id] = alert
        
        if tenant_id not in self.by_tenant:
            self.by_tenant[tenant_id] = []
        self.by_tenant[tenant_id].append(alert.id)
        
        return alert

    def create_from_drift(
        self,
        drift: DriftResult,
        tenant_id: str,
        agent_name: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Optional[RegressionAlert]:
        if not drift.detected:
            return None
        
        if self._is_suppressed(tenant_id, agent_name, model, AlertType.DRIFT_DETECTED):
            return None
        
        alert = RegressionAlert.from_drift(drift, tenant_id, agent_name, model)
        self.alerts[alert.id] = alert
        
        if tenant_id not in self.by_tenant:
            self.by_tenant[tenant_id] = []
        self.by_tenant[tenant_id].append(alert.id)
        
        return alert

    def create_batch_alerts(
        self,
        drifts: list[DriftResult],
        tenant_id: str,
        agent_name: Optional[str] = None,
        model: Optional[str] = None,
    ) -> list[RegressionAlert]:
        significant = [d for d in drifts if d.detected and d.severity in [
            DriftSeverity.HIGH, DriftSeverity.CRITICAL
        ]]
        
        if not significant:
            return []
        
        if len(significant) >= 3:
            return [self._create_aggregate_alert(significant, tenant_id, agent_name, model)]
        
        return [
            self.create_from_drift(d, tenant_id, agent_name, model)
            for d in significant
            if d is not None
        ]

    def _create_aggregate_alert(
        self,
        drifts: list[DriftResult],
        tenant_id: str,
        agent_name: Optional[str],
        model: Optional[str],
    ) -> RegressionAlert:
        critical = sum(1 for d in drifts if d.severity == DriftSeverity.CRITICAL)
        high = sum(1 for d in drifts if d.severity == DriftSeverity.HIGH)
        
        priority = AlertPriority.P1 if critical > 0 else AlertPriority.P2
        
        alert = RegressionAlert(
            id=str(uuid.uuid4()),
            alert_type=AlertType.REGRESSION_SUMMARY,
            priority=priority,
            status=AlertStatus.OPEN,
            title=f"Multiple Regressions Detected ({len(drifts)} prompts)",
            message=f"Detected drift in {len(drifts)} prompts. Critical: {critical}, High: {high}",
            tenant_id=tenant_id,
            agent_name=agent_name,
            model=model,
            drift_results=drifts,
            metadata={
                "total_drifts": len(drifts),
                "critical_count": critical,
                "high_count": high,
            },
        )
        
        self.alerts[alert.id] = alert
        
        if tenant_id not in self.by_tenant:
            self.by_tenant[tenant_id] = []
        self.by_tenant[tenant_id].append(alert.id)
        
        return alert

    def get_alert(self, alert_id: str) -> Optional[RegressionAlert]:
        return self.alerts.get(alert_id)

    def get_alerts_for_tenant(
        self,
        tenant_id: str,
        status: Optional[AlertStatus] = None,
        priority: Optional[AlertPriority] = None,
    ) -> list[RegressionAlert]:
        alert_ids = self.by_tenant.get(tenant_id, [])
        alerts = [self.alerts[aid] for aid in alert_ids if aid in self.alerts]
        
        if status:
            alerts = [a for a in alerts if a.status == status]
        if priority:
            alerts = [a for a in alerts if a.priority == priority]
        
        return sorted(alerts, key=lambda a: (a.priority.value, a.created_at))

    def acknowledge(self, alert_id: str) -> bool:
        alert = self.get_alert(alert_id)
        if alert:
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.updated_at = datetime.utcnow()
            return True
        return False

    def resolve(self, alert_id: str) -> bool:
        alert = self.get_alert(alert_id)
        if alert:
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.utcnow()
            alert.updated_at = datetime.utcnow()
            return True
        return False

    def suppress_pattern(
        self,
        tenant_id: str,
        agent_name: Optional[str] = None,
        model: Optional[str] = None,
        alert_type: Optional[AlertType] = None,
        duration_hours: int = 24,
    ):
        self.suppressed_patterns.append({
            "tenant_id": tenant_id,
            "agent_name": agent_name,
            "model": model,
            "alert_type": alert_type,
            "expires_at": datetime.utcnow() + timedelta(hours=duration_hours),
        })

    def _is_suppressed(
        self,
        tenant_id: str,
        agent_name: Optional[str],
        model: Optional[str],
        alert_type: AlertType,
    ) -> bool:
        now = datetime.utcnow()
        
        for pattern in self.suppressed_patterns:
            if pattern["expires_at"] < now:
                continue
            
            if pattern["tenant_id"] != tenant_id:
                continue
            
            if pattern["agent_name"] and pattern["agent_name"] != agent_name:
                continue
            
            if pattern["model"] and pattern["model"] != model:
                continue
            
            if pattern["alert_type"] and pattern["alert_type"] != alert_type:
                continue
            
            return True
        
        return False

    def generate_weekly_report(self, tenant_id: str) -> dict:
        week_ago = datetime.utcnow() - timedelta(days=7)
        alerts = self.get_alerts_for_tenant(tenant_id)
        recent = [a for a in alerts if a.created_at >= week_ago]
        
        by_priority = {p.value: 0 for p in AlertPriority}
        by_type = {t.value: 0 for t in AlertType}
        by_status = {s.value: 0 for s in AlertStatus}
        
        for alert in recent:
            by_priority[alert.priority.value] += 1
            by_type[alert.alert_type.value] += 1
            by_status[alert.status.value] += 1
        
        return {
            "period_start": week_ago.isoformat(),
            "period_end": datetime.utcnow().isoformat(),
            "total_alerts": len(recent),
            "by_priority": by_priority,
            "by_type": by_type,
            "by_status": by_status,
            "open_alerts": by_status.get("open", 0),
            "resolved_alerts": by_status.get("resolved", 0),
        }


alert_manager = AlertManager()
