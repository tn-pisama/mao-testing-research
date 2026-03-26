"""Tests for Delegation Quality Detector (F18)."""

import pytest
from app.detection.delegation import (
    DelegationQualityDetector,
    DelegationResult,
    DelegationSeverity,
    DelegationIssueType,
)


class TestDelegationQualityDetector:
    def setup_method(self):
        self.detector = DelegationQualityDetector()

    # --- Clear positives (should detect) ---

    def test_empty_instruction(self):
        result = self.detector.detect(delegator_instruction="")
        assert result.detected is True
        assert result.severity == DelegationSeverity.SEVERE
        assert result.primary_issue == DelegationIssueType.VAGUE_INSTRUCTION

    def test_vague_instruction_handle_this(self):
        result = self.detector.detect(delegator_instruction="Handle this")
        assert result.detected is True
        assert result.specificity_score < 0.40

    def test_vague_instruction_take_over(self):
        result = self.detector.detect(
            delegator_instruction="Take over the project"
        )
        assert result.detected is True

    def test_vague_instruction_figure_it_out(self):
        result = self.detector.detect(
            delegator_instruction="Figure it out and get it done"
        )
        assert result.detected is True
        assert any(
            i.issue_type == DelegationIssueType.VAGUE_INSTRUCTION
            for i in result.issues
        )

    def test_missing_criteria_and_context(self):
        result = self.detector.detect(
            delegator_instruction="Fix the customer onboarding flow",
        )
        assert result.detected is True
        assert any(
            i.issue_type == DelegationIssueType.MISSING_SUCCESS_CRITERIA
            for i in result.issues
        )

    def test_no_bounds_at_all(self):
        result = self.detector.detect(
            delegator_instruction="Build a new API endpoint for user profiles",
        )
        assert result.bounds_score < 0.25

    # --- Clear negatives (should NOT detect) ---

    def test_well_specified_delegation(self):
        result = self.detector.detect(
            delegator_instruction=(
                "Implement a REST endpoint POST /api/v1/users that accepts "
                "JSON with fields name (string, required) and email (string, required). "
                "Return 201 on success with the created user object. "
                "Use the existing UserService.create() method. "
                "Must include input validation and return 400 for invalid payloads."
            ),
            success_criteria=(
                "Done when: all 5 unit tests pass, endpoint returns 201 for valid input "
                "and 400 for missing name or invalid email format."
            ),
            task_context=(
                "We're building the user management API. The UserService class is in "
                "backend/app/services/user.py. The database schema already has a users table. "
                "This is part of the Phase 2 milestone, due by 2026-04-01."
            ),
        )
        assert result.detected is False
        assert result.specificity_score > 0.40
        assert result.criteria_score > 0.30

    def test_informal_but_complete(self):
        """Informal language with all necessary elements should not trigger."""
        result = self.detector.detect(
            delegator_instruction=(
                "Hey, can you add a search function to the ProductCatalog page? "
                "It should filter products by name and category using the existing "
                "ProductService.search() method. Don't touch the checkout flow."
            ),
            success_criteria=(
                "Should return at least 3 matching results for 'laptop' query. "
                "Search takes less than 200ms on the test dataset."
            ),
            task_context=(
                "ProductCatalog is in frontend/src/app/catalog/page.tsx. "
                "ProductService already has a search endpoint at GET /api/products?q=. "
                "Budget: max 4 hours of work."
            ),
        )
        assert result.detected is False

    def test_self_contained_long_instruction(self):
        """A long, detailed instruction without separate fields should score well."""
        result = self.detector.detect(
            delegator_instruction=(
                "Create a Python function called validate_email that takes a string "
                "and returns True if it's a valid email format. Use regex, not external "
                "libraries. Must handle edge cases: no @, multiple @, missing domain, "
                "missing TLD. Write 10 unit tests covering these cases. The function "
                "should return False for any input longer than 254 characters. "
                "Complete this within 2 hours, budget max $5 in API costs."
            ),
        )
        assert result.specificity_score > 0.50
        assert result.bounds_score > 0.0

    # --- Dimension-specific tests ---

    def test_specificity_scoring_short_vague(self):
        score = self.detector._score_specificity("Do the thing")
        assert score < 0.30

    def test_specificity_scoring_detailed(self):
        score = self.detector._score_specificity(
            "Create a function called parse_csv that reads a CSV file using pandas "
            "and returns a DataFrame with columns id, name, and email"
        )
        assert score > 0.50

    def test_criteria_explicit_field(self):
        score = self.detector._score_criteria(
            "Build a search endpoint",
            success_criteria="Done when search returns results in under 100ms and tests pass",
        )
        assert score >= 0.30

    def test_criteria_embedded_in_instruction(self):
        score = self.detector._score_criteria(
            "Build a search endpoint that must return at least 10 results for common queries",
            success_criteria="",
        )
        assert score > 0.0

    def test_criteria_missing_entirely(self):
        score = self.detector._score_criteria(
            "Fix the bug",
            success_criteria="",
        )
        assert score < 0.30

    def test_context_with_entities(self):
        score = self.detector._score_context(
            "Update the UserService to handle the new ProfileSchema",
            "UserService is in backend/services/user.py. ProfileSchema was added in PR #42.",
        )
        assert score > 0.30

    def test_context_missing(self):
        score = self.detector._score_context(
            "Update the UserService to handle the new ProfileSchema",
            "",
        )
        assert score < 0.35

    def test_bounds_with_deadline(self):
        score = self.detector._score_bounds("Complete by Friday, budget $100, scoped to the API layer only")
        assert score > 0.40

    def test_bounds_none(self):
        score = self.detector._score_bounds("Build a new feature")
        assert score == 0.0

    def test_capability_mismatch(self):
        result = self.detector.detect(
            delegator_instruction="Deploy the service to production and delete the old database",
            delegatee_capabilities="Can read and write code, execute tests, create files",
        )
        cap_issues = [
            i for i in result.issues
            if i.issue_type == DelegationIssueType.CAPABILITY_MISMATCH
        ]
        assert len(cap_issues) > 0

    # --- Result structure ---

    def test_result_has_all_fields(self):
        result = self.detector.detect(delegator_instruction="Do something")
        assert isinstance(result, DelegationResult)
        assert isinstance(result.detected, bool)
        assert isinstance(result.confidence, float)
        assert 0.0 <= result.confidence <= 1.0
        assert isinstance(result.specificity_score, float)
        assert isinstance(result.criteria_score, float)
        assert isinstance(result.context_score, float)
        assert isinstance(result.bounds_score, float)
        assert isinstance(result.explanation, str)

    def test_confidence_range(self):
        """Confidence should be between 0 and 1."""
        for instruction in ["", "Handle this", "Do something", "Build a REST API endpoint POST /users"]:
            result = self.detector.detect(delegator_instruction=instruction)
            assert 0.0 <= result.confidence <= 1.0, f"Confidence out of range for: {instruction}"

    def test_suggested_fix_when_detected(self):
        result = self.detector.detect(delegator_instruction="Handle this")
        assert result.detected is True
        assert result.suggested_fix is not None
        assert len(result.suggested_fix) > 0

    def test_no_suggested_fix_when_not_detected(self):
        result = self.detector.detect(
            delegator_instruction=(
                "Implement POST /api/v1/users with name and email fields. "
                "Return 201 on success. Must validate input. Budget: $10, deadline: Friday."
            ),
            success_criteria="All 5 tests pass, endpoint returns correct status codes.",
            task_context="UserService is in backend/services/. Schema in models/user.py.",
        )
        if not result.detected:
            assert result.suggested_fix is None
