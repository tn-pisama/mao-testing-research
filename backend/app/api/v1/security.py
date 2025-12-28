"""Security detection API endpoints."""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.detection import (
    injection_detector,
    hallucination_detector,
    overflow_detector,
    cost_calculator,
)
from app.core.auth import get_current_tenant

router = APIRouter(prefix="/security", tags=["security"])


class InjectionCheckRequest(BaseModel):
    text: str
    context: Optional[str] = None
    is_user_input: bool = True


class InjectionCheckResponse(BaseModel):
    detected: bool
    confidence: float
    attack_type: Optional[str]
    severity: str
    matched_patterns: List[str]
    details: dict


class HallucinationCheckRequest(BaseModel):
    output: str
    sources: Optional[List[str]] = None
    context: Optional[str] = None
    tool_results: Optional[List[dict]] = None


class HallucinationCheckResponse(BaseModel):
    detected: bool
    confidence: float
    hallucination_type: Optional[str]
    grounding_score: float
    evidence: List[str]
    details: dict


class OverflowCheckRequest(BaseModel):
    current_tokens: int
    model: str
    messages: Optional[List[dict]] = None
    expected_output_tokens: int = 4096


class OverflowCheckResponse(BaseModel):
    severity: str
    current_tokens: int
    context_window: int
    usage_percent: float
    remaining_tokens: int
    estimated_overflow_in: Optional[int]
    warnings: List[str]
    suggestions: List[str]
    details: dict


class CostCalculateRequest(BaseModel):
    model: str
    input_tokens: int
    output_tokens: int


class CostCalculateResponse(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float
    total_cost_cents: float
    model: str
    provider: str


@router.post("/injection/check", response_model=InjectionCheckResponse)
async def check_injection(
    request: InjectionCheckRequest,
    tenant=Depends(get_current_tenant),
):
    result = injection_detector.detect_injection(
        text=request.text,
        context=request.context,
        is_user_input=request.is_user_input,
    )
    
    return InjectionCheckResponse(
        detected=result.detected,
        confidence=result.confidence,
        attack_type=result.attack_type,
        severity=result.severity,
        matched_patterns=result.matched_patterns,
        details=result.details,
    )


@router.post("/hallucination/check", response_model=HallucinationCheckResponse)
async def check_hallucination(
    request: HallucinationCheckRequest,
    tenant=Depends(get_current_tenant),
):
    from app.detection.hallucination import SourceDocument
    
    sources = None
    if request.sources:
        sources = [SourceDocument(content=s) for s in request.sources]
    
    result = hallucination_detector.detect_hallucination(
        output=request.output,
        sources=sources,
        context=request.context,
        tool_results=request.tool_results,
    )
    
    return HallucinationCheckResponse(
        detected=result.detected,
        confidence=result.confidence,
        hallucination_type=result.hallucination_type,
        grounding_score=result.grounding_score,
        evidence=result.evidence,
        details=result.details,
    )


@router.post("/overflow/check", response_model=OverflowCheckResponse)
async def check_overflow(
    request: OverflowCheckRequest,
    tenant=Depends(get_current_tenant),
):
    result = overflow_detector.detect_overflow(
        current_tokens=request.current_tokens,
        model=request.model,
        messages=request.messages,
        expected_output_tokens=request.expected_output_tokens,
    )
    
    suggestions = overflow_detector.suggest_remediation(result)
    
    return OverflowCheckResponse(
        severity=result.severity.value,
        current_tokens=result.current_tokens,
        context_window=result.context_window,
        usage_percent=result.usage_percent,
        remaining_tokens=result.remaining_tokens,
        estimated_overflow_in=result.estimated_overflow_in,
        warnings=result.warnings,
        suggestions=suggestions,
        details=result.details,
    )


@router.post("/cost/calculate", response_model=CostCalculateResponse)
async def calculate_cost(
    request: CostCalculateRequest,
    tenant=Depends(get_current_tenant),
):
    result = cost_calculator.calculate_cost(
        model=request.model,
        input_tokens=request.input_tokens,
        output_tokens=request.output_tokens,
    )
    
    return CostCalculateResponse(
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        total_tokens=result.total_tokens,
        input_cost_usd=result.input_cost_usd,
        output_cost_usd=result.output_cost_usd,
        total_cost_usd=result.total_cost_usd,
        total_cost_cents=result.total_cost_cents,
        model=result.model,
        provider=result.provider,
    )


@router.get("/models")
async def list_models():
    models = cost_calculator.list_models()
    return {
        model: {
            "input_per_1m": pricing.input_per_1m,
            "output_per_1m": pricing.output_per_1m,
            "context_window": pricing.context_window,
            "provider": pricing.provider,
        }
        for model, pricing in models.items()
    }
