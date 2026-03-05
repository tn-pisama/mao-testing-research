"""Tests for SourceFixGenerator."""
import pytest
from unittest.mock import MagicMock, patch
from app.fixes.source_fix_generator import (
    SourceFixGenerator,
    SourceFixInput,
    SourceFixOutput,
    DETECTION_FIX_PROMPTS,
    _SONNET_INPUT_COST_PER_1M,
    _SONNET_OUTPUT_COST_PER_1M,
    _DEFAULT_MODEL,
    _SYSTEM_PROMPT,
)


class TestDetectionPromptCoverage:
    """Verify that all 17 detection types have fix prompt guidance."""

    EXPECTED_TYPES = [
        "loop", "corruption", "persona_drift", "coordination",
        "hallucination", "injection", "overflow", "derailment",
        "context", "communication", "specification", "decomposition",
        "workflow", "withholding", "completion", "cost", "grounding",
    ]

    def test_all_17_types_covered(self):
        for dt in self.EXPECTED_TYPES:
            assert dt in DETECTION_FIX_PROMPTS, f"Missing prompt for {dt}"

    def test_prompts_are_nonempty(self):
        for dt, prompt in DETECTION_FIX_PROMPTS.items():
            assert len(prompt) > 50, f"Prompt for {dt} is too short: {len(prompt)} chars"

    def test_prompts_mention_common_causes(self):
        for dt, prompt in DETECTION_FIX_PROMPTS.items():
            assert "common" in prompt.lower(), f"Prompt for {dt} should mention common patterns"

    def test_no_extra_types(self):
        """Ensure no unexpected detection types snuck in."""
        for dt in DETECTION_FIX_PROMPTS:
            assert dt in self.EXPECTED_TYPES, f"Unexpected detection type in prompts: {dt}"


class TestDiffGeneration:
    """Test the unified diff generation."""

    def test_generates_unified_diff(self):
        original = "def foo():\n    return 1\n"
        fixed = "def foo():\n    return 2\n"
        diff = SourceFixGenerator._generate_diff("test.py", original, fixed)
        assert "--- a/test.py" in diff
        assert "+++ b/test.py" in diff
        assert "-    return 1" in diff
        assert "+    return 2" in diff

    def test_identical_files_produce_empty_diff(self):
        code = "def foo():\n    return 1\n"
        diff = SourceFixGenerator._generate_diff("test.py", code, code)
        assert diff == ""

    def test_multiline_diff(self):
        original = "line1\nline2\nline3\n"
        fixed = "line1\nline2_modified\nline3\nline4\n"
        diff = SourceFixGenerator._generate_diff("app.py", original, fixed)
        assert "-line2" in diff
        assert "+line2_modified" in diff
        assert "+line4" in diff

    def test_empty_original(self):
        diff = SourceFixGenerator._generate_diff("new.py", "", "print('hello')\n")
        assert "+print('hello')" in diff

    def test_empty_fixed(self):
        diff = SourceFixGenerator._generate_diff("old.py", "print('hello')\n", "")
        assert "-print('hello')" in diff


class TestExtractTag:
    """Test the XML tag extraction helper."""

    def test_extracts_simple_tag(self):
        text = "<explanation>This is the explanation</explanation>"
        result = SourceFixGenerator._extract_tag(text, "explanation")
        assert result == "This is the explanation"

    def test_extracts_multiline_tag(self):
        text = """<fixed_code>
def foo():
    return 2
</fixed_code>"""
        result = SourceFixGenerator._extract_tag(text, "fixed_code")
        assert "return 2" in result

    def test_strips_whitespace(self):
        text = "<confidence>  0.85  </confidence>"
        result = SourceFixGenerator._extract_tag(text, "confidence")
        assert result == "0.85"

    def test_returns_empty_on_missing_tag(self):
        text = "No tags here"
        result = SourceFixGenerator._extract_tag(text, "explanation")
        assert result == ""

    def test_extracts_from_complex_document(self):
        text = """Some preamble text

<fixed_code>
def foo():
    return 2
</fixed_code>

<explanation>Changed return value</explanation>

<root_cause>Wrong value</root_cause>

<confidence>0.85</confidence>

<breaking_risk>low</breaking_risk>"""
        assert "return 2" in SourceFixGenerator._extract_tag(text, "fixed_code")
        assert "Changed" in SourceFixGenerator._extract_tag(text, "explanation")
        assert "Wrong" in SourceFixGenerator._extract_tag(text, "root_cause")
        assert "0.85" in SourceFixGenerator._extract_tag(text, "confidence")
        assert "low" in SourceFixGenerator._extract_tag(text, "breaking_risk")


class TestResponseParsing:
    """Test _parse_response with realistic LLM output."""

    def _make_gen(self):
        gen = SourceFixGenerator.__new__(SourceFixGenerator)
        return gen

    def test_parses_structured_response(self):
        gen = self._make_gen()
        raw = """<fixed_code>
def foo():
    return 2
</fixed_code>
<explanation>Changed return value</explanation>
<root_cause>Wrong return value</root_cause>
<confidence>0.85</confidence>
<breaking_risk>low</breaking_risk>"""
        fixed, explanation, root_cause, confidence, risk = gen._parse_response(
            raw, "def foo():\n    return 1"
        )
        assert "return 2" in fixed
        assert "Changed" in explanation
        assert "Wrong" in root_cause
        assert confidence == 0.85
        assert risk == "low"

    def test_falls_back_on_missing_fixed_code(self):
        gen = self._make_gen()
        raw = """<explanation>Some explanation</explanation>"""
        original = "def foo():\n    return 1\n"
        fixed, explanation, root_cause, confidence, risk = gen._parse_response(
            raw, original
        )
        # Falls back to original code
        assert fixed == original
        assert "Some explanation" in explanation

    def test_falls_back_on_missing_explanation(self):
        gen = self._make_gen()
        raw = """<fixed_code>def foo(): pass</fixed_code>"""
        fixed, explanation, root_cause, confidence, risk = gen._parse_response(
            raw, "original"
        )
        assert "did not provide" in explanation.lower()

    def test_falls_back_on_missing_root_cause(self):
        gen = self._make_gen()
        raw = """<fixed_code>def foo(): pass</fixed_code>"""
        fixed, explanation, root_cause, confidence, risk = gen._parse_response(
            raw, "original"
        )
        assert "unable to determine" in root_cause.lower()

    def test_clamps_confidence(self):
        gen = self._make_gen()
        raw = """<fixed_code>x</fixed_code>
<confidence>1.5</confidence>
<breaking_risk>low</breaking_risk>"""
        _, _, _, confidence, _ = gen._parse_response(raw, "orig")
        assert confidence == 1.0  # clamped

    def test_clamps_negative_confidence(self):
        gen = self._make_gen()
        raw = """<fixed_code>x</fixed_code>
<confidence>-0.5</confidence>
<breaking_risk>low</breaking_risk>"""
        _, _, _, confidence, _ = gen._parse_response(raw, "orig")
        assert confidence == 0.0  # clamped

    def test_defaults_confidence_on_invalid(self):
        gen = self._make_gen()
        raw = """<fixed_code>x</fixed_code>
<confidence>not a number</confidence>
<breaking_risk>low</breaking_risk>"""
        _, _, _, confidence, _ = gen._parse_response(raw, "orig")
        assert confidence == 0.5  # default

    def test_defaults_missing_confidence(self):
        gen = self._make_gen()
        raw = """<fixed_code>x</fixed_code>"""
        _, _, _, confidence, _ = gen._parse_response(raw, "orig")
        assert confidence == 0.5  # default

    def test_normalizes_breaking_risk(self):
        gen = self._make_gen()
        for valid_risk in ("low", "medium", "high"):
            raw = f"""<fixed_code>x</fixed_code>
<breaking_risk>{valid_risk}</breaking_risk>"""
            _, _, _, _, risk = gen._parse_response(raw, "orig")
            assert risk == valid_risk

    def test_defaults_invalid_breaking_risk(self):
        gen = self._make_gen()
        raw = """<fixed_code>x</fixed_code>
<breaking_risk>catastrophic</breaking_risk>"""
        _, _, _, _, risk = gen._parse_response(raw, "orig")
        assert risk == "medium"  # default for invalid

    def test_defaults_missing_breaking_risk(self):
        gen = self._make_gen()
        raw = """<fixed_code>x</fixed_code>"""
        _, _, _, _, risk = gen._parse_response(raw, "orig")
        assert risk == "medium"  # default


class TestCostCalculation:
    """Test static cost calculation."""

    def test_sonnet_pricing_basic(self):
        cost = SourceFixGenerator._calculate_cost(1000, 500)
        expected = (1000 * _SONNET_INPUT_COST_PER_1M + 500 * _SONNET_OUTPUT_COST_PER_1M) / 1_000_000
        assert abs(cost - expected) < 0.000001

    def test_zero_tokens(self):
        cost = SourceFixGenerator._calculate_cost(0, 0)
        assert cost == 0.0

    def test_large_request(self):
        cost = SourceFixGenerator._calculate_cost(100_000, 8_000)
        expected = (100_000 * 3.0 + 8_000 * 15.0) / 1_000_000
        assert abs(cost - expected) < 0.000001

    def test_output_more_expensive(self):
        """Output tokens should cost more than input tokens."""
        input_only = SourceFixGenerator._calculate_cost(1000, 0)
        output_only = SourceFixGenerator._calculate_cost(0, 1000)
        assert output_only > input_only


class TestBuildUserPrompt:
    """Test prompt construction from SourceFixInput."""

    def _make_gen(self):
        gen = SourceFixGenerator.__new__(SourceFixGenerator)
        return gen

    def test_includes_detection_type(self):
        gen = self._make_gen()
        inp = SourceFixInput(
            detection_type="loop",
            detection_method="hash",
            detection_details={"count": 5},
            confidence=85,
            file_path="agent.py",
            file_content="while True: pass",
            language="python",
        )
        prompt = gen._build_user_prompt(inp)
        assert "loop" in prompt
        assert "hash" in prompt
        assert "85%" in prompt

    def test_includes_source_code(self):
        gen = self._make_gen()
        inp = SourceFixInput(
            detection_type="corruption",
            detection_method="delta",
            detection_details={},
            confidence=70,
            file_path="state.py",
            file_content="class State:\n    pass\n",
            language="python",
        )
        prompt = gen._build_user_prompt(inp)
        assert "class State:" in prompt
        assert "state.py" in prompt

    def test_includes_framework_context(self):
        gen = self._make_gen()
        inp = SourceFixInput(
            detection_type="coordination",
            detection_method="pattern",
            detection_details={},
            confidence=60,
            file_path="main.py",
            file_content="code",
            language="python",
            framework="LangGraph",
        )
        prompt = gen._build_user_prompt(inp)
        assert "LangGraph" in prompt

    def test_includes_related_files(self):
        gen = self._make_gen()
        inp = SourceFixInput(
            detection_type="loop",
            detection_method="hash",
            detection_details={},
            confidence=90,
            file_path="main.py",
            file_content="import helper",
            language="python",
            related_files=[
                {"path": "helper.py", "language": "python", "content": "def help(): pass"},
            ],
        )
        prompt = gen._build_user_prompt(inp)
        assert "helper.py" in prompt
        assert "def help()" in prompt

    def test_includes_detection_guidance(self):
        gen = self._make_gen()
        inp = SourceFixInput(
            detection_type="hallucination",
            detection_method="embedding",
            detection_details={},
            confidence=80,
            file_path="rag.py",
            file_content="code",
            language="python",
        )
        prompt = gen._build_user_prompt(inp)
        # Should include guidance from DETECTION_FIX_PROMPTS
        assert "hallucination" in prompt.lower() or "grounding" in prompt.lower()

    def test_includes_root_cause_analysis(self):
        gen = self._make_gen()
        inp = SourceFixInput(
            detection_type="loop",
            detection_method="hash",
            detection_details={},
            confidence=90,
            file_path="main.py",
            file_content="code",
            language="python",
            root_cause_analysis="The retry counter is never incremented",
        )
        prompt = gen._build_user_prompt(inp)
        assert "retry counter is never incremented" in prompt


class TestGenerateFix:
    """Test the full generate_fix flow with mocked Anthropic."""

    @patch("app.fixes.source_fix_generator.Anthropic")
    def test_generates_fix_successfully(self, mock_cls):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_block = MagicMock()
        mock_block.type = "text"
        mock_block.text = """<fixed_code>
def foo():
    # FIX: Changed return value to fix incorrect output
    return 2
</fixed_code>
<explanation>Changed return value from 1 to 2</explanation>
<root_cause>Incorrect hardcoded return value</root_cause>
<confidence>0.9</confidence>
<breaking_risk>low</breaking_risk>"""

        mock_resp = MagicMock()
        mock_resp.content = [mock_block]
        mock_resp.usage.input_tokens = 5000
        mock_resp.usage.output_tokens = 1000
        mock_client.messages.create.return_value = mock_resp

        gen = SourceFixGenerator(api_key="test-key")
        result = gen.generate_fix(
            SourceFixInput(
                detection_type="completion",
                detection_method="heuristic",
                detection_details={"issue": "wrong return"},
                confidence=80,
                file_path="utils.py",
                file_content="def foo():\n    return 1\n",
                language="python",
            )
        )

        assert isinstance(result, SourceFixOutput)
        assert result.file_path == "utils.py"
        assert result.language == "python"
        assert "return 2" in result.fixed_code
        assert "Changed return value" in result.explanation
        assert result.confidence == 0.9
        assert result.breaking_risk == "low"
        assert result.requires_testing is False  # low risk
        assert result.cost_usd > 0
        assert result.tokens_used == 6000
        assert result.model_used == _DEFAULT_MODEL
        assert len(result.unified_diff) > 0

    @patch("app.fixes.source_fix_generator.Anthropic")
    def test_requires_testing_for_high_risk(self, mock_cls):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_block = MagicMock()
        mock_block.type = "text"
        mock_block.text = """<fixed_code>new code</fixed_code>
<explanation>Major refactoring</explanation>
<root_cause>Architectural issue</root_cause>
<confidence>0.5</confidence>
<breaking_risk>high</breaking_risk>"""

        mock_resp = MagicMock()
        mock_resp.content = [mock_block]
        mock_resp.usage.input_tokens = 1000
        mock_resp.usage.output_tokens = 500
        mock_client.messages.create.return_value = mock_resp

        gen = SourceFixGenerator(api_key="test-key")
        result = gen.generate_fix(
            SourceFixInput(
                detection_type="corruption",
                detection_method="delta",
                detection_details={},
                confidence=90,
                file_path="state.py",
                file_content="original code",
                language="python",
            )
        )

        assert result.requires_testing is True  # high risk
        assert result.breaking_risk == "high"


class TestServiceInit:
    @patch("app.fixes.source_fix_generator.Anthropic")
    def test_uses_env_key(self, mock_cls, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key-123")
        gen = SourceFixGenerator()
        mock_cls.assert_called_once_with(api_key="env-key-123")

    def test_raises_without_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(ValueError, match="API key is required"):
            SourceFixGenerator()

    @patch("app.fixes.source_fix_generator.Anthropic")
    def test_accepts_explicit_key(self, mock_cls):
        gen = SourceFixGenerator(api_key="explicit-key")
        mock_cls.assert_called_once_with(api_key="explicit-key")


class TestDataModels:
    def test_source_fix_input_defaults(self):
        inp = SourceFixInput(
            detection_type="loop",
            detection_method="hash",
            detection_details={"key": "val"},
            confidence=80,
            file_path="test.py",
            file_content="code",
            language="python",
        )
        assert inp.root_cause_analysis is None
        assert inp.framework is None
        assert inp.related_files == []

    def test_source_fix_output_all_fields(self):
        out = SourceFixOutput(
            file_path="test.py",
            language="python",
            original_code="old",
            fixed_code="new",
            unified_diff="diff text",
            explanation="explanation",
            root_cause="root cause",
            confidence=0.85,
            breaking_risk="low",
            requires_testing=False,
            framework_specific=False,
            model_used="claude-sonnet-4-20250514",
            cost_usd=0.01,
            tokens_used=5000,
        )
        assert out.file_path == "test.py"
        assert out.confidence == 0.85


class TestSystemPrompt:
    def test_prompt_mentions_instructions(self):
        assert "Analyze the detection" in _SYSTEM_PROMPT
        assert "fixed_code" in _SYSTEM_PROMPT
        assert "explanation" in _SYSTEM_PROMPT
        assert "root_cause" in _SYSTEM_PROMPT
        assert "confidence" in _SYSTEM_PROMPT
        assert "breaking_risk" in _SYSTEM_PROMPT

    def test_prompt_mentions_fix_comments(self):
        assert "# FIX:" in _SYSTEM_PROMPT
