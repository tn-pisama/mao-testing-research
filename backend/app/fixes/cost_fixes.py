"""Fix generators for cost overrun detections."""

from typing import List, Dict, Any

from .generator import BaseFixGenerator
from .models import FixSuggestion, FixType, FixConfidence, CodeChange


class CostFixGenerator(BaseFixGenerator):
    """Generates fixes for cost overrun and budget-related detections."""

    def can_handle(self, detection_type: str) -> bool:
        return "cost" in detection_type or "budget" in detection_type

    def generate_fixes(
        self,
        detection: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[FixSuggestion]:
        fixes = []
        detection_id = detection.get("id", "")
        details = detection.get("details", {})

        fixes.append(self._budget_limiter_fix(detection_id, details, context))
        fixes.append(self._cost_monitor_fix(detection_id, details, context))
        fixes.append(self._token_optimizer_fix(detection_id, details, context))

        return fixes

    def _budget_limiter_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''from typing import Any, Callable, Dict, Optional
from dataclasses import dataclass, field
from enum import Enum
import time
import logging

logger = logging.getLogger(__name__)


class BudgetAction(Enum):
    CONTINUE = "continue"
    WARN = "warn"
    DEGRADE = "degrade"  # switch to cheaper model
    SHUTDOWN = "shutdown"


@dataclass
class BudgetConfig:
    hard_limit_usd: float = 10.0
    soft_limit_usd: float = 7.0    # trigger warnings
    degrade_limit_usd: float = 8.5  # switch to cheaper model
    per_call_limit_usd: float = 0.50


class BudgetLimiter:
    """
    Hard budget enforcement with graceful degradation.
    Tracks cumulative spend and blocks execution when budget is exhausted.
    """

    def __init__(self, config: Optional[BudgetConfig] = None):
        self._config = config or BudgetConfig()
        self._total_spent: float = 0.0
        self._call_count: int = 0
        self._started_at: float = time.time()
        self._shutdown: bool = False
        self._spend_log: list = []

    @property
    def remaining(self) -> float:
        return max(0.0, self._config.hard_limit_usd - self._total_spent)

    @property
    def utilization(self) -> float:
        if self._config.hard_limit_usd <= 0:
            return 0.0
        return self._total_spent / self._config.hard_limit_usd

    def check_budget(self, estimated_cost: float = 0.0) -> BudgetAction:
        """Check budget status before making a call."""
        if self._shutdown:
            return BudgetAction.SHUTDOWN

        projected = self._total_spent + estimated_cost

        if projected >= self._config.hard_limit_usd:
            logger.error(
                "Budget exhausted: $%.4f spent of $%.2f limit",
                self._total_spent,
                self._config.hard_limit_usd,
            )
            self._shutdown = True
            return BudgetAction.SHUTDOWN

        if projected >= self._config.degrade_limit_usd:
            logger.warning("Budget critical, degrading to cheaper model")
            return BudgetAction.DEGRADE

        if projected >= self._config.soft_limit_usd:
            logger.warning(
                "Budget warning: $%.4f of $%.2f",
                projected,
                self._config.hard_limit_usd,
            )
            return BudgetAction.WARN

        return BudgetAction.CONTINUE

    def record_spend(self, cost_usd: float, metadata: Optional[Dict] = None) -> None:
        self._total_spent += cost_usd
        self._call_count += 1
        self._spend_log.append({
            "cost": cost_usd,
            "cumulative": self._total_spent,
            "timestamp": time.time(),
            "metadata": metadata or {},
        })

    async def guarded_call(
        self,
        call_fn: Callable,
        args: Dict[str, Any],
        estimated_cost: float,
        fallback_fn: Optional[Callable] = None,
    ) -> Any:
        """Execute a call with budget guard. Uses fallback on DEGRADE."""
        action = self.check_budget(estimated_cost)

        if action == BudgetAction.SHUTDOWN:
            raise BudgetExhaustedError(
                f"Budget exhausted: ${self._total_spent:.4f} / "
                f"${self._config.hard_limit_usd:.2f}"
            )

        if action == BudgetAction.DEGRADE and fallback_fn:
            result = await fallback_fn(args)
        else:
            result = await call_fn(args)

        actual_cost = result.get("usage", {}).get("cost_usd", estimated_cost)
        self.record_spend(actual_cost, metadata={"action": action.value})
        return result

    def summary(self) -> Dict[str, Any]:
        elapsed = time.time() - self._started_at
        return {
            "total_spent_usd": round(self._total_spent, 4),
            "budget_limit_usd": self._config.hard_limit_usd,
            "remaining_usd": round(self.remaining, 4),
            "utilization_pct": round(self.utilization * 100, 1),
            "call_count": self._call_count,
            "elapsed_seconds": round(elapsed, 1),
            "shutdown": self._shutdown,
        }


class BudgetExhaustedError(Exception):
    pass'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="cost",
            fix_type=FixType.BUDGET_LIMITER,
            confidence=FixConfidence.HIGH,
            title="Enforce hard budget limit with graceful degradation",
            description=(
                "Track cumulative dollar spend and enforce a hard ceiling. "
                "Before the ceiling, degrade to cheaper models automatically. "
                "At the ceiling, shut down gracefully instead of running up costs."
            ),
            rationale=(
                "Without a hard budget limiter, runaway loops or unexpectedly "
                "expensive prompts can exhaust the budget before anyone notices. "
                "A per-call guard with graceful degradation keeps costs predictable."
            ),
            code_changes=[
                CodeChange(
                    file_path="utils/budget_limiter.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Hard budget enforcement with soft/degrade/shutdown thresholds",
                )
            ],
            estimated_impact="Prevents runaway cost by enforcing a hard ceiling with early degradation",
            tags=["cost", "budget", "limiter", "graceful-shutdown"],
        )

    def _cost_monitor_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import time
import logging

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class CostAlert:
    severity: AlertSeverity
    message: str
    current_spend: float
    threshold: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class CostRecord:
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float
    timestamp: float = field(default_factory=time.time)


# Average cost per 1K tokens (input / output) in USD
MODEL_PRICING = {
    "gpt-4o": (0.0025, 0.010),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4-turbo": (0.01, 0.03),
    "claude-3-5-sonnet": (0.003, 0.015),
    "claude-3-haiku": (0.00025, 0.00125),
    "claude-opus-4": (0.015, 0.075),
}


class CostMonitor:
    """Real-time cost tracking with configurable alert thresholds."""

    def __init__(
        self,
        alert_thresholds: Optional[Dict[str, float]] = None,
        alert_callback: Optional[Callable[[CostAlert], None]] = None,
    ):
        self._thresholds = alert_thresholds or {
            "info": 1.0,
            "warning": 5.0,
            "critical": 9.0,
        }
        self._callback = alert_callback or self._default_alert
        self._records: List[CostRecord] = []
        self._alerts_fired: Dict[str, bool] = {}
        self._window_start: float = time.time()

    def estimate_cost(
        self, model: str, input_tokens: int, output_tokens: int
    ) -> float:
        pricing = MODEL_PRICING.get(model, (0.005, 0.015))
        input_cost = (input_tokens / 1000) * pricing[0]
        output_cost = (output_tokens / 1000) * pricing[1]
        return input_cost + output_cost

    def record(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float = 0.0,
    ) -> CostRecord:
        cost = self.estimate_cost(model, input_tokens, output_tokens)
        record = CostRecord(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
        )
        self._records.append(record)
        self._check_alerts()
        return record

    @property
    def total_cost(self) -> float:
        return sum(r.cost_usd for r in self._records)

    @property
    def total_tokens(self) -> int:
        return sum(r.input_tokens + r.output_tokens for r in self._records)

    def cost_by_model(self) -> Dict[str, float]:
        breakdown: Dict[str, float] = {}
        for r in self._records:
            breakdown[r.model] = breakdown.get(r.model, 0.0) + r.cost_usd
        return breakdown

    def cost_rate_per_minute(self) -> float:
        elapsed = (time.time() - self._window_start) / 60.0
        return self.total_cost / elapsed if elapsed > 0 else 0.0

    def _check_alerts(self) -> None:
        total = self.total_cost
        for level, threshold in sorted(
            self._thresholds.items(), key=lambda x: x[1]
        ):
            if total >= threshold and not self._alerts_fired.get(level):
                severity = AlertSeverity(level)
                alert = CostAlert(
                    severity=severity,
                    message=f"Cost {level} threshold breached: ${total:.4f} >= ${threshold:.2f}",
                    current_spend=total,
                    threshold=threshold,
                )
                self._alerts_fired[level] = True
                self._callback(alert)

    @staticmethod
    def _default_alert(alert: CostAlert) -> None:
        if alert.severity == AlertSeverity.CRITICAL:
            logger.critical(alert.message)
        elif alert.severity == AlertSeverity.WARNING:
            logger.warning(alert.message)
        else:
            logger.info(alert.message)

    def summary(self) -> Dict[str, Any]:
        return {
            "total_cost_usd": round(self.total_cost, 4),
            "total_tokens": self.total_tokens,
            "call_count": len(self._records),
            "cost_by_model": self.cost_by_model(),
            "rate_per_minute": round(self.cost_rate_per_minute(), 4),
        }'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="cost",
            fix_type=FixType.COST_MONITOR,
            confidence=FixConfidence.HIGH,
            title="Add real-time cost tracking with tiered alerts",
            description=(
                "Track every LLM call's token usage and dollar cost in real time, "
                "with configurable alert thresholds at info, warning, and critical "
                "levels so operators can intervene before the budget is blown."
            ),
            rationale=(
                "Cost overruns are often detected after the fact. Real-time "
                "monitoring with progressive alerts gives operators early warning "
                "and the data needed to identify which models or steps are expensive."
            ),
            code_changes=[
                CodeChange(
                    file_path="utils/cost_monitor.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Real-time cost tracker with model pricing and alert callbacks",
                )
            ],
            estimated_impact="Provides early warning of cost overruns with per-model breakdown",
            tags=["cost", "monitoring", "alerts", "token-tracking"],
        )

    def _token_optimizer_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import re
import logging

logger = logging.getLogger(__name__)


class ModelTier(Enum):
    PREMIUM = "premium"    # gpt-4o, claude-opus-4
    STANDARD = "standard"  # gpt-4o-mini, claude-3-5-sonnet
    ECONOMY = "economy"    # gpt-4o-mini, claude-3-haiku


MODEL_TIERS = {
    ModelTier.PREMIUM: ["claude-opus-4", "gpt-4-turbo"],
    ModelTier.STANDARD: ["claude-3-5-sonnet", "gpt-4o"],
    ModelTier.ECONOMY: ["claude-3-haiku", "gpt-4o-mini"],
}


@dataclass
class RoutingRule:
    """Route a task to a specific model tier based on heuristics."""
    name: str
    matcher: Callable[[Dict[str, Any]], bool]
    tier: ModelTier


class TokenOptimizer:
    """
    Reduce cost via intelligent model routing and prompt compression.
    Routes simple tasks to cheaper models and compresses verbose prompts.
    """

    def __init__(self, default_tier: ModelTier = ModelTier.STANDARD):
        self._default_tier = default_tier
        self._rules: List[RoutingRule] = []
        self._savings_log: list = []

    def add_rule(self, rule: RoutingRule) -> None:
        self._rules.append(rule)

    def select_model(self, task: Dict[str, Any]) -> Tuple[ModelTier, str]:
        """Select the cheapest appropriate model for a task."""
        for rule in self._rules:
            if rule.matcher(task):
                models = MODEL_TIERS.get(rule.tier, [])
                model = models[0] if models else "gpt-4o-mini"
                return (rule.tier, model)
        models = MODEL_TIERS.get(self._default_tier, [])
        return (self._default_tier, models[0] if models else "gpt-4o")

    @staticmethod
    def compress_prompt(prompt: str, max_tokens: int = 2000) -> str:
        """
        Compress a prompt to fit within token budget.
        Uses heuristic compression (not tokenizer-exact).
        """
        # Approximate: 1 token ~ 4 characters
        approx_tokens = len(prompt) // 4
        if approx_tokens <= max_tokens:
            return prompt

        compressed = prompt

        # 1. Remove excessive whitespace
        compressed = re.sub(r"\n{3,}", "\n\n", compressed)
        compressed = re.sub(r" {2,}", " ", compressed)

        # 2. Remove markdown formatting that doesn't add meaning
        compressed = re.sub(r"#{1,6}\s+", "", compressed)
        compressed = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", compressed)

        # 3. Truncate very long code blocks (keep first/last 5 lines)
        def truncate_code(match):
            lines = match.group(1).split("\n")
            if len(lines) > 15:
                kept = lines[:5] + ["  # ... truncated ..."] + lines[-5:]
                return "```\n" + "\n".join(kept) + "\n```"
            return match.group(0)

        compressed = re.sub(
            r"```[^\n]*\n(.*?)```",
            truncate_code,
            compressed,
            flags=re.DOTALL,
        )

        # 4. Final hard truncation if still too long
        char_limit = max_tokens * 4
        if len(compressed) > char_limit:
            compressed = compressed[:char_limit] + "\n[...truncated for budget]"

        saved_chars = len(prompt) - len(compressed)
        if saved_chars > 0:
            logger.info(
                "Prompt compressed: %d -> %d chars (saved ~%d tokens)",
                len(prompt),
                len(compressed),
                saved_chars // 4,
            )
        return compressed

    async def optimized_call(
        self,
        task: Dict[str, Any],
        call_fn: Callable,
        prompt: str,
        max_prompt_tokens: int = 2000,
    ) -> Dict[str, Any]:
        """Route to optimal model and compress prompt before calling."""
        tier, model = self.select_model(task)
        compressed = self.compress_prompt(prompt, max_prompt_tokens)

        original_tokens = len(prompt) // 4
        compressed_tokens = len(compressed) // 4
        token_savings = original_tokens - compressed_tokens

        result = await call_fn(model=model, prompt=compressed, **task)

        self._savings_log.append({
            "tier": tier.value,
            "model": model,
            "original_tokens": original_tokens,
            "compressed_tokens": compressed_tokens,
            "token_savings": token_savings,
        })
        return result

    def total_savings(self) -> Dict[str, Any]:
        total_saved = sum(e["token_savings"] for e in self._savings_log)
        return {
            "total_token_savings": total_saved,
            "calls_optimized": len(self._savings_log),
            "tier_distribution": self._tier_distribution(),
        }

    def _tier_distribution(self) -> Dict[str, int]:
        dist: Dict[str, int] = {}
        for entry in self._savings_log:
            tier = entry["tier"]
            dist[tier] = dist.get(tier, 0) + 1
        return dist'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="cost",
            fix_type=FixType.TOKEN_OPTIMIZER,
            confidence=FixConfidence.MEDIUM,
            title="Optimize cost with model routing and prompt compression",
            description=(
                "Route tasks to the cheapest model that can handle them and compress "
                "verbose prompts to reduce token consumption, cutting cost without "
                "significantly impacting output quality."
            ),
            rationale=(
                "Many workflows use a single expensive model for every task, including "
                "simple ones. Intelligent model routing sends simple tasks to cheaper "
                "models while prompt compression eliminates wasted tokens."
            ),
            code_changes=[
                CodeChange(
                    file_path="utils/token_optimizer.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Model routing by task complexity and heuristic prompt compression",
                )
            ],
            estimated_impact="Reduces token spend by routing to cheaper models and compressing prompts",
            tags=["cost", "optimization", "model-routing", "prompt-compression"],
        )
