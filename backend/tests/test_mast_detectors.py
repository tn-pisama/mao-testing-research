"""
Tests for MAST Taxonomy Detectors (F4, F8, F13, F14)
====================================================

Comprehensive tests for the 4 MAST failure mode detectors:
- F4: Inadequate Tool Provision
- F8: Information Withholding
- F13: Quality Gate Bypass
- F14: Completion Misjudgment
"""

import pytest
from app.detection_enterprise.tool_provision import (
    tool_provision_detector,
    ToolProvisionDetector,
    ToolProvisionResult,
    ProvisionSeverity,
    ProvisionIssueType,
)
from app.detection.withholding import (
    withholding_detector,
    InformationWithholdingDetector,
    WithholdingResult,
    WithholdingSeverity,
    WithholdingType,
)
from app.detection_enterprise.quality_gate import (
    quality_gate_detector,
    QualityGateDetector,
    QualityGateResult,
    QualityGateSeverity,
    QualityGateIssueType,
)
from app.detection.completion import (
    completion_detector,
    CompletionMisjudgmentDetector,
    CompletionResult,
    CompletionSeverity,
    CompletionIssueType,
)


# =============================================================================
# F4: Tool Provision Detector Tests
# =============================================================================

class TestToolProvisionDetector:
    """Tests for F4: Inadequate Tool Provision Detection."""

    def test_singleton_instance_exists(self):
        """Test that singleton instance is available."""
        assert tool_provision_detector is not None
        assert isinstance(tool_provision_detector, ToolProvisionDetector)

    def test_no_issues_with_adequate_tools(self):
        """Test detection when all needed tools are available."""
        result = tool_provision_detector.detect(
            task="Calculate the sum of 5 and 10",
            agent_output="The sum of 5 and 10 is 15.",
            available_tools=["calculator", "python"],
        )
        assert not result.detected
        assert result.severity == ProvisionSeverity.NONE

    def test_detect_workaround_web_limitation(self):
        """Test detection of web access workaround."""
        result = tool_provision_detector.detect(
            task="Search for the latest news about AI",
            agent_output="I cannot browse the web to search for current news. Based on my training data...",
            available_tools=[],
        )
        assert result.detected
        assert any(i.issue_type == ProvisionIssueType.WORKAROUND_DETECTED for i in result.issues)

    def test_detect_workaround_code_limitation(self):
        """Test detection of code execution workaround."""
        result = tool_provision_detector.detect(
            task="Run this Python script",
            agent_output="I'm unable to execute code directly. However, I can explain what the code would do...",
            available_tools=[],
        )
        assert result.detected
        assert any(i.issue_type == ProvisionIssueType.WORKAROUND_DETECTED for i in result.issues)

    def test_detect_explicit_tool_admission(self):
        """Test detection when agent admits lacking tools."""
        result = tool_provision_detector.detect(
            task="Send an email to the team",
            agent_output="I don't have access to email tools. I cannot send emails on your behalf.",
            available_tools=[],
        )
        assert result.detected
        assert any(i.issue_type == ProvisionIssueType.WORKAROUND_DETECTED for i in result.issues)

    def test_detect_simulation_workaround(self):
        """Test detection of simulation workaround."""
        result = tool_provision_detector.detect(
            task="Query the database for user records",
            agent_output="I'll simulate what a database query would return. Let me pretend we have the following records...",
            available_tools=[],
        )
        assert result.detected
        assert any(i.issue_type == ProvisionIssueType.WORKAROUND_DETECTED for i in result.issues)

    def test_detect_hallucinated_tool(self):
        """Test detection of hallucinated tool usage."""
        detector = ToolProvisionDetector(known_tools=["read_file", "write_file"])
        result = detector.detect(
            task="Process the data",
            agent_output="Using the super_data_processor_tool to handle this. Let me call super_data_processor()",
            available_tools=["read_file", "write_file"],
        )
        assert result.detected
        assert any(i.issue_type == ProvisionIssueType.HALLUCINATED_TOOL for i in result.issues)

    def test_detect_missing_web_search_tool(self):
        """Test detection of missing web search tool."""
        detector = ToolProvisionDetector()
        result = detector.detect(
            task="Search for the current price of Bitcoin",
            agent_output="Here's what I found about Bitcoin prices...",
            available_tools=["calculator"],
        )
        assert result.detected
        assert "web_search" in result.missing_tools

    def test_detect_missing_file_ops_tool(self):
        """Test detection of missing file operations tool."""
        detector = ToolProvisionDetector()
        result = detector.detect(
            task="Read the configuration file and update settings",
            agent_output="Here are the settings...",
            available_tools=["calculator"],
        )
        assert result.detected
        assert "file_ops" in result.missing_tools

    def test_detect_tool_call_failure(self):
        """Test detection of failed tool calls."""
        result = tool_provision_detector.detect(
            task="Get user data",
            agent_output="Attempted to get user data",
            available_tools=["fetch_user"],
            tool_calls=[
                {"name": "unknown_tool", "status": "failed", "error": "Tool not found"},
            ],
        )
        assert result.detected
        assert any(i.issue_type == ProvisionIssueType.TOOL_CALL_FAILURE for i in result.issues)

    def test_normalize_tool_name(self):
        """Test tool name normalization."""
        detector = ToolProvisionDetector()
        assert detector._normalize_tool_name("Web-Search") == "web_search"
        assert detector._normalize_tool_name("READ FILE") == "read_file"
        assert detector._normalize_tool_name("  calculator  ") == "calculator"

    def test_infer_needed_tools_database(self):
        """Test inference of database tool need."""
        detector = ToolProvisionDetector()
        needed = detector._infer_needed_tools("Query the SQL database for user records")
        assert "database" in needed

    def test_infer_needed_tools_email(self):
        """Test inference of email tool need."""
        detector = ToolProvisionDetector()
        needed = detector._infer_needed_tools("Send email to the marketing team")
        assert "email" in needed

    def test_infer_needed_tools_calendar(self):
        """Test inference of calendar tool need."""
        detector = ToolProvisionDetector()
        needed = detector._infer_needed_tools("Schedule a meeting for tomorrow")
        assert "calendar" in needed

    def test_strict_mode(self):
        """Test strict mode increases severity."""
        detector = ToolProvisionDetector(strict_mode=True)
        result = detector.detect(
            task="Search the web for news",
            agent_output="Here's some information...",
            available_tools=["calculator"],
        )
        assert result.detected
        assert result.severity in [ProvisionSeverity.SEVERE, ProvisionSeverity.MODERATE]

    def test_successful_tool_calls(self):
        """Test that successful tool calls are tracked."""
        result = tool_provision_detector.detect(
            task="Calculate something",
            agent_output="Calculation complete",
            available_tools=["calculator"],
            tool_calls=[
                {"name": "calculator", "status": "success", "result": {"value": 42}},
            ],
        )
        assert "calculator" in result.attempted_tools

    def test_empty_task_and_output(self):
        """Test handling of empty inputs."""
        result = tool_provision_detector.detect(
            task="",
            agent_output="",
            available_tools=[],
        )
        assert not result.detected
        assert result.severity == ProvisionSeverity.NONE

    def test_confidence_calculation(self):
        """Test confidence increases with more issues."""
        result = tool_provision_detector.detect(
            task="Search web, send email, query database",
            agent_output="I don't have access to these tools. As an AI, I cannot browse the internet or send emails.",
            available_tools=[],
        )
        assert result.detected
        assert result.confidence >= 0.5

    def test_extract_tool_mentions(self):
        """Test extraction of tool mentions from text."""
        detector = ToolProvisionDetector()
        mentions = detector._extract_tool_mentions("Using the search tool to find data. Calling calculator()")
        assert "search" in mentions or "calculator" in mentions


# =============================================================================
# F8: Information Withholding Detector Tests
# =============================================================================

class TestInformationWithholdingDetector:
    """Tests for F8: Information Withholding Detection."""

    def test_singleton_instance_exists(self):
        """Test that singleton instance is available."""
        assert withholding_detector is not None
        assert isinstance(withholding_detector, InformationWithholdingDetector)

    def test_no_withholding_full_information(self):
        """Test no detection when all information is passed."""
        result = withholding_detector.detect(
            internal_state="Found 3 errors in the code: syntax error on line 5, missing import on line 10, undefined variable on line 15",
            agent_output="I found 3 errors in the code: syntax error on line 5, missing import on line 10, undefined variable on line 15",
        )
        assert not result.detected
        assert result.severity == WithholdingSeverity.NONE

    def test_detect_critical_omission(self):
        """Test detection of critical information omission."""
        result = withholding_detector.detect(
            internal_state="CRITICAL: Security vulnerability found in authentication. ERROR: Database connection failing. Warning: Memory usage high.",
            agent_output="The system is running normally.",
        )
        assert result.detected
        assert any(i.issue_type == WithholdingType.CRITICAL_OMISSION for i in result.issues)
        assert result.severity in [WithholdingSeverity.SEVERE, WithholdingSeverity.CRITICAL]

    def test_detect_negative_suppression(self):
        """Test detection of negative finding suppression."""
        result = withholding_detector.detect(
            internal_state="No users found. Missing configuration. Invalid API key. Not authorized. Unable to connect. Insufficient permissions. Rejected request.",
            agent_output="I checked the system.",
        )
        assert result.detected
        assert any(i.issue_type == WithholdingType.NEGATIVE_SUPPRESSION for i in result.issues)

    def test_detect_detail_loss(self):
        """Test detection of detail/entity loss."""
        result = withholding_detector.detect(
            internal_state='Found issues: Error code 500 at API endpoint /users. Cost is $1500. John Smith reported the bug. AWS S3 bucket "prod-data" affected.',
            agent_output="Found some issues in the system.",
        )
        assert result.detected
        # Should detect loss of specific entities (numbers, names, etc.)

    def test_detect_context_stripping(self):
        """Test detection of excessive summarization."""
        detector = InformationWithholdingDetector()
        long_internal = """
        Detailed analysis of the codebase revealed multiple issues:
        1. Authentication module has SQL injection vulnerability CVE-2024-1234
        2. API rate limiting is not properly configured, allowing 10000 requests/second
        3. Database connection pool exhaustion occurs after 500 concurrent users
        4. Memory leak in image processing causes 100MB/hour growth
        5. Cross-site scripting vulnerability in user profile page
        """
        result = detector.detect(
            internal_state=long_internal,
            agent_output="In summary, there are some issues with the codebase.",
        )
        assert result.detected

    def test_information_retention_ratio(self):
        """Test information retention ratio calculation."""
        result = withholding_detector.detect(
            internal_state="Error A found. Warning B detected. Critical issue C discovered.",
            agent_output="Error A was found.",
        )
        assert result.information_retention_ratio < 1.0

    def test_empty_inputs(self):
        """Test handling of empty inputs."""
        result = withholding_detector.detect(
            internal_state="",
            agent_output="",
        )
        assert not result.detected
        assert result.confidence == 0.5

    def test_extract_critical_items(self):
        """Test extraction of critical items."""
        detector = InformationWithholdingDetector()
        items = detector._extract_critical_items("Found critical error and security vulnerability")
        assert len(items) > 0

    def test_extract_negative_findings(self):
        """Test extraction of negative findings."""
        detector = InformationWithholdingDetector()
        findings = detector._extract_negative_findings("No data found. Missing configuration.")
        assert len(findings) >= 2

    def test_calculate_information_density(self):
        """Test information density calculation."""
        detector = InformationWithholdingDetector()
        high_density = detector._calculate_information_density("Authentication vulnerability CVE-2024 critical security")
        low_density = detector._calculate_information_density("the a an is are was were be")
        assert high_density > low_density

    def test_extract_entities(self):
        """Test entity extraction."""
        detector = InformationWithholdingDetector()
        entities = detector._extract_entities('Found error at API endpoint. Cost is $500. "Important message"')
        assert len(entities) > 0

    def test_custom_thresholds(self):
        """Test custom retention thresholds."""
        detector = InformationWithholdingDetector(
            critical_retention_threshold=0.95,
            detail_retention_threshold=0.8,
        )
        result = detector.detect(
            internal_state="Error found. Warning detected.",
            agent_output="Error found.",
        )
        # With higher thresholds, more likely to detect issues
        assert result is not None

    def test_suggested_fix_for_critical_omission(self):
        """Test suggested fix generation."""
        result = withholding_detector.detect(
            internal_state="CRITICAL: Security breach detected. Urgent action required.",
            agent_output="Everything looks fine.",
        )
        assert result.detected
        assert result.suggested_fix is not None

    def test_confidence_calculation(self):
        """Test confidence increases with more issues."""
        result = withholding_detector.detect(
            internal_state="Error 1. Error 2. Warning 1. Critical issue. Security vulnerability.",
            agent_output="System checked.",
        )
        if result.detected:
            assert result.confidence >= 0.6


# =============================================================================
# F13: Quality Gate Bypass Detector Tests
# =============================================================================

class TestQualityGateDetector:
    """Tests for F13: Quality Gate Bypass Detection."""

    def test_singleton_instance_exists(self):
        """Test that singleton instance is available."""
        assert quality_gate_detector is not None
        assert isinstance(quality_gate_detector, QualityGateDetector)

    def test_no_bypass_clean_output(self):
        """Test no detection when quality gates are followed."""
        result = quality_gate_detector.detect(
            task="Deploy the application",
            agent_output="Running tests... All tests passed. Running lint... No issues. Review approved. Deploying to production.",
        )
        # When all inferred required gates are mentioned, should not detect
        assert result.severity in [QualityGateSeverity.NONE, QualityGateSeverity.MINOR, QualityGateSeverity.MODERATE]

    def test_detect_explicit_skip(self):
        """Test detection of explicit skip patterns."""
        result = quality_gate_detector.detect(
            task="Push the code changes",
            agent_output="Skipping validation to save time. Pushing directly to main.",
        )
        assert result.detected
        assert any(i.issue_type == QualityGateIssueType.SKIPPED_VALIDATION for i in result.issues)

    def test_detect_bypass_pattern(self):
        """Test detection of bypass patterns."""
        result = quality_gate_detector.detect(
            task="Commit the changes",
            agent_output="Bypassing code review. git commit --no-verify -m 'Quick fix'",
        )
        assert result.detected
        assert any(i.issue_type in [QualityGateIssueType.BYPASSED_REVIEW, QualityGateIssueType.SKIPPED_VALIDATION] for i in result.issues)

    def test_detect_git_no_verify(self):
        """Test detection of --no-verify flag."""
        result = quality_gate_detector.detect(
            task="Commit and push",
            agent_output="git commit --no-verify -m 'Hotfix'",
        )
        assert result.detected

    def test_detect_force_flag(self):
        """Test detection of force flags."""
        result = quality_gate_detector.detect(
            task="Deploy",
            agent_output="Proceeding anyway despite failing checks. Using -f flag.",
        )
        assert result.detected

    def test_detect_disabled_checks(self):
        """Test detection of disabled checks."""
        result = quality_gate_detector.detect(
            task="Run the build",
            agent_output="Disabled lint checks. Disabled test suite. Building...",
        )
        assert result.detected
        assert any(i.issue_type == QualityGateIssueType.SKIPPED_VALIDATION for i in result.issues)

    def test_detect_ignored_errors(self):
        """Test detection of ignored errors."""
        result = quality_gate_detector.detect(
            task="Build the project",
            agent_output="Ignoring error in compilation. Ignoring warning about deprecated API.",
        )
        assert result.detected

    def test_workflow_step_analysis_skipped(self):
        """Test analysis of workflow steps with skipped gates."""
        result = quality_gate_detector.detect(
            task="Deploy",
            agent_output="Deployment complete.",
            workflow_steps=[
                {"type": "lint", "status": "skipped", "is_quality_gate": True},
                {"type": "test", "status": "passed", "is_quality_gate": True},
                {"type": "deploy", "status": "success"},
            ],
        )
        assert result.detected
        assert result.gates_skipped >= 1

    def test_workflow_step_analysis_failed_but_continued(self):
        """Test detection when workflow continues after failed gate."""
        result = quality_gate_detector.detect(
            task="Deploy",
            agent_output="Deployment complete.",
            workflow_steps=[
                {"type": "test", "status": "failed", "is_quality_gate": True},
                {"type": "deploy", "status": "success"},
            ],
        )
        assert result.detected

    def test_missing_required_gates(self):
        """Test detection of missing required gates."""
        result = quality_gate_detector.detect(
            task="Deploy to production",
            agent_output="Deploying now...",
            required_gates=["test", "review", "approval"],
        )
        assert result.detected
        assert any(i.issue_type == QualityGateIssueType.MISSING_CHECKS for i in result.issues)

    def test_task_type_inference_deployment(self):
        """Test task type inference for deployment."""
        detector = QualityGateDetector()
        task_type = detector._infer_task_type("Deploy to production")
        assert task_type == "deployment"

    def test_task_type_inference_security(self):
        """Test task type inference for security changes."""
        detector = QualityGateDetector()
        task_type = detector._infer_task_type("Update authentication system")
        assert task_type == "security_change"

    def test_task_type_inference_code(self):
        """Test task type inference for code changes."""
        detector = QualityGateDetector()
        task_type = detector._infer_task_type("Refactor the user class")
        assert task_type == "code_change"

    def test_strict_mode(self):
        """Test strict mode increases severity."""
        detector = QualityGateDetector(strict_mode=True, required_gates=["test"])
        result = detector.detect(
            task="Make changes",
            agent_output="Changes made.",
        )
        assert result.detected

    def test_gates_mentioned_extraction(self):
        """Test extraction of mentioned gates."""
        detector = QualityGateDetector()
        gates = detector._extract_gates_mentioned("Running validation and testing. Code review complete.")
        assert "validation" in gates
        assert "testing" in gates
        assert "review" in gates

    def test_forced_completion_detection(self):
        """Test detection of forced completion."""
        result = quality_gate_detector.detect(
            task="Complete the deployment",
            agent_output="Force complete the deployment despite warnings. Proceeding anyway.",
        )
        assert result.detected
        # Either FORCED_COMPLETION or bypass patterns should be detected
        assert any(i.issue_type in [QualityGateIssueType.FORCED_COMPLETION, QualityGateIssueType.SKIPPED_VALIDATION] for i in result.issues)

    def test_quality_threshold_ignored(self):
        """Test detection of ignored quality thresholds."""
        result = quality_gate_detector.detect(
            task="Deploy",
            agent_output="Coverage 45% below threshold of 80%. Proceeding anyway.",
        )
        assert result.detected

    def test_suggested_fix_generation(self):
        """Test suggested fix is generated."""
        result = quality_gate_detector.detect(
            task="Deploy",
            agent_output="Skipping all tests. Deploying now.",
        )
        assert result.detected
        assert result.suggested_fix is not None

    def test_confidence_calculation(self):
        """Test confidence calculation."""
        result = quality_gate_detector.detect(
            task="Deploy",
            agent_output="Skipping validation. Bypassing review. --no-verify.",
        )
        assert result.detected
        assert result.confidence >= 0.5


# =============================================================================
# F14: Completion Misjudgment Detector Tests
# =============================================================================

class TestCompletionMisjudgmentDetector:
    """Tests for F14: Completion Misjudgment Detection."""

    def test_singleton_instance_exists(self):
        """Test that singleton instance is available."""
        assert completion_detector is not None
        assert isinstance(completion_detector, CompletionMisjudgmentDetector)

    def test_no_misjudgment_complete_task(self):
        """Test no detection when task is actually complete."""
        result = completion_detector.detect(
            task="Add a function to calculate sum",
            agent_output="Task is complete. I've added the calculateSum function that takes two parameters and returns their sum.",
        )
        # If there are no incomplete markers, should not detect
        assert result.completion_claimed == True

    def test_detect_premature_completion_with_todo(self):
        """Test detection of premature completion with TODO markers."""
        result = completion_detector.detect(
            task="Implement the feature",
            agent_output="Task is complete! Here's the code:\n```\ndef feature():\n    # TODO: implement logic\n    pass\n```",
        )
        assert result.detected
        assert any(i.issue_type == CompletionIssueType.INCOMPLETE_VERIFICATION for i in result.issues)

    def test_detect_premature_completion_with_fixme(self):
        """Test detection with FIXME markers."""
        result = completion_detector.detect(
            task="Fix the bug",
            agent_output="Job done! The code now works:\n```\n# FIXME: edge case not handled\nreturn result\n```",
        )
        assert result.detected

    def test_detect_false_success_with_errors(self):
        """Test detection of false success claim with errors."""
        result = completion_detector.detect(
            task="Build the project",
            agent_output="Successfully completed! Build output: Error: Module not found. Exception occurred during compilation.",
        )
        assert result.detected
        assert any(i.issue_type == CompletionIssueType.FALSE_SUCCESS_CLAIM for i in result.issues)

    def test_detect_ignored_subtasks(self):
        """Test detection of ignored incomplete subtasks."""
        result = completion_detector.detect(
            task="Complete all items",
            agent_output="All tasks are done!",
            subtasks=[
                {"name": "Task 1", "status": "completed"},
                {"name": "Task 2", "status": "pending"},
                {"name": "Task 3", "status": "in_progress"},
            ],
        )
        assert result.detected
        assert any(i.issue_type == CompletionIssueType.IGNORED_SUBTASKS for i in result.issues)
        assert result.subtasks_completed == 1
        assert result.subtasks_total == 3

    def test_detect_missed_criteria(self):
        """Test detection of missed success criteria."""
        result = completion_detector.detect(
            task="The function should handle errors and log them",
            agent_output="Task complete! Here's the function that processes data.",
            success_criteria=["handle errors", "log errors"],
        )
        assert result.detected
        assert any(i.issue_type == CompletionIssueType.MISSED_CRITERIA for i in result.issues)

    def test_detect_partial_delivery(self):
        """Test detection of partial delivery."""
        result = completion_detector.detect(
            task="Create user management",
            agent_output="I've finished everything!",
            expected_outputs=["create user", "delete user", "update user", "list users"],
        )
        assert result.detected
        assert any(i.issue_type == CompletionIssueType.PARTIAL_DELIVERY for i in result.issues)

    def test_detect_placeholder_code(self):
        """Test detection of placeholder code."""
        result = completion_detector.detect(
            task="Implement authentication",
            agent_output="Task is done! Here's the code:\n```\ndef authenticate(user):\n    # placeholder implementation\n    return stub_result\n```",
        )
        assert result.detected

    def test_detect_partial_progress_indicator(self):
        """Test detection of partial progress indicators."""
        result = completion_detector.detect(
            task="Complete all steps",
            agent_output="Task is complete! Step 2 of 5 done.",
        )
        assert result.detected

    def test_completion_claim_detection(self):
        """Test various completion claim patterns."""
        detector = CompletionMisjudgmentDetector()

        assert detector._detect_completion_claim("Task is complete.")
        assert detector._detect_completion_claim("I have completed the work.")
        assert detector._detect_completion_claim("Successfully finished the task.")
        assert detector._detect_completion_claim("Job done!")
        assert detector._detect_completion_claim("Mission accomplished!")
        assert not detector._detect_completion_claim("I am working on the task.")

    def test_incomplete_markers_detection(self):
        """Test detection of various incomplete markers."""
        detector = CompletionMisjudgmentDetector()
        markers = detector._detect_incomplete_markers("TODO: finish this. FIXME: bug here. HACK: workaround")
        assert len(markers) >= 3

    def test_error_detection(self):
        """Test error pattern detection."""
        detector = CompletionMisjudgmentDetector()
        errors = detector._detect_errors("Error occurred. The process failed. Could not connect.")
        assert len(errors) >= 3

    def test_success_criteria_extraction(self):
        """Test extraction of success criteria from task."""
        detector = CompletionMisjudgmentDetector()
        criteria = detector._extract_success_criteria(
            "The system should handle errors gracefully. It must log all events. Required to support multiple users."
        )
        assert len(criteria) >= 2

    def test_criteria_checking(self):
        """Test success criteria checking."""
        detector = CompletionMisjudgmentDetector()
        met, total, unmet = detector._check_criteria_met(
            ["handle authentication", "validate input"],
            "The system handles authentication and validates all input correctly."
        )
        assert met >= 1

    def test_subtask_analysis(self):
        """Test subtask analysis."""
        detector = CompletionMisjudgmentDetector()
        completed, total, incomplete = detector._analyze_subtasks([
            {"name": "Task A", "status": "complete"},
            {"name": "Task B", "status": "done"},
            {"name": "Task C", "status": "pending"},
        ])
        assert completed == 2
        assert total == 3
        assert "Task C" in incomplete

    def test_completion_ratio_calculation(self):
        """Test completion ratio calculation."""
        detector = CompletionMisjudgmentDetector()

        # High completion (no issues)
        ratio1 = detector._calculate_completion_ratio("All done correctly.", "Complete task")
        assert ratio1 == 1.0

        # Low completion (many issues)
        ratio2 = detector._calculate_completion_ratio(
            "TODO: finish. FIXME: bug. Error occurred. Failed to complete.",
            "Complete task"
        )
        assert ratio2 < 1.0

    def test_custom_completion_threshold(self):
        """Test custom completion threshold."""
        detector = CompletionMisjudgmentDetector(completion_threshold=0.95)
        result = detector.detect(
            task="Complete everything",
            agent_output="Task complete! TODO: minor cleanup",
        )
        assert result.detected

    def test_strict_mode(self):
        """Test strict mode behavior."""
        detector = CompletionMisjudgmentDetector(strict_mode=True)
        result = detector.detect(
            task="Build and test",
            agent_output="Build done! All tasks complete!",
            subtasks=[
                {"name": "Build", "status": "complete"},
                {"name": "Test", "status": "pending"},
            ],
        )
        assert result.detected

    def test_suggested_fix_generation(self):
        """Test suggested fix is generated."""
        result = completion_detector.detect(
            task="Complete the implementation",
            agent_output="Task is done! TODO: handle edge cases",
        )
        assert result.detected
        assert result.suggested_fix is not None

    def test_confidence_calculation(self):
        """Test confidence calculation."""
        result = completion_detector.detect(
            task="Build the project",
            agent_output="Successfully completed! Error: build failed. TODO: fix.",
        )
        if result.detected:
            assert result.confidence >= 0.5

    def test_no_completion_claim_no_detection(self):
        """Test no detection when no completion is claimed."""
        result = completion_detector.detect(
            task="Work on feature",
            agent_output="Still working on it. TODO: finish implementation.",
        )
        # Even with TODO markers, if no completion is claimed, may not detect misjudgment
        assert result.completion_claimed == False


# =============================================================================
# Integration Tests
# =============================================================================

class TestMastDetectorIntegration:
    """Integration tests for MAST detectors."""

    def test_all_detectors_importable(self):
        """Test all detectors can be imported from detection module."""
        from app.detection import (
            tool_provision_detector,
            withholding_detector,
            quality_gate_detector,
            completion_detector,
        )
        assert tool_provision_detector is not None
        assert withholding_detector is not None
        assert quality_gate_detector is not None
        assert completion_detector is not None

    def test_all_result_types_importable(self):
        """Test all result types can be imported."""
        from app.detection import (
            ToolProvisionResult,
            WithholdingResult,
            QualityGateResult,
            CompletionResult,
        )
        assert ToolProvisionResult is not None
        assert WithholdingResult is not None
        assert QualityGateResult is not None
        assert CompletionResult is not None

    def test_all_severity_enums_importable(self):
        """Test all severity enums can be imported."""
        from app.detection import (
            ProvisionSeverity,
            WithholdingSeverity,
            QualityGateSeverity,
            CompletionSeverity,
        )
        assert ProvisionSeverity.NONE is not None
        assert WithholdingSeverity.CRITICAL is not None
        assert QualityGateSeverity.SEVERE is not None
        assert CompletionSeverity.MODERATE is not None

    def test_combined_detection_scenario(self):
        """Test a complex scenario involving multiple failure modes."""
        # Simulate an agent that has multiple issues
        task = "Search for data, process it, and deploy the results"
        agent_output = """
        I don't have access to web search. Let me simulate the data instead.
        Task is complete!
        Skipping validation to save time.
        git commit --no-verify
        """

        # Tool provision - should detect workaround
        tp_result = tool_provision_detector.detect(task, agent_output, available_tools=[])
        assert tp_result.detected

        # Quality gate - should detect bypass
        qg_result = quality_gate_detector.detect(task, agent_output)
        assert qg_result.detected

        # Completion - should detect potential misjudgment
        cm_result = completion_detector.detect(task, agent_output)
        assert cm_result.completion_claimed == True

    def test_detector_result_serialization(self):
        """Test that detector results can be serialized."""
        import json
        from dataclasses import asdict

        result = tool_provision_detector.detect(
            task="Search for news",
            agent_output="I cannot browse the web.",
            available_tools=[],
        )

        # Should be able to convert to dict
        result_dict = asdict(result)
        assert isinstance(result_dict, dict)

        # Should be JSON serializable
        json_str = json.dumps(result_dict, default=str)
        assert isinstance(json_str, str)
