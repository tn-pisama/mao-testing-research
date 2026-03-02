"""E2E tests for embedding-based detection with E5-large model."""
import pytest
import numpy as np


class TestEmbeddingDetectionE2E:
    """End-to-end tests for detection algorithms using real embeddings."""
    
    @pytest.fixture(autouse=True)
    def reset_embedder(self):
        from app.core.embeddings import EmbeddingService
        EmbeddingService.reset()
        yield
        EmbeddingService.reset()
    
    def test_loop_detection_with_semantic_similarity(self):
        from app.detection.loop import MultiLevelLoopDetector, StateSnapshot
        
        detector = MultiLevelLoopDetector()
        
        states = [
            StateSnapshot(
                agent_id="agent1",
                state_delta={"query": "find hotels"},
                content="User asks to find hotels in Paris for their vacation",
                sequence_num=0
            ),
            StateSnapshot(
                agent_id="agent1",
                state_delta={"query": "search hotels"},
                content="Looking for hotel accommodations in Paris for the trip",
                sequence_num=1
            ),
            StateSnapshot(
                agent_id="agent1",
                state_delta={"query": "locate hotels"},
                content="Searching for places to stay in Paris during vacation",
                sequence_num=2
            ),
            StateSnapshot(
                agent_id="agent1",
                state_delta={"query": "get hotels"},
                content="Finding hotel options in Paris for the holiday",
                sequence_num=3
            ),
        ]
        
        result = detector.detect_loop(states)
        assert result.detected
        assert result.confidence >= 0.7
    
    def test_loop_detection_no_loop_with_distinct_content(self):
        from app.detection.loop import MultiLevelLoopDetector, StateSnapshot
        
        detector = MultiLevelLoopDetector()
        
        states = [
            StateSnapshot(
                agent_id="agent1",
                state_delta={"step": 1},
                content="Analyzing the quarterly financial report for Q3 2024",
                sequence_num=0
            ),
            StateSnapshot(
                agent_id="agent1",
                state_delta={"step": 2, "revenue": 5000000},
                content="Implementing new machine learning model for fraud detection",
                sequence_num=1
            ),
            StateSnapshot(
                agent_id="agent1",
                state_delta={"step": 3, "accuracy": 0.95},
                content="Deploying containerized microservices to Kubernetes cluster",
                sequence_num=2
            ),
            StateSnapshot(
                agent_id="agent1",
                state_delta={"step": 4, "pods": 10},
                content="Writing comprehensive API documentation for developers",
                sequence_num=3
            ),
        ]
        
        result = detector.detect_loop(states)
        assert not result.detected
    
    def test_persona_consistency_with_embeddings(self):
        from app.detection.persona import PersonaConsistencyScorer, Agent
        
        scorer = PersonaConsistencyScorer()
        
        agent = Agent(
            id="legal_assistant",
            persona_description="A professional legal assistant that helps with contract review and legal document analysis",
            allowed_actions=["search", "analyze", "summarize"],
        )
        
        consistent_output = "I've analyzed the contract and found three key clauses that require attention: the liability limitation, the termination conditions, and the intellectual property rights section."
        result = scorer.score_consistency(agent, consistent_output)
        assert result.score > 0.5
        
        inconsistent_output = "OMG this pizza is amazing! Let's go to the beach and play volleyball! I love summer vibes!"
        result2 = scorer.score_consistency(agent, inconsistent_output)
        assert result2.score < result.score
    
    def test_hallucination_detection_uses_embeddings(self):
        from app.detection.hallucination import HallucinationDetector, SourceDocument
        
        detector = HallucinationDetector()
        
        sources = [
            SourceDocument(content="The company was founded in 2020 in San Francisco by John Smith."),
            SourceDocument(content="The product has exactly 500 active users as of December 2024."),
        ]
        
        grounded_output = "The company was established in 2020 in the San Francisco area."
        result = detector.detect_hallucination(grounded_output, sources=sources)
        
        assert result.grounding_score > 0
        assert "source_grounding_score" in result.details
        
        no_source_result = detector.detect_hallucination(grounded_output, sources=None)
        assert no_source_result.grounding_score == 1.0
    
    def test_embedding_dimensions_correct(self):
        from app.core.embeddings import get_embedder
        
        embedder = get_embedder()
        
        test_text = "This is a test sentence for embedding dimension verification."
        embedding = embedder.encode(test_text)
        
        assert embedding.shape == (embedder.dimensions,)
        assert embedder.dimensions > 0
    
    def test_e5_prefix_applied(self):
        from app.core.embeddings import get_embedder
        
        embedder = get_embedder()
        
        query_emb = embedder.encode_query("What is machine learning?")
        passage_emb = embedder.encode("Machine learning is a subset of artificial intelligence.")
        
        assert query_emb.shape == (embedder.dimensions,)
        assert passage_emb.shape == (embedder.dimensions,)
        
        sim = embedder.similarity(query_emb, passage_emb)
        assert sim > 0.3
    
    def test_batch_encoding_consistency(self):
        from app.core.embeddings import get_embedder
        
        embedder = get_embedder()
        
        texts = [
            "The cat sat on the mat.",
            "A feline rested on the rug.",
            "Stock markets crashed today.",
        ]
        
        batch_embeddings = embedder.encode(texts)
        individual_embeddings = [embedder.encode(t) for t in texts]
        
        for i, (batch_emb, ind_emb) in enumerate(zip(batch_embeddings, individual_embeddings)):
            similarity = embedder.similarity(batch_emb, ind_emb)
            assert similarity > 0.99, f"Embedding {i} differs between batch and individual encoding"
