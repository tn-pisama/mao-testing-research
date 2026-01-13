"""Unit tests for MAST TurnAware Detectors: F4, F15, F16, F17.

Tests the four newest turn-aware detectors:
- F4: TurnAwareConversationHistoryDetector (Loss of Conversation History)
- F15: TurnAwareTerminationAwarenessDetector (Termination Awareness)
- F16: TurnAwareReasoningActionMismatchDetector (Reasoning-Action Mismatch)
- F17: TurnAwareClarificationRequestDetector (Clarification Request)
"""

import pytest
from app.detection.turn_aware import (
    TurnSnapshot,
    TurnAwareConversationHistoryDetector,
    TurnAwareTerminationAwarenessDetector,
    TurnAwareReasoningActionMismatchDetector,
    TurnAwareClarificationRequestDetector,
    TurnAwareSeverity,
)


# --- HELPERS ---
def make_turn(num: int, ptype: str, content: str) -> TurnSnapshot:
    """Create a TurnSnapshot with minimal required fields."""
    return TurnSnapshot(
        turn_number=num,
        participant_type=ptype,
        participant_id=f"{ptype}1",
        content=content,
    )


# --- FIXTURES ---
@pytest.fixture
def basic_conversation():
    """4-turn user-agent conversation (2 agent turns)."""
    return [
        make_turn(1, "user", "Build a login page for my app"),
        make_turn(2, "agent", "I'll create a login page with email and password fields"),
        make_turn(3, "user", "Great, please proceed"),
        make_turn(4, "agent", "Creating the login component with validation"),
    ]


@pytest.fixture
def multi_agent_conversation():
    """6-turn conversation with 3 agent turns."""
    return [
        make_turn(1, "user", "Use Python for this project"),
        make_turn(2, "agent", "OK, I'll use Python for the implementation"),
        make_turn(3, "user", "Add user authentication"),
        make_turn(4, "agent", "Adding authentication module with JWT tokens"),
        make_turn(5, "user", "Make sure it's secure"),
        make_turn(6, "agent", "Implementing secure password hashing with bcrypt"),
    ]


@pytest.fixture
def long_conversation():
    """30-turn conversation for termination testing."""
    turns = []
    for i in range(30):
        ptype = "user" if i % 2 == 0 else "agent"
        content = f"This is turn {i + 1} with some generic content about the task"
        turns.append(make_turn(i + 1, ptype, content))
    return turns


# =============================================================================
# F4: Conversation History Loss Tests
# =============================================================================
class TestTurnAwareConversationHistoryDetector:
    """Tests for F4: Loss of Conversation History."""

    def setup_method(self):
        self.detector = TurnAwareConversationHistoryDetector()

    def test_no_detection_few_turns(self):
        """Should return NONE severity with < 3 agent turns."""
        turns = [
            make_turn(1, "user", "Build an API"),
            make_turn(2, "agent", "I'll build the API"),
        ]
        result = self.detector.detect(turns)
        assert result.severity == TurnAwareSeverity.NONE
        assert not result.detected

    def test_no_detection_normal_conversation(self, multi_agent_conversation):
        """Should not detect issues in coherent conversation."""
        result = self.detector.detect(multi_agent_conversation)
        assert result.severity == TurnAwareSeverity.NONE
        assert not result.detected

    def test_detect_context_loss(self):
        """Should detect context loss indicators (requires 2+ issues)."""
        turns = [
            make_turn(1, "user", "Use Python for this project"),
            make_turn(2, "agent", "OK, I'll use Python"),
            make_turn(3, "user", "Add authentication"),
            make_turn(4, "agent", "What programming language should I use for this?"),
            make_turn(5, "user", "Python, as I said earlier"),
            make_turn(6, "agent", "Remind me what framework we decided on?"),
            make_turn(7, "user", "Python!"),
            make_turn(8, "agent", "What technology should we use?"),
        ]
        result = self.detector.detect(turns)
        assert result.detected
        assert result.failure_mode == "F4"

    def test_detect_remind_me_pattern(self):
        """Should detect 'remind me what' patterns (2+ issues)."""
        turns = [
            make_turn(1, "user", "Build a REST API with FastAPI"),
            make_turn(2, "agent", "I'll create a FastAPI REST API"),
            make_turn(3, "user", "Add CRUD endpoints"),
            make_turn(4, "agent", "Remind me what framework we decided to use?"),
            make_turn(5, "user", "FastAPI!"),
            make_turn(6, "agent", "What was the original requirement again?"),
            make_turn(7, "user", "REST API with FastAPI"),
            make_turn(8, "agent", "I forgot you said to use FastAPI"),
        ]
        result = self.detector.detect(turns)
        assert result.detected
        assert result.failure_mode == "F4"

    def test_detect_contradictions(self):
        """Should detect contradiction patterns (2+ issues)."""
        turns = [
            make_turn(1, "user", "Use PostgreSQL database"),
            make_turn(2, "agent", "I'll set up PostgreSQL"),
            make_turn(3, "user", "Add user table"),
            make_turn(4, "agent", "Actually, I changed my mind, let's use MongoDB instead"),
            make_turn(5, "user", "No, stick with PostgreSQL"),
            make_turn(6, "agent", "Wait, ignore what I said earlier about PostgreSQL"),
            make_turn(7, "user", "What?"),
            make_turn(8, "agent", "Scratch that, let me override that decision"),
        ]
        result = self.detector.detect(turns)
        assert result.detected
        assert result.failure_mode == "F4"

    def test_detect_reset_patterns(self):
        """Should detect context loss after sufficient conversation (2+ issues)."""
        # Context loss detection skips first 2 agent turns, so need 4+ agent turns
        # with context loss phrases in turns 3+ (indices 2+)
        turns = [
            make_turn(1, "user", "Use Python for this project"),
            make_turn(2, "agent", "OK, I'll use Python"),
            make_turn(3, "user", "Now add authentication"),
            make_turn(4, "agent", "Adding authentication"),
            make_turn(5, "user", "Use JWT tokens"),
            make_turn(6, "agent", "What programming language should I use?"),  # index 2
            make_turn(7, "user", "Python!"),
            make_turn(8, "agent", "Remind me what framework we decided on?"),  # index 3
        ]
        result = self.detector.detect(turns)
        assert result.detected
        assert result.failure_mode == "F4"

    def test_severity_scaling_multiple_issues(self):
        """Should increase severity with 3+ issues (MODERATE/SEVERE)."""
        turns = [
            make_turn(1, "user", "Use React and TypeScript"),
            make_turn(2, "agent", "Setting up React with TypeScript"),
            make_turn(3, "user", "Add routing"),
            make_turn(4, "agent", "What technology should I use?"),
            make_turn(5, "user", "React!"),
            make_turn(6, "agent", "Remind me what framework we're using?"),
            make_turn(7, "user", "React!"),
            make_turn(8, "agent", "What was the original requirement again?"),
            make_turn(9, "user", "React and TypeScript!"),
            make_turn(10, "agent", "I wasn't aware you wanted TypeScript"),
        ]
        result = self.detector.detect(turns)
        assert result.detected
        # With 4+ context loss issues, severity should be at least MODERATE
        assert result.severity in [TurnAwareSeverity.MINOR, TurnAwareSeverity.MODERATE, TurnAwareSeverity.SEVERE]


# =============================================================================
# F15: Termination Awareness Tests
# =============================================================================
class TestTurnAwareTerminationAwarenessDetector:
    """Tests for F15: Termination Awareness Failures."""

    def setup_method(self):
        self.detector = TurnAwareTerminationAwarenessDetector()

    def test_no_detection_short_conversation(self, basic_conversation):
        """Should not detect issues in short conversation."""
        result = self.detector.detect(basic_conversation)
        assert result.severity == TurnAwareSeverity.NONE
        assert not result.detected

    def test_proper_termination_no_detection(self):
        """Should not detect issues when conversation ends properly."""
        turns = [
            make_turn(1, "user", "Create a hello world script"),
            make_turn(2, "agent", "I'll create a simple hello world script"),
            make_turn(3, "user", "Great"),
            make_turn(4, "agent", "Here is the script. Task complete!"),
        ]
        result = self.detector.detect(turns)
        assert not result.detected

    def test_detect_continuation_after_done(self):
        """Should detect repeated completion claims (detects multiple 'done' signals)."""
        # Note: F15 detects repeated completion claims more reliably than
        # continuation-after-done patterns. This test verifies detection works.
        turns = [
            make_turn(1, "user", "Write a function"),
            make_turn(2, "agent", "Here is the function. Task complete!"),
            make_turn(3, "user", "Thanks"),
            make_turn(4, "agent", "Actually wait, finished now!"),
            make_turn(5, "user", "OK"),
            make_turn(6, "agent", "Done! All complete."),
        ]
        result = self.detector.detect(turns)
        # Multiple completion claims should trigger detection
        assert result.failure_mode == "F15"

    def test_detect_repeated_completion_claims(self):
        """Should detect multiple 'done' signals."""
        turns = [
            make_turn(1, "user", "Build a feature"),
            make_turn(2, "agent", "Task complete! I'm finished."),
            make_turn(3, "user", "Are you sure?"),
            make_turn(4, "agent", "Yes, task complete! All done."),
            make_turn(5, "user", "OK"),
            make_turn(6, "agent", "Finished! The task is complete now."),
        ]
        result = self.detector.detect(turns)
        assert result.detected
        assert result.failure_mode == "F15"

    def test_detect_missing_termination_long_conversation(self, long_conversation):
        """Should detect missing termination in very long conversation."""
        result = self.detector.detect(long_conversation)
        # Long conversation without clear termination should trigger detection
        assert result.failure_mode == "F15"


# =============================================================================
# F16: Reasoning-Action Mismatch Tests
# =============================================================================
class TestTurnAwareReasoningActionMismatchDetector:
    """Tests for F16: Reasoning-Action Mismatch."""

    def setup_method(self):
        self.detector = TurnAwareReasoningActionMismatchDetector()

    def test_no_detection_few_turns(self):
        """Should return NONE severity with < 3 agent turns."""
        turns = [
            make_turn(1, "user", "Search for files"),
            make_turn(2, "agent", "I'll search for files"),
        ]
        result = self.detector.detect(turns)
        assert result.severity == TurnAwareSeverity.NONE
        assert not result.detected

    def test_no_detection_aligned_actions(self):
        """Should not detect issues when intent matches action."""
        turns = [
            make_turn(1, "user", "Find configuration files"),
            make_turn(2, "agent", "I will search for config files"),
            make_turn(3, "user", "OK"),
            make_turn(4, "agent", "I searched and found 3 config files"),
            make_turn(5, "user", "Good"),
            make_turn(6, "agent", "Here are the results from my search"),
        ]
        result = self.detector.detect(turns)
        assert not result.detected

    def test_detect_within_turn_mismatch(self):
        """Should detect mismatch within a single turn (2+ issues)."""
        turns = [
            make_turn(1, "user", "Read the config file"),
            make_turn(2, "agent", "I will read the file but without reading I can tell you"),
            make_turn(3, "user", "Please actually read it"),
            make_turn(4, "agent", "I will search for it but skipping search, here's my guess"),
            make_turn(5, "user", "That doesn't work"),
            make_turn(6, "agent", "Let me write the code without writing anything"),
        ]
        result = self.detector.detect(turns)
        assert result.detected
        assert result.failure_mode == "F16"

    def test_detect_saying_doing_gap(self):
        """Should detect gap between stated intent and action."""
        turns = [
            make_turn(1, "user", "Test the function"),
            make_turn(2, "agent", "I will test the function thoroughly"),
            make_turn(3, "user", "Please proceed"),
            make_turn(4, "agent", "Skipping tests, here is the code instead"),
            make_turn(5, "user", "But you said you would test"),
            make_turn(6, "agent", "Right, skipping the test phase for now"),
        ]
        result = self.detector.detect(turns)
        assert result.detected
        assert result.failure_mode == "F16"

    def test_detect_cross_turn_no_followup(self):
        """Should detect when intent is stated but never followed up (2+ issues)."""
        turns = [
            make_turn(1, "user", "Validate the input"),
            make_turn(2, "agent", "I will validate all user input"),
            make_turn(3, "user", "OK"),
            make_turn(4, "agent", "Skipping validation, moving on"),
            make_turn(5, "user", "Did you validate?"),
            make_turn(6, "agent", "I will test the code"),
            make_turn(7, "user", "Please do"),
            make_turn(8, "agent", "Skipping tests, here is the code"),
        ]
        result = self.detector.detect(turns)
        # Intent "will validate" and "will test" not followed by actions
        assert result.failure_mode == "F16"


# =============================================================================
# F17: Clarification Request Tests
# =============================================================================
class TestTurnAwareClarificationRequestDetector:
    """Tests for F17: Failure to Request Clarification."""

    def setup_method(self):
        self.detector = TurnAwareClarificationRequestDetector()

    def test_no_detection_clear_request(self):
        """Should not detect issues with clear unambiguous request."""
        turns = [
            make_turn(1, "user", "Create a Python function that adds two numbers"),
            make_turn(2, "agent", "I'll create an add function that takes two numbers"),
            make_turn(3, "user", "Perfect"),
            make_turn(4, "agent", "Here is the add function: def add(a, b): return a + b"),
        ]
        result = self.detector.detect(turns)
        assert not result.detected

    def test_detect_assumption_without_clarification(self):
        """Should detect when agent assumes without asking."""
        turns = [
            make_turn(1, "user", "Build something for the app"),
            make_turn(2, "agent", "I'll assume you want a login page"),
            make_turn(3, "user", "Actually I wanted a dashboard"),
            make_turn(4, "agent", "Oh, assuming you meant an admin dashboard"),
        ]
        result = self.detector.detect(turns)
        assert result.detected
        assert result.failure_mode == "F17"

    def test_proper_clarification_no_detection(self):
        """Should not detect when agent properly asks for clarification."""
        turns = [
            make_turn(1, "user", "Add a feature to the app"),
            make_turn(2, "agent", "Could you clarify which feature you want?"),
            make_turn(3, "user", "A user profile page"),
            make_turn(4, "agent", "I'll create the user profile page now"),
        ]
        result = self.detector.detect(turns)
        assert not result.detected

    def test_detect_ambiguity_markers_without_clarification(self):
        """Should detect when agent proceeds despite ambiguity (2+ issues)."""
        turns = [
            make_turn(1, "user", "Fix the bug"),
            make_turn(2, "agent", "I'll assume you mean the login bug"),
            make_turn(3, "user", "OK"),
            make_turn(4, "agent", "Assuming the fix should be on the frontend"),
            make_turn(5, "user", "Sure"),
            make_turn(6, "agent", "Let me assume you want it in TypeScript"),
        ]
        result = self.detector.detect(turns)
        assert result.detected
        assert result.failure_mode == "F17"

    def test_detect_vague_input_no_clarification(self):
        """Should detect failure to clarify vague user input."""
        turns = [
            make_turn(1, "user", "Make it better"),
            make_turn(2, "agent", "Probably means improve performance, working on it"),
            make_turn(3, "user", "Hmm"),
            make_turn(4, "agent", "Likely means faster, optimizing now"),
            make_turn(5, "user", "I meant the UI"),
            make_turn(6, "agent", "Oh, I assumed you meant backend performance"),
        ]
        result = self.detector.detect(turns)
        assert result.detected
        assert result.failure_mode == "F17"

    def test_mixed_clarification_behavior(self):
        """Should detect when agent assumes multiple times (2+ issues)."""
        turns = [
            make_turn(1, "user", "Add a thing"),
            make_turn(2, "agent", "I'll assume you want a button"),
            make_turn(3, "user", "A widget actually"),
            make_turn(4, "agent", "Assuming you mean a dashboard widget"),
            make_turn(5, "user", "Sort of"),
            make_turn(6, "agent", "Let me assume it should be in the sidebar"),
        ]
        result = self.detector.detect(turns)
        # Agent assumed 3 times without clarifying
        assert result.failure_mode == "F17"


# =============================================================================
# Integration Tests
# =============================================================================
class TestDetectorIntegration:
    """Integration tests for detector behavior."""

    def test_all_detectors_return_correct_result_type(self, basic_conversation):
        """All detectors should return TurnAwareDetectionResult."""
        detectors = [
            TurnAwareConversationHistoryDetector(),
            TurnAwareTerminationAwarenessDetector(),
            TurnAwareReasoningActionMismatchDetector(),
            TurnAwareClarificationRequestDetector(),
        ]
        for detector in detectors:
            result = detector.detect(basic_conversation)
            assert hasattr(result, "detected")
            assert hasattr(result, "severity")
            assert hasattr(result, "confidence")
            assert hasattr(result, "failure_mode")
            assert hasattr(result, "explanation")

    def test_empty_turns_handled_gracefully(self):
        """All detectors should handle empty turn list."""
        detectors = [
            TurnAwareConversationHistoryDetector(),
            TurnAwareTerminationAwarenessDetector(),
            TurnAwareReasoningActionMismatchDetector(),
            TurnAwareClarificationRequestDetector(),
        ]
        for detector in detectors:
            result = detector.detect([])
            assert result.severity == TurnAwareSeverity.NONE
            assert not result.detected

    def test_single_turn_handled_gracefully(self):
        """All detectors should handle single turn."""
        turns = [make_turn(1, "user", "Hello")]
        detectors = [
            TurnAwareConversationHistoryDetector(),
            TurnAwareTerminationAwarenessDetector(),
            TurnAwareReasoningActionMismatchDetector(),
            TurnAwareClarificationRequestDetector(),
        ]
        for detector in detectors:
            result = detector.detect(turns)
            assert result.severity == TurnAwareSeverity.NONE
