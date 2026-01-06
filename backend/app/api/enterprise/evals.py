"""Evaluation API endpoints."""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.evals import EvalScorer, EvalType, EvalConfig, EvalResult
from app.evals.llm_judge import LLMJudge, JudgeModel, create_default_scorers
from app.evals.metrics import (
    relevance_score,
    coherence_score,
    helpfulness_score,
    safety_score,
    factuality_score,
)
from app.core.auth import get_current_tenant

router = APIRouter(prefix="/evals", tags=["evals"])


class EvalRequest(BaseModel):
    output: str
    context: Optional[str] = None
    expected: Optional[str] = None
    eval_types: List[str] = ["relevance", "coherence", "helpfulness", "safety"]
    use_llm_judge: bool = False
    threshold: float = 0.7


class EvalResponse(BaseModel):
    overall_score: float
    passed: bool
    scores: dict
    results: List[dict]


class QuickEvalRequest(BaseModel):
    output: str
    context: Optional[str] = None


class QuickEvalResponse(BaseModel):
    relevance: float
    coherence: float
    helpfulness: float
    safety: float
    overall: float


class LLMJudgeRequest(BaseModel):
    output: str
    context: Optional[str] = None
    expected: Optional[str] = None
    eval_type: str = "relevance"
    model: str = "gpt-4o-mini"


class LLMJudgeResponse(BaseModel):
    score: float
    passed: bool
    reasoning: str
    confidence: float
    model_used: str
    tokens_used: int


@router.post("/evaluate", response_model=EvalResponse)
async def evaluate(
    request: EvalRequest,
    tenant=Depends(get_current_tenant),
):
    if request.use_llm_judge:
        judge = LLMJudge(model=JudgeModel.GPT4O_MINI)
        scorers = create_default_scorers(judge)
        
        scorer = EvalScorer()
        for eval_type, s in scorers.items():
            scorer.register_scorer(eval_type, s)
    else:
        scorer = EvalScorer()
    
    configs = []
    for eval_type_str in request.eval_types:
        try:
            eval_type = EvalType(eval_type_str)
            configs.append(EvalConfig(
                eval_type=eval_type,
                threshold=request.threshold,
            ))
        except ValueError:
            continue
    
    if request.use_llm_judge:
        results = scorer.evaluate(
            output=request.output,
            configs=configs,
            context=request.context,
            expected=request.expected,
        )
    else:
        results = []
        import uuid
        
        for config in configs:
            score = 0.5
            
            if config.eval_type == EvalType.RELEVANCE and request.context:
                score = relevance_score(request.output, request.context)
            elif config.eval_type == EvalType.COHERENCE:
                score = coherence_score(request.output)
            elif config.eval_type == EvalType.HELPFULNESS:
                score = helpfulness_score(request.output, request.context)
            elif config.eval_type == EvalType.SAFETY:
                score = safety_score(request.output)
            
            results.append(EvalResult(
                id=str(uuid.uuid4()),
                eval_type=config.eval_type,
                score=score,
                passed=score >= config.threshold,
                threshold=config.threshold,
            ))
    
    aggregated = scorer.aggregate_scores(results, configs) if hasattr(scorer, 'aggregate_scores') else {
        "overall_score": sum(r.score for r in results) / len(results) if results else 0,
        "passed": all(r.passed for r in results),
        "scores": {r.eval_type.value: r.score for r in results},
    }
    
    return EvalResponse(
        overall_score=aggregated.get("overall_score", 0),
        passed=aggregated.get("passed", False),
        scores=aggregated.get("scores", {}),
        results=[r.to_dict() for r in results],
    )


@router.post("/quick", response_model=QuickEvalResponse)
async def quick_eval(
    request: QuickEvalRequest,
    tenant=Depends(get_current_tenant),
):
    rel = relevance_score(request.output, request.context) if request.context else 0.7
    coh = coherence_score(request.output)
    hlp = helpfulness_score(request.output, request.context)
    saf = safety_score(request.output)
    
    overall = (rel + coh + hlp + saf) / 4
    
    return QuickEvalResponse(
        relevance=round(rel, 4),
        coherence=round(coh, 4),
        helpfulness=round(hlp, 4),
        safety=round(saf, 4),
        overall=round(overall, 4),
    )


@router.post("/llm-judge", response_model=LLMJudgeResponse)
async def llm_judge_eval(
    request: LLMJudgeRequest,
    tenant=Depends(get_current_tenant),
):
    try:
        model = JudgeModel(request.model)
    except ValueError:
        model = JudgeModel.GPT4O_MINI
    
    try:
        eval_type = EvalType(request.eval_type)
    except ValueError:
        eval_type = EvalType.RELEVANCE
    
    judge = LLMJudge(model=model)
    result = judge.judge(
        eval_type=eval_type,
        output=request.output,
        context=request.context,
        expected=request.expected,
    )
    
    return LLMJudgeResponse(
        score=result.score,
        passed=result.score >= 0.7,
        reasoning=result.reasoning,
        confidence=result.confidence,
        model_used=result.model_used,
        tokens_used=result.tokens_used,
    )


@router.get("/types")
async def list_eval_types():
    return {
        "types": [t.value for t in EvalType],
        "descriptions": {
            "relevance": "How relevant the output is to the context/question",
            "coherence": "Logical flow and consistency of the output",
            "helpfulness": "How helpful and actionable the output is",
            "safety": "Whether the output is safe and appropriate",
            "factuality": "Factual accuracy of claims in the output",
            "completeness": "Whether the output covers all required aspects",
            "toxicity": "Level of harmful or offensive content",
        },
    }
