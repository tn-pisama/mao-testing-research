# Multi-Provider Integration Fix Plan

## Problem Statement

**CRITICAL BUG:** The multi-provider model configuration (Gemini, OpenAI, Anthropic) exists but is NOT being used. The `MASTLLMJudge` class still uses the legacy `CLAUDE_MODELS` registry which only contains Claude models.

### Current State
- ✅ `_models.py`: Multi-provider registry implemented with Gemini, OpenAI, Anthropic
- ✅ Tier selection: Points to `gemini-flash-lite`, `sonnet-4`, `sonnet-4-thinking`
- ❌ `judge.py`: Still uses `CLAUDE_MODELS` (Claude-only)
- ❌ **Result**: `KeyError` when trying to use Tier 1 (`gemini-flash-lite`)

### Evidence
```python
# _models.py sets:
LOW_STAKES_MODEL_KEY = "gemini-flash-lite"

# But CLAUDE_MODELS doesn't have it:
CLAUDE_MODELS = {
    'opus-4.5', 'sonnet-4', 'sonnet-4-thinking',
    'haiku-4.5', 'haiku-3.5'  # NO gemini-flash-lite!
}
```

## Solution: Refactor judge.py to Multi-Provider

### Phase 1: Update Model Loading (PRIORITY 1)
**File:** `backend/app/detection/llm_judge/judge.py`

**Changes:**
1. Import multi-provider types:
   ```python
   from ._models import (
       MODELS,  # NEW: Multi-provider registry
       ModelConfig,  # NEW: Provider-agnostic config
       ModelProvider,  # NEW: Provider enum
       get_model_config,  # NEW: Helper function
       # Keep for backward compat:
       CLAUDE_MODELS, DEFAULT_MODEL_KEY, get_cost_tracker
   )
   ```

2. Update `__init__` to use multi-provider registry:
   ```python
   def __init__(self, ..., model_key: str = DEFAULT_MODEL_KEY):
       # Try multi-provider first, fallback to Claude-only
       if model_key in MODELS:
           self.model_config = get_model_config(model_key)
           self.is_multi_provider = True
       elif model_key in CLAUDE_MODELS:
           # Backward compatibility
           claude_config = CLAUDE_MODELS[model_key]
           self.model_config = ModelConfig(
               model_id=claude_config.model_id,
               provider=ModelProvider.ANTHROPIC,
               input_price_per_1m=claude_config.input_price_per_1m,
               output_price_per_1m=claude_config.output_price_per_1m,
               ...
           )
           self.is_multi_provider = False
       else:
           raise ValueError(f"Unknown model: {model_key}")
   ```

### Phase 2: Add Provider-Specific API Calls (PRIORITY 1)

**Add method:** `_call_gemini(prompt, max_tokens) -> Tuple[str, int, int, float]`
```python
def _call_gemini(self, prompt: str, max_tokens: int = 1000) -> Tuple[str, int, int, float]:
    """Call Google Gemini API."""
    import httpx
    start_time = time.time()

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.MODEL}:generateContent"
    response = httpx.post(
        f"{url}?key={self.google_api_key}",
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.3}
        },
        timeout=60.0
    )
    response.raise_for_status()

    data = response.json()
    content = data["candidates"][0]["content"]["parts"][0]["text"]

    # Gemini doesn't return token counts - estimate
    input_tokens = len(prompt) // 4
    output_tokens = len(content) // 4
    latency_ms = int((time.time() - start_time) * 1000)

    return content, input_tokens, output_tokens, latency_ms
```

**Update method:** `_call_openai` to use multi-provider config

### Phase 3: Update evaluate() Method (PRIORITY 1)

**Route to correct provider:**
```python
def evaluate(self, ...):
    # ... [existing code for prompt building] ...

    # Route to provider based on model config
    if self.model_config.provider == ModelProvider.GOOGLE:
        content, input_tok, output_tok, latency = self._call_gemini(prompt)
    elif self.model_config.provider == ModelProvider.OPENAI:
        content, input_tok, output_tok, latency = self._call_openai(prompt)
    else:  # ANTHROPIC
        content, input_tok, output_tok, latency = self._call_claude(prompt)

    # ... [rest of existing code] ...
```

### Phase 4: Add Google API Key Support (PRIORITY 2)

```python
@property
def google_api_key(self) -> str:
    if self._google_api_key:
        return self._google_api_key
    return os.getenv("GOOGLE_API_KEY", "")
```

### Phase 5: Update Cost Tracking (PRIORITY 2)

Ensure `JudgmentResult` includes provider:
```python
result = JudgmentResult(
    ...,
    provider=self.model_config.provider.value,  # NEW
)
```

## Testing Plan

### Unit Tests
1. Test model loading for all providers
2. Test API routing (Gemini, OpenAI, Claude)
3. Test fallback behavior
4. Test cost calculation per provider

### Integration Tests
1. End-to-end detection with Tier 1 (Gemini)
2. End-to-end detection with Tier 2 (Sonnet/O3)
3. End-to-end detection with Tier 3 (Thinking)
4. Verify cost tracking across providers

### Production Validation
1. Deploy to staging environment
2. Run sample traces through all tiers
3. Verify costs match expectations
4. Monitor for API errors

## Rollback Plan

If issues occur:
1. Revert judge.py to use CLAUDE_MODELS only
2. Update tier constants to use haiku-4.5 instead of gemini-flash-lite:
   ```python
   LOW_STAKES_MODEL_KEY = "haiku-4.5"  # Fallback to Claude
   ```
3. All existing functionality continues working

## Migration Strategy

### Option A: Big Bang (RECOMMENDED)
- Implement all changes in one PR
- Comprehensive testing before merge
- Single deployment

**Pros:** Clean, atomic change
**Cons:** Higher risk if bugs exist

### Option B: Gradual Migration
- Phase 1: Add multi-provider support alongside legacy
- Phase 2: Update tier 1 only (Gemini)
- Phase 3: Enable other providers
- Phase 4: Remove legacy code

**Pros:** Lower risk
**Cons:** More complex, longer timeline

## Recommendation

**Use Option A (Big Bang)** because:
1. Changes are localized to judge.py
2. Backward compatibility maintained via dual registry lookup
3. Comprehensive test suite already exists
4. Can be thoroughly tested locally before deployment

## Implementation Checklist

- [ ] Update imports in judge.py
- [ ] Refactor __init__ for multi-provider
- [ ] Add _call_gemini method
- [ ] Update _call_openai for multi-provider config
- [ ] Extract _call_claude from existing code
- [ ] Update evaluate() to route by provider
- [ ] Add google_api_key property
- [ ] Update provider tracking in results
- [ ] Write unit tests for new code
- [ ] Run integration tests locally
- [ ] Update documentation
- [ ] Deploy to staging
- [ ] Validate in staging
- [ ] Deploy to production
- [ ] Monitor production metrics

## Timeline Estimate

- Implementation: 2-3 hours
- Testing: 1-2 hours
- Documentation: 30 min
- Deployment & validation: 1 hour

**Total:** ~5-7 hours for complete multi-provider integration

## Success Criteria

✅ All 3 providers (Gemini, OpenAI, Anthropic) working
✅ Tier 1 uses Gemini Flash Lite successfully
✅ Cost tracking shows provider breakdown
✅ All existing tests pass
✅ No production errors after 24h
✅ Cost reduction visible in metrics
