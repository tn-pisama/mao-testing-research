"""Tests for PISAMA MCP Server.

Tests the MCP server's static helpers, data structures, validation,
and tool dispatch logic without requiring an actual MCP runtime.
"""
import json
import re
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.mcp.server import (
    create_server,
    PISAMAMCPClient,
    DETECTION_TYPES,
    FIX_CATEGORIES,
    TOOLS,
    RESOURCES,
    _build_detection_types_markdown,
    _build_fix_types_markdown,
    _validate_uuid,
    _validate_int_range,
    _validate_iso_datetime,
    _dispatch_tool,
)


# ===========================================================================
# Detection types markdown
# ===========================================================================


class TestDetectionTypesMarkdown:
    def test_includes_all_detector_names(self):
        md = _build_detection_types_markdown()
        for det in DETECTION_TYPES:
            assert det in md.lower(), f"Missing detection type: {det}"

    def test_is_valid_markdown(self):
        md = _build_detection_types_markdown()
        assert md.startswith("# PISAMA Detection Types")
        assert "##" in md

    def test_includes_tier_info(self):
        md = _build_detection_types_markdown()
        assert "Tier 1" in md
        assert "Tier 5" in md
        assert "Hash" in md
        assert "LLM Judge" in md

    def test_includes_confidence_scoring(self):
        md = _build_detection_types_markdown()
        assert "Confidence" in md
        assert "80-100" in md

    def test_has_table_headers(self):
        md = _build_detection_types_markdown()
        assert "| # | Type | Description |" in md

    def test_all_17_types_in_table(self):
        md = _build_detection_types_markdown()
        # Count table rows (lines starting with |, excluding headers)
        table_rows = [
            line for line in md.split("\n")
            if line.startswith("| ") and "|---" not in line and "# |" not in line
        ]
        assert len(table_rows) == len(DETECTION_TYPES)


# ===========================================================================
# Fix types markdown
# ===========================================================================


class TestFixTypesMarkdown:
    def test_includes_fix_categories(self):
        md = _build_fix_types_markdown()
        for category in FIX_CATEGORIES:
            assert category in md

    def test_starts_with_header(self):
        md = _build_fix_types_markdown()
        assert md.startswith("# PISAMA Fix Types")

    def test_includes_lifecycle(self):
        md = _build_fix_types_markdown()
        assert "Lifecycle" in md
        assert "Generated" in md
        assert "Applied" in md
        assert "Validated" in md
        assert "Rolled back" in md

    def test_has_minimum_length(self):
        md = _build_fix_types_markdown()
        assert len(md) > 200

    def test_includes_all_fix_types(self):
        md = _build_fix_types_markdown()
        for category, fixes in FIX_CATEGORIES.items():
            for fix in fixes:
                assert fix["type"] in md


# ===========================================================================
# Detection types data
# ===========================================================================


class TestDetectionTypesData:
    def test_has_17_types(self):
        assert len(DETECTION_TYPES) == 17

    def test_expected_types_present(self):
        expected = {
            "loop", "corruption", "persona_drift", "coordination",
            "hallucination", "injection", "overflow", "derailment",
            "context", "communication", "specification", "decomposition",
            "workflow", "withholding", "completion", "retrieval_quality",
            "grounding",
        }
        assert set(DETECTION_TYPES.keys()) == expected

    def test_descriptions_nonempty(self):
        for dt, desc in DETECTION_TYPES.items():
            assert len(desc) > 10, f"Description for {dt} is too short"


# ===========================================================================
# Fix categories data
# ===========================================================================


class TestFixCategoriesData:
    def test_has_four_categories(self):
        assert len(FIX_CATEGORIES) == 4

    def test_expected_categories(self):
        expected = {"Runtime Fixes", "Configuration Fixes", "Source Code Fixes", "Workflow Fixes"}
        assert set(FIX_CATEGORIES.keys()) == expected

    def test_each_category_has_fixes(self):
        for category, fixes in FIX_CATEGORIES.items():
            assert len(fixes) >= 2, f"Category {category} has too few fixes"
            for fix in fixes:
                assert "type" in fix
                assert "description" in fix


# ===========================================================================
# Tools definitions
# ===========================================================================


class TestToolDefinitions:
    def test_has_tools(self):
        assert len(TOOLS) >= 10

    def test_tool_names_prefixed(self):
        for tool in TOOLS:
            assert tool.name.startswith("pisama_"), f"Tool {tool.name} should start with pisama_"

    def test_tool_has_input_schema(self):
        for tool in TOOLS:
            assert tool.inputSchema is not None
            assert "type" in tool.inputSchema

    def test_key_tools_present(self):
        tool_names = {t.name for t in TOOLS}
        expected = {
            "pisama_query_traces",
            "pisama_query_detections",
            "pisama_get_trace_detail",
            "pisama_get_detection_detail",
            "pisama_get_fix_suggestions",
            "pisama_apply_fix",
            "pisama_submit_feedback",
            "pisama_create_scorer",
            "pisama_run_scorer",
            "pisama_list_scorers",
            "pisama_evaluate_conversation",
            "pisama_generate_source_fix",
        }
        for name in expected:
            assert name in tool_names, f"Missing tool: {name}"


# ===========================================================================
# Resources
# ===========================================================================


class TestResources:
    def test_has_resources(self):
        assert len(RESOURCES) == 3

    def test_resource_uris(self):
        uris = {str(r.uri) for r in RESOURCES}
        assert "pisama://docs/detection-types" in uris
        assert "pisama://docs/fix-types" in uris
        assert "pisama://status/summary" in uris


# ===========================================================================
# Validation helpers
# ===========================================================================


class TestValidateUuid:
    def test_valid_uuid(self):
        result = _validate_uuid("12345678-1234-1234-1234-123456789abc", "test")
        assert result == "12345678-1234-1234-1234-123456789abc"

    def test_strips_whitespace(self):
        result = _validate_uuid("  12345678-1234-1234-1234-123456789abc  ", "test")
        assert result == "12345678-1234-1234-1234-123456789abc"

    def test_rejects_invalid(self):
        with pytest.raises(ValueError, match="must be a valid UUID"):
            _validate_uuid("not-a-uuid", "test_field")

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            _validate_uuid("", "test_field")


class TestValidateIntRange:
    def test_valid_value(self):
        assert _validate_int_range(5, "page", 1, 100, 1) == 5

    def test_returns_default_on_none(self):
        assert _validate_int_range(None, "page", 1, 100, 42) == 42

    def test_rejects_below_min(self):
        with pytest.raises(ValueError, match="must be between"):
            _validate_int_range(0, "page", 1, 100, 1)

    def test_rejects_above_max(self):
        with pytest.raises(ValueError, match="must be between"):
            _validate_int_range(101, "per_page", 1, 100, 20)

    def test_rejects_non_integer(self):
        with pytest.raises(ValueError, match="must be an integer"):
            _validate_int_range("abc", "page", 1, 100, 1)

    def test_converts_string_integer(self):
        assert _validate_int_range("5", "page", 1, 100, 1) == 5


class TestValidateIsoDatetime:
    def test_returns_none_on_none(self):
        assert _validate_iso_datetime(None, "since") is None

    def test_valid_iso(self):
        result = _validate_iso_datetime("2026-03-01T00:00:00Z", "since")
        assert result == "2026-03-01T00:00:00Z"

    def test_valid_with_offset(self):
        result = _validate_iso_datetime("2026-03-01T00:00:00+00:00", "since")
        assert result is not None

    def test_rejects_invalid(self):
        with pytest.raises(ValueError, match="must be a valid ISO-8601"):
            _validate_iso_datetime("not-a-date", "since")


# ===========================================================================
# PISAMAMCPClient
# ===========================================================================


class TestPISAMAMCPClientInit:
    def test_creates_with_valid_params(self):
        client = PISAMAMCPClient("http://localhost:8000", "test-key", "tenant-1")
        assert client.base_url == "http://localhost:8000"
        assert client.api_key == "test-key"
        assert client.tenant_id == "tenant-1"

    def test_strips_trailing_slash(self):
        client = PISAMAMCPClient("http://localhost:8000/", "key", "t")
        assert client.base_url == "http://localhost:8000"


# ===========================================================================
# Server creation
# ===========================================================================


class TestServerCreation:
    def test_creates_server_successfully(self):
        client = PISAMAMCPClient("http://localhost:8000", "key", "tenant")
        server = create_server(client)
        assert server is not None
        assert server.name == "pisama"


# ===========================================================================
# Tool dispatch
# ===========================================================================


class TestToolDispatch:
    @pytest.mark.asyncio
    async def test_unknown_tool_raises(self):
        client = MagicMock(spec=PISAMAMCPClient)
        with pytest.raises(ValueError, match="Unknown tool"):
            await _dispatch_tool(client, "nonexistent_tool", {})

    @pytest.mark.asyncio
    async def test_query_traces_dispatches(self):
        client = AsyncMock(spec=PISAMAMCPClient)
        client.query_traces = AsyncMock(return_value={"traces": []})
        result = await _dispatch_tool(client, "pisama_query_traces", {})
        assert result == {"traces": []}

    @pytest.mark.asyncio
    async def test_query_detections_validates_type(self):
        client = AsyncMock(spec=PISAMAMCPClient)
        with pytest.raises(ValueError, match="Unknown detection type"):
            await _dispatch_tool(
                client, "pisama_query_detections", {"type": "fake_detector"}
            )

    @pytest.mark.asyncio
    async def test_get_trace_detail_validates_uuid(self):
        client = AsyncMock(spec=PISAMAMCPClient)
        with pytest.raises(ValueError, match="must be a valid UUID"):
            await _dispatch_tool(
                client, "pisama_get_trace_detail", {"trace_id": "bad-id"}
            )

    @pytest.mark.asyncio
    async def test_create_scorer_validates_name(self):
        client = AsyncMock(spec=PISAMAMCPClient)
        with pytest.raises(ValueError, match="name is required"):
            await _dispatch_tool(
                client, "pisama_create_scorer",
                {"name": "", "description": "A long enough description for validation"}
            )

    @pytest.mark.asyncio
    async def test_create_scorer_validates_description_length(self):
        client = AsyncMock(spec=PISAMAMCPClient)
        with pytest.raises(ValueError, match="at least 10 characters"):
            await _dispatch_tool(
                client, "pisama_create_scorer",
                {"name": "test", "description": "short"}
            )

    @pytest.mark.asyncio
    async def test_generate_source_fix_validates_language(self):
        client = AsyncMock(spec=PISAMAMCPClient)
        with pytest.raises(ValueError, match="Unsupported language"):
            await _dispatch_tool(
                client, "pisama_generate_source_fix",
                {
                    "detection_id": "12345678-1234-1234-1234-123456789abc",
                    "file_path": "test.py",
                    "file_content": "code",
                    "language": "brainfuck",
                }
            )

    @pytest.mark.asyncio
    async def test_submit_feedback_validates_is_correct(self):
        client = AsyncMock(spec=PISAMAMCPClient)
        with pytest.raises(ValueError, match="is_correct is required"):
            await _dispatch_tool(
                client, "pisama_submit_feedback",
                {"detection_id": "12345678-1234-1234-1234-123456789abc"}
            )

    @pytest.mark.asyncio
    async def test_submit_feedback_validates_boolean(self):
        client = AsyncMock(spec=PISAMAMCPClient)
        with pytest.raises(ValueError, match="must be a boolean"):
            await _dispatch_tool(
                client, "pisama_submit_feedback",
                {
                    "detection_id": "12345678-1234-1234-1234-123456789abc",
                    "is_correct": "yes",
                }
            )

    @pytest.mark.asyncio
    async def test_run_scorer_defaults_latest_n(self):
        client = AsyncMock(spec=PISAMAMCPClient)
        client.run_scorer = AsyncMock(return_value={"scores": []})
        await _dispatch_tool(
            client, "pisama_run_scorer",
            {"scorer_id": "12345678-1234-1234-1234-123456789abc"}
        )
        # Should default to latest_n=10 when nothing specified
        client.run_scorer.assert_called_once()
        call_kwargs = client.run_scorer.call_args
        assert call_kwargs.kwargs.get("latest_n") == 10 or call_kwargs[1].get("latest_n") == 10

    @pytest.mark.asyncio
    async def test_list_scorers_dispatches(self):
        client = AsyncMock(spec=PISAMAMCPClient)
        client.list_scorers = AsyncMock(return_value={"scorers": []})
        result = await _dispatch_tool(client, "pisama_list_scorers", {})
        assert result == {"scorers": []}
