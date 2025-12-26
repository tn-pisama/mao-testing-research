# Reviewing Detections

Help improve MAO's detection accuracy by reviewing and labeling detected issues.

## Quick Start

1. Navigate to **Review Queue** in the sidebar
2. Review each detection's pattern and confidence
3. Label using keyboard shortcuts or buttons
4. Your labels improve detection accuracy over time

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `C` | Mark as **Correct** (true positive) |
| `F` | Mark as **False Positive** |
| `U` | Mark as **Unclear** (need more context) |
| `S` | **Skip** (review later) |
| `←` `→` | Navigate between detections |
| `Enter` | View full trace |
| `Space` | View fix suggestion |

## Understanding Detection Cards

Each detection shows:

```
┌─────────────────────────────────────────────────────────────────┐
│ Detection #abc123 - Infinite Loop                               │
│ Trace: xyz789... | Agent: LangChain ReAct                       │
│                                                                  │
│ Pattern: search_tool called 8 times with query "meaning of life"│
│ Confidence: 94.2%                                                │
│                                                                  │
│ [View Trace]  [View Suggestion]                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Fields Explained

- **Detection ID**: Unique identifier for this detection
- **Type**: Infinite Loop, State Corruption, Persona Drift, or Deadlock
- **Trace ID**: Link to the full agent execution trace
- **Agent Type**: Framework and agent pattern detected
- **Pattern**: What triggered the detection
- **Confidence**: How certain MAO is about this detection (0-100%)

## Labeling Guidelines

### Correct (True Positive)

Mark as correct when:
- The detected pattern clearly matches the issue type
- The agent behavior was genuinely problematic
- The fix suggestion would help resolve the issue

**Examples:**
- Agent called `search("weather")` 15 times in a row ✅ Infinite Loop
- State went from `balance=100` to `balance=-999999` ✅ State Corruption
- Researcher agent started writing poetry ✅ Persona Drift

### False Positive

Mark as false positive when:
- The pattern looks similar but isn't actually a problem
- The repetition was intentional (e.g., polling for updates)
- The state change was valid business logic

**Examples:**
- Agent retried API call 3 times due to rate limits ❌ Not a loop
- Balance went negative due to valid transaction ❌ Not corruption
- Agent adapted tone for different user ❌ Not drift

### Unclear

Mark as unclear when:
- You need more context to decide
- The detection is borderline
- You're not familiar with this agent's expected behavior

### Skip

Skip when:
- You want to review this later
- You need to consult with the team
- The detection requires domain expertise you lack

## Filtering Detections

### By Type
Filter to focus on specific detection types:
- All Types
- Infinite Loop
- State Corruption  
- Persona Drift
- Deadlock

### By Confidence
- **High Confidence (>90%)**: Most likely correct, quick to review
- **Medium (70-90%)**: Needs careful review
- **Low (<70%)**: Often false positives, needs context

### By Status
- Pending review
- Reviewed by me
- Conflicting labels (multiple reviewers disagree)

## Progress Tracking

The review interface shows:
- **Session progress**: How many you've reviewed today
- **Pending count**: Total detections awaiting review
- **Your accuracy**: Your agreement rate with other reviewers

## Best Practices

### Review Efficiently
1. Start with high-confidence detections (quick wins)
2. Use keyboard shortcuts for faster labeling
3. Take breaks every 20-30 reviews

### When Uncertain
1. Click "View Trace" to see full agent execution
2. Check the fix suggestion for context
3. Look for similar past detections
4. Mark as "Unclear" rather than guessing

### Maintain Quality
- Don't rush - accuracy matters more than speed
- Disagree with the AI when you're confident
- Flag patterns that seem consistently wrong

## Multi-Reviewer Consensus

For training data quality, MAO uses consensus:
- Detections are labeled by multiple reviewers
- Conflicting labels trigger additional review
- Strong consensus (3+ agree) becomes training data

## Viewing Detection Details

### Full Trace View
Click "View Trace" to see:
- Complete agent execution timeline
- All tool calls and LLM responses
- State changes at each step
- Where the detection was triggered

### Fix Suggestion View
Click "View Suggestion" to see:
- Recommended code changes
- Explanation of why this fix helps
- Confidence score for the fix
- Example before/after code

## API Access

You can also review detections via API:

```bash
# Get pending detections
curl https://api.mao-testing.com/api/v1/detections/pending \
  -H "Authorization: Bearer $API_KEY"

# Label a detection
curl -X POST https://api.mao-testing.com/api/v1/detections/{id}/label \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"label": "correct", "notes": "Clear infinite loop pattern"}'
```

## FAQ

**Q: How long should each review take?**
A: High-confidence detections: 10-15 seconds. Complex cases: up to 2 minutes.

**Q: What if I make a mistake?**
A: You can change your label within 24 hours by navigating back to the detection.

**Q: Do my labels directly affect the model?**
A: Labels are aggregated with other reviewers. No single label changes the model.

**Q: Why do some detections have no fix suggestion?**
A: Fix suggestions are only generated when we have high confidence in both the detection and the fix.
