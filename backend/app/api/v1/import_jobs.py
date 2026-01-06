"""API endpoints for historical data import."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from uuid import UUID
from datetime import datetime
import hashlib

from app.storage.database import get_db, set_tenant_context
from app.storage.models import ImportJob, ImportError as ImportErrorModel, Trace, State, Detection, Tenant
from app.core.auth import get_current_tenant
from app.ingestion.import_parsers import (
    get_parser, 
    compute_file_hash, 
    count_records,
    ImportParser,
    ParsedRecord,
)
from app.detection.loop import MultiLevelLoopDetector, StateSnapshot
from pydantic import BaseModel
from typing import Dict, Any


router = APIRouter(prefix="/import-jobs", tags=["import-jobs"])

MAX_FILE_SIZE = 100 * 1024 * 1024
ALLOWED_EXTENSIONS = {".json", ".jsonl"}


class ImportJobResponse(BaseModel):
    id: UUID
    status: str
    format: Optional[str]
    file_name: str
    file_size_bytes: int
    records_total: int
    records_processed: int
    records_failed: int
    traces_created: int
    detections_found: int
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


class ImportJobListResponse(BaseModel):
    jobs: List[ImportJobResponse]
    total: int
    page: int
    per_page: int


class ImportResultsResponse(BaseModel):
    id: UUID
    status: str
    summary: Dict[str, Any]
    errors: List[Dict[str, Any]]


@router.get("", response_model=ImportJobListResponse)
async def list_import_jobs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant_context(db, tenant_id)
    
    query = select(ImportJob).where(ImportJob.tenant_id == UUID(tenant_id))
    
    if status:
        query = query.where(ImportJob.status == status)
    
    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar()
    
    query = query.order_by(ImportJob.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    return ImportJobListResponse(
        jobs=[_job_to_response(j) for j in jobs],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("", response_model=ImportJobResponse, status_code=202)
async def create_import_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    format: str = Form("auto"),
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant_context(db, tenant_id)
    
    if not any(file.filename.endswith(ext) for ext in ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {ALLOWED_EXTENSIONS}",
        )
    
    content = await file.read()
    
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB",
        )
    
    file_hash = compute_file_hash(content)
    
    existing = await db.execute(
        select(ImportJob).where(
            ImportJob.tenant_id == UUID(tenant_id),
            ImportJob.file_hash == file_hash,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="This file has already been imported",
        )
    
    content_str = content.decode("utf-8")
    
    detected_format = format
    if format == "auto":
        detected_format = ImportParser.detect_format(content_str)
        if not detected_format:
            raise HTTPException(
                status_code=422,
                detail="Could not detect file format. Please specify format explicitly.",
            )
    
    record_count = count_records(content_str, detected_format)
    
    import_job = ImportJob(
        tenant_id=UUID(tenant_id),
        status="pending",
        format=detected_format,
        file_name=file.filename,
        file_size_bytes=len(content),
        file_hash=file_hash,
        records_total=record_count,
    )
    db.add(import_job)
    await db.commit()
    await db.refresh(import_job)
    
    background_tasks.add_task(
        process_import_job,
        str(import_job.id),
        tenant_id,
        content_str,
        detected_format,
    )
    
    return _job_to_response(import_job)


@router.get("/{import_job_id}", response_model=ImportJobResponse)
async def get_import_job(
    import_job_id: UUID,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant_context(db, tenant_id)
    
    result = await db.execute(
        select(ImportJob).where(
            ImportJob.id == import_job_id,
            ImportJob.tenant_id == UUID(tenant_id),
        )
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found")
    
    return _job_to_response(job)


@router.get("/{import_job_id}/results", response_model=ImportResultsResponse)
async def get_import_results(
    import_job_id: UUID,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant_context(db, tenant_id)
    
    result = await db.execute(
        select(ImportJob).where(
            ImportJob.id == import_job_id,
            ImportJob.tenant_id == UUID(tenant_id),
        )
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found")
    
    errors_result = await db.execute(
        select(ImportErrorModel)
        .where(ImportErrorModel.import_job_id == import_job_id)
        .order_by(ImportErrorModel.record_index)
        .limit(100)
    )
    errors = errors_result.scalars().all()
    
    return ImportResultsResponse(
        id=job.id,
        status=job.status,
        summary={
            "records_total": job.records_total,
            "records_processed": job.records_processed,
            "records_failed": job.records_failed,
            "traces_created": job.traces_created,
            "detections_found": job.detections_found,
            "format": job.format,
            "file_name": job.file_name,
            "processing_time_seconds": (
                (job.completed_at - job.started_at).total_seconds()
                if job.completed_at and job.started_at
                else None
            ),
        },
        errors=[
            {
                "record_index": e.record_index,
                "error_message": e.error_message,
            }
            for e in errors
        ],
    )


@router.delete("/{import_job_id}", status_code=204)
async def delete_import_job(
    import_job_id: UUID,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant_context(db, tenant_id)
    
    result = await db.execute(
        select(ImportJob).where(
            ImportJob.id == import_job_id,
            ImportJob.tenant_id == UUID(tenant_id),
        )
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found")
    
    await db.delete(job)
    await db.commit()


def _job_to_response(job: ImportJob) -> ImportJobResponse:
    return ImportJobResponse(
        id=job.id,
        status=job.status,
        format=job.format,
        file_name=job.file_name,
        file_size_bytes=job.file_size_bytes,
        records_total=job.records_total,
        records_processed=job.records_processed,
        records_failed=job.records_failed,
        traces_created=job.traces_created,
        detections_found=job.detections_found,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


async def process_import_job(
    import_job_id: str,
    tenant_id: str,
    content: str,
    format_type: str,
):
    from app.storage.database import async_session_maker
    
    async with async_session_maker() as db:
        await set_tenant_context(db, tenant_id)
        
        result = await db.execute(
            select(ImportJob).where(ImportJob.id == UUID(import_job_id))
        )
        job = result.scalar_one()
        
        job.status = "processing"
        job.started_at = datetime.utcnow()
        await db.commit()
        
        try:
            # Fetch tenant settings for threshold configuration
            tenant_result = await db.execute(
                select(Tenant).where(Tenant.id == UUID(tenant_id))
            )
            tenant = tenant_result.scalar_one_or_none()
            tenant_settings = tenant.settings if tenant else None

            parser = get_parser(format_type)
            traces_map = {}
            states_by_trace = {}

            # Detect the actual agent framework from content
            detected_framework = ImportParser.detect_framework(content)

            for i, record in enumerate(parser.parse(content)):
                try:
                    if record.trace_id not in traces_map:
                        trace = Trace(
                            tenant_id=UUID(tenant_id),
                            session_id=record.trace_id,
                            framework=detected_framework,  # Use detected framework, not format
                            status="imported",
                        )
                        db.add(trace)
                        await db.flush()
                        traces_map[record.trace_id] = trace
                        states_by_trace[record.trace_id] = []
                        job.traces_created += 1
                    
                    trace = traces_map[record.trace_id]
                    seq_num = len(states_by_trace[record.trace_id])
                    
                    state_delta = {
                        "inputs": record.inputs,
                        "outputs": record.outputs,
                        "name": record.name,
                    }
                    state_hash = hashlib.sha256(
                        str(state_delta).encode()
                    ).hexdigest()[:16]
                    
                    state = State(
                        trace_id=trace.id,
                        tenant_id=UUID(tenant_id),
                        sequence_num=seq_num,
                        agent_id=record.agent_id,
                        state_delta=state_delta,
                        state_hash=state_hash,
                        token_count=record.token_count,
                        latency_ms=int(
                            (record.end_time - record.start_time).total_seconds() * 1000
                        ),
                    )
                    db.add(state)
                    states_by_trace[record.trace_id].append(state)
                    
                    trace.total_tokens += record.token_count
                    
                    job.records_processed += 1
                    
                    if job.records_processed % 100 == 0:
                        await db.commit()
                        
                except Exception as e:
                    job.records_failed += 1
                    error = ImportErrorModel(
                        import_job_id=UUID(import_job_id),
                        record_index=i,
                        error_message=str(e),
                    )
                    db.add(error)
            
            await db.commit()

            # Create tenant-aware detector for post-import analysis
            # Uses tenant threshold overrides merged with framework defaults
            loop_detector = MultiLevelLoopDetector.for_tenant(tenant_settings, detected_framework)

            for trace_id, states in states_by_trace.items():
                if len(states) < 3:
                    continue

                snapshots = [
                    StateSnapshot(
                        agent_id=s.agent_id,
                        state_delta=s.state_delta,
                        content=str(s.state_delta),
                        sequence_num=s.sequence_num,
                    )
                    for s in states
                ]

                loop_result = loop_detector.detect_loop(snapshots)

                if loop_result.detected:
                    trace = traces_map[trace_id]
                    detection = Detection(
                        tenant_id=UUID(tenant_id),
                        trace_id=trace.id,
                        detection_type="infinite_loop",
                        confidence=int(loop_result.confidence * 100),
                        method=loop_result.method,
                        details={
                            "loop_start_index": loop_result.loop_start_index,
                            "loop_length": loop_result.loop_length,
                            "source": "import",
                            "framework": detected_framework,
                            "evidence": loop_result.evidence,
                        },
                    )
                    db.add(detection)
                    job.detections_found += 1
            
            await db.commit()
            
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            await db.commit()
            
        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            await db.commit()
