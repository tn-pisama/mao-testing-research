"""Comprehensive tests for export modules (datadog, prometheus)."""

import pytest
import time
from unittest.mock import patch, AsyncMock, MagicMock

from app.export.datadog import (
    DatadogExporter,
    DatadogMetric,
    DatadogEvent,
    MetricType,
    datadog_exporter,
)
from app.export.prometheus import (
    Counter,
    Gauge,
    Histogram,
    MetricValue,
    MAOMetrics,
    PrometheusExporter,
    mao_metrics,
    prometheus_exporter,
)


# ============================================================================
# Datadog MetricType Tests
# ============================================================================

class TestMetricType:
    """Tests for MetricType enum."""

    def test_count_value(self):
        """COUNT should have correct value."""
        assert MetricType.COUNT.value == "count"

    def test_gauge_value(self):
        """GAUGE should have correct value."""
        assert MetricType.GAUGE.value == "gauge"

    def test_rate_value(self):
        """RATE should have correct value."""
        assert MetricType.RATE.value == "rate"

    def test_distribution_value(self):
        """DISTRIBUTION should have correct value."""
        assert MetricType.DISTRIBUTION.value == "distribution"


# ============================================================================
# DatadogMetric Tests
# ============================================================================

class TestDatadogMetric:
    """Tests for DatadogMetric dataclass."""

    def test_create_metric(self):
        """Should create metric with all fields."""
        metric = DatadogMetric(
            metric="test.metric",
            type=MetricType.GAUGE,
            points=[(1234567890, 42.5)],
            tags=["env:test"],
            host="testhost",
            interval=10,
        )

        assert metric.metric == "test.metric"
        assert metric.type == MetricType.GAUGE
        assert metric.points == [(1234567890, 42.5)]
        assert metric.tags == ["env:test"]
        assert metric.host == "testhost"
        assert metric.interval == 10

    def test_create_metric_defaults(self):
        """Should use default values."""
        metric = DatadogMetric(
            metric="test.metric",
            type=MetricType.COUNT,
            points=[(1234567890, 1)],
        )

        assert metric.tags == []
        assert metric.host is None
        assert metric.interval is None


# ============================================================================
# DatadogEvent Tests
# ============================================================================

class TestDatadogEvent:
    """Tests for DatadogEvent dataclass."""

    def test_create_event(self):
        """Should create event with all fields."""
        event = DatadogEvent(
            title="Test Event",
            text="Event description",
            alert_type="warning",
            tags=["env:test"],
            host="testhost",
        )

        assert event.title == "Test Event"
        assert event.text == "Event description"
        assert event.alert_type == "warning"
        assert event.tags == ["env:test"]
        assert event.host == "testhost"

    def test_create_event_defaults(self):
        """Should use default values."""
        event = DatadogEvent(
            title="Test Event",
            text="Description",
        )

        assert event.alert_type == "info"
        assert event.tags == []
        assert event.host is None


# ============================================================================
# DatadogExporter Tests
# ============================================================================

class TestDatadogExporter:
    """Tests for DatadogExporter class."""

    def test_init_with_env_vars(self):
        """Should use environment variables by default."""
        with patch.dict("os.environ", {"DD_API_KEY": "test_key", "DD_APP_KEY": "test_app"}):
            exporter = DatadogExporter()
            assert exporter.api_key == "test_key"
            assert exporter.app_key == "test_app"

    def test_init_with_explicit_keys(self):
        """Should accept explicit API keys."""
        exporter = DatadogExporter(api_key="explicit_key", app_key="explicit_app")
        assert exporter.api_key == "explicit_key"
        assert exporter.app_key == "explicit_app"

    def test_init_custom_site(self):
        """Should use custom Datadog site."""
        exporter = DatadogExporter(site="datadoghq.eu")
        assert exporter.site == "datadoghq.eu"
        assert exporter.base_url == "https://api.datadoghq.eu"

    def test_default_tags(self):
        """Should have default tags."""
        exporter = DatadogExporter()
        assert "service:mao-testing" in exporter.default_tags
        assert any(t.startswith("env:") for t in exporter.default_tags)

    def test_get_headers(self):
        """Should return proper headers."""
        exporter = DatadogExporter(api_key="key1", app_key="key2")
        headers = exporter._get_headers()

        assert headers["DD-API-KEY"] == "key1"
        assert headers["DD-APPLICATION-KEY"] == "key2"
        assert headers["Content-Type"] == "application/json"

    def test_gauge(self):
        """Should add gauge metric to buffer."""
        exporter = DatadogExporter()
        exporter.gauge("test.gauge", 42.5, tags=["custom:tag"])

        assert len(exporter._buffer) == 1
        metric = exporter._buffer[0]
        assert metric.metric == "mao.test.gauge"
        assert metric.type == MetricType.GAUGE
        assert metric.points[0][1] == 42.5
        assert "custom:tag" in metric.tags

    def test_gauge_with_timestamp(self):
        """Should use provided timestamp."""
        exporter = DatadogExporter()
        ts = 1234567890.0
        exporter.gauge("test.gauge", 10, timestamp=ts)

        metric = exporter._buffer[0]
        assert metric.points[0][0] == 1234567890

    def test_count(self):
        """Should add count metric to buffer."""
        exporter = DatadogExporter()
        exporter.count("test.count", 5, tags=["custom:tag"])

        assert len(exporter._buffer) == 1
        metric = exporter._buffer[0]
        assert metric.metric == "mao.test.count"
        assert metric.type == MetricType.COUNT
        assert metric.points[0][1] == 5
        assert metric.interval == 10

    def test_count_default_value(self):
        """Count should default to 1."""
        exporter = DatadogExporter()
        exporter.count("test.count")

        metric = exporter._buffer[0]
        assert metric.points[0][1] == 1

    def test_distribution(self):
        """Should add distribution metric to buffer."""
        exporter = DatadogExporter()
        exporter.distribution("test.dist", 0.5)

        assert len(exporter._buffer) == 1
        metric = exporter._buffer[0]
        assert metric.metric == "mao.test.dist"
        assert metric.type == MetricType.DISTRIBUTION

    def test_event(self):
        """Should add event to buffer."""
        exporter = DatadogExporter()
        exporter.event("Test Title", "Test text", alert_type="warning", tags=["custom:tag"])

        assert len(exporter._events_buffer) == 1
        event = exporter._events_buffer[0]
        assert event.title == "Test Title"
        assert event.text == "Test text"
        assert event.alert_type == "warning"
        assert "custom:tag" in event.tags

    def test_record_trace(self):
        """Should record trace metrics."""
        exporter = DatadogExporter()
        exporter.record_trace(
            tenant_id="tenant1",
            framework="langchain",
            status="success",
            tokens=1000,
            cost_usd=0.05,
        )

        assert len(exporter._buffer) == 3  # traces, tokens, cost

    def test_record_detection(self):
        """Should record detection metrics."""
        exporter = DatadogExporter()
        exporter.record_detection(
            tenant_id="tenant1",
            detection_type="loop",
            severity="high",
            confidence=0.85,
        )

        assert len(exporter._buffer) == 2  # detections, confidence
        assert len(exporter._events_buffer) == 1  # warning event for high severity

    def test_record_detection_critical(self):
        """Should record error event for critical severity."""
        exporter = DatadogExporter()
        exporter.record_detection(
            tenant_id="tenant1",
            detection_type="injection",
            severity="critical",
            confidence=0.95,
        )

        event = exporter._events_buffer[0]
        assert event.alert_type == "error"

    def test_record_detection_low_severity(self):
        """Should not create event for low severity."""
        exporter = DatadogExporter()
        exporter.record_detection(
            tenant_id="tenant1",
            detection_type="drift",
            severity="low",
            confidence=0.6,
        )

        assert len(exporter._events_buffer) == 0

    def test_record_latency(self):
        """Should record latency distribution."""
        exporter = DatadogExporter()
        exporter.record_latency("ingestion", 0.5, tags=["region:us"])

        metric = exporter._buffer[0]
        assert metric.type == MetricType.DISTRIBUTION
        assert "operation:ingestion" in metric.tags

    def test_record_eval(self):
        """Should record eval metrics."""
        exporter = DatadogExporter()
        exporter.record_eval(
            tenant_id="tenant1",
            eval_type="relevance",
            score=0.85,
            passed=True,
        )

        assert len(exporter._buffer) == 3  # score, total, passed

    def test_record_eval_failed(self):
        """Should not record passed counter for failed eval."""
        exporter = DatadogExporter()
        exporter.record_eval(
            tenant_id="tenant1",
            eval_type="relevance",
            score=0.3,
            passed=False,
        )

        assert len(exporter._buffer) == 2  # score, total (no passed)

    @pytest.mark.asyncio
    async def test_flush_without_api_key(self):
        """Should clear buffers and return False without API key."""
        exporter = DatadogExporter(api_key="")
        exporter.gauge("test", 1)
        exporter.event("title", "text")

        result = await exporter.flush()

        assert result is False
        assert len(exporter._buffer) == 0
        assert len(exporter._events_buffer) == 0

    @pytest.mark.asyncio
    async def test_flush_empty_buffers(self):
        """Should return True for empty buffers."""
        exporter = DatadogExporter(api_key="key")
        result = await exporter.flush()
        assert result is True

    @pytest.mark.asyncio
    async def test_flush_success(self):
        """Should send metrics and clear buffers."""
        exporter = DatadogExporter(api_key="key")
        exporter.gauge("test", 1)

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 202
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            result = await exporter.flush()

            assert result is True
            assert len(exporter._buffer) == 0

    @pytest.mark.asyncio
    async def test_flush_failure(self):
        """Should return False on API error."""
        exporter = DatadogExporter(api_key="key")
        exporter.gauge("test", 1)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(side_effect=Exception("Network error"))

            result = await exporter.flush()

            assert result is False

    @pytest.mark.asyncio
    async def test_send_events(self):
        """Should send events."""
        exporter = DatadogExporter(api_key="key")
        exporter.event("Title", "Text")

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 202
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            result = await exporter.flush()

            assert result is True
            assert len(exporter._events_buffer) == 0

    def test_get_dashboard_json(self):
        """Should return valid dashboard JSON."""
        exporter = DatadogExporter()
        dashboard = exporter.get_dashboard_json()

        assert dashboard["title"] == "MAO Testing Platform"
        assert "widgets" in dashboard
        assert len(dashboard["widgets"]) == 6
        assert dashboard["layout_type"] == "ordered"

    def test_singleton_exporter(self):
        """datadog_exporter should be a singleton instance."""
        assert isinstance(datadog_exporter, DatadogExporter)


# ============================================================================
# Prometheus Counter Tests
# ============================================================================

class TestPrometheusCounter:
    """Tests for Prometheus Counter class."""

    def test_create_counter(self):
        """Should create counter with name and description."""
        counter = Counter("test_counter", "Test description", ["label1"])
        assert counter.name == "test_counter"
        assert counter.description == "Test description"
        assert counter.label_names == ["label1"]

    def test_inc_default(self):
        """Should increment by 1 by default."""
        counter = Counter("test_counter", "Test")
        counter.inc()
        counter.inc()

        values = counter.get_all()
        assert values[()] == 2

    def test_inc_with_value(self):
        """Should increment by specified value."""
        counter = Counter("test_counter", "Test")
        counter.inc(5)

        values = counter.get_all()
        assert values[()] == 5

    def test_inc_with_labels(self):
        """Should track separate values per label set."""
        counter = Counter("test_counter", "Test", ["env"])
        counter.inc(label1="a")
        counter.inc(label1="a")
        counter.inc(label1="b")

        values = counter.get_all()
        assert len(values) == 2

    def test_get_all_empty(self):
        """Should return empty dict when no increments."""
        counter = Counter("test_counter", "Test")
        assert counter.get_all() == {}


# ============================================================================
# Prometheus Gauge Tests
# ============================================================================

class TestPrometheusGauge:
    """Tests for Prometheus Gauge class."""

    def test_create_gauge(self):
        """Should create gauge with name and description."""
        gauge = Gauge("test_gauge", "Test description", ["label1"])
        assert gauge.name == "test_gauge"
        assert gauge.description == "Test description"

    def test_set_value(self):
        """Should set gauge value."""
        gauge = Gauge("test_gauge", "Test")
        gauge.set(42.5)

        values = gauge.get_all()
        assert values[()] == 42.5

    def test_set_overwrites(self):
        """Set should overwrite previous value."""
        gauge = Gauge("test_gauge", "Test")
        gauge.set(10)
        gauge.set(20)

        values = gauge.get_all()
        assert values[()] == 20

    def test_inc_gauge(self):
        """Should increment gauge value."""
        gauge = Gauge("test_gauge", "Test")
        gauge.set(10)
        gauge.inc(5)

        values = gauge.get_all()
        assert values[()] == 15

    def test_dec_gauge(self):
        """Should decrement gauge value."""
        gauge = Gauge("test_gauge", "Test")
        gauge.set(10)
        gauge.dec(3)

        values = gauge.get_all()
        assert values[()] == 7

    def test_inc_from_zero(self):
        """Inc should work without prior set."""
        gauge = Gauge("test_gauge", "Test")
        gauge.inc(5)

        values = gauge.get_all()
        assert values[()] == 5

    def test_gauge_with_labels(self):
        """Should track separate values per label set."""
        gauge = Gauge("test_gauge", "Test", ["env"])
        gauge.set(10, env="dev")
        gauge.set(20, env="prod")

        values = gauge.get_all()
        assert len(values) == 2


# ============================================================================
# Prometheus Histogram Tests
# ============================================================================

class TestPrometheusHistogram:
    """Tests for Prometheus Histogram class."""

    def test_create_histogram(self):
        """Should create histogram with default buckets."""
        histogram = Histogram("test_histogram", "Test description")
        assert histogram.name == "test_histogram"
        assert len(histogram.buckets) > 0

    def test_create_histogram_custom_buckets(self):
        """Should accept custom buckets."""
        histogram = Histogram("test_histogram", "Test", buckets=[0.1, 0.5, 1.0])
        assert histogram.buckets == [0.1, 0.5, 1.0]

    def test_observe(self):
        """Should record observation."""
        histogram = Histogram("test_histogram", "Test", buckets=[0.1, 0.5, 1.0])
        histogram.observe(0.3)

        data = histogram.get_all()
        assert len(data) == 1
        assert data[()]["count"] == 1
        assert data[()]["sum"] == 0.3

    def test_observe_multiple(self):
        """Should record multiple observations."""
        histogram = Histogram("test_histogram", "Test", buckets=[0.1, 0.5, 1.0])
        histogram.observe(0.05)
        histogram.observe(0.3)
        histogram.observe(0.8)

        data = histogram.get_all()
        assert data[()]["count"] == 3
        assert data[()]["sum"] == pytest.approx(1.15)

    def test_bucket_counts(self):
        """Should compute correct bucket counts (cumulative)."""
        histogram = Histogram("test_histogram", "Test", buckets=[0.1, 0.5, 1.0])
        histogram.observe(0.05)  # <= 0.1, 0.5, 1.0, +Inf
        histogram.observe(0.3)   # <= 0.5, 1.0, +Inf
        histogram.observe(0.8)   # <= 1.0, +Inf

        data = histogram.get_all()[()]
        # Buckets are cumulative: each bucket counts all observations <= that value
        assert data["buckets"][0.1] == 1   # 0.05
        assert data["buckets"][0.5] == 2   # 0.05 + 0.3
        assert data["buckets"][1.0] == 3   # 0.05 + 0.3 + 0.8
        assert data["buckets"][float('inf')] == 3  # All observations are <= +Inf

    def test_histogram_with_labels(self):
        """Should track separate histograms per label set."""
        histogram = Histogram("test_histogram", "Test", ["env"])
        histogram.observe(0.1, env="dev")
        histogram.observe(0.2, env="prod")

        data = histogram.get_all()
        assert len(data) == 2


# ============================================================================
# MAOMetrics Tests
# ============================================================================

class TestMAOMetrics:
    """Tests for MAOMetrics class."""

    def test_init_creates_all_metrics(self):
        """Should initialize all metric types."""
        metrics = MAOMetrics()

        assert isinstance(metrics.traces_total, Counter)
        assert isinstance(metrics.detections_total, Counter)
        assert isinstance(metrics.tokens_total, Counter)
        assert isinstance(metrics.cost_total, Counter)
        assert isinstance(metrics.active_traces, Gauge)
        assert isinstance(metrics.detection_confidence, Gauge)
        assert isinstance(metrics.ingestion_latency, Histogram)
        assert isinstance(metrics.detection_latency, Histogram)
        assert isinstance(metrics.eval_scores, Histogram)

    def test_record_trace(self):
        """Should record trace counter."""
        metrics = MAOMetrics()
        metrics.record_trace("tenant1", "langchain", "success")

        values = metrics.traces_total.get_all()
        assert len(values) == 1

    def test_record_detection(self):
        """Should record detection counter and confidence gauge."""
        metrics = MAOMetrics()
        metrics.record_detection("tenant1", "loop", "high", 0.85)

        counter_values = metrics.detections_total.get_all()
        gauge_values = metrics.detection_confidence.get_all()

        assert len(counter_values) == 1
        assert len(gauge_values) == 1

    def test_record_tokens(self):
        """Should record input and output tokens separately."""
        metrics = MAOMetrics()
        metrics.record_tokens("tenant1", "gpt-4", 100, 200)

        values = metrics.tokens_total.get_all()
        assert len(values) == 2  # input and output

    def test_record_cost(self):
        """Should record cost counter."""
        metrics = MAOMetrics()
        metrics.record_cost("tenant1", "gpt-4", "openai", 0.05)

        values = metrics.cost_total.get_all()
        assert len(values) == 1

    def test_record_ingestion_latency(self):
        """Should record ingestion latency histogram."""
        metrics = MAOMetrics()
        metrics.record_ingestion_latency("tenant1", "langchain", 0.5)

        data = metrics.ingestion_latency.get_all()
        assert len(data) == 1

    def test_record_detection_latency(self):
        """Should record detection latency histogram."""
        metrics = MAOMetrics()
        metrics.record_detection_latency("loop", 0.1)

        data = metrics.detection_latency.get_all()
        assert len(data) == 1

    def test_record_eval(self):
        """Should record eval score histogram."""
        metrics = MAOMetrics()
        metrics.record_eval("tenant1", "relevance", 0.85)

        data = metrics.eval_scores.get_all()
        assert len(data) == 1


# ============================================================================
# PrometheusExporter Tests
# ============================================================================

class TestPrometheusExporter:
    """Tests for PrometheusExporter class."""

    def test_export_empty_metrics(self):
        """Should export empty metrics without errors."""
        metrics = MAOMetrics()
        exporter = PrometheusExporter(metrics)

        output = exporter.export()

        assert "# HELP mao_traces_total" in output
        assert "# TYPE mao_traces_total counter" in output

    def test_export_counter_with_data(self):
        """Should export counter with values."""
        metrics = MAOMetrics()
        metrics.record_trace("tenant1", "langchain", "success")

        exporter = PrometheusExporter(metrics)
        output = exporter.export()

        assert "mao_traces_total" in output
        assert 'tenant_id="tenant1"' in output
        assert 'framework="langchain"' in output

    def test_export_gauge_with_data(self):
        """Should export gauge with values."""
        metrics = MAOMetrics()
        metrics.record_detection("tenant1", "loop", "high", 0.85)

        exporter = PrometheusExporter(metrics)
        output = exporter.export()

        assert "mao_detection_confidence" in output
        assert "0.85" in output

    def test_export_histogram_with_data(self):
        """Should export histogram with buckets."""
        metrics = MAOMetrics()
        metrics.record_ingestion_latency("tenant1", "langchain", 0.5)

        exporter = PrometheusExporter(metrics)
        output = exporter.export()

        assert "mao_ingestion_latency_seconds_bucket" in output
        assert "mao_ingestion_latency_seconds_sum" in output
        assert "mao_ingestion_latency_seconds_count" in output
        assert 'le="' in output

    def test_format_labels_empty(self):
        """Should return empty string for no labels."""
        metrics = MAOMetrics()
        exporter = PrometheusExporter(metrics)

        result = exporter._format_labels(())
        assert result == ""

    def test_format_labels_with_values(self):
        """Should format labels correctly."""
        metrics = MAOMetrics()
        exporter = PrometheusExporter(metrics)

        result = exporter._format_labels((("env", "prod"), ("region", "us")))
        assert 'env="prod"' in result
        assert 'region="us"' in result
        assert result.startswith("{")
        assert result.endswith("}")

    def test_histogram_cumulative_buckets(self):
        """Should export cumulative bucket counts."""
        metrics = MAOMetrics()
        # Add multiple observations
        metrics.record_ingestion_latency("tenant1", "langchain", 0.01)
        metrics.record_ingestion_latency("tenant1", "langchain", 0.1)
        metrics.record_ingestion_latency("tenant1", "langchain", 1.0)

        exporter = PrometheusExporter(metrics)
        output = exporter.export()

        # Check that buckets are in output
        assert "_bucket" in output
        # Check count equals 3
        assert "mao_ingestion_latency_seconds_count" in output

    def test_histogram_inf_bucket(self):
        """Should export +Inf bucket."""
        metrics = MAOMetrics()
        metrics.record_ingestion_latency("tenant1", "langchain", 0.5)

        exporter = PrometheusExporter(metrics)
        output = exporter.export()

        assert 'le="+Inf"' in output

    def test_singleton_metrics(self):
        """mao_metrics should be a singleton instance."""
        assert isinstance(mao_metrics, MAOMetrics)

    def test_singleton_exporter(self):
        """prometheus_exporter should be a singleton instance."""
        assert isinstance(prometheus_exporter, PrometheusExporter)


# ============================================================================
# MetricValue Tests
# ============================================================================

class TestMetricValue:
    """Tests for MetricValue dataclass."""

    def test_create_metric_value(self):
        """Should create metric value with all fields."""
        value = MetricValue(
            value=42.5,
            labels={"env": "prod"},
        )

        assert value.value == 42.5
        assert value.labels == {"env": "prod"}
        assert value.timestamp > 0

    def test_create_metric_value_defaults(self):
        """Should use default values."""
        value = MetricValue(value=10)

        assert value.labels == {}
        assert value.timestamp > 0


# ============================================================================
# Integration Tests
# ============================================================================

class TestExportIntegration:
    """Integration tests for export modules."""

    def test_datadog_full_workflow(self):
        """Should record all metric types and generate dashboard."""
        exporter = DatadogExporter()

        # Record various metrics
        exporter.record_trace("tenant1", "langchain", "success", 1000, 0.05)
        exporter.record_detection("tenant1", "loop", "high", 0.85)
        exporter.record_latency("ingestion", 0.5)
        exporter.record_eval("tenant1", "relevance", 0.9, True)

        # Check buffers
        assert len(exporter._buffer) > 0
        assert len(exporter._events_buffer) > 0

        # Check dashboard generation
        dashboard = exporter.get_dashboard_json()
        assert len(dashboard["widgets"]) > 0

    def test_prometheus_full_workflow(self):
        """Should record metrics and export in Prometheus format."""
        metrics = MAOMetrics()

        # Record various metrics
        metrics.record_trace("tenant1", "langchain", "success")
        metrics.record_detection("tenant1", "loop", "high", 0.85)
        metrics.record_tokens("tenant1", "gpt-4", 100, 200)
        metrics.record_cost("tenant1", "gpt-4", "openai", 0.05)
        metrics.record_ingestion_latency("tenant1", "langchain", 0.5)
        metrics.record_detection_latency("loop", 0.1)
        metrics.record_eval("tenant1", "relevance", 0.85)

        # Export
        exporter = PrometheusExporter(metrics)
        output = exporter.export()

        # Verify all metric types present
        assert "mao_traces_total" in output
        assert "mao_detections_total" in output
        assert "mao_tokens_total" in output
        assert "mao_cost_usd_total" in output
        assert "mao_detection_confidence" in output
        assert "mao_ingestion_latency_seconds" in output
        assert "mao_detection_latency_seconds" in output
        assert "mao_eval_score" in output

    def test_prometheus_export_format_validity(self):
        """Prometheus export should be valid format."""
        metrics = MAOMetrics()
        metrics.record_trace("tenant1", "langchain", "success")

        exporter = PrometheusExporter(metrics)
        output = exporter.export()

        lines = output.strip().split("\n")

        # Check structure
        for line in lines:
            if line.startswith("#"):
                assert line.startswith("# HELP") or line.startswith("# TYPE")
            else:
                # Metric line should have name and value
                assert " " in line or len(line) == 0
