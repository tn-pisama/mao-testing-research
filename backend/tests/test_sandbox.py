"""
Tests for the fixes/sandbox.py module - sandboxed fix validation.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
import json
import warnings
import sys

from app.fixes.sandbox import (
    ValidationResult,
    FixSuggestion,
    DOCKER_AVAILABLE,
)


# =============================================================================
# ValidationResult Tests
# =============================================================================

class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_validation_result_defaults(self):
        """Test ValidationResult with default values."""
        result = ValidationResult(success=True)
        assert result.success is True
        assert result.output is None
        assert result.error is None
        assert result.execution_time == 0.0
        assert result.issue_resolved is False
        assert result.new_issues == 0

    def test_validation_result_success(self):
        """Test successful validation result."""
        result = ValidationResult(
            success=True,
            output="Test passed",
            execution_time=1.5,
            issue_resolved=True,
            new_issues=0,
        )
        assert result.success is True
        assert result.output == "Test passed"
        assert result.issue_resolved is True

    def test_validation_result_failure(self):
        """Test failed validation result."""
        result = ValidationResult(
            success=False,
            error="Timeout error",
            execution_time=30.0,
            issue_resolved=False,
            new_issues=2,
        )
        assert result.success is False
        assert result.error == "Timeout error"
        assert result.new_issues == 2


# =============================================================================
# FixSuggestion Tests
# =============================================================================

class TestFixSuggestion:
    """Tests for FixSuggestion dataclass."""

    def test_fix_suggestion_minimal(self):
        """Test FixSuggestion with required fields only."""
        fix = FixSuggestion(
            fix_type="max_iterations",
            code_change="max_iterations=10",
            description="Add max iterations limit",
            confidence=0.9,
        )
        assert fix.fix_type == "max_iterations"
        assert fix.code_change == "max_iterations=10"
        assert fix.description == "Add max iterations limit"
        assert fix.confidence == 0.9
        assert fix.line_number is None
        assert fix.file_path is None

    def test_fix_suggestion_with_location(self):
        """Test FixSuggestion with file location."""
        fix = FixSuggestion(
            fix_type="timeout",
            code_change="timeout=300",
            description="Add timeout",
            confidence=0.85,
            line_number=42,
            file_path="/path/to/agent.py",
        )
        assert fix.line_number == 42
        assert fix.file_path == "/path/to/agent.py"


# =============================================================================
# SandboxedFixValidator Tests
# =============================================================================

@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker SDK not available")
class TestSandboxedFixValidator:
    """Tests for SandboxedFixValidator class."""

    @pytest.fixture
    def validator_with_mock_client(self):
        """Create validator with mocked docker client."""
        from app.fixes.sandbox import SandboxedFixValidator

        with patch('docker.from_env') as mock_from_env:
            mock_client = MagicMock()
            mock_from_env.return_value = mock_client
            validator = SandboxedFixValidator()
            validator.client = mock_client
            yield validator, mock_client

    def test_validator_initialization(self, validator_with_mock_client):
        """Test validator initialization when Docker is available."""
        validator, _ = validator_with_mock_client
        assert validator.SANDBOX_IMAGE == "mao/fix-sandbox:latest"
        assert validator.DEFAULT_TIMEOUT == 30

    def test_validator_constants(self, validator_with_mock_client):
        """Test validator has correct constants."""
        validator, _ = validator_with_mock_client
        assert validator.MAX_MEMORY == "512m"
        assert validator.MAX_CPUS == 1.0

    def test_apply_fix_with_line_number(self, validator_with_mock_client):
        """Test applying fix at specific line number."""
        validator, _ = validator_with_mock_client
        original_code = "line1\nline2\nline3"
        fix = FixSuggestion(
            fix_type="test",
            code_change="modified_line2",
            description="Change line 2",
            confidence=0.9,
            line_number=2,
        )

        result = validator._apply_fix(original_code, fix)
        assert result == "line1\nmodified_line2\nline3"

    def test_apply_fix_without_line_number(self, validator_with_mock_client):
        """Test applying fix using pattern matching."""
        validator, _ = validator_with_mock_client
        original_code = "agent = AgentExecutor(tools=tools)"
        fix = FixSuggestion(
            fix_type="max_iterations",
            code_change="AgentExecutor(tools=tools, max_iterations=10)",
            description="Add max iterations",
            confidence=0.9,
        )

        result = validator._apply_fix(original_code, fix)
        assert "max_iterations=10" in result

    def test_find_replacement_target_max_iterations(self, validator_with_mock_client):
        """Test finding replacement target for max_iterations fix type."""
        validator, _ = validator_with_mock_client
        code = "agent = AgentExecutor(tools=my_tools, verbose=True)"
        fix = FixSuggestion(
            fix_type="max_iterations",
            code_change="replacement",
            description="Test",
            confidence=0.9,
        )

        target = validator._find_replacement_target(code, fix)
        assert "AgentExecutor(" in target

    def test_find_replacement_target_timeout(self, validator_with_mock_client):
        """Test finding replacement target for timeout fix type."""
        validator, _ = validator_with_mock_client
        code = "crew = Crew(agents=[agent1], tasks=[task1])"
        fix = FixSuggestion(
            fix_type="timeout",
            code_change="replacement",
            description="Test",
            confidence=0.9,
        )

        target = validator._find_replacement_target(code, fix)
        assert "Crew(" in target

    def test_find_replacement_target_state_validation(self, validator_with_mock_client):
        """Test finding replacement target for state validation fix type."""
        validator, _ = validator_with_mock_client
        code = "def process_data(self, input):\n    return input"
        fix = FixSuggestion(
            fix_type="state_validation",
            code_change="replacement",
            description="Test",
            confidence=0.9,
        )

        target = validator._find_replacement_target(code, fix)
        assert "def process_data" in target

    def test_generate_wrapper(self, validator_with_mock_client):
        """Test wrapper script generation."""
        validator, _ = validator_with_mock_client
        wrapper = validator._generate_wrapper("test_code")

        assert "import json" in wrapper
        assert "def run_test():" in wrapper
        assert "issue_resolved" in wrapper
        assert "RecursionError" in wrapper
        assert "TimeoutError" in wrapper

    def test_parse_output_valid_json(self, validator_with_mock_client):
        """Test parsing valid JSON output."""
        validator, _ = validator_with_mock_client
        output = '{"issue_resolved": true, "new_issues": 0}'

        result = validator._parse_output(output)
        assert result["issue_resolved"] is True
        assert result["new_issues"] == 0

    def test_parse_output_multiline(self, validator_with_mock_client):
        """Test parsing multiline output with JSON."""
        validator, _ = validator_with_mock_client
        output = "Some log output\n{\"issue_resolved\": true, \"new_issues\": 0}\nMore logs"

        result = validator._parse_output(output)
        assert result["issue_resolved"] is True

    def test_parse_output_invalid_json(self, validator_with_mock_client):
        """Test parsing invalid JSON returns default."""
        validator, _ = validator_with_mock_client
        output = "not valid json"

        result = validator._parse_output(output)
        assert result["issue_resolved"] is False
        assert result["new_issues"] == 0

    def test_parse_output_empty(self, validator_with_mock_client):
        """Test parsing empty output."""
        validator, _ = validator_with_mock_client
        result = validator._parse_output("")
        assert result["issue_resolved"] is False

    @pytest.mark.asyncio
    async def test_validate_fix_success(self, validator_with_mock_client):
        """Test successful fix validation."""
        validator, mock_client = validator_with_mock_client
        mock_client.containers.run.return_value = b'{"issue_resolved": true, "new_issues": 0}'

        fix = FixSuggestion(
            fix_type="max_iterations",
            code_change="max_iterations=10",
            description="Add limit",
            confidence=0.9,
        )

        result = await validator.validate_fix(
            original_code="agent = AgentExecutor()",
            fix=fix,
            test_input={"query": "test"},
        )

        assert result.success is True
        assert result.issue_resolved is True
        mock_client.containers.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_fix_exception(self, validator_with_mock_client):
        """Test fix validation with exception."""
        validator, mock_client = validator_with_mock_client
        mock_client.containers.run.side_effect = Exception("Docker error")

        fix = FixSuggestion(
            fix_type="test",
            code_change="code",
            description="Test",
            confidence=0.9,
        )

        result = await validator.validate_fix(
            original_code="code",
            fix=fix,
            test_input={},
        )

        assert result.success is False
        assert "error" in result.error.lower()

    @pytest.mark.asyncio
    async def test_validate_batch(self, validator_with_mock_client):
        """Test batch validation of multiple fixes."""
        validator, mock_client = validator_with_mock_client
        mock_client.containers.run.return_value = b'{"issue_resolved": true, "new_issues": 0}'

        fixes = [
            FixSuggestion(
                fix_type=f"type_{i}",
                code_change=f"change_{i}",
                description=f"Fix {i}",
                confidence=0.9,
            )
            for i in range(3)
        ]

        results = await validator.validate_batch(
            fixes=fixes,
            original_code="original",
            test_input={},
            max_concurrent=2,
        )

        assert len(results) == 3
        assert all(r.success for r in results)


# =============================================================================
# SandboxedFixValidator without Docker
# =============================================================================

class TestSandboxedFixValidatorWithoutDocker:
    """Tests for SandboxedFixValidator when Docker SDK is not available."""

    def test_validator_raises_without_docker(self):
        """Test validator raises when Docker is not available."""
        with patch('app.fixes.sandbox.DOCKER_AVAILABLE', False):
            from app.fixes.sandbox import SandboxedFixValidator
            with pytest.raises(RuntimeError, match="Docker SDK not available"):
                SandboxedFixValidator()


# =============================================================================
# LocalFixValidator Tests
# =============================================================================

class TestLocalFixValidator:
    """Tests for LocalFixValidator class."""

    def test_validator_initialization_warns(self):
        """Test that LocalFixValidator warns about security."""
        from app.fixes.sandbox import LocalFixValidator, SecurityWarning

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            LocalFixValidator()
            assert len(w) == 1
            assert issubclass(w[0].category, SecurityWarning)
            assert "without sandboxing" in str(w[0].message)

    @pytest.mark.asyncio
    async def test_validate_fix_success(self):
        """Test successful local fix validation."""
        from app.fixes.sandbox import LocalFixValidator

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            validator = LocalFixValidator()

        fix = FixSuggestion(
            fix_type="test",
            code_change="x = 1",
            description="Simple assignment",
            confidence=0.9,
        )

        result = await validator.validate_fix(
            original_code="# Original",
            fix=fix,
            test_input={},
        )

        assert result.success is True
        assert result.issue_resolved is True
        assert result.execution_time > 0

    @pytest.mark.asyncio
    async def test_validate_fix_exception(self):
        """Test local fix validation with exception in original code."""
        from app.fixes.sandbox import LocalFixValidator

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            validator = LocalFixValidator()

        fix = FixSuggestion(
            fix_type="test",
            code_change="fixed code",
            description="Fix error",
            confidence=0.9,
        )

        # The validator executes original_code, which raises
        result = await validator.validate_fix(
            original_code="raise ValueError('test error')",
            fix=fix,
            test_input={},
        )

        assert result.success is False
        assert "ValueError" in result.error or "test error" in result.error


# =============================================================================
# get_validator Tests
# =============================================================================

class TestGetValidator:
    """Tests for get_validator factory function."""

    def test_get_validator_use_docker_false(self):
        """Test get_validator with use_docker=False returns LocalFixValidator."""
        from app.fixes.sandbox import get_validator, LocalFixValidator

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            validator = get_validator(use_docker=False)
            assert isinstance(validator, LocalFixValidator)

    def test_get_validator_with_docker_unavailable(self):
        """Test get_validator when Docker unavailable returns LocalFixValidator."""
        with patch('app.fixes.sandbox.DOCKER_AVAILABLE', False):
            from app.fixes.sandbox import get_validator, LocalFixValidator
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                validator = get_validator(use_docker=True)
                assert isinstance(validator, LocalFixValidator)

    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker SDK not available")
    def test_get_validator_docker_ping_fails(self):
        """Test get_validator falls back to LocalFixValidator when Docker ping fails."""
        from app.fixes.sandbox import get_validator, LocalFixValidator

        with patch('docker.from_env') as mock_from_env:
            mock_client = MagicMock()
            mock_client.ping.side_effect = Exception("Connection failed")
            mock_from_env.return_value = mock_client

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                validator = get_validator(use_docker=True)
                assert isinstance(validator, LocalFixValidator)

    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker SDK not available")
    def test_get_validator_docker_success(self):
        """Test get_validator returns SandboxedFixValidator when Docker works."""
        from app.fixes.sandbox import get_validator, SandboxedFixValidator

        with patch('docker.from_env') as mock_from_env:
            mock_client = MagicMock()
            mock_client.ping.return_value = True
            mock_from_env.return_value = mock_client

            validator = get_validator(use_docker=True)

            assert isinstance(validator, SandboxedFixValidator)


# =============================================================================
# Integration Tests
# =============================================================================

@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker SDK not available")
class TestSandboxIntegration:
    """Integration tests for sandbox functionality."""

    @pytest.fixture
    def validator_with_mock(self):
        """Create validator with mocked docker client."""
        from app.fixes.sandbox import SandboxedFixValidator

        with patch('docker.from_env') as mock_from_env:
            mock_client = MagicMock()
            mock_from_env.return_value = mock_client
            validator = SandboxedFixValidator()
            validator.client = mock_client
            yield validator, mock_client

    @pytest.mark.asyncio
    async def test_full_validation_workflow(self, validator_with_mock):
        """Test complete validation workflow."""
        validator, mock_client = validator_with_mock
        mock_client.containers.run.return_value = json.dumps({
            "success": True,
            "issue_resolved": True,
            "new_issues": 0,
            "output": "Agent executed successfully",
        }).encode()

        fix = FixSuggestion(
            fix_type="max_iterations",
            code_change="AgentExecutor(tools=tools, max_iterations=10)",
            description="Add max_iterations to prevent infinite loops",
            confidence=0.95,
        )

        original_code = """
from langchain.agents import AgentExecutor
agent = AgentExecutor(tools=tools)
result = agent.invoke({"query": "test"})
"""

        result = await validator.validate_fix(
            original_code=original_code,
            fix=fix,
            test_input={"query": "test query"},
            timeout=30,
        )

        assert result.success is True
        assert result.issue_resolved is True
        assert result.execution_time > 0

    def test_fix_suggestion_types(self, validator_with_mock):
        """Test different fix suggestion types."""
        validator, _ = validator_with_mock

        fix_types = [
            ("max_iterations", "AgentExecutor(max_iterations=10)"),
            ("timeout", "Crew(timeout=300)"),
            ("state_validation", "def validate(self, state):"),
        ]

        for fix_type, code_change in fix_types:
            fix = FixSuggestion(
                fix_type=fix_type,
                code_change=code_change,
                description=f"Test {fix_type}",
                confidence=0.9,
            )
            assert fix.fix_type == fix_type

    @pytest.mark.asyncio
    async def test_concurrent_validation(self, validator_with_mock):
        """Test concurrent fix validation."""
        validator, mock_client = validator_with_mock

        call_count = [0]

        def mock_run(*args, **kwargs):
            call_count[0] += 1
            return json.dumps({
                "issue_resolved": True,
                "new_issues": 0,
            }).encode()

        mock_client.containers.run.side_effect = mock_run

        fixes = [
            FixSuggestion(
                fix_type=f"type_{i}",
                code_change=f"change_{i}",
                description=f"Fix {i}",
                confidence=0.8 + i * 0.05,
            )
            for i in range(5)
        ]

        results = await validator.validate_batch(
            fixes=fixes,
            original_code="agent = AgentExecutor()",
            test_input={"query": "test"},
            max_concurrent=3,
        )

        assert len(results) == 5
        assert call_count[0] == 5


# =============================================================================
# Module Import Tests
# =============================================================================

class TestModuleImports:
    """Tests for module imports."""

    def test_import_all_components(self):
        """Test all components are importable."""
        from app.fixes.sandbox import (
            ValidationResult,
            FixSuggestion,
            SandboxedFixValidator,
            LocalFixValidator,
            get_validator,
            DOCKER_AVAILABLE,
        )

        assert ValidationResult is not None
        assert FixSuggestion is not None
        assert SandboxedFixValidator is not None
        assert LocalFixValidator is not None
        assert get_validator is not None
        assert isinstance(DOCKER_AVAILABLE, bool)

    def test_docker_available_flag(self):
        """Test DOCKER_AVAILABLE reflects actual availability."""
        try:
            import docker
            expected = hasattr(docker, 'from_env')
        except ImportError:
            expected = False

        assert DOCKER_AVAILABLE == expected
