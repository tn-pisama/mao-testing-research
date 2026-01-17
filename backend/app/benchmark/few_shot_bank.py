"""Few-shot examples for MAST failure mode detection.

Curated examples from MAST traces for each failure mode to improve
LLM-based detection accuracy through in-context learning.

Each mode has:
- positive: Examples that clearly exhibit the failure mode
- negative: Examples that look similar but are NOT the failure mode
"""

from typing import Dict, List, Any

# Curated few-shot examples for semantic failure modes
MAST_FEW_SHOT_EXAMPLES: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
    "F6": {  # Task Derailment
        "positive": [
            {
                "task": "Build a snake game with keyboard controls",
                "trajectory_snippet": """[Programmer]: I'll start by implementing the game...
Actually, let me first add a menu system with settings...
Now I'm thinking we need a leaderboard with online sync...
Let me implement the database schema for user accounts...""",
                "explanation": "Agent derailed from the core snake game task to unrelated features like online accounts and databases that weren't requested.",
            },
            {
                "task": "Fix the login authentication bug",
                "trajectory_snippet": """[Programmer]: Looking at the login code...
The CSS here is quite messy, let me refactor the styles...
While I'm at it, the color scheme could be improved...
Adding a new theme system with dark mode support...""",
                "explanation": "Agent was asked to fix a bug but derailed into CSS refactoring and theme systems completely unrelated to authentication.",
            },
        ],
        "negative": [
            {
                "task": "Build a todo app with user authentication",
                "trajectory_snippet": """[Programmer]: Starting with the user authentication system...
Setting up JWT tokens for sessions...
Now implementing the todo CRUD operations...
Adding the frontend components for todo lists...""",
                "explanation": "Agent stayed focused on the requested features: authentication and todo functionality. No derailment occurred.",
            },
        ],
    },
    "F8": {  # Information Withholding
        "positive": [
            {
                "task": "Implement file upload with size validation",
                "trajectory_snippet": """[Programmer]: Implemented the upload endpoint.
[Tester]: Running tests now... all tests pass!
(Note: The tests only check if files are saved, not size limits)
[CEO]: Great, shipping to production!""",
                "explanation": "The tester withheld that tests don't actually verify size validation - a critical gap in the requirements that wasn't communicated.",
            },
            {
                "task": "Build a payment processing system",
                "trajectory_snippet": """[Architect]: Designed the payment flow.
[Programmer]: Noticed the API rate limits are very low (10 req/min).
[Programmer]: Implemented the payment system.
[CEO]: Ready for demo?
[Programmer]: Yes, all working!""",
                "explanation": "Programmer discovered rate limit constraints but withheld this critical information from the team before demo.",
            },
        ],
        "negative": [
            {
                "task": "Create user profile page",
                "trajectory_snippet": """[Programmer]: Implementing profile page...
Found an issue - the avatar upload has a 1MB limit from the CDN.
[CEO]: Good catch! Let's document that limit.
[Programmer]: Added validation and user-facing error message.""",
                "explanation": "Programmer shared the discovered constraint with the team and it was addressed. No information withholding.",
            },
        ],
    },
    "F9": {  # Role Usurpation
        "positive": [
            {
                "task": "Design and implement user dashboard",
                "trajectory_snippet": """[CEO]: As CEO, I'll design the product requirements...
Actually, let me write the React components myself...
Here's my implementation of the dashboard:
```jsx
function Dashboard() { return <div>...</div> }
```""",
                "explanation": "CEO usurped the Programmer role by directly implementing code instead of staying in the product/strategy role.",
            },
            {
                "task": "Build API with database",
                "trajectory_snippet": """[Tester]: I'm the QA tester.
Looking at the code, I think the database schema should be different.
Let me redesign the schema myself:
CREATE TABLE users (id INT, name VARCHAR...)
And I'll write the migration code too...""",
                "explanation": "Tester usurped Architect/DBA role by redesigning database schema instead of focusing on testing.",
            },
        ],
        "negative": [
            {
                "task": "Implement search feature",
                "trajectory_snippet": """[CEO]: Requirements: search across all content types.
[Architect]: Designing search index strategy...
[Programmer]: Implementing the search API.
[Tester]: Writing test cases for search accuracy.""",
                "explanation": "Each agent stayed within their designated role. No usurpation occurred.",
            },
        ],
    },
    "F13": {  # Quality Gate Bypass
        "positive": [
            {
                "task": "Implement secure password reset",
                "trajectory_snippet": """[Programmer]: Password reset implemented.
[Tester]: Running quick smoke test...
Tested: Can click reset button - works!
All tests pass, ready for production!""",
                "explanation": "Tester's validation was shallow - only tested UI click, not actual security requirements like token expiration, email delivery, or brute force protection.",
            },
            {
                "task": "Build checkout flow",
                "trajectory_snippet": """[Programmer]: Checkout complete.
[Code Reviewer]: Looking at the code...
The styling looks good, nicely formatted.
Approved! Ship it.
(Never checked payment validation logic)""",
                "explanation": "Code reviewer only checked cosmetic aspects, bypassing actual quality verification of business logic and edge cases.",
            },
        ],
        "negative": [
            {
                "task": "Add email notifications",
                "trajectory_snippet": """[Programmer]: Email system implemented.
[Tester]: Testing scenarios:
- Valid email sent: PASS
- Invalid email rejected: PASS
- Rate limiting works: PASS
- Unsubscribe link works: PASS
All critical paths verified.""",
                "explanation": "Tester performed thorough validation covering multiple scenarios and edge cases. Quality gates properly applied.",
            },
        ],
    },
}


def get_examples_for_mode(mode: str) -> Dict[str, List[Dict[str, Any]]]:
    """Get few-shot examples for a specific failure mode.

    Args:
        mode: Failure mode (e.g., 'F6', 'F8', 'F9', 'F13')

    Returns:
        Dict with 'positive' and 'negative' example lists
    """
    return MAST_FEW_SHOT_EXAMPLES.get(mode, {"positive": [], "negative": []})


def format_examples_for_prompt(mode: str, max_examples: int = 3) -> str:
    """Format examples as a string for inclusion in LLM prompts.

    Args:
        mode: Failure mode
        max_examples: Maximum total examples to include

    Returns:
        Formatted string with examples
    """
    examples = get_examples_for_mode(mode)
    lines = []

    # Add positive examples
    for i, ex in enumerate(examples.get("positive", [])[:max_examples // 2 + 1]):
        lines.append(f"\n### Example of {mode} - YES")
        lines.append(f"**Task:** {ex['task']}")
        lines.append(f"**Trajectory:**\n```\n{ex['trajectory_snippet']}\n```")
        lines.append(f"**Why {mode}:** {ex['explanation']}")

    # Add negative examples
    for i, ex in enumerate(examples.get("negative", [])[:max_examples // 2]):
        lines.append(f"\n### Example of {mode} - NO")
        lines.append(f"**Task:** {ex['task']}")
        lines.append(f"**Trajectory:**\n```\n{ex['trajectory_snippet']}\n```")
        lines.append(f"**Why NOT {mode}:** {ex['explanation']}")

    return "\n".join(lines)
