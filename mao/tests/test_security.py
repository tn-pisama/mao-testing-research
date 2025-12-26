"""Tests for security utilities."""

import pytest
from mao.core.security import validate_trace_id, validate_detection_id, validate_file_path
from mao.core.errors import ValidationError
from pathlib import Path


class TestValidateTraceId:
    def test_valid_trace_id(self):
        assert validate_trace_id("trace-123") == "trace-123"
        assert validate_trace_id("abc_def-456") == "abc_def-456"
        assert validate_trace_id("TRACE123") == "TRACE123"
    
    def test_empty_trace_id(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_trace_id("")
    
    def test_invalid_characters(self):
        with pytest.raises(ValidationError, match="Invalid trace ID"):
            validate_trace_id("trace;DROP TABLE")
        
        with pytest.raises(ValidationError, match="Invalid trace ID"):
            validate_trace_id("trace/../etc/passwd")
    
    def test_too_long(self):
        with pytest.raises(ValidationError, match="Invalid trace ID"):
            validate_trace_id("a" * 200)


class TestValidateDetectionId:
    def test_valid_detection_id(self):
        assert validate_detection_id("det-123") == "det-123"
    
    def test_empty_detection_id(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_detection_id("")


class TestValidateFilePath:
    def test_valid_path(self, tmp_path):
        test_file = tmp_path / "test.py"
        test_file.touch()
        
        result = validate_file_path(str(test_file), tmp_path)
        assert result == test_file
    
    def test_path_traversal(self, tmp_path):
        with pytest.raises(ValidationError, match="outside project"):
            validate_file_path("/etc/passwd", tmp_path)
        
        with pytest.raises(ValidationError, match="outside project"):
            validate_file_path(str(tmp_path / ".." / ".." / "etc" / "passwd"), tmp_path)
    
    def test_disallowed_extension(self, tmp_path):
        with pytest.raises(ValidationError, match="not allowed"):
            validate_file_path(str(tmp_path / "script.sh"), tmp_path)
        
        with pytest.raises(ValidationError, match="not allowed"):
            validate_file_path(str(tmp_path / "config.yaml"), tmp_path)
    
    def test_allowed_extensions(self, tmp_path):
        for ext in [".py", ".js", ".ts", ".go", ".rs"]:
            path = tmp_path / f"file{ext}"
            path.touch()
            result = validate_file_path(str(path), tmp_path)
            assert result.suffix == ext
