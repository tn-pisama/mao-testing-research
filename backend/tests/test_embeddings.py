"""Unit tests for the centralized EmbeddingService."""

import pytest
import numpy as np
from unittest.mock import patch, MagicMock


class TestEmbeddingService:
    def setup_method(self):
        from app.core.embeddings import EmbeddingService
        EmbeddingService.reset()
    
    def teardown_method(self):
        from app.core.embeddings import EmbeddingService
        EmbeddingService.reset()
    
    def test_singleton_pattern(self):
        from app.core.embeddings import EmbeddingService, get_embedder
        
        service1 = EmbeddingService.get_instance()
        service2 = EmbeddingService.get_instance()
        service3 = get_embedder()
        
        assert service1 is service2
        assert service1 is service3
    
    def test_lazy_model_loading(self):
        from app.core.embeddings import EmbeddingService
        
        service = EmbeddingService.get_instance()
        assert service._model is None
    
    def test_dimensions_from_config(self):
        from app.core.embeddings import get_embedder
        
        embedder = get_embedder()
        assert embedder.dimensions == 1024
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_encode_single_text(self, mock_st):
        from app.core.embeddings import get_embedder
        
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.randn(1024).astype(np.float32)
        mock_st.return_value = mock_model
        
        embedder = get_embedder()
        result = embedder.encode("test text")
        
        assert mock_model.encode.called
        assert result.shape == (1024,)
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_encode_multiple_texts(self, mock_st):
        from app.core.embeddings import get_embedder
        
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.randn(3, 1024).astype(np.float32)
        mock_st.return_value = mock_model
        
        embedder = get_embedder()
        texts = ["text 1", "text 2", "text 3"]
        result = embedder.encode(texts)
        
        assert mock_model.encode.called
        assert result.shape == (3, 1024)
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_e5_prefix_for_passages(self, mock_st):
        from app.core.embeddings import get_embedder
        
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.randn(1024).astype(np.float32)
        mock_st.return_value = mock_model
        
        embedder = get_embedder()
        embedder.encode("test text", is_query=False)
        
        call_args = mock_model.encode.call_args
        called_text = call_args[0][0]
        assert called_text.startswith("passage: ")
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_e5_prefix_for_queries(self, mock_st):
        from app.core.embeddings import get_embedder
        
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.randn(1024).astype(np.float32)
        mock_st.return_value = mock_model
        
        embedder = get_embedder()
        embedder.encode_query("test query")
        
        call_args = mock_model.encode.call_args
        called_text = call_args[0][0]
        assert called_text.startswith("query: ")
    
    def test_similarity_identical_vectors(self):
        from app.core.embeddings import get_embedder
        
        embedder = get_embedder()
        vec = np.array([1.0, 0.0, 0.0])
        
        sim = embedder.similarity(vec, vec)
        assert abs(sim - 1.0) < 1e-6
    
    def test_similarity_orthogonal_vectors(self):
        from app.core.embeddings import get_embedder
        
        embedder = get_embedder()
        vec1 = np.array([1.0, 0.0, 0.0])
        vec2 = np.array([0.0, 1.0, 0.0])
        
        sim = embedder.similarity(vec1, vec2)
        assert abs(sim) < 1e-6
    
    def test_similarity_opposite_vectors(self):
        from app.core.embeddings import get_embedder
        
        embedder = get_embedder()
        vec1 = np.array([1.0, 0.0, 0.0])
        vec2 = np.array([-1.0, 0.0, 0.0])
        
        sim = embedder.similarity(vec1, vec2)
        assert abs(sim - (-1.0)) < 1e-6
    
    def test_similarity_zero_vector(self):
        from app.core.embeddings import get_embedder
        
        embedder = get_embedder()
        vec1 = np.array([1.0, 0.0, 0.0])
        vec2 = np.array([0.0, 0.0, 0.0])
        
        sim = embedder.similarity(vec1, vec2)
        assert sim == 0.0
    
    def test_batch_similarity(self):
        from app.core.embeddings import get_embedder
        
        embedder = get_embedder()
        query = np.array([1.0, 0.0, 0.0])
        passages = np.array([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [-1.0, 0.0, 0.0],
        ])
        
        sims = embedder.batch_similarity(query, passages)
        
        assert len(sims) == 3
        assert abs(sims[0] - 1.0) < 1e-6
        assert abs(sims[1]) < 1e-6
        assert abs(sims[2] - (-1.0)) < 1e-6
    
    def test_reset_clears_singleton(self):
        from app.core.embeddings import EmbeddingService, get_embedder
        
        service1 = get_embedder()
        EmbeddingService.reset()
        service2 = get_embedder()
        
        assert service1 is not service2


class TestEmbeddingServiceIntegration:
    """Integration tests that load the actual model (slower)."""
    
    @pytest.fixture(autouse=True)
    def reset_service(self):
        from app.core.embeddings import EmbeddingService
        EmbeddingService.reset()
        yield
        EmbeddingService.reset()
    
    @pytest.mark.slow
    def test_real_model_encoding(self):
        from app.core.embeddings import get_embedder
        
        embedder = get_embedder()
        result = embedder.encode("Hello world")
        
        assert result.shape == (embedder.dimensions,)
        assert np.linalg.norm(result) > 0
    
    @pytest.mark.slow
    def test_real_semantic_similarity(self):
        from app.core.embeddings import get_embedder
        
        embedder = get_embedder()
        
        similar1 = embedder.encode("The cat sat on the mat")
        similar2 = embedder.encode("A feline rested on the rug")
        different = embedder.encode("Financial markets crashed today")
        
        sim_similar = embedder.similarity(similar1, similar2)
        sim_different = embedder.similarity(similar1, different)
        
        assert sim_similar > sim_different
        assert sim_similar > 0.5
    
    @pytest.mark.slow
    def test_real_batch_encoding(self):
        from app.core.embeddings import get_embedder, EmbeddingService
        
        EmbeddingService.reset()
        embedder = get_embedder()
        texts = [
            "First sentence",
            "Second sentence", 
            "Third sentence",
        ]
        
        result = embedder.encode(texts)
        
        assert result.shape == (3, embedder.dimensions)
