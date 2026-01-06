"""Tests for MAO Testing SDK configuration."""

import os
import pytest
from mao_testing.config import MAOConfig, SamplingRule
from mao_testing.errors import ConfigError


class TestMAOConfig:
    def test_default_config(self):
        config = MAOConfig()
        assert config.endpoint == "https://api.mao-testing.com"
        assert config.environment == "development"
        assert config.sample_rate == 1.0
        assert config.on_error == "log"
        assert config.enabled is True
    
    def test_custom_config(self):
        config = MAOConfig(
            api_key="test-key",
            endpoint="http://localhost:8000",
            environment="production",
            service_name="my-service",
            sample_rate=0.5,
        )
        assert config.api_key == "test-key"
        assert config.endpoint == "http://localhost:8000"
        assert config.environment == "production"
        assert config.service_name == "my-service"
        assert config.sample_rate == 0.5
    
    def test_config_from_env(self, monkeypatch):
        monkeypatch.setenv("MAO_API_KEY", "env-key")
        monkeypatch.setenv("MAO_ENDPOINT", "http://env-endpoint")
        monkeypatch.setenv("MAO_ENVIRONMENT", "staging")
        
        config = MAOConfig.from_env()
        assert config.api_key == "env-key"
        assert config.endpoint == "http://env-endpoint"
        assert config.environment == "staging"
    
    def test_invalid_sample_rate(self):
        with pytest.raises(ConfigError) as exc_info:
            MAOConfig(sample_rate=1.5)
        assert "sample_rate must be between 0.0 and 1.0" in str(exc_info.value)
    
    def test_invalid_on_error(self):
        with pytest.raises(ConfigError) as exc_info:
            MAOConfig(on_error="invalid")
        assert "on_error must be" in str(exc_info.value)


class TestSamplingRule:
    def test_status_match(self):
        rule = SamplingRule(condition="status == 'error'", rate=1.0)
        assert rule.matches({"status": "error"}) is True
        assert rule.matches({"status": "ok"}) is False
    
    def test_duration_match(self):
        rule = SamplingRule(condition="duration > 30s", rate=1.0)
        assert rule.matches({"duration_s": 45}) is True
        assert rule.matches({"duration_s": 15}) is False
    
    def test_cost_match(self):
        rule = SamplingRule(condition="cost > 0.50", rate=1.0)
        assert rule.matches({"cost": 0.75}) is True
        assert rule.matches({"cost": 0.25}) is False
    
    def test_tag_match(self):
        rule = SamplingRule(condition="tag:production", rate=1.0)
        assert rule.matches({"tags": ["production", "critical"]}) is True
        assert rule.matches({"tags": ["staging"]}) is False
