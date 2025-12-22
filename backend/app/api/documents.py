# backend/app/api/documents.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID

from app.core.database import get_session
from app.core.deps import require_user
from app.models.user import User
from app.models.document import Document, ProcessingStatus, SourceType
from app.schemas.document import DocumentCreate, DocumentResponse, DocumentDetail, DocumentList
from app.services.pipeline.orchestrator import DocumentPipeline

router = APIRouter(prefix="/documents", tags=["documents"])


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
        result = await pipeline.process_url(document_data.url)

        if result.get("status") == "failed":
            document.processing_status = ProcessingStatus.FAILED
            document.error_message = result.get("error", "Unknown error")
        else:
            document.processing_status = ProcessingStatus.COMPLETED
            document.content = result.get("content")
            document.content_hash = result.get("content_hash")
            document.title = result.get("title")
            document.summary = result.get("summary")
            document.quick_summary = result.get("quick_summary")
            document.keywords = result.get("keywords")
            document.industries = result.get("industries")
            document.language = result.get("language")
            document.embedding = result.get("embedding")
            document.quality_score = result.get("quality_score")
            document.token_count = result.get("token_count")

            # Calculate processing cost from LLM metadata if available
            llm_metadata = result.get("llm_metadata", {})
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

    # Read file content
    pdf_content = await file.read()

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
        result = await pipeline.process_pdf(pdf_content, file.filename or "")

        if result.get("status") == "failed":
            document.processing_status = ProcessingStatus.FAILED
            document.error_message = result.get("error", "Unknown error")
        else:
            document.processing_status = ProcessingStatus.COMPLETED
            document.content = result.get("content")
            document.content_hash = result.get("content_hash")
            document.title = result.get("title") or file.filename
            document.summary = result.get("summary")
            document.quick_summary = result.get("quick_summary")
            document.keywords = result.get("keywords")
            document.industries = result.get("industries")
            document.language = result.get("language")
            document.embedding = result.get("embedding")
            document.quality_score = result.get("quality_score")
            document.token_count = result.get("token_count")

            # Calculate processing cost from LLM metadata if available
            llm_metadata = result.get("llm_metadata", {})
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
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_user),
) -> DocumentList:
    """List documents with pagination."""
    # Build query
    query = select(Document)
    if status:
        query = query.where(Document.processing_status == status)

    # Get total count
    count_query = select(func.count()).select_from(Document)
    if status:
        count_query = count_query.where(Document.processing_status == status)
    total_result = await session.execute(count_query)
    total = total_result.scalar_one()

    # Apply pagination and ordering
    query = query.order_by(Document.created_at.desc())
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
