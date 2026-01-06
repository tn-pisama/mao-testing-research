"""
Tests for Regression Detection Module
=====================================

Comprehensive tests for:
- Model fingerprinting
- Baseline storage
- Drift detection
- Alert management
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app.enterprise.regression.fingerprint import (
    model_fingerprinter,
    ModelFingerprinter,
    ModelFingerprint,
)
from app.enterprise.regression.baseline import (
    baseline_store,
    BaselineStore,
    Baseline,
    BaselineEntry,
)
from app.enterprise.regression.drift import (
    drift_detector,
    DriftDetector,
    DriftResult,
    DriftSeverity,
    DriftType,
)
from app.enterprise.regression.alerts import (
    alert_manager,
    AlertManager,
    RegressionAlert,
    AlertType,
    AlertPriority,
    AlertStatus,
)


# =============================================================================
# Model Fingerprint Tests
# =============================================================================

class TestModelFingerprinter:
    """Tests for model fingerprinting."""

    def test_fingerprint_openai_model(self):
        """Test fingerprinting OpenAI models."""
        fp = ModelFingerprinter()
        result = fp.fingerprint("gpt-4o-2024-08-06")

        assert result.model_id == "gpt-4o-2024-08-06"
        assert result.provider == "openai"
        assert result.version == "2024-08-06"
        assert result.fingerprint_hash is not None
        assert len(result.fingerprint_hash) == 16

    def test_fingerprint_anthropic_model(self):
        """Test fingerprinting Anthropic models."""
        fp = ModelFingerprinter()
        result = fp.fingerprint("claude-3-5-sonnet-20241022")

        assert result.provider == "anthropic"
        assert result.version == "20241022"

    def test_fingerprint_google_model(self):
        """Test fingerprinting Google models."""
        fp = ModelFingerprinter()
        result = fp.fingerprint("gemini-1.5-pro")

        assert result.provider == "google"

    def test_fingerprint_unknown_provider(self):
        """Test fingerprinting unknown provider models."""
        fp = ModelFingerprinter()
        result = fp.fingerprint("custom-model-v1")

        assert result.provider == "unknown"

    def test_detect_preview_model(self):
        """Test detection of preview models."""
        fp = ModelFingerprinter()
        result = fp.fingerprint("gpt-4-turbo-preview")

        assert result.is_preview == True

    def test_detect_deprecated_model(self):
        """Test detection of deprecated models."""
        fp = ModelFingerprinter()
        result = fp.fingerprint("gpt-4-0314")

        assert result.is_deprecated == True

    def test_known_model_context_window(self):
        """Test known model context window lookup."""
        fp = ModelFingerprinter()
        result = fp.fingerprint("gpt-4o-2024-08-06")

        assert result.context_window == 128000
        assert result.known_cutoff == "Oct 2023"

    def test_detect_version_change(self):
        """Test version change detection."""
        fp = ModelFingerprinter()

        # First fingerprint
        initial = fp.fingerprint("gpt-4o")

        # Check against different hash
        changed, message = fp.detect_version_change("gpt-4o", "different_hash")

        assert changed == True
        assert "changed" in message.lower()

    def test_detect_no_version_change(self):
        """Test no version change detection."""
        fp = ModelFingerprinter()

        initial = fp.fingerprint("gpt-4o")
        changed, message = fp.detect_version_change("gpt-4o", initial.fingerprint_hash)

        assert changed == False

    def test_get_version_history(self):
        """Test version history retrieval."""
        fp = ModelFingerprinter()

        fp.detect_version_change("gpt-4o", "old_hash_1")
        fp.detect_version_change("gpt-4o", "old_hash_2")

        history = fp.get_version_history("gpt-4o")
        assert len(history) >= 2

    def test_compare_models_same_provider(self):
        """Test comparing models from same provider."""
        fp = ModelFingerprinter()
        result = fp.compare_models("gpt-4o-2024-08-06", "gpt-4o-2024-11-20")

        assert result["same_provider"] == True
        assert result["same_family"] == True

    def test_compare_models_different_provider(self):
        """Test comparing models from different providers."""
        fp = ModelFingerprinter()
        result = fp.compare_models("gpt-4o", "claude-3-opus")

        assert result["same_provider"] == False
        assert result["same_family"] == False

    def test_extract_version_date_format(self):
        """Test version extraction with date format."""
        fp = ModelFingerprinter()
        version = fp._extract_version("gpt-4o-2024-08-06")
        assert version == "2024-08-06"

    def test_extract_version_numeric_format(self):
        """Test version extraction with numeric format."""
        fp = ModelFingerprinter()
        version = fp._extract_version("gemini-1.5-pro")
        assert version in ["1.5", "1"]

    def test_detect_meta_provider(self):
        """Test detection of Meta provider."""
        fp = ModelFingerprinter()
        provider = fp._detect_provider("llama-2-70b")
        assert provider == "meta"

    def test_detect_mistral_provider(self):
        """Test detection of Mistral provider."""
        fp = ModelFingerprinter()
        provider = fp._detect_provider("mixtral-8x7b")
        assert provider == "mistral"


# =============================================================================
# Baseline Store Tests
# =============================================================================

class TestBaselineEntry:
    """Tests for baseline entries."""

    def test_create_baseline_entry(self):
        """Test creating a baseline entry."""
        entry = BaselineEntry.create(
            prompt="What is 2+2?",
            output="The answer is 4.",
            model="gpt-4o",
            tokens_used=50,
            latency_ms=200,
        )

        assert entry.prompt_text == "What is 2+2?"
        assert entry.output_text == "The answer is 4."
        assert entry.model == "gpt-4o"
        assert entry.tokens_used == 50
        assert entry.latency_ms == 200
        assert entry.prompt_hash is not None
        assert entry.output_hash is not None

    def test_baseline_entry_hashing(self):
        """Test that same prompts produce same hashes."""
        entry1 = BaselineEntry.create(prompt="Hello", output="Hi", model="gpt-4")
        entry2 = BaselineEntry.create(prompt="Hello", output="Hi there", model="gpt-4")

        assert entry1.prompt_hash == entry2.prompt_hash
        assert entry1.output_hash != entry2.output_hash

    def test_baseline_entry_with_tags(self):
        """Test baseline entry with tags."""
        entry = BaselineEntry.create(
            prompt="Test",
            output="Result",
            model="gpt-4",
            tags=["production", "critical"],
        )

        assert "production" in entry.tags
        assert "critical" in entry.tags


class TestBaseline:
    """Tests for baseline management."""

    def test_create_baseline(self):
        """Test creating a baseline."""
        baseline = Baseline(
            name="Test Baseline",
            description="For testing",
            tenant_id="tenant-1",
        )

        assert baseline.name == "Test Baseline"
        assert baseline.tenant_id == "tenant-1"
        assert baseline.is_active == True
        assert len(baseline.entries) == 0

    def test_add_entry_to_baseline(self):
        """Test adding entries to baseline."""
        baseline = Baseline(
            name="Test",
            description="Test",
            tenant_id="tenant-1",
        )

        entry = BaselineEntry.create(
            prompt="Test prompt",
            output="Test output",
            model="gpt-4",
        )

        baseline.add_entry(entry)

        assert baseline.total_prompts == 1
        assert "gpt-4" in baseline.models_covered

    def test_get_entry_by_prompt(self):
        """Test retrieving entry by prompt."""
        baseline = Baseline(
            name="Test",
            description="Test",
            tenant_id="tenant-1",
        )

        entry = BaselineEntry.create(
            prompt="What is AI?",
            output="AI is artificial intelligence",
            model="gpt-4",
        )
        baseline.add_entry(entry)

        found = baseline.get_entry_by_prompt("What is AI?")
        assert found is not None
        assert found.output_text == "AI is artificial intelligence"

    def test_get_entry_not_found(self):
        """Test retrieving non-existent entry."""
        baseline = Baseline(
            name="Test",
            description="Test",
            tenant_id="tenant-1",
        )

        found = baseline.get_entry_by_prompt("Unknown prompt")
        assert found is None

    def test_get_entries_by_model(self):
        """Test retrieving entries by model."""
        baseline = Baseline(
            name="Test",
            description="Test",
            tenant_id="tenant-1",
        )

        for model in ["gpt-4", "gpt-4", "claude-3"]:
            entry = BaselineEntry.create(prompt=f"Prompt for {model}", output="Output", model=model)
            baseline.add_entry(entry)

        gpt4_entries = baseline.get_entries_by_model("gpt-4")
        assert len(gpt4_entries) == 2


class TestBaselineStore:
    """Tests for baseline store."""

    def test_create_baseline_in_store(self):
        """Test creating baseline in store."""
        store = BaselineStore()
        baseline = store.create_baseline(
            name="Production Baseline",
            description="Golden traces for production",
            tenant_id="tenant-123",
            agent_name="CustomerService",
        )

        assert baseline.name == "Production Baseline"
        assert baseline.id in store.baselines

    def test_get_baseline(self):
        """Test getting baseline by ID."""
        store = BaselineStore()
        created = store.create_baseline(
            name="Test",
            description="Test",
            tenant_id="tenant-1",
        )

        retrieved = store.get_baseline(created.id)
        assert retrieved is not None
        assert retrieved.name == "Test"

    def test_get_baselines_for_tenant(self):
        """Test getting baselines for tenant."""
        store = BaselineStore()
        store.create_baseline(name="B1", description="", tenant_id="tenant-1")
        store.create_baseline(name="B2", description="", tenant_id="tenant-1")
        store.create_baseline(name="B3", description="", tenant_id="tenant-2")

        tenant1_baselines = store.get_baselines_for_tenant("tenant-1")
        assert len(tenant1_baselines) == 2

    def test_get_active_baseline(self):
        """Test getting active baseline."""
        store = BaselineStore()
        b1 = store.create_baseline(name="Old", description="", tenant_id="tenant-1")
        b2 = store.create_baseline(name="New", description="", tenant_id="tenant-1")

        active = store.get_active_baseline("tenant-1")
        assert active is not None
        assert active.name == "New"  # Most recently updated

    def test_get_active_baseline_by_agent(self):
        """Test getting active baseline by agent name."""
        store = BaselineStore()
        store.create_baseline(name="General", description="", tenant_id="tenant-1")
        store.create_baseline(name="Agent Specific", description="", tenant_id="tenant-1", agent_name="Sales")

        active = store.get_active_baseline("tenant-1", agent_name="Sales")
        assert active.name == "Agent Specific"

    def test_add_entry_to_baseline(self):
        """Test adding entry via store."""
        store = BaselineStore()
        baseline = store.create_baseline(name="Test", description="", tenant_id="tenant-1")

        entry = store.add_entry_to_baseline(
            baseline_id=baseline.id,
            prompt="Hello",
            output="Hi there",
            model="gpt-4",
            tokens_used=20,
            latency_ms=100,
        )

        assert entry is not None
        assert baseline.total_prompts == 1

    def test_create_baseline_from_trace(self):
        """Test creating baseline from trace."""
        store = BaselineStore()
        trace = {
            "trace_id": "trace-123",
            "spans": [
                {
                    "type": "llm",
                    "input": {"messages": [{"role": "user", "content": "Hello"}]},
                    "output": {"content": "Hi there!"},
                    "model": "gpt-4",
                    "tokens_used": 30,
                },
                {
                    "type": "tool",
                    "input": "search query",
                    "output": "results",
                },
            ],
        }

        baseline = store.create_baseline_from_trace(
            trace=trace,
            name="From Trace",
            tenant_id="tenant-1",
        )

        assert baseline.total_prompts == 1  # Only LLM span

    def test_deactivate_baseline(self):
        """Test deactivating baseline."""
        store = BaselineStore()
        baseline = store.create_baseline(name="Test", description="", tenant_id="tenant-1")

        result = store.deactivate_baseline(baseline.id)
        assert result == True
        assert baseline.is_active == False

    def test_delete_baseline(self):
        """Test deleting baseline."""
        store = BaselineStore()
        baseline = store.create_baseline(name="Test", description="", tenant_id="tenant-1")
        baseline_id = baseline.id

        result = store.delete_baseline(baseline_id)
        assert result == True
        assert store.get_baseline(baseline_id) is None


# =============================================================================
# Drift Detector Tests
# =============================================================================

class TestDriftDetector:
    """Tests for drift detection."""

    def test_no_drift_identical_output(self):
        """Test no drift with identical output."""
        detector = DriftDetector()

        baseline = Baseline(name="Test", description="", tenant_id="tenant-1")
        entry = BaselineEntry.create(
            prompt="What is 2+2?",
            output="The answer is 4.",
            model="gpt-4",
        )
        baseline.add_entry(entry)

        result = detector.detect(
            prompt="What is 2+2?",
            current_output="The answer is 4.",
            baseline=baseline,
        )

        assert result.detected == False
        assert result.severity == DriftSeverity.NONE
        assert result.similarity_score >= 0.99

    def test_no_baseline_entry(self):
        """Test detection when no baseline entry exists."""
        detector = DriftDetector()
        baseline = Baseline(name="Test", description="", tenant_id="tenant-1")

        result = detector.detect(
            prompt="Unknown prompt",
            current_output="Some output",
            baseline=baseline,
        )

        assert result.detected == False
        assert "No baseline entry" in result.explanation

    def test_semantic_drift_detection(self):
        """Test semantic drift detection."""
        detector = DriftDetector(semantic_threshold=0.8)

        baseline = Baseline(name="Test", description="", tenant_id="tenant-1")
        entry = BaselineEntry.create(
            prompt="What is Python?",
            output="Python is a high-level programming language known for its clear syntax.",
            model="gpt-4",
        )
        baseline.add_entry(entry)

        result = detector.detect(
            prompt="What is Python?",
            current_output="Python is a snake found in tropical regions.",
            baseline=baseline,
        )

        assert result.detected == True
        assert result.drift_type == DriftType.SEMANTIC

    def test_performance_drift_latency(self):
        """Test performance drift from latency change."""
        detector = DriftDetector(latency_threshold_pct=0.3)

        baseline = Baseline(name="Test", description="", tenant_id="tenant-1")
        entry = BaselineEntry.create(
            prompt="Test",
            output="Response",
            model="gpt-4",
            latency_ms=100,
        )
        baseline.add_entry(entry)

        result = detector.detect(
            prompt="Test",
            current_output="Response",
            baseline=baseline,
            current_latency_ms=200,  # 100% increase
        )

        assert result.detected == True
        assert result.latency_delta_ms == 100

    def test_performance_drift_tokens(self):
        """Test performance drift from token change."""
        detector = DriftDetector(token_threshold_pct=0.3)

        baseline = Baseline(name="Test", description="", tenant_id="tenant-1")
        entry = BaselineEntry.create(
            prompt="Test",
            output="Response",
            model="gpt-4",
            tokens_used=100,
        )
        baseline.add_entry(entry)

        result = detector.detect(
            prompt="Test",
            current_output="Response",
            baseline=baseline,
            current_tokens=150,  # 50% increase
        )

        assert result.detected == True
        assert result.token_delta == 50

    def test_drift_severity_critical(self):
        """Test critical severity for very low similarity."""
        detector = DriftDetector()

        baseline = Baseline(name="Test", description="", tenant_id="tenant-1")
        entry = BaselineEntry.create(
            prompt="Hello",
            output="Hi there! How can I help you today?",
            model="gpt-4",
        )
        baseline.add_entry(entry)

        result = detector.detect(
            prompt="Hello",
            current_output="xyz abc 123 completely unrelated text",
            baseline=baseline,
        )

        if result.detected:
            assert result.severity in [DriftSeverity.HIGH, DriftSeverity.CRITICAL]

    def test_detect_batch(self):
        """Test batch drift detection."""
        detector = DriftDetector()

        baseline = Baseline(name="Test", description="", tenant_id="tenant-1")
        for i in range(3):
            entry = BaselineEntry.create(
                prompt=f"Prompt {i}",
                output=f"Output {i}",
                model="gpt-4",
            )
            baseline.add_entry(entry)

        prompts_outputs = [
            ("Prompt 0", "Output 0"),
            ("Prompt 1", "Completely different"),
            ("Prompt 2", "Output 2"),
        ]

        results = detector.detect_batch(prompts_outputs, baseline)

        assert len(results) == 3

    def test_compute_drift_rate(self):
        """Test drift rate computation."""
        detector = DriftDetector()

        results = [
            DriftResult(detected=True, drift_type=DriftType.SEMANTIC, severity=DriftSeverity.HIGH,
                       similarity_score=0.5, baseline_entry_id="1", prompt="p", baseline_output="b", current_output="c"),
            DriftResult(detected=False, drift_type=None, severity=DriftSeverity.NONE,
                       similarity_score=0.9, baseline_entry_id="2", prompt="p", baseline_output="b", current_output="c"),
            DriftResult(detected=True, drift_type=DriftType.PERFORMANCE, severity=DriftSeverity.MEDIUM,
                       similarity_score=0.8, baseline_entry_id="3", prompt="p", baseline_output="b", current_output="c"),
        ]

        rate = detector.compute_drift_rate(results)

        assert rate["total"] == 3
        assert rate["drifted"] == 2
        assert rate["drift_rate"] == pytest.approx(2/3)

    def test_compute_drift_rate_empty(self):
        """Test drift rate with empty results."""
        detector = DriftDetector()
        rate = detector.compute_drift_rate([])

        assert rate["drift_rate"] == 0

    def test_suggested_action_critical(self):
        """Test suggested action for critical drift."""
        detector = DriftDetector()
        action = detector._suggest_action(DriftType.SEMANTIC, DriftSeverity.CRITICAL)

        assert "URGENT" in action

    def test_suggested_action_semantic(self):
        """Test suggested action for semantic drift."""
        detector = DriftDetector()
        action = detector._suggest_action(DriftType.SEMANTIC, DriftSeverity.MEDIUM)

        assert "meaning" in action.lower() or "baseline" in action.lower()

    def test_fallback_similarity_computation(self):
        """Test fallback word-based similarity when embeddings unavailable."""
        detector = DriftDetector()
        detector._embedder = "fallback"

        sim = detector._compute_similarity("hello world", "hello there world")
        assert 0 < sim < 1

    def test_similarity_empty_texts(self):
        """Test similarity with empty texts."""
        detector = DriftDetector()

        assert detector._compute_similarity("", "") == 1.0
        assert detector._compute_similarity("hello", "") == 0.0
        assert detector._compute_similarity("", "hello") == 0.0


# =============================================================================
# Alert Manager Tests
# =============================================================================

class TestRegressionAlert:
    """Tests for regression alerts."""

    def test_create_alert_from_drift(self):
        """Test creating alert from drift result."""
        drift = DriftResult(
            detected=True,
            drift_type=DriftType.SEMANTIC,
            severity=DriftSeverity.HIGH,
            similarity_score=0.4,
            baseline_entry_id="entry-1",
            prompt="Test prompt",
            baseline_output="Expected",
            current_output="Actual",
            explanation="Semantic drift detected",
            suggested_action="Review output",
        )

        alert = RegressionAlert.from_drift(drift, tenant_id="tenant-1", model="gpt-4")

        assert alert.alert_type == AlertType.DRIFT_DETECTED
        assert alert.priority == AlertPriority.P2  # HIGH severity
        assert alert.status == AlertStatus.OPEN
        assert alert.tenant_id == "tenant-1"

    def test_severity_to_priority_mapping(self):
        """Test severity to priority mapping."""
        assert RegressionAlert._severity_to_priority(DriftSeverity.CRITICAL) == AlertPriority.P1
        assert RegressionAlert._severity_to_priority(DriftSeverity.HIGH) == AlertPriority.P2
        assert RegressionAlert._severity_to_priority(DriftSeverity.MEDIUM) == AlertPriority.P3
        assert RegressionAlert._severity_to_priority(DriftSeverity.LOW) == AlertPriority.P4


class TestAlertManager:
    """Tests for alert manager."""

    def test_create_alert(self):
        """Test creating an alert."""
        manager = AlertManager()
        alert = manager.create_alert(
            alert_type=AlertType.MODEL_UPDATE,
            priority=AlertPriority.P2,
            title="Model Updated",
            message="GPT-4 was updated to new version",
            tenant_id="tenant-1",
            model="gpt-4",
        )

        assert alert is not None
        assert alert.title == "Model Updated"
        assert alert.id in manager.alerts

    def test_create_from_drift(self):
        """Test creating alert from drift result."""
        manager = AlertManager()
        drift = DriftResult(
            detected=True,
            drift_type=DriftType.SEMANTIC,
            severity=DriftSeverity.MEDIUM,
            similarity_score=0.6,
            baseline_entry_id="e1",
            prompt="p",
            baseline_output="b",
            current_output="c",
        )

        alert = manager.create_from_drift(drift, tenant_id="tenant-1")

        assert alert is not None
        assert alert.alert_type == AlertType.DRIFT_DETECTED

    def test_create_from_drift_no_detection(self):
        """Test no alert created when no drift detected."""
        manager = AlertManager()
        drift = DriftResult(
            detected=False,
            drift_type=None,
            severity=DriftSeverity.NONE,
            similarity_score=0.95,
            baseline_entry_id="e1",
            prompt="p",
            baseline_output="b",
            current_output="b",
        )

        alert = manager.create_from_drift(drift, tenant_id="tenant-1")

        assert alert is None

    def test_create_batch_alerts_aggregate(self):
        """Test batch alert creation with aggregation."""
        manager = AlertManager()
        drifts = [
            DriftResult(detected=True, drift_type=DriftType.SEMANTIC, severity=DriftSeverity.HIGH,
                       similarity_score=0.4, baseline_entry_id=str(i), prompt="p", baseline_output="b", current_output="c")
            for i in range(5)
        ]

        alerts = manager.create_batch_alerts(drifts, tenant_id="tenant-1")

        assert len(alerts) == 1  # Aggregated into one
        assert alerts[0].alert_type == AlertType.REGRESSION_SUMMARY

    def test_create_batch_alerts_individual(self):
        """Test batch alert creation without aggregation."""
        manager = AlertManager()
        drifts = [
            DriftResult(detected=True, drift_type=DriftType.SEMANTIC, severity=DriftSeverity.HIGH,
                       similarity_score=0.4, baseline_entry_id=str(i), prompt="p", baseline_output="b", current_output="c")
            for i in range(2)
        ]

        alerts = manager.create_batch_alerts(drifts, tenant_id="tenant-1")

        assert len(alerts) == 2  # Not enough for aggregation

    def test_get_alerts_for_tenant(self):
        """Test getting alerts for tenant."""
        manager = AlertManager()
        manager.create_alert(AlertType.DRIFT_DETECTED, AlertPriority.P2, "A1", "M1", "tenant-1")
        manager.create_alert(AlertType.DRIFT_DETECTED, AlertPriority.P3, "A2", "M2", "tenant-1")
        manager.create_alert(AlertType.DRIFT_DETECTED, AlertPriority.P2, "A3", "M3", "tenant-2")

        alerts = manager.get_alerts_for_tenant("tenant-1")
        assert len(alerts) == 2

    def test_get_alerts_filtered_by_status(self):
        """Test getting alerts filtered by status."""
        manager = AlertManager()
        a1 = manager.create_alert(AlertType.DRIFT_DETECTED, AlertPriority.P2, "A1", "M1", "tenant-1")
        manager.create_alert(AlertType.DRIFT_DETECTED, AlertPriority.P2, "A2", "M2", "tenant-1")

        manager.resolve(a1.id)

        open_alerts = manager.get_alerts_for_tenant("tenant-1", status=AlertStatus.OPEN)
        assert len(open_alerts) == 1

    def test_get_alerts_filtered_by_priority(self):
        """Test getting alerts filtered by priority."""
        manager = AlertManager()
        manager.create_alert(AlertType.DRIFT_DETECTED, AlertPriority.P1, "A1", "M1", "tenant-1")
        manager.create_alert(AlertType.DRIFT_DETECTED, AlertPriority.P3, "A2", "M2", "tenant-1")

        p1_alerts = manager.get_alerts_for_tenant("tenant-1", priority=AlertPriority.P1)
        assert len(p1_alerts) == 1

    def test_acknowledge_alert(self):
        """Test acknowledging an alert."""
        manager = AlertManager()
        alert = manager.create_alert(AlertType.DRIFT_DETECTED, AlertPriority.P2, "Test", "Msg", "tenant-1")

        result = manager.acknowledge(alert.id)

        assert result == True
        assert alert.status == AlertStatus.ACKNOWLEDGED

    def test_resolve_alert(self):
        """Test resolving an alert."""
        manager = AlertManager()
        alert = manager.create_alert(AlertType.DRIFT_DETECTED, AlertPriority.P2, "Test", "Msg", "tenant-1")

        result = manager.resolve(alert.id)

        assert result == True
        assert alert.status == AlertStatus.RESOLVED
        assert alert.resolved_at is not None

    def test_suppress_pattern(self):
        """Test alert suppression pattern."""
        manager = AlertManager()
        manager.suppress_pattern(
            tenant_id="tenant-1",
            agent_name="TestAgent",
            alert_type=AlertType.DRIFT_DETECTED,
            duration_hours=1,
        )

        alert = manager.create_alert(
            AlertType.DRIFT_DETECTED,
            AlertPriority.P2,
            "Suppressed",
            "Should be suppressed",
            tenant_id="tenant-1",
            agent_name="TestAgent",
        )

        assert alert is None

    def test_suppress_pattern_expired(self):
        """Test expired suppression pattern."""
        manager = AlertManager()
        manager.suppressed_patterns.append({
            "tenant_id": "tenant-1",
            "agent_name": None,
            "model": None,
            "alert_type": AlertType.DRIFT_DETECTED,
            "expires_at": datetime.utcnow() - timedelta(hours=1),  # Expired
        })

        alert = manager.create_alert(
            AlertType.DRIFT_DETECTED,
            AlertPriority.P2,
            "Not Suppressed",
            "Should not be suppressed",
            tenant_id="tenant-1",
        )

        assert alert is not None

    def test_generate_weekly_report(self):
        """Test weekly report generation."""
        manager = AlertManager()

        # Create some alerts
        manager.create_alert(AlertType.DRIFT_DETECTED, AlertPriority.P1, "A1", "M1", "tenant-1")
        manager.create_alert(AlertType.DRIFT_DETECTED, AlertPriority.P2, "A2", "M2", "tenant-1")
        a3 = manager.create_alert(AlertType.MODEL_UPDATE, AlertPriority.P3, "A3", "M3", "tenant-1")
        manager.resolve(a3.id)

        report = manager.generate_weekly_report("tenant-1")

        assert report["total_alerts"] == 3
        assert report["by_priority"]["p1"] == 1
        assert report["by_priority"]["p2"] == 1
        assert report["resolved_alerts"] == 1


# =============================================================================
# Integration Tests
# =============================================================================

class TestRegressionIntegration:
    """Integration tests for regression module."""

    def test_full_regression_workflow(self):
        """Test complete regression detection workflow."""
        # 1. Create baseline
        store = BaselineStore()
        baseline = store.create_baseline(
            name="Production",
            description="Production baseline",
            tenant_id="tenant-1",
        )

        # 2. Add baseline entries
        store.add_entry_to_baseline(
            baseline_id=baseline.id,
            prompt="Summarize this article about AI",
            output="AI is transforming industries through automation and data analysis.",
            model="gpt-4o",
            latency_ms=500,
            tokens_used=100,
        )

        # 3. Detect drift
        detector = DriftDetector()
        result = detector.detect(
            prompt="Summarize this article about AI",
            current_output="Artificial intelligence enables machines to learn from data.",
            baseline=baseline,
            current_latency_ms=600,
            current_tokens=80,
        )

        # 4. Create alert if needed
        manager = AlertManager()
        if result.detected:
            alert = manager.create_from_drift(result, tenant_id="tenant-1", model="gpt-4o")
            assert alert is not None

    def test_model_fingerprint_with_baseline(self):
        """Test model fingerprinting integrated with baseline."""
        fp = ModelFingerprinter()
        store = BaselineStore()

        # Fingerprint model
        fingerprint = fp.fingerprint("gpt-4o-2024-08-06")

        # Create baseline with model version
        baseline = store.create_baseline(
            name="Versioned Baseline",
            description="With model version",
            tenant_id="tenant-1",
        )

        store.add_entry_to_baseline(
            baseline_id=baseline.id,
            prompt="Test",
            output="Result",
            model="gpt-4o-2024-08-06",
            model_version=fingerprint.fingerprint_hash,
        )

        # Check version change
        changed, _ = fp.detect_version_change("gpt-4o-2024-08-06", fingerprint.fingerprint_hash)
        assert changed == False

    def test_imports_from_module(self):
        """Test all components importable from module."""
        from app.regression import (
            model_fingerprinter,
            BaselineStore,
            DriftDetector,
            alert_manager,
        )

        assert model_fingerprinter is not None
        assert BaselineStore is not None
        assert DriftDetector is not None
        assert alert_manager is not None
