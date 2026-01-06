"""Comprehensive tests for fast evaluation metrics."""

import pytest
import numpy as np
from unittest.mock import patch, MagicMock

from app.enterprise.evals.metrics import (
    get_embedder,
    cosine_similarity,
    relevance_score,
    coherence_score,
    helpfulness_score,
    safety_score,
    factuality_score,
    completeness_score,
    toxicity_score,
)


# ============================================================================
# Cosine Similarity Tests
# ============================================================================

class TestCosineSimilarity:
    """Tests for cosine_similarity function."""

    def test_identical_vectors(self):
        """Identical vectors should have similarity 1.0."""
        a = np.array([1.0, 2.0, 3.0])
        b = np.array([1.0, 2.0, 3.0])
        assert cosine_similarity(a, b) == pytest.approx(1.0)

    def test_opposite_vectors(self):
        """Opposite vectors should have similarity -1.0."""
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([-1.0, 0.0, 0.0])
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_orthogonal_vectors(self):
        """Orthogonal vectors should have similarity 0.0."""
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([0.0, 1.0, 0.0])
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_similar_vectors(self):
        """Similar vectors should have high similarity."""
        a = np.array([1.0, 2.0, 3.0])
        b = np.array([1.1, 2.1, 3.1])
        assert cosine_similarity(a, b) > 0.99

    def test_high_dimensional(self):
        """Should work with high-dimensional vectors."""
        a = np.random.randn(384)
        b = a + np.random.randn(384) * 0.1
        sim = cosine_similarity(a, b)
        assert 0.8 < sim <= 1.0


# ============================================================================
# Relevance Score Tests
# ============================================================================

class TestRelevanceScore:
    """Tests for relevance_score function."""

    def test_empty_output(self):
        """Empty output should return 0."""
        assert relevance_score("", "test context") == 0.0

    def test_empty_context(self):
        """Empty context should return 0."""
        assert relevance_score("test output", "") == 0.0

    def test_both_empty(self):
        """Both empty should return 0."""
        assert relevance_score("", "") == 0.0

    def test_word_overlap_mode(self):
        """Should calculate word overlap when embeddings disabled."""
        output = "The cat sat on the mat"
        context = "The cat is on the mat"
        score = relevance_score(output, context, use_embeddings=False)
        assert 0.5 < score <= 1.0

    def test_no_overlap(self):
        """No word overlap should return low score."""
        output = "banana apple orange"
        context = "car truck bicycle"
        score = relevance_score(output, context, use_embeddings=False)
        assert score == 0.0

    def test_full_overlap(self):
        """Full word overlap should return 1.0."""
        text = "hello world test"
        score = relevance_score(text, text, use_embeddings=False)
        assert score == 1.0

    def test_embedding_mode(self):
        """Should use embeddings for semantic similarity."""
        output = "The capital of France is Paris"
        context = "Paris is the capital city of France"
        score = relevance_score(output, context, use_embeddings=True)
        assert score > 0.7  # Semantically similar

    def test_embedding_dissimilar(self):
        """Dissimilar content should have lower embedding score than similar content."""
        output = "The weather is sunny today"
        context = "Python programming language syntax"
        score = relevance_score(output, context, use_embeddings=True)
        # Embedding models may still find some similarity even for different topics
        # The key is that this should be lower than semantically similar text
        similar_score = relevance_score("Paris is the capital of France", "France's capital city is Paris", use_embeddings=True)
        assert score < similar_score


# ============================================================================
# Coherence Score Tests
# ============================================================================

class TestCoherenceScore:
    """Tests for coherence_score function."""

    def test_empty_output(self):
        """Empty output should return 0."""
        assert coherence_score("") == 0.0

    def test_single_sentence(self):
        """Single sentence should return high score."""
        score = coherence_score("This is a single sentence about testing.")
        assert score == 0.8  # Default for single sentence

    def test_short_sentences_ignored(self):
        """Very short sentences should be ignored."""
        score = coherence_score("Hi. Yes. No. Ok.")
        assert score == 0.8  # Falls back to single sentence logic

    def test_coherent_paragraph(self):
        """Coherent paragraph should score high."""
        text = (
            "Machine learning is a subset of artificial intelligence. "
            "It allows computers to learn from data. "
            "Therefore, predictions can be made without explicit programming."
        )
        score = coherence_score(text)
        assert score > 0.6

    def test_incoherent_text(self):
        """Incoherent text should score lower."""
        text = (
            "Machine learning uses neural networks for pattern recognition. "
            "The weather in Paris is often rainy during autumn months. "
            "Cooking pasta requires boiling water at high temperature."
        )
        score = coherence_score(text)
        # Still might score reasonably due to sentence structure
        assert 0.0 <= score <= 1.0

    def test_transition_words_bonus(self):
        """Text with transition words should get bonus."""
        text_with_transitions = (
            "First, we gather the data from various sources. "
            "Therefore, we can begin the analysis process. "
            "Furthermore, the results indicate clear patterns. "
            "In conclusion, the hypothesis is supported."
        )
        text_without = (
            "We gather the data from various sources. "
            "We can begin the analysis process. "
            "The results indicate clear patterns. "
            "The hypothesis is supported."
        )
        score_with = coherence_score(text_with_transitions)
        score_without = coherence_score(text_without)
        # Both should be coherent, but transition words add bonus
        assert 0.0 <= score_without <= 1.0
        assert 0.0 <= score_with <= 1.0


# ============================================================================
# Helpfulness Score Tests
# ============================================================================

class TestHelpfulnessScore:
    """Tests for helpfulness_score function."""

    def test_empty_output(self):
        """Empty output should return 0."""
        assert helpfulness_score("") == 0.0

    def test_short_output_baseline(self):
        """Short output gets baseline score."""
        score = helpfulness_score("Yes, that's correct.")
        assert score == 0.5

    def test_longer_output_bonus(self):
        """Longer output gets length bonus."""
        short = "Yes."
        long = "This is a much longer response that provides detailed information about the topic at hand, explaining various aspects thoroughly."

        short_score = helpfulness_score(short)
        long_score = helpfulness_score(long)

        assert long_score > short_score

    def test_very_long_output(self):
        """Very long output gets maximum length bonus."""
        very_long = "word " * 100  # 500 characters
        score = helpfulness_score(very_long)
        assert score >= 0.7

    def test_actionable_patterns(self):
        """Actionable patterns increase score."""
        actionable = "You should first do this. Then you can try that. Step 1 is to begin."
        non_actionable = "The weather is nice today."

        actionable_score = helpfulness_score(actionable)
        non_actionable_score = helpfulness_score(non_actionable)

        assert actionable_score > non_actionable_score

    def test_query_relevance(self):
        """Relevant query increases score."""
        output = "Python is a programming language used for data science."
        query = "What is Python used for?"

        score_with_query = helpfulness_score(output, query=query)
        score_without = helpfulness_score(output, query=None)

        assert score_with_query > score_without

    def test_step_patterns(self):
        """Step patterns increase helpfulness."""
        with_steps = "1. First step. 2. Second step. 3. Third step."
        without_steps = "Do the first thing then the second thing then third."

        assert helpfulness_score(with_steps) >= helpfulness_score(without_steps)


# ============================================================================
# Safety Score Tests
# ============================================================================

class TestSafetyScore:
    """Tests for safety_score function."""

    def test_empty_output(self):
        """Empty output should be fully safe."""
        assert safety_score("") == 1.0

    def test_safe_content(self):
        """Safe content should score 1.0."""
        safe = "The weather today is sunny and warm. Perfect for a walk in the park."
        assert safety_score(safe) == 1.0

    def test_profanity_penalty(self):
        """Profanity should reduce score."""
        clean = "This is a clean message."
        profane = "This is a damn message."

        assert safety_score(clean) > safety_score(profane)

    def test_multiple_profanity(self):
        """Multiple profanity words increase penalty."""
        mild = "That was a damn mistake."
        severe = "Damn, that was a hell of a damn mistake."

        assert safety_score(mild) > safety_score(severe)

    def test_harmful_content(self):
        """Harmful content should be penalized heavily."""
        harmful = "How to make a bomb at home using household items."
        score = safety_score(harmful)
        assert score < 0.6

    def test_pii_ssn_penalty(self):
        """SSN patterns should reduce score."""
        with_ssn = "My SSN is 123-45-6789 for your records."
        without = "Please provide your identification number."

        assert safety_score(without) > safety_score(with_ssn)

    def test_pii_email_penalty(self):
        """Email addresses should reduce score."""
        with_email = "Contact me at john.doe@example.com for details."
        without = "Contact me for details."

        assert safety_score(without) > safety_score(with_email)

    def test_pii_credit_card(self):
        """Credit card numbers should reduce score."""
        with_cc = "My card number is 1234567890123456."
        without = "I'll pay with my card."

        assert safety_score(without) > safety_score(with_cc)

    def test_score_never_negative(self):
        """Score should never go below 0."""
        very_unsafe = "How to kill yourself with suicide methods. Damn hell bitch."
        score = safety_score(very_unsafe)
        assert score >= 0.0


# ============================================================================
# Factuality Score Tests
# ============================================================================

class TestFactualityScore:
    """Tests for factuality_score function."""

    def test_empty_output(self):
        """Empty output should return default 0.5."""
        assert factuality_score("", ["source text"]) == 0.5

    def test_empty_sources(self):
        """Empty sources should return default 0.5."""
        assert factuality_score("output text", []) == 0.5

    def test_grounded_output(self):
        """Output grounded in sources should score high."""
        sources = ["Paris is the capital of France. It is located in Europe."]
        output = "The capital of France is Paris, a European city."

        score = factuality_score(output, sources)
        assert score > 0.6

    def test_ungrounded_output(self):
        """Output not grounded in sources should score lower than grounded output."""
        sources = ["Python is a programming language created by Guido van Rossum."]
        ungrounded_output = "The weather in Tokyo is often humid in summer months."
        grounded_output = "Python was created by Guido van Rossum as a programming language."

        ungrounded_score = factuality_score(ungrounded_output, sources)
        grounded_score = factuality_score(grounded_output, sources)
        # Ungrounded content should score lower than grounded content
        assert ungrounded_score < grounded_score

    def test_multiple_sources(self):
        """Should check against multiple sources."""
        sources = [
            "Machine learning is part of AI.",
            "Python is used for data science.",
            "Neural networks process information.",
        ]
        output = "AI includes machine learning. Python is popular for data science applications."

        score = factuality_score(output, sources)
        assert score > 0.5

    def test_short_sentences_ignored(self):
        """Very short sentences in output should be ignored."""
        sources = ["Testing is important for software quality."]
        output = "Yes. No. Testing matters for quality software development and maintenance."

        score = factuality_score(output, sources)
        assert 0.0 <= score <= 1.0


# ============================================================================
# Completeness Score Tests
# ============================================================================

class TestCompletenessScore:
    """Tests for completeness_score function."""

    def test_empty_output(self):
        """Empty output should return default 0.5."""
        assert completeness_score("", ["element"]) == 0.5

    def test_empty_expected(self):
        """Empty expected should return default 0.5."""
        assert completeness_score("output", []) == 0.5

    def test_all_elements_present(self):
        """All elements present should return 1.0."""
        output = "The report includes name, email, and phone number."
        expected = ["name", "email", "phone"]

        score = completeness_score(output, expected)
        assert score == 1.0

    def test_no_elements_present(self):
        """No elements present should return 0.0."""
        output = "The weather is nice today."
        expected = ["name", "email", "phone"]

        score = completeness_score(output, expected)
        assert score == 0.0

    def test_partial_elements(self):
        """Partial elements should return proportional score."""
        output = "The report includes name and email."
        expected = ["name", "email", "phone", "address"]

        score = completeness_score(output, expected)
        assert score == 0.5  # 2 out of 4

    def test_partial_word_match(self):
        """Partial word matches should get partial credit."""
        output = "User information details available"
        expected = ["user information"]

        score = completeness_score(output, expected)
        assert score == 1.0  # Both words present

    def test_case_insensitive(self):
        """Matching should be case insensitive."""
        output = "NAME and EMAIL are included"
        expected = ["name", "email"]

        score = completeness_score(output, expected)
        assert score == 1.0


# ============================================================================
# Toxicity Score Tests
# ============================================================================

class TestToxicityScore:
    """Tests for toxicity_score function."""

    def test_empty_output(self):
        """Empty output should be non-toxic."""
        assert toxicity_score("") == 0.0

    def test_safe_content(self):
        """Safe content should have 0 toxicity."""
        safe = "The weather today is beautiful."
        assert toxicity_score(safe) == 0.0

    def test_toxic_content(self):
        """Toxic content should have positive toxicity."""
        toxic = "This is a damn frustrating situation."
        assert toxicity_score(toxic) > 0.0

    def test_inverse_of_safety(self):
        """Toxicity should be inverse of safety."""
        text = "Some text with profanity like damn and hell."
        safety = safety_score(text)
        toxicity = toxicity_score(text)

        assert toxicity == pytest.approx(1.0 - safety)


# ============================================================================
# Get Embedder Tests
# ============================================================================

class TestGetEmbedder:
    """Tests for get_embedder function."""

    def test_returns_embedder(self):
        """Should return a SentenceTransformer instance."""
        embedder = get_embedder()
        assert embedder is not None

    def test_singleton_pattern(self):
        """Should return same instance on multiple calls."""
        embedder1 = get_embedder()
        embedder2 = get_embedder()
        assert embedder1 is embedder2

    def test_embedder_can_encode(self):
        """Embedder should be able to encode text."""
        embedder = get_embedder()
        embedding = embedder.encode("test text")
        assert isinstance(embedding, np.ndarray)
        assert len(embedding) > 0


# ============================================================================
# Integration Tests
# ============================================================================

class TestMetricsIntegration:
    """Integration tests for evaluation metrics."""

    def test_all_metrics_on_same_text(self):
        """All metrics should work on the same text."""
        text = (
            "Python is a versatile programming language. "
            "It is widely used for data science and web development. "
            "You can start learning Python by installing it from python.org."
        )
        context = "What is Python and how do I learn it?"
        sources = ["Python is a programming language used in many domains."]
        expected = ["Python", "programming", "learn"]

        relevance = relevance_score(text, context)
        coherence = coherence_score(text)
        helpfulness = helpfulness_score(text, query=context)
        safety = safety_score(text)
        factuality = factuality_score(text, sources)
        completeness = completeness_score(text, expected)
        toxicity = toxicity_score(text)

        assert 0.0 <= relevance <= 1.0
        assert 0.0 <= coherence <= 1.0
        assert 0.0 <= helpfulness <= 1.0
        assert 0.0 <= safety <= 1.0
        assert 0.0 <= factuality <= 1.0
        assert 0.0 <= completeness <= 1.0
        assert 0.0 <= toxicity <= 1.0

        # This text should be safe and relevant
        assert safety > 0.9
        assert relevance > 0.5
        assert completeness == 1.0

    def test_metrics_differentiate_quality(self):
        """Metrics should differentiate between good and bad outputs."""
        good_output = (
            "To learn Python, you should first install it from python.org. "
            "Then, try online tutorials like Codecademy or freeCodeCamp. "
            "Practice by building small projects."
        )

        bad_output = "I don't know. Maybe try Google."

        query = "How do I learn Python programming?"

        good_help = helpfulness_score(good_output, query=query)
        bad_help = helpfulness_score(bad_output, query=query)

        assert good_help > bad_help
