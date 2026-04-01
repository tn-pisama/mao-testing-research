"""Benchmark test configuration.

Sets up the backend import path so benchmark scripts can import
from app.detection.* without sys.path hacks in each file.
"""

import os
import sys
from pathlib import Path

# Add backend to Python path for detector imports
_BACKEND_PATH = str(Path(__file__).resolve().parent.parent / "backend")
if _BACKEND_PATH not in sys.path:
    sys.path.insert(0, _BACKEND_PATH)

# Minimal env vars required by backend config
os.environ.setdefault("JWT_SECRET", "benchmark-runner-jwt-key-not-for-prod-32chars")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://localhost/pisama_test")
os.environ.setdefault("TESTING", "1")
