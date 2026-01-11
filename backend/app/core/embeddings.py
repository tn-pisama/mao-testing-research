"""
Centralized Embedding Service for MAO Testing Platform.

Provides singleton access to embedding models with:
- Lazy loading for fast startup
- E5 instruction prefix support
- Batch encoding optimization
- Model caching
- Multi-model ensemble for best-in-class detection

Ensemble Strategy (per failure mode):
- OpenAI text-embedding-3-large (3072d): F6, F8 (semantic derailment)
- Cohere embed-english-v3 (1024d): F4, F7 (context/clarification)
- Voyage voyage-large-2 (1024d): F1, F11 (code understanding)
- E5-large-instruct (1024d): F12-F14 (verification) - default
"""

import logging
import os
from typing import List, Union, Optional, Dict, Any
import numpy as np

logger = logging.getLogger(__name__)

# Mode to preferred embedding model mapping
MODE_EMBEDDING_MAP: Dict[str, str] = {
    # Semantic derailment - OpenAI excels
    "F6": "openai",
    "F8": "openai",
    # Context/clarification - Cohere excels
    "F4": "cohere",
    "F7": "cohere",
    # Code understanding - Voyage excels
    "F1": "voyage",
    "F11": "voyage",
    # Verification - E5 (default)
    "F12": "e5",
    "F13": "e5",
    "F14": "e5",
    # Others use E5 as default
    "F2": "e5",
    "F3": "e5",
    "F5": "e5",
    "F9": "e5",
    "F10": "e5",
}


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


class EmbeddingEnsemble:
    """
    Multi-model embedding ensemble for best-in-class MAST detection.

    Supports:
    - OpenAI text-embedding-3-large (3072 dimensions)
    - Cohere embed-english-v3 (1024 dimensions)
    - Voyage voyage-large-2 (1024 dimensions)
    - E5-large-instruct (1024 dimensions) - local, always available

    Usage:
        ensemble = EmbeddingEnsemble()

        # Mode-specific embedding (uses best model for that mode)
        emb = ensemble.encode("trace text", mode="F6")

        # Full ensemble (concatenated)
        emb = ensemble.encode_full_ensemble("trace text")
    """

    _instance: Optional["EmbeddingEnsemble"] = None

    # Model dimensions
    DIMENSIONS = {
        "openai": 3072,
        "cohere": 1024,
        "voyage": 1024,
        "e5": 1024,
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._openai_client = None
        self._cohere_client = None
        self._voyage_client = None
        self._e5_service = None

        # Track which providers are available
        self._available_providers = set()
        self._check_available_providers()

    def _check_available_providers(self):
        """Check which embedding providers are configured."""
        # E5 is always available (local)
        self._available_providers.add("e5")

        if os.getenv("OPENAI_API_KEY"):
            self._available_providers.add("openai")
            logger.info("OpenAI embedding provider available")

        if os.getenv("COHERE_API_KEY"):
            self._available_providers.add("cohere")
            logger.info("Cohere embedding provider available")

        if os.getenv("VOYAGE_API_KEY"):
            self._available_providers.add("voyage")
            logger.info("Voyage embedding provider available")

        logger.info(f"Embedding ensemble providers: {self._available_providers}")

    @property
    def e5_service(self) -> EmbeddingService:
        """Lazy load E5 embedding service."""
        if self._e5_service is None:
            self._e5_service = EmbeddingService.get_instance()
        return self._e5_service

    @property
    def openai_client(self):
        """Lazy load OpenAI client."""
        if self._openai_client is None and "openai" in self._available_providers:
            try:
                from openai import OpenAI
                self._openai_client = OpenAI()
                logger.info("OpenAI client initialized")
            except ImportError:
                logger.warning("OpenAI package not installed")
                self._available_providers.discard("openai")
        return self._openai_client

    @property
    def cohere_client(self):
        """Lazy load Cohere client."""
        if self._cohere_client is None and "cohere" in self._available_providers:
            try:
                import cohere
                self._cohere_client = cohere.Client(os.getenv("COHERE_API_KEY"))
                logger.info("Cohere client initialized")
            except ImportError:
                logger.warning("Cohere package not installed")
                self._available_providers.discard("cohere")
        return self._cohere_client

    @property
    def voyage_client(self):
        """Lazy load Voyage client."""
        if self._voyage_client is None and "voyage" in self._available_providers:
            try:
                import voyageai
                self._voyage_client = voyageai.Client(api_key=os.getenv("VOYAGE_API_KEY"))
                logger.info("Voyage client initialized")
            except ImportError:
                logger.warning("Voyage package not installed")
                self._available_providers.discard("voyage")
        return self._voyage_client

    def _encode_openai(self, text: str) -> np.ndarray:
        """Encode text using OpenAI text-embedding-3-large."""
        if self.openai_client is None:
            return self._encode_e5(text)  # Fallback

        try:
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-large",
                input=text,
            )
            return np.array(response.data[0].embedding, dtype=np.float32)
        except Exception as e:
            logger.error(f"OpenAI embedding error: {e}")
            return self._encode_e5(text)  # Fallback

    def _encode_cohere(self, text: str) -> np.ndarray:
        """Encode text using Cohere embed-english-v3."""
        if self.cohere_client is None:
            return self._encode_e5(text)  # Fallback

        try:
            response = self.cohere_client.embed(
                texts=[text],
                model="embed-english-v3.0",
                input_type="search_document",
            )
            return np.array(response.embeddings[0], dtype=np.float32)
        except Exception as e:
            logger.error(f"Cohere embedding error: {e}")
            return self._encode_e5(text)  # Fallback

    def _encode_voyage(self, text: str) -> np.ndarray:
        """Encode text using Voyage voyage-large-2."""
        if self.voyage_client is None:
            return self._encode_e5(text)  # Fallback

        try:
            response = self.voyage_client.embed(
                texts=[text],
                model="voyage-large-2",
            )
            return np.array(response.embeddings[0], dtype=np.float32)
        except Exception as e:
            logger.error(f"Voyage embedding error: {e}")
            return self._encode_e5(text)  # Fallback

    def _encode_e5(self, text: str) -> np.ndarray:
        """Encode text using local E5 model."""
        return self.e5_service.encode(text, is_query=False)

    def get_provider_for_mode(self, mode: str) -> str:
        """Get the best available provider for a failure mode."""
        preferred = MODE_EMBEDDING_MAP.get(mode, "e5")
        if preferred in self._available_providers:
            return preferred
        # Fallback to e5 (always available)
        return "e5"

    def encode(
        self,
        text: str,
        mode: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> np.ndarray:
        """
        Encode text using the best model for the given mode.

        Args:
            text: Text to encode
            mode: MAST failure mode (F1-F14) for mode-specific encoding
            provider: Override provider selection (openai, cohere, voyage, e5)

        Returns:
            Embedding vector
        """
        # Determine provider
        if provider is None:
            provider = self.get_provider_for_mode(mode) if mode else "e5"

        # Route to appropriate encoder
        if provider == "openai":
            return self._encode_openai(text)
        elif provider == "cohere":
            return self._encode_cohere(text)
        elif provider == "voyage":
            return self._encode_voyage(text)
        else:
            return self._encode_e5(text)

    def encode_full_ensemble(self, text: str) -> np.ndarray:
        """
        Encode text using all available models and concatenate.

        Returns a vector of up to 6144 dimensions (3072 + 1024 + 1024 + 1024)
        if all providers are available, otherwise uses fallbacks.
        """
        embeddings = []

        # Always include E5 as base
        embeddings.append(self._encode_e5(text))

        # Add other providers if available
        if "openai" in self._available_providers:
            embeddings.append(self._encode_openai(text))

        if "cohere" in self._available_providers:
            embeddings.append(self._encode_cohere(text))

        if "voyage" in self._available_providers:
            embeddings.append(self._encode_voyage(text))

        return np.concatenate(embeddings)

    def get_total_dimensions(self) -> int:
        """Get total embedding dimensions for full ensemble."""
        total = self.DIMENSIONS["e5"]  # Always included
        for provider in ["openai", "cohere", "voyage"]:
            if provider in self._available_providers:
                total += self.DIMENSIONS[provider]
        return total

    @property
    def available_providers(self) -> set:
        """Get set of available embedding providers."""
        return self._available_providers.copy()

    @classmethod
    def get_instance(cls) -> "EmbeddingEnsemble":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset singleton for testing."""
        cls._instance = None


def get_embedding_ensemble() -> EmbeddingEnsemble:
    """Get the embedding ensemble singleton."""
    return EmbeddingEnsemble.get_instance()
