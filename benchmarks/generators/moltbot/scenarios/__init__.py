"""Scenario generators for different detection types."""

from benchmarks.generators.moltbot.scenarios.loop import LoopScenarioGenerator
from benchmarks.generators.moltbot.scenarios.completion import CompletionScenarioGenerator
from benchmarks.generators.moltbot.scenarios.injection import InjectionScenarioGenerator
from benchmarks.generators.moltbot.scenarios.persona import PersonaScenarioGenerator
from benchmarks.generators.moltbot.scenarios.coordination import CoordinationScenarioGenerator
from benchmarks.generators.moltbot.scenarios.corruption import CorruptionScenarioGenerator
from benchmarks.generators.moltbot.scenarios.overflow import OverflowScenarioGenerator
from benchmarks.generators.moltbot.scenarios.hallucination import HallucinationScenarioGenerator

__all__ = [
    "LoopScenarioGenerator",
    "CompletionScenarioGenerator",
    "InjectionScenarioGenerator",
    "PersonaScenarioGenerator",
    "CoordinationScenarioGenerator",
    "CorruptionScenarioGenerator",
    "OverflowScenarioGenerator",
    "HallucinationScenarioGenerator",
]
