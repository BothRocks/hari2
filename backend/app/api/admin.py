from typing import Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_session
from app.core.deps import require_admin
from app.models.document import Document, ProcessingStatus
from app.models.user import User
from app.services.quality.scorer import get_grade

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/quality/report")
async def quality_report(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    """Get quality distribution report."""
    result = await session.execute(
        select(Document).where(Document.processing_status == ProcessingStatus.COMPLETED)
    )
    docs = result.scalars().all()

    grades = {"A": 0, "B": 0, "C": 0, "D": 0}
    for doc in docs:
        if doc.quality_score is not None:
            grade = get_grade(doc.quality_score)
            grades[grade.value] += 1

    total = len(docs)
    return {
        "total_documents": total,
        "grade_distribution": grades,
        "average_score": sum(d.quality_score or 0 for d in docs) / total if total > 0 else 0,
    }


@router.get("/documents/failed")
async def list_failed_documents(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> list[dict[str, Any]]:
    """List all failed documents."""
    result = await session.execute(
        select(Document)
        .where(Document.processing_status == ProcessingStatus.FAILED)
        .order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()

    return [
        {
            "id": str(doc.id),
            "url": doc.url,
            "error_message": doc.error_message,
            "created_at": doc.created_at,
        }
        for doc in docs
    ]


@router.post("/documents/{document_id}/retry")
async def retry_document(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    """Retry processing a failed document."""
    result = await session.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if doc.processing_status != ProcessingStatus.FAILED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document is not in failed state")

    # Reset and reprocess
    from app.services.pipeline.orchestrator import DocumentPipeline

    doc.processing_status = ProcessingStatus.PROCESSING
    doc.error_message = None
    await session.commit()

    pipeline = DocumentPipeline()

    if doc.source_type.value == "url":
        pipeline_result = await pipeline.process_url(doc.url)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot retry non-URL documents without original file")

    if pipeline_result.get("status") == "completed":
        doc.processing_status = ProcessingStatus.COMPLETED
        doc.content = pipeline_result.get("content")
        doc.summary = pipeline_result.get("summary")
        doc.quick_summary = pipeline_result.get("quick_summary")
        doc.keywords = pipeline_result.get("keywords")
        doc.industries = pipeline_result.get("industries")
        doc.embedding = pipeline_result.get("embedding")
        doc.quality_score = pipeline_result.get("quality_score")
    else:
        doc.processing_status = ProcessingStatus.FAILED
        doc.error_message = pipeline_result.get("error")

    await session.commit()
    await session.refresh(doc)

    return {"status": doc.processing_status.value, "quality_score": doc.quality_score}
