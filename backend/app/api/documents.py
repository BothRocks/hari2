# backend/app/api/documents.py
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, desc, asc
from uuid import UUID

from app.core.database import get_session
from app.core.deps import require_user
from app.core.config import settings
from app.models.user import User
from app.models.document import Document, ProcessingStatus, SourceType
from app.schemas.document import DocumentCreate, DocumentUpdate, DocumentResponse, DocumentDetail, DocumentList, ReprocessResponse
from app.models.job import Job, JobType, JobStatus
from app.services.pipeline.orchestrator import DocumentPipeline

router = APIRouter(prefix="/documents", tags=["documents"])


def check_upload_size(content_length: int) -> None:
    """Check if upload size is within limits.

    Args:
        content_length: Size in bytes

    Raises:
        HTTPException: 413 if file exceeds max_upload_size_mb
    """
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if content_length > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.max_upload_size_mb}MB."
        )


@router.post("/", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document_from_url(
    document_data: DocumentCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_user),
) -> DocumentResponse:
    """Create a document from a URL."""
    # Validate URL is provided
    if not document_data.url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL is required"
        )

    # Check for duplicate URL
    result = await session.execute(
        select(Document).where(Document.url == document_data.url)
    )
    existing_doc = result.scalar_one_or_none()
    if existing_doc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document with this URL already exists"
        )

    # Create document with PROCESSING status
    document = Document(
        url=document_data.url,
        source_type=SourceType.URL,
        processing_status=ProcessingStatus.PROCESSING,
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)

    # Process through pipeline
    pipeline = DocumentPipeline()
    try:
        pipeline_result = await pipeline.process_url(document_data.url)

        if pipeline_result.get("status") == "failed":
            document.processing_status = ProcessingStatus.FAILED
            document.error_message = pipeline_result.get("error", "Unknown error")
        else:
            document.processing_status = ProcessingStatus.COMPLETED
            document.content = pipeline_result.get("content")
            document.content_hash = pipeline_result.get("content_hash")
            document.title = pipeline_result.get("title")
            document.summary = pipeline_result.get("summary")
            document.quick_summary = pipeline_result.get("quick_summary")
            document.keywords = pipeline_result.get("keywords")
            document.industries = pipeline_result.get("industries")
            document.language = pipeline_result.get("language")
            document.embedding = pipeline_result.get("embedding")
            document.quality_score = pipeline_result.get("quality_score")
            document.token_count = pipeline_result.get("token_count")
            document.author = pipeline_result.get("author")
            document.needs_review = pipeline_result.get("needs_review", False)
            document.review_reasons = pipeline_result.get("review_reasons")
            document.original_metadata = pipeline_result.get("original_metadata")

            # Calculate processing cost from LLM metadata if available
            llm_metadata = pipeline_result.get("llm_metadata", {})
            if "cost_usd" in llm_metadata:
                document.processing_cost_usd = llm_metadata["cost_usd"]

        await session.commit()
        await session.refresh(document)

    except Exception as e:
        document.processing_status = ProcessingStatus.FAILED
        document.error_message = str(e)
        await session.commit()
        await session.refresh(document)

    return DocumentResponse.model_validate(document)


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_pdf(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_user),
) -> DocumentResponse:
    """Upload a PDF document."""
    # Validate file is PDF
    if not file.content_type or "pdf" not in file.content_type.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted"
        )

    # Check file size from header if available
    if file.size:
        check_upload_size(file.size)

    # Read file content
    pdf_content = await file.read()

    # Double-check actual content size
    check_upload_size(len(pdf_content))

    # Create document with PROCESSING status
    document = Document(
        url=file.filename,
        source_type=SourceType.PDF,
        processing_status=ProcessingStatus.PROCESSING,
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)

    # Process through pipeline
    pipeline = DocumentPipeline()
    try:
        pipeline_result = await pipeline.process_pdf(pdf_content, file.filename or "")

        if pipeline_result.get("status") == "failed":
            document.processing_status = ProcessingStatus.FAILED
            document.error_message = pipeline_result.get("error", "Unknown error")
        else:
            document.processing_status = ProcessingStatus.COMPLETED
            document.content = pipeline_result.get("content")
            document.content_hash = pipeline_result.get("content_hash")
            document.title = pipeline_result.get("title") or file.filename
            document.summary = pipeline_result.get("summary")
            document.quick_summary = pipeline_result.get("quick_summary")
            document.keywords = pipeline_result.get("keywords")
            document.industries = pipeline_result.get("industries")
            document.language = pipeline_result.get("language")
            document.embedding = pipeline_result.get("embedding")
            document.quality_score = pipeline_result.get("quality_score")
            document.token_count = pipeline_result.get("token_count")
            document.author = pipeline_result.get("author")
            document.needs_review = pipeline_result.get("needs_review", False)
            document.review_reasons = pipeline_result.get("review_reasons")
            document.original_metadata = pipeline_result.get("original_metadata")

            # Calculate processing cost from LLM metadata if available
            llm_metadata = pipeline_result.get("llm_metadata", {})
            if "cost_usd" in llm_metadata:
                document.processing_cost_usd = llm_metadata["cost_usd"]

        await session.commit()
        await session.refresh(document)

    except Exception as e:
        document.processing_status = ProcessingStatus.FAILED
        document.error_message = str(e)
        await session.commit()
        await session.refresh(document)

    return DocumentResponse.model_validate(document)


@router.get("/", response_model=DocumentList)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: ProcessingStatus | None = Query(None),
    needs_review: bool | None = Query(None),
    search: str | None = Query(None, description="Search in title and author"),
    sort_by: Literal["created_at", "title", "author", "quality_score"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_user),
) -> DocumentList:
    """List documents with search, filtering, sorting, and pagination."""
    # Build query
    query = select(Document)

    # Apply filters
    if status:
        query = query.where(Document.processing_status == status)

    if needs_review is not None:
        query = query.where(Document.needs_review == needs_review)

    # Apply search
    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.where(
            or_(
                func.lower(Document.title).like(search_pattern),
                func.lower(Document.author).like(search_pattern),
            )
        )

    # Get total count before pagination
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Apply sorting
    sort_column = getattr(Document, sort_by, Document.created_at)
    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(asc(sort_column))

    # Apply pagination
    query = query.offset((page - 1) * page_size).limit(page_size)

    # Execute query
    result = await session.execute(query)
    documents = result.scalars().all()

    return DocumentList(
        items=[DocumentResponse.model_validate(doc) for doc in documents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_user),
) -> DocumentDetail:
    """Get a single document by ID."""
    result = await session.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    return DocumentDetail.model_validate(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_user),
) -> None:
    """Delete a document."""
    result = await session.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    await session.delete(document)
    await session.commit()


@router.put("/{document_id}", response_model=DocumentDetail)
async def update_document(
    document_id: UUID,
    update_data: DocumentUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_user),
) -> DocumentDetail:
    """Update document editable fields (title, author)."""
    result = await session.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    if update_data.title is not None:
        document.title = update_data.title
    if update_data.author is not None:
        document.author = update_data.author

    await session.commit()
    await session.refresh(document)

    return DocumentDetail.model_validate(document)


@router.post("/{document_id}/reprocess", response_model=ReprocessResponse)
async def reprocess_document(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_user),
) -> ReprocessResponse:
    """Trigger full pipeline re-processing for a document."""
    result = await session.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Create reprocess job
    job = Job(
        job_type=JobType.PROCESS_DOCUMENT,
        payload={"document_id": str(document_id), "reprocess": True},
        created_by_id=user.id,
        status=JobStatus.PENDING,
    )
    session.add(job)
    await session.commit()

    return ReprocessResponse(
        job_id=job.id,
        message=f"Reprocessing job created for document {document_id}"
    )


@router.post("/{document_id}/review", response_model=DocumentDetail)
async def mark_document_reviewed(
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_user),
) -> DocumentDetail:
    """Mark document as reviewed, clearing the needs_review flag."""
    from datetime import datetime, timezone

    result = await session.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    document.needs_review = False
    document.reviewed_at = datetime.now(timezone.utc)
    document.reviewed_by_id = user.id

    await session.commit()
    await session.refresh(document)

    return DocumentDetail.model_validate(document)
