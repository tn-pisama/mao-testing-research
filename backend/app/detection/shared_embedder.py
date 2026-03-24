"""Shared embedder singleton for all detectors.

Uses the centralized embedding service which routes to:
1. Voyage AI API (primary) — fast, no local model
2. all-MiniLM-L6-v2 (fallback) — local, loads if Voyage unavailable

All detectors should use get_shared_embedder() instead of
creating their own embedding instances.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_embedder = None


def get_shared_embedder(model_name: str = "all-MiniLM-L6-v2"):
    """Get the shared embedder (Voyage AI primary, local fallback).

    Args:
        model_name: Fallback model name (default: all-MiniLM-L6-v2)

    Returns:
        Embedder instance with .encode() method
    """
    global _embedder

    if _embedder is not None:
        return _embedder

    # Try centralized embedding service first (uses Voyage AI)
    try:
        from app.core.embeddings import get_embedder
        _embedder = get_embedder()
        logger.info("Using centralized embedder (Voyage AI primary)")
        return _embedder
    except Exception as e:
        logger.debug(f"Centralized embedder unavailable: {e}")

    # Fallback to local SentenceTransformer
    try:
        from sentence_transformers import SentenceTransformer
        logger.info(f"Falling back to local SentenceTransformer: {model_name}")
        _embedder = SentenceTransformer(model_name)
        return _embedder
    except Exception as e:
        logger.warning(f"Local SentenceTransformer failed: {e}")
        return None


def clear_shared_embedder():
    """Free the shared embedder from memory."""
    global _embedder
    _embedder = None
