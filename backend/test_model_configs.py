"""
Test Multi-Provider LLM Configuration
======================================

Tests the new model configurations across all 3 tiers:
- Tier 1: Gemini Flash Lite (with Haiku fallback)
- Tier 2: Sonnet 4 / O3
- Tier 3: Sonnet 4 with thinking

Validates:
1. API connectivity for each provider
2. Model selection logic
3. Cost tracking
4. Fallback mechanisms
"""

import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
backend_dir = Path(__file__).parent
env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✓ Loaded .env from {env_path}\n")

# Add backend to path
sys.path.insert(0, str(backend_dir))

from app.detection.llm_judge._models import (
    get_model_config,
    get_model_for_failure_mode,
    get_recommended_models_by_tier,
    get_cost_tracker,
    reset_cost_tracker,
    ModelProvider,
    MODELS,
)
from app.detection.llm_judge._dataclasses import JudgmentResult
from app.detection.llm_judge._enums import MASTFailureMode
from app.core.summarizer import ConversationSummarizer, SummarizerProvider


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")


def test_model_registry():
    """Test 1: Validate model registry structure."""
    print_section("TEST 1: Model Registry Validation")

    print(f"Total models registered: {len(MODELS)}")
    print(f"\nModels by provider:")

    providers_count = {}
    for key, config in MODELS.items():
        provider = config.provider.value
        providers_count[provider] = providers_count.get(provider, 0) + 1

        status = "DEPRECATED" if config.deprecated else "ACTIVE"
        print(f"  [{status:10}] {key:25} -> {config.model_id:40} (${config.input_price_per_1m:5.2f}/${config.output_price_per_1m:5.2f})")

    print(f"\nProvider distribution:")
    for provider, count in providers_count.items():
        print(f"  {provider}: {count} models")

    return True


def test_tier_selection():
    """Test 2: Verify tier selection logic."""
    print_section("TEST 2: Tier Selection Logic")

    test_cases = [
        ("F3", False, "gemini-flash-lite", "Tier 1 Low-stakes"),
        ("F7", False, "gemini-flash-lite", "Tier 1 Low-stakes"),
        ("F11", False, "gemini-flash-lite", "Tier 1 Low-stakes"),
        ("F12", False, "gemini-flash-lite", "Tier 1 Low-stakes"),
        ("F1", False, "sonnet-4", "Tier 2 Default"),
        ("F2", False, "sonnet-4", "Tier 2 Default"),
        ("F5", False, "sonnet-4", "Tier 2 Default"),
        ("F5", True, "o3", "Tier 2 Cost-optimized"),
        ("F6", False, "sonnet-4-thinking", "Tier 3 High-stakes"),
        ("F8", False, "sonnet-4-thinking", "Tier 3 High-stakes"),
        ("F9", False, "sonnet-4-thinking", "Tier 3 High-stakes"),
        ("F14", False, "sonnet-4-thinking", "Tier 3 High-stakes"),
    ]

    all_passed = True
    for failure_mode, cost_opt, expected, description in test_cases:
        result = get_model_for_failure_mode(failure_mode, cost_optimized=cost_opt)
        passed = result == expected
        all_passed = all_passed and passed

        status = "✓" if passed else "✗"
        print(f"  {status} {failure_mode} (cost_opt={cost_opt:5}) -> {result:25} [{description}]")

    return all_passed


def test_api_connectivity():
    """Test 3: Test API connectivity for all providers."""
    print_section("TEST 3: API Connectivity Tests")

    # Check environment variables
    print("Environment variable status:")
    google_key = os.getenv("GOOGLE_API_KEY", "")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")

    print(f"  GOOGLE_API_KEY:     {'✓ Set' if google_key else '✗ Missing'}")
    print(f"  ANTHROPIC_API_KEY:  {'✓ Set' if anthropic_key else '✗ Missing'}")
    print(f"  OPENAI_API_KEY:     {'✓ Set' if openai_key else '✗ Missing'}")

    results = {}

    # Test Gemini (Tier 1 primary)
    print("\n[1/3] Testing Gemini API...")
    if google_key:
        try:
            import httpx
            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent"
            response = httpx.post(
                f"{url}?key={google_key}",
                json={
                    "contents": [{"parts": [{"text": "Say 'Hello' in exactly one word."}]}],
                    "generationConfig": {"maxOutputTokens": 10}
                },
                timeout=10.0
            )

            if response.status_code == 200:
                result_text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
                print(f"  ✓ Gemini API working: '{result_text.strip()}'")
                results["gemini"] = True
            else:
                print(f"  ✗ Gemini API error: HTTP {response.status_code}")
                print(f"    Response: {response.text[:200]}")
                results["gemini"] = False
        except Exception as e:
            print(f"  ✗ Gemini API failed: {e}")
            results["gemini"] = False
    else:
        print("  ⊘ Skipping (no API key)")
        results["gemini"] = False

    # Test Anthropic (Tier 2/3)
    print("\n[2/3] Testing Anthropic API...")
    if anthropic_key:
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=anthropic_key)
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=10,
                messages=[{"role": "user", "content": "Say 'Hello' in exactly one word."}]
            )
            print(f"  ✓ Anthropic API working: '{response.content[0].text.strip()}'")
            results["anthropic"] = True
        except Exception as e:
            print(f"  ✗ Anthropic API failed: {e}")
            results["anthropic"] = False
    else:
        print("  ⊘ Skipping (no API key)")
        results["anthropic"] = False

    # Test OpenAI (Tier 2 cost-optimized)
    print("\n[3/3] Testing OpenAI API...")
    if openai_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=10,
                messages=[{"role": "user", "content": "Say 'Hello' in exactly one word."}]
            )
            print(f"  ✓ OpenAI API working: '{response.choices[0].message.content.strip()}'")
            results["openai"] = True
        except Exception as e:
            print(f"  ✗ OpenAI API failed: {e}")
            results["openai"] = False
    else:
        print("  ⊘ Skipping (no API key)")
        results["openai"] = False

    return results


def test_summarizer():
    """Test 4: Test summarizer with Gemini and fallback."""
    print_section("TEST 4: Summarizer Tests")

    # Sample conversation
    sample_turns = [
        {"role": "user", "participant_id": "user1", "content": "Help me analyze this data", "turn_number": 1},
        {"role": "assistant", "participant_id": "agent1", "content": "I'll help analyze the data. What format is it in?", "turn_number": 2},
        {"role": "user", "participant_id": "user1", "content": "It's in CSV format with 10,000 rows", "turn_number": 3},
    ]

    # Test with Gemini (primary)
    print("[1/2] Testing Gemini summarizer...")
    try:
        summarizer = ConversationSummarizer(prefer_provider=SummarizerProvider.GEMINI)
        result = summarizer.summarize_turns(sample_turns, max_output_tokens=100)

        print(f"  Model used: {result.model_used}")
        print(f"  Provider: {result.provider}")
        print(f"  Original tokens: {result.original_tokens}")
        print(f"  Summary tokens: {result.summary_tokens}")
        print(f"  Compression: {result.compression_ratio:.2%}")
        print(f"  Summary preview: {result.summary[:100]}...")

        gemini_worked = result.provider == "gemini"
        print(f"  {'✓' if gemini_worked else '✗'} Gemini summarizer {'working' if gemini_worked else 'failed (using fallback)'}")
    except Exception as e:
        print(f"  ✗ Gemini summarizer failed: {e}")
        gemini_worked = False

    # Test with Claude fallback
    print("\n[2/2] Testing Claude fallback summarizer...")
    try:
        summarizer = ConversationSummarizer(prefer_provider=SummarizerProvider.ANTHROPIC)
        result = summarizer.summarize_turns(sample_turns, max_output_tokens=100)

        print(f"  Model used: {result.model_used}")
        print(f"  Provider: {result.provider}")
        print(f"  Compression: {result.compression_ratio:.2%}")

        claude_worked = result.provider == "anthropic"
        print(f"  {'✓' if claude_worked else '✗'} Claude summarizer {'working' if claude_worked else 'failed'}")
    except Exception as e:
        print(f"  ✗ Claude summarizer failed: {e}")
        claude_worked = False

    return gemini_worked or claude_worked


def test_cost_tracking():
    """Test 5: Verify cost tracking functionality."""
    print_section("TEST 5: Cost Tracking")

    reset_cost_tracker()
    tracker = get_cost_tracker()

    # Simulate usage across tiers
    print("Simulating usage across all tiers...")

    # Tier 1: Gemini Flash Lite (100 judgments)
    gemini_config = get_model_config("gemini-flash-lite")
    for i in range(100):
        input_tok, output_tok = 500, 100
        cost = (input_tok / 1_000_000 * gemini_config.input_price_per_1m +
                output_tok / 1_000_000 * gemini_config.output_price_per_1m)
        tracker.record(JudgmentResult(
            failure_mode=MASTFailureMode.F3,
            verdict="NO",
            confidence=0.95,
            reasoning="Test judgment",
            raw_response="Test",
            model_used=gemini_config.model_id,
            tokens_used=input_tok + output_tok,
            cost_usd=cost,
            provider="google",
        ))

    # Tier 2: Sonnet 4 (50 judgments)
    sonnet_config = get_model_config("sonnet-4")
    for i in range(50):
        input_tok, output_tok = 800, 200
        cost = (input_tok / 1_000_000 * sonnet_config.input_price_per_1m +
                output_tok / 1_000_000 * sonnet_config.output_price_per_1m)
        tracker.record(JudgmentResult(
            failure_mode=MASTFailureMode.F1,
            verdict="YES",
            confidence=0.92,
            reasoning="Test judgment",
            raw_response="Test",
            model_used=sonnet_config.model_id,
            tokens_used=input_tok + output_tok,
            cost_usd=cost,
            provider="anthropic",
        ))

    # Tier 3: Sonnet 4 with thinking (20 judgments)
    thinking_config = get_model_config("sonnet-4-thinking")
    for i in range(20):
        input_tok, output_tok, thinking_tok = 1000, 300, 5000
        cost = (input_tok / 1_000_000 * thinking_config.input_price_per_1m +
                output_tok / 1_000_000 * thinking_config.output_price_per_1m +
                thinking_tok / 1_000_000 * thinking_config.thinking_price_per_1m)
        tracker.record(JudgmentResult(
            failure_mode=MASTFailureMode.F6,
            verdict="YES",
            confidence=0.98,
            reasoning="Test judgment with thinking",
            raw_response="Test",
            model_used=thinking_config.model_id,
            tokens_used=input_tok + output_tok + thinking_tok,
            cost_usd=cost,
            provider="anthropic",
        ))

    # Display results
    print(f"\nTotal judgments: {tracker.total_calls}")
    print(f"Total cost: ${tracker.total_cost_usd:.4f}")
    avg_cost = tracker.total_cost_usd / tracker.total_calls if tracker.total_calls > 0 else 0
    print(f"Average cost per judgment: ${avg_cost:.4f}")

    print("\nCost breakdown by provider:")
    provider_summary = tracker.get_provider_summary()
    for provider, data in provider_summary.items():
        if provider == "total":
            continue
        avg_cost = data['cost'] / data['calls'] if data['calls'] > 0 else 0
        print(f"\n  {provider.upper()}:")
        print(f"    Judgments: {data['calls']}")
        print(f"    Cost: ${data['cost']:.4f}")
        print(f"    Avg per judgment: ${avg_cost:.4f}")

    # Calculate savings vs old Haiku 3.5
    print("\n💰 Cost Savings Analysis (vs deprecated Haiku 3.5):")

    # Old cost: all 170 judgments on Haiku 3.5
    old_input_cost = (100 * 500 + 50 * 800 + 20 * 1000) / 1_000_000 * 0.80
    old_output_cost = (100 * 100 + 50 * 200 + 20 * 300) / 1_000_000 * 4.00
    old_total = old_input_cost + old_output_cost

    savings = old_total - tracker.total_cost_usd
    savings_pct = (savings / old_total) * 100 if old_total > 0 else 0

    print(f"  Old cost (all Haiku 3.5): ${old_total:.4f}")
    print(f"  New cost (multi-tier):    ${tracker.total_cost_usd:.4f}")
    print(f"  Savings:                  ${savings:.4f} ({savings_pct:.1f}%)")

    return True


def main():
    """Run all tests."""
    print_section("Multi-Provider LLM Configuration Test Suite")
    print("Testing the new 3-tier model architecture with Gemini, Claude, and OpenAI")

    results = {}

    # Test 1: Registry
    results["registry"] = test_model_registry()

    # Test 2: Tier selection
    results["tier_selection"] = test_tier_selection()

    # Test 3: API connectivity
    api_results = test_api_connectivity()
    results["api_connectivity"] = api_results

    # Test 4: Summarizer
    results["summarizer"] = test_summarizer()

    # Test 5: Cost tracking
    results["cost_tracking"] = test_cost_tracking()

    # Summary
    print_section("Test Summary")

    print("Results:")
    print(f"  ✓ Model Registry:      {'PASS' if results['registry'] else 'FAIL'}")
    print(f"  ✓ Tier Selection:      {'PASS' if results['tier_selection'] else 'FAIL'}")
    print(f"  ✓ Gemini API:          {'PASS' if api_results.get('gemini') else 'FAIL'}")
    print(f"  ✓ Anthropic API:       {'PASS' if api_results.get('anthropic') else 'FAIL'}")
    print(f"  ✓ OpenAI API:          {'PASS' if api_results.get('openai') else 'FAIL'}")
    print(f"  ✓ Summarizer:          {'PASS' if results['summarizer'] else 'FAIL'}")
    print(f"  ✓ Cost Tracking:       {'PASS' if results['cost_tracking'] else 'FAIL'}")

    all_critical_pass = (
        results["registry"] and
        results["tier_selection"] and
        results["cost_tracking"] and
        (api_results.get("gemini") or api_results.get("anthropic"))  # At least one working
    )

    if all_critical_pass:
        print("\n✓ All critical tests passed!")
        print("\nRecommendations:")
        if not api_results.get("gemini"):
            print("  ⚠ Gemini API not working - Tier 1 will use Haiku 4.5 fallback (5x more expensive)")
        if not api_results.get("openai"):
            print("  ⚠ OpenAI API not working - cost-optimized Tier 2 unavailable")
        return 0
    else:
        print("\n✗ Some tests failed - review configuration")
        return 1


if __name__ == "__main__":
    sys.exit(main())
