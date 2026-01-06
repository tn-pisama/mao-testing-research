"""Enterprise API endpoints.

These endpoints require enterprise feature flags to be enabled.
They are conditionally loaded in main.py based on feature flags.

Feature flags required:
- chaos_engineering: Chaos injection endpoints
- trace_replay: Trace replay endpoints
- regression_testing: Regression and testing endpoints
- advanced_evals: Evaluation endpoints
- ml_detection: Diagnose/forensics endpoints
"""

# Enterprise routers are imported directly in main.py when needed
# This allows conditional loading without import errors

__all__ = [
    "chaos",
    "replay",
    "regression",
    "testing",
    "diagnose",
    "evals",
]
