"""Fix generators for communication breakdown detections."""

from typing import List, Dict, Any

from .generator import BaseFixGenerator
from .models import FixSuggestion, FixType, FixConfidence, CodeChange


class CommunicationFixGenerator(BaseFixGenerator):
    """Generates fixes for communication breakdown detections."""

    def can_handle(self, detection_type: str) -> bool:
        return "communication" in detection_type or "channel" in detection_type

    def generate_fixes(
        self,
        detection: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[FixSuggestion]:
        fixes = []
        detection_id = detection.get("id", "")
        details = detection.get("details", {})

        fixes.append(self._message_schema_fix(detection_id, details, context))
        fixes.append(self._handoff_protocol_fix(detection_id, details, context))
        fixes.append(self._retry_limit_fix(detection_id, details, context))

        return fixes

    def _message_schema_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import uuid
import json

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Standard message types for inter-agent communication."""
    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    STATUS_UPDATE = "status_update"
    ERROR_REPORT = "error_report"
    CONTEXT_SHARE = "context_share"
    HANDOFF = "handoff"
    ACKNOWLEDGMENT = "acknowledgment"


class MessagePriority(Enum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class AgentMessage:
    """Typed, validated message format for inter-agent communication."""
    message_id: str
    message_type: MessageType
    sender: str
    recipient: str
    payload: Dict[str, Any]
    priority: MessagePriority = MessagePriority.NORMAL
    correlation_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    ttl_seconds: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        message_type: MessageType,
        sender: str,
        recipient: str,
        payload: Dict[str, Any],
        **kwargs,
    ) -> "AgentMessage":
        return cls(
            message_id=str(uuid.uuid4()),
            message_type=message_type,
            sender=sender,
            recipient=recipient,
            payload=payload,
            **kwargs,
        )

    def validate(self) -> List[str]:
        """Validate message structure. Returns list of errors."""
        errors = []
        if not self.sender:
            errors.append("Message must have a sender")
        if not self.recipient:
            errors.append("Message must have a recipient")
        if not isinstance(self.payload, dict):
            errors.append("Payload must be a dictionary")

        required_fields = MESSAGE_SCHEMAS.get(self.message_type, {})
        for req_field in required_fields.get("required", []):
            if req_field not in self.payload:
                errors.append(
                    f"Missing required field '{req_field}' for {self.message_type.value}"
                )
        return errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "message_type": self.message_type.value,
            "sender": self.sender,
            "recipient": self.recipient,
            "payload": self.payload,
            "priority": self.priority.value,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp.isoformat(),
            "ttl_seconds": self.ttl_seconds,
            "metadata": self.metadata,
        }


# Define required payload fields per message type
MESSAGE_SCHEMAS: Dict[MessageType, Dict[str, Any]] = {
    MessageType.TASK_REQUEST: {
        "required": ["task_description", "expected_output_format"],
        "optional": ["constraints", "deadline"],
    },
    MessageType.TASK_RESPONSE: {
        "required": ["status", "result"],
        "optional": ["confidence", "warnings"],
    },
    MessageType.ERROR_REPORT: {
        "required": ["error_type", "error_message"],
        "optional": ["recoverable", "suggested_action"],
    },
    MessageType.HANDOFF: {
        "required": ["task_context", "handoff_reason"],
        "optional": ["partial_result", "instructions"],
    },
}


class MessageBus:
    """Central message bus enforcing typed communication."""

    def __init__(self):
        self._log: List[AgentMessage] = []

    def send(self, message: AgentMessage) -> bool:
        errors = message.validate()
        if errors:
            logger.error(f"Invalid message from {message.sender}: {errors}")
            raise MessageValidationError(f"Message validation failed: {errors}")
        self._log.append(message)
        logger.info(
            f"[{message.message_type.value}] {message.sender} -> "
            f"{message.recipient} (id={message.message_id[:8]})"
        )
        return True

    def get_messages_for(
        self, recipient: str, message_type: Optional[MessageType] = None
    ) -> List[AgentMessage]:
        msgs = [m for m in self._log if m.recipient == recipient]
        if message_type:
            msgs = [m for m in msgs if m.message_type == message_type]
        return msgs


class MessageValidationError(Exception):
    pass'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="communication_breakdown",
            fix_type=FixType.MESSAGE_SCHEMA,
            confidence=FixConfidence.HIGH,
            title="Enforce typed message schema for inter-agent communication",
            description="Replace free-form agent-to-agent messaging with a typed, validated message format that enforces required fields per message type and logs all communication.",
            rationale="Communication breakdowns often stem from mismatched expectations about message format and content. A typed schema with validation catches malformed messages at send time and provides a clear contract between agents.",
            code_changes=[
                CodeChange(
                    file_path="utils/message_schema.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Typed message format with validation and central message bus",
                )
            ],
            estimated_impact="Prevents miscommunication by enforcing message contracts between agents",
            tags=["communication", "message-schema", "validation", "reliability"],
        )

    def _handoff_protocol_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''import logging
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class HandoffState(Enum):
    INITIATED = "initiated"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass
class HandoffRecord:
    """Tracks the lifecycle of a single agent handoff."""
    handoff_id: str
    from_agent: str
    to_agent: str
    task_context: Dict[str, Any]
    state: HandoffState = HandoffState.INITIATED
    initiated_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0


class HandoffProtocol:
    """
    Three-phase acknowledgment protocol for agent handoffs:
    1. Initiate - sender requests handoff
    2. Acknowledge - receiver confirms receipt
    3. Complete/Fail - receiver reports outcome

    Prevents lost handoffs and provides visibility into handoff status.
    """

    def __init__(
        self,
        ack_timeout: float = 10.0,
        completion_timeout: float = 120.0,
        max_retries: int = 3,
    ):
        self._ack_timeout = ack_timeout
        self._completion_timeout = completion_timeout
        self._max_retries = max_retries
        self._handoffs: Dict[str, HandoffRecord] = {}
        self._callbacks: Dict[str, asyncio.Event] = {}

    async def initiate_handoff(
        self,
        from_agent: str,
        to_agent: str,
        task_context: Dict[str, Any],
    ) -> HandoffRecord:
        """Initiate a handoff and wait for acknowledgment."""
        handoff_id = str(uuid.uuid4())
        record = HandoffRecord(
            handoff_id=handoff_id,
            from_agent=from_agent,
            to_agent=to_agent,
            task_context=task_context,
        )
        self._handoffs[handoff_id] = record
        self._callbacks[handoff_id] = asyncio.Event()

        logger.info(f"Handoff initiated: {from_agent} -> {to_agent} (id={handoff_id[:8]})")

        # Wait for acknowledgment
        try:
            await asyncio.wait_for(
                self._callbacks[handoff_id].wait(),
                timeout=self._ack_timeout,
            )
            logger.info(f"Handoff {handoff_id[:8]} acknowledged by {to_agent}")
        except asyncio.TimeoutError:
            record.state = HandoffState.TIMED_OUT
            logger.warning(
                f"Handoff {handoff_id[:8]} not acknowledged by {to_agent} "
                f"within {self._ack_timeout}s"
            )
            raise HandoffTimeoutError(
                f"Agent '{to_agent}' did not acknowledge handoff within {self._ack_timeout}s"
            )

        return record

    def acknowledge(self, handoff_id: str, agent: str) -> HandoffRecord:
        """Acknowledge receipt of a handoff."""
        record = self._handoffs.get(handoff_id)
        if not record:
            raise ValueError(f"Unknown handoff: {handoff_id}")
        if record.to_agent != agent:
            raise ValueError(f"Agent '{agent}' is not the recipient of this handoff")

        record.state = HandoffState.ACKNOWLEDGED
        record.acknowledged_at = datetime.utcnow()
        if handoff_id in self._callbacks:
            self._callbacks[handoff_id].set()
        return record

    def complete(
        self, handoff_id: str, agent: str, result: Dict[str, Any]
    ) -> HandoffRecord:
        """Mark a handoff as completed with result."""
        record = self._handoffs.get(handoff_id)
        if not record:
            raise ValueError(f"Unknown handoff: {handoff_id}")
        record.state = HandoffState.COMPLETED
        record.completed_at = datetime.utcnow()
        record.result = result
        logger.info(f"Handoff {handoff_id[:8]} completed by {agent}")
        return record

    def fail(self, handoff_id: str, agent: str, error: str) -> HandoffRecord:
        """Mark a handoff as failed."""
        record = self._handoffs.get(handoff_id)
        if not record:
            raise ValueError(f"Unknown handoff: {handoff_id}")
        record.state = HandoffState.FAILED
        record.error = error
        logger.error(f"Handoff {handoff_id[:8]} failed: {error}")
        return record

    def get_pending_handoffs(self, agent: str) -> List[HandoffRecord]:
        """Get all pending handoffs for an agent."""
        return [
            h for h in self._handoffs.values()
            if h.to_agent == agent and h.state in (HandoffState.INITIATED, HandoffState.ACKNOWLEDGED)
        ]


class HandoffTimeoutError(Exception):
    pass'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="communication_breakdown",
            fix_type=FixType.HANDOFF_PROTOCOL,
            confidence=FixConfidence.HIGH,
            title="Add three-phase acknowledgment protocol for agent handoffs",
            description="Implement an initiate-acknowledge-complete protocol for all agent handoffs, ensuring no handoff is silently lost and providing visibility into handoff state.",
            rationale="Communication breakdowns frequently occur during handoffs when the receiving agent never processes the request. A three-phase protocol with timeouts guarantees that failed handoffs are detected immediately rather than causing silent failures downstream.",
            code_changes=[
                CodeChange(
                    file_path="utils/handoff_protocol.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Three-phase handoff protocol with acknowledgment and timeout handling",
                )
            ],
            estimated_impact="Eliminates silent handoff failures, provides immediate detection of communication breakdowns",
            tags=["communication", "handoff", "protocol", "acknowledgment"],
        )

    def _retry_limit_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''import logging
import asyncio
from typing import Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class EscalationLevel(Enum):
    RETRY = "retry"
    ALTERNATE_AGENT = "alternate_agent"
    HUMAN_ESCALATION = "human_escalation"
    ABORT = "abort"


@dataclass
class RetryPolicy:
    """Configuration for message retry behavior."""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    backoff_factor: float = 2.0
    escalation_after: int = 2  # escalate after this many retries


@dataclass
class DeliveryAttempt:
    """Record of a single message delivery attempt."""
    attempt_number: int
    timestamp: datetime
    success: bool
    error: Optional[str] = None
    response_time_ms: Optional[float] = None


class MessageRetryManager:
    """
    Manages retry logic for failed inter-agent messages with
    exponential backoff and escalation to alternate agents or humans.
    """

    def __init__(
        self,
        default_policy: Optional[RetryPolicy] = None,
        escalation_handler: Optional[Callable] = None,
    ):
        self._policy = default_policy or RetryPolicy()
        self._escalation_handler = escalation_handler
        self._delivery_log: Dict[str, list] = {}

    def _compute_delay(self, attempt: int) -> float:
        delay = self._policy.base_delay * (self._policy.backoff_factor ** attempt)
        return min(delay, self._policy.max_delay)

    async def send_with_retry(
        self,
        message_id: str,
        send_fn: Callable[..., Awaitable[Dict[str, Any]]],
        *args,
        policy: Optional[RetryPolicy] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Attempt to send a message with retry and escalation.

        Args:
            message_id: Unique identifier for tracking
            send_fn: Async function that sends the message
            policy: Optional override policy
        """
        policy = policy or self._policy
        self._delivery_log[message_id] = []

        for attempt in range(policy.max_retries + 1):
            start = datetime.utcnow()
            try:
                result = await send_fn(*args, **kwargs)
                elapsed = (datetime.utcnow() - start).total_seconds() * 1000

                self._delivery_log[message_id].append(
                    DeliveryAttempt(
                        attempt_number=attempt + 1,
                        timestamp=start,
                        success=True,
                        response_time_ms=elapsed,
                    )
                )
                if attempt > 0:
                    logger.info(
                        f"Message {message_id[:8]} delivered on attempt {attempt + 1}"
                    )
                return result

            except Exception as e:
                elapsed = (datetime.utcnow() - start).total_seconds() * 1000
                self._delivery_log[message_id].append(
                    DeliveryAttempt(
                        attempt_number=attempt + 1,
                        timestamp=start,
                        success=False,
                        error=str(e),
                        response_time_ms=elapsed,
                    )
                )
                logger.warning(
                    f"Message {message_id[:8]} attempt {attempt + 1} failed: {e}"
                )

                # Check if we should escalate
                if attempt >= policy.escalation_after:
                    escalation = await self._escalate(message_id, attempt, str(e))
                    if escalation.get("resolved"):
                        return escalation.get("result", {})

                # Last attempt exhausted
                if attempt >= policy.max_retries:
                    logger.error(
                        f"Message {message_id[:8]} failed after "
                        f"{policy.max_retries + 1} attempts"
                    )
                    raise MessageDeliveryError(
                        f"Failed to deliver message after {policy.max_retries + 1} attempts"
                    ) from e

                delay = self._compute_delay(attempt)
                logger.info(f"Retrying message {message_id[:8]} in {delay:.1f}s")
                await asyncio.sleep(delay)

        raise MessageDeliveryError("Retry loop exhausted unexpectedly")

    async def _escalate(
        self, message_id: str, attempt: int, error: str
    ) -> Dict[str, Any]:
        """Escalate a failing message delivery."""
        level = EscalationLevel.ALTERNATE_AGENT
        if attempt >= self._policy.max_retries:
            level = EscalationLevel.HUMAN_ESCALATION

        logger.warning(f"Escalating message {message_id[:8]} to level: {level.value}")

        if self._escalation_handler:
            return await self._escalation_handler(message_id, level, error)

        return {"resolved": False}

    def get_delivery_stats(self, message_id: str) -> Dict[str, Any]:
        """Get delivery statistics for a message."""
        attempts = self._delivery_log.get(message_id, [])
        return {
            "total_attempts": len(attempts),
            "successful": any(a.success for a in attempts),
            "avg_response_ms": (
                sum(a.response_time_ms or 0 for a in attempts) / len(attempts)
                if attempts else 0
            ),
        }


class MessageDeliveryError(Exception):
    pass'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="communication_breakdown",
            fix_type=FixType.RETRY_LIMIT,
            confidence=FixConfidence.MEDIUM,
            title="Retry failed messages with exponential backoff and escalation",
            description="Add retry logic with exponential backoff for failed inter-agent messages, with automatic escalation to alternate agents or human oversight after repeated failures.",
            rationale="Transient communication failures between agents can be recovered by retrying with backoff. When retries are exhausted, escalation ensures the failure is handled rather than silently dropped, preventing cascading breakdowns.",
            code_changes=[
                CodeChange(
                    file_path="utils/message_retry.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Message retry manager with exponential backoff and escalation",
                )
            ],
            estimated_impact="Recovers from transient communication failures automatically, escalates persistent issues",
            tags=["communication", "retry", "backoff", "escalation"],
        )
