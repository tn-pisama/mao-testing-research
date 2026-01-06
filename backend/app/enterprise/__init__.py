"""Enterprise modules for PISAMA.

These modules require enterprise feature flags to be enabled.
They include advanced testing, simulation, and compliance features.

Feature flags required:
- chaos_engineering: Chaos injection and resilience testing
- trace_replay: Trace replay and what-if simulation
- regression_testing: Regression testing framework
- advanced_evals: Advanced evaluation framework

To enable, set in environment:
    FEATURE_ENTERPRISE_ENABLED=true
    FEATURE_CHAOS_ENGINEERING=true
    # etc.

Note: audit logging is available in ICP tier at app.core.audit
"""

from app.core.feature_gate import is_feature_enabled

__all__ = []

# Conditionally expose enterprise submodules
if is_feature_enabled("chaos_engineering"):
    from . import chaos
    __all__.append("chaos")

if is_feature_enabled("trace_replay"):
    from . import replay
    __all__.append("replay")

if is_feature_enabled("regression_testing"):
    from . import regression
    from . import testing
    __all__.extend(["regression", "testing"])

if is_feature_enabled("advanced_evals"):
    from . import evals
    from . import integrations
    __all__.extend(["evals", "integrations"])
