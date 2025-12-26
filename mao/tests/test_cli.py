"""Tests for CLI commands."""

import pytest
from click.testing import CliRunner
from unittest.mock import AsyncMock, patch, MagicMock

from mao.cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.endpoint = "http://localhost:8000"
    config.tenant_id = "default"
    config.get_api_key.return_value = "test-api-key"
    return config


class TestDebugCommand:
    def test_debug_requires_trace_id_or_last(self, runner, mock_config):
        with patch("mao.cli.main.load_config", return_value=mock_config):
            result = runner.invoke(cli, ["debug"])
            assert result.exit_code == 2
            assert "Specify a trace ID" in result.output
    
    def test_debug_with_trace_id(self, runner, mock_config):
        mock_result = {
            "trace_id": "trace-123",
            "framework": "langchain",
            "duration_ms": 1500,
            "healthy": True,
            "status": "OK",
            "detections": [],
        }
        
        with patch("mao.cli.main.load_config", return_value=mock_config):
            with patch("mao.cli.main.create_client") as mock_client:
                mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
                mock_client.return_value.__aexit__ = AsyncMock()
                mock_client.return_value.__aenter__.return_value.analyze_trace = AsyncMock(
                    return_value=mock_result
                )
                
                result = runner.invoke(cli, ["debug", "trace-123"])
                
                assert "trace-123" in result.output or result.exit_code == 0


class TestConfigCommand:
    def test_config_show(self, runner, mock_config):
        with patch("mao.cli.main.load_config", return_value=mock_config):
            result = runner.invoke(cli, ["config", "show"])
            assert result.exit_code == 0
            assert "Endpoint" in result.output


class TestCommandAliases:
    def test_d_alias(self, runner, mock_config):
        with patch("mao.cli.main.load_config", return_value=mock_config):
            result = runner.invoke(cli, ["d"])
            assert result.exit_code == 2
    
    def test_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "MAO" in result.output
        assert "debug" in result.output
        assert "fix" in result.output
        assert "watch" in result.output


class TestCICommands:
    def test_ci_check(self, runner, mock_config):
        with patch("mao.cli.main.load_config", return_value=mock_config):
            with patch("mao.cli.main.create_client") as mock_client:
                mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
                mock_client.return_value.__aexit__ = AsyncMock()
                
                result = runner.invoke(cli, ["ci", "check"])
                
                assert result.exit_code == 0
                assert "94.2%" in result.output or "passed" in result.output.lower()
