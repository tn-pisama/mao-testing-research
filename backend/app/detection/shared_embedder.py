"""Shared SentenceTransformer embedder singleton.

Prevents multiple model loads during calibration (each ~500MB).
All detectors that need embeddings should import get_shared_embedder()
instead of creating their own SentenceTransformer instance.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_embedder = None
_model_name: Optional[str] = None


def get_shared_embedder(model_name: str = "all-MiniLM-L6-v2"):
    """Get or create a shared SentenceTransformer instance.

    Args:
        model_name: Model to load (default: all-MiniLM-L6-v2)

    Returns:
        SentenceTransformer instance (shared singleton)
    """
    global _embedder, _model_name

    if _embedder is not None and _model_name == model_name:
        return _embedder

    from sentence_transformers import SentenceTransformer

    logger.info(f"Loading shared embedder: {model_name}")
    _embedder = SentenceTransformer(model_name)
    _model_name = model_name
    return _embedder


def clear_shared_embedder():
    """Free the shared embedder from memory."""
    global _embedder, _model_name
    _embedder = None
    _model_name = None
