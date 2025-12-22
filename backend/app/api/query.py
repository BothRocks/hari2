from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.deps import require_user
from app.models.user import User
from app.schemas.query import QueryRequest, QueryResponse, SourceReference
from app.services.search.hybrid import HybridSearch
from app.services.query.generator import generate_response

router = APIRouter(prefix="/query", tags=["query"])


@router.post("/", response_model=QueryResponse)
async def query_knowledge_base(
    data: QueryRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_user),
):
    """Query the knowledge base with RAG."""
    # Search for relevant documents
    search = HybridSearch(session)
    results = await search.search(
        query=data.query,
        limit=data.limit,
        session=session,
    )

    # Generate response
    response = await generate_response(
        question=data.query,
        context=results,
    )

    if "error" in response:
        return QueryResponse(answer=f"Error: {response['error']}", sources=[])

    return QueryResponse(
        answer=response["answer"],
        sources=[
            SourceReference(id=s.get("id"), title=s.get("title"), url=s.get("url"))
            for s in response.get("sources", [])
        ],
    )
