"""LLM prompts for semantic quality analysis escalation."""

# Prompt templates for LLM-based quality assessment
# Used only for Tier 3 escalation when fast metrics are inconclusive

ROLE_CLARITY_EVAL_PROMPT = """Evaluate the clarity of this agent's role definition.

System Prompt:
{system_prompt}

Agent Name: {agent_name}
Agent Type: {agent_type}

Score from 0.0 to 1.0 where:
- 0.0-0.3: No clear role, vague or missing purpose
- 0.4-0.6: Partial role definition, some ambiguity
- 0.7-0.8: Clear role with minor gaps
- 0.9-1.0: Excellent role definition, specific and bounded

Consider these factors:
1. Explicit role statement (e.g., "You are a...")
2. Clear task boundaries (what it should/shouldn't do)
3. Output format specification
4. Specificity of expertise claims
5. Constraint definitions

Respond ONLY with valid JSON:
{{"score": <float>, "reasoning": "<1-2 sentence explanation>", "suggestions": ["<suggestion1>", "<suggestion2>"]}}"""

OUTPUT_CONSISTENCY_EVAL_PROMPT = """Analyze these agent outputs for structural consistency.

Agent Name: {agent_name}
Expected Output Format: {expected_format}

Output Samples:
{output_samples}

Evaluate structural consistency across outputs:
1. Do all outputs follow the same schema/structure?
2. Are field names consistent?
3. Are data types consistent for each field?
4. Is there a clear pattern in the output format?

Score from 0.0 to 1.0:
- 0.0-0.3: Completely inconsistent structures
- 0.4-0.6: Some consistency but notable variations
- 0.7-0.8: Mostly consistent with minor variations
- 0.9-1.0: Highly consistent output structure

Respond ONLY with valid JSON:
{{"score": <float>, "reasoning": "<explanation>", "schema_issues": ["<issue1>", "<issue2>"]}}"""

PROMPT_IMPROVEMENT_PROMPT = """Suggest improvements for this agent's system prompt.

Current System Prompt:
{current_prompt}

Agent Name: {agent_name}
Agent Type: {agent_type}
Workflow Context: {workflow_context}

The prompt currently scores {current_score:.2f} on role clarity.

Provide 2-3 specific, actionable improvements. Focus on:
1. Role clarity and specificity
2. Output format specification
3. Boundary/constraint definition
4. Error handling guidance

Respond ONLY with valid JSON:
{{
  "improvements": [
    {{"title": "<short title>", "description": "<what to change>", "example": "<improved prompt snippet>"}},
    ...
  ]
}}"""

ORCHESTRATION_ANALYSIS_PROMPT = """Analyze this n8n workflow architecture for quality issues.

Workflow Name: {workflow_name}
Node Count: {node_count}
Agent Count: {agent_count}
Detected Pattern: {detected_pattern}
Complexity Metrics: {complexity_metrics}

Workflow Structure:
{workflow_structure}

Evaluate the workflow architecture:
1. Is the data flow clear and explicit?
2. Is the complexity appropriate for the task?
3. Are there tight coupling issues between agents?
4. Is there adequate observability (checkpoints, logging)?
5. Are best practices followed (retry, timeout, error handling)?

Score each dimension from 0.0 to 1.0 and provide reasoning.

Respond ONLY with valid JSON:
{{
  "data_flow_score": <float>,
  "complexity_score": <float>,
  "coupling_score": <float>,
  "observability_score": <float>,
  "best_practices_score": <float>,
  "overall_assessment": "<1-2 sentence summary>",
  "critical_issues": ["<issue1>", "<issue2>"]
}}"""

SUMMARY_GENERATION_PROMPT = """Generate a concise summary of this quality assessment.

Workflow: {workflow_name}
Overall Score: {overall_score:.2f} ({overall_grade})

Agent Scores:
{agent_summary}

Orchestration Score: {orchestration_score:.2f} ({orchestration_grade})

Top Issues:
{top_issues}

Top Improvements:
{top_improvements}

Write a 2-3 sentence executive summary highlighting:
1. The main quality strengths
2. The most critical issues to address
3. Expected impact of suggested improvements

Respond with just the summary text, no JSON."""


def format_role_clarity_prompt(
    system_prompt: str,
    agent_name: str,
    agent_type: str,
) -> str:
    """Format the role clarity evaluation prompt."""
    return ROLE_CLARITY_EVAL_PROMPT.format(
        system_prompt=system_prompt or "(no system prompt)",
        agent_name=agent_name,
        agent_type=agent_type,
    )


def format_output_consistency_prompt(
    agent_name: str,
    expected_format: str,
    output_samples: list,
) -> str:
    """Format the output consistency evaluation prompt."""
    samples_text = "\n---\n".join(
        f"Sample {i+1}:\n{sample}" for i, sample in enumerate(output_samples[:5])
    )
    return OUTPUT_CONSISTENCY_EVAL_PROMPT.format(
        agent_name=agent_name,
        expected_format=expected_format or "Not specified",
        output_samples=samples_text,
    )


def format_prompt_improvement_prompt(
    current_prompt: str,
    agent_name: str,
    agent_type: str,
    workflow_context: str,
    current_score: float,
) -> str:
    """Format the prompt improvement suggestion prompt."""
    return PROMPT_IMPROVEMENT_PROMPT.format(
        current_prompt=current_prompt or "(empty)",
        agent_name=agent_name,
        agent_type=agent_type,
        workflow_context=workflow_context or "Not provided",
        current_score=current_score,
    )


def format_orchestration_analysis_prompt(
    workflow_name: str,
    node_count: int,
    agent_count: int,
    detected_pattern: str,
    complexity_metrics: dict,
    workflow_structure: str,
) -> str:
    """Format the orchestration analysis prompt."""
    return ORCHESTRATION_ANALYSIS_PROMPT.format(
        workflow_name=workflow_name,
        node_count=node_count,
        agent_count=agent_count,
        detected_pattern=detected_pattern,
        complexity_metrics=str(complexity_metrics),
        workflow_structure=workflow_structure,
    )


def format_summary_prompt(
    workflow_name: str,
    overall_score: float,
    overall_grade: str,
    agent_summary: str,
    orchestration_score: float,
    orchestration_grade: str,
    top_issues: list,
    top_improvements: list,
) -> str:
    """Format the summary generation prompt."""
    issues_text = "\n".join(f"- {issue}" for issue in top_issues[:5])
    improvements_text = "\n".join(f"- {imp}" for imp in top_improvements[:3])

    return SUMMARY_GENERATION_PROMPT.format(
        workflow_name=workflow_name,
        overall_score=overall_score,
        overall_grade=overall_grade,
        agent_summary=agent_summary,
        orchestration_score=orchestration_score,
        orchestration_grade=orchestration_grade,
        top_issues=issues_text or "None identified",
        top_improvements=improvements_text or "None suggested",
    )
