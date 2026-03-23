"""Pre-production failure simulation engine.

Generate synthetic failure scenarios, inject failures into traces,
and validate detector coverage before deploying agents to production.
"""

from .injector import FailureInjector, InjectionType
from .generator import ScenarioGenerator
from .validator import PreDeploymentValidator, ValidationReport

__all__ = [
    "FailureInjector",
    "InjectionType",
    "ScenarioGenerator",
    "PreDeploymentValidator",
    "ValidationReport",
]
