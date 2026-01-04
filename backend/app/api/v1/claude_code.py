"""Claude Code trace ingestion API."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import UUID

from app.storage.database import get_db, set_tenant_context
from app.storage.models import Trace, State
from app.core.auth import get_current_tenant
from app.core.rate_limit import check_rate_limit


router = APIRouter(prefix="/traces/claude-code", tags=["claude-code"])


class ClaudeCodeTrace(BaseModel):
    """A single Claude Code trace."""
    timestamp: str
    tool_name: str
    hook_type: str = "unknown"
    session_id: str = "unknown"
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[Any] = None
    working_dir: Optional[str] = None
    
    # Enhanced fields
    trace_type: Optional[str] = None  # tool, skill, task, mcp
    skill_name: Optional[str] = None
    skill_source: Optional[str] = None


class ClaudeCodeIngestRequest(BaseModel):
    """Request body for Claude Code trace ingestion."""
    source: str = "claude-code"
    version: str = "0.1.0"
    uploaded_at: str
    trace_count: int
    traces: List[ClaudeCodeTrace]


class IngestResponse(BaseModel):
    """Response after ingestion."""
    success: bool
    traces_received: int
    traces_stored: int
    session_ids: List[str]
    message: str


@router.post("/ingest", response_model=IngestResponse)
async def ingest_claude_code_traces(
    request: ClaudeCodeIngestRequest,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Ingest traces from Claude Code CLI.
    
    This endpoint receives traces captured by pisama-claude-code
    and stores them for analysis and detection.
    """
    await check_rate_limit(tenant_id, "claude_code_ingest", limit=1000, window=60)
    await set_tenant_context(db, tenant_id)
    
    if not request.traces:
        return IngestResponse(
            success=True,
            traces_received=0,
            traces_stored=0,
            session_ids=[],
            message="No traces to ingest",
        )
    
    # Group traces by session
    sessions: Dict[str, List[ClaudeCodeTrace]] = {}
    for trace in request.traces:
        sid = trace.session_id
        if sid not in sessions:
            sessions[sid] = []
        sessions[sid].append(trace)
    
    traces_stored = 0
    
    for session_id, session_traces in sessions.items():
        # Create or get trace record
        trace_record = Trace(
            tenant_id=UUID(tenant_id),
            session_id=session_id,
            source="claude-code",
            metadata={
                "version": request.version,
                "uploaded_at": request.uploaded_at,
                "trace_count": len(session_traces),
            },
        )
        db.add(trace_record)
        await db.flush()
        
        # Create state records for each trace
        for t in session_traces:
            state = State(
                trace_id=trace_record.id,
                timestamp=datetime.fromisoformat(t.timestamp.replace("Z", "+00:00")),
                agent_name=t.tool_name,
                action=t.hook_type,
                input_data=t.tool_input,
                output_data={"output": t.tool_output} if t.tool_output else None,
                metadata={
                    "trace_type": t.trace_type,
                    "skill_name": t.skill_name,
                    "skill_source": t.skill_source,
                    "working_dir": t.working_dir,
                },
            )
            db.add(state)
            traces_stored += 1
    
    await db.commit()
    
    return IngestResponse(
        success=True,
        traces_received=len(request.traces),
        traces_stored=traces_stored,
        session_ids=list(sessions.keys()),
        message=f"Ingested {traces_stored} traces from {len(sessions)} sessions",
    )


@router.get("/sessions")
async def list_claude_code_sessions(
    limit: int = 20,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List recent Claude Code sessions."""
    await set_tenant_context(db, tenant_id)
    
    from sqlalchemy import select
    
    result = await db.execute(
        select(Trace)
        .where(Trace.source == "claude-code")
        .where(Trace.tenant_id == UUID(tenant_id))
        .order_by(Trace.created_at.desc())
        .limit(limit)
    )
    traces = result.scalars().all()
    
    return {
        "sessions": [
            {
                "id": str(t.id),
                "session_id": t.session_id,
                "created_at": t.created_at.isoformat(),
                "metadata": t.metadata,
            }
            for t in traces
        ]
    }
