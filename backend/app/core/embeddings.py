"""
Centralized Embedding Service for MAO Testing Platform.

Provides singleton access to embedding models with:
- Lazy loading for fast startup
- E5 instruction prefix support
- Batch encoding optimization
- Model caching
"""

import logging
from typing import List, Union, Optional
import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingService:
    _instance: Optional["EmbeddingService"] = None
    _model = None
    _model_name: Optional[str] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def get_instance(cls) -> "EmbeddingService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset(cls):
        cls._instance = None
        cls._model = None
        cls._model_name = None
    
    @property
    def model(self):
        if self._model is None:
            self._load_model()
        return self._model
    
    @property
    def dimensions(self) -> int:
        from app.config import get_settings
        return get_settings().embedding_dimensions
    
    def _load_model(self):
        from sentence_transformers import SentenceTransformer
        from app.config import get_settings
        
        settings = get_settings()
        self._model_name = settings.embedding_model
        
        logger.info(f"Loading embedding model: {self._model_name}")
        self._model = SentenceTransformer(self._model_name)
        logger.info(f"Embedding model loaded: {self._model_name} ({self.dimensions} dimensions)")
    
    def _should_use_prefix(self) -> bool:
        from app.config import get_settings
        settings = get_settings()
        return settings.embedding_instruction_prefix and "e5" in settings.embedding_model.lower()
    
    def _add_prefix(self, texts: Union[str, List[str]], prefix: str) -> Union[str, List[str]]:
        if isinstance(texts, str):
            return f"{prefix}: {texts}"
        return [f"{prefix}: {t}" for t in texts]
    
    def encode(
        self,
        texts: Union[str, List[str]],
        is_query: bool = False,
        batch_size: int = 32,
        show_progress: bool = False,
        normalize: bool = True,
    ) -> np.ndarray:
        if self._should_use_prefix():
            prefix = "query" if is_query else "passage"
            texts = self._add_prefix(texts, prefix)
        
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            normalize_embeddings=normalize,
        )
        
        return embeddings
    
    def encode_query(self, query: str, normalize: bool = True) -> np.ndarray:
        return self.encode(query, is_query=True, normalize=normalize)
    
    def encode_passages(
        self,
        passages: List[str],
        batch_size: int = 32,
        normalize: bool = True,
    ) -> np.ndarray:
        return self.encode(passages, is_query=False, batch_size=batch_size, normalize=normalize)
    
    def similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(embedding1, embedding2) / (norm1 * norm2))
    
    def batch_similarity(
        self,
        query_embedding: np.ndarray,
        passage_embeddings: np.ndarray,
    ) -> np.ndarray:
        query_norm = query_embedding / np.linalg.norm(query_embedding)
        passage_norms = passage_embeddings / np.linalg.norm(passage_embeddings, axis=1, keepdims=True)
        return np.dot(passage_norms, query_norm)
    
    def warmup(self):
        logger.info("Warming up embedding model...")
        _ = self.encode("warmup text for model initialization")
        logger.info("Embedding model warmed up")


def get_embedder() -> EmbeddingService:
    return EmbeddingService.get_instance()
