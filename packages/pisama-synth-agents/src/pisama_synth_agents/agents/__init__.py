"""Synthetic customer agent implementations."""

from .ava import AvaAgent
from .bram import BramAgent
from .clara import ClaraAgent
from .diego import DiegoAgent
from .elin import ElinAgent
from .fiona import FionaAgent
from .gustav import GustavAgent

ALL_AGENTS = {
    "ava": AvaAgent,
    "bram": BramAgent,
    "clara": ClaraAgent,
    "diego": DiegoAgent,
    "elin": ElinAgent,
    "fiona": FionaAgent,
    "gustav": GustavAgent,
}

__all__ = [
    "ALL_AGENTS", "AvaAgent", "BramAgent", "ClaraAgent",
    "DiegoAgent", "ElinAgent", "FionaAgent", "GustavAgent",
]
