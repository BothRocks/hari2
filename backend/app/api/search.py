from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.deps import require_user
from app.models.user import User
from app.schemas.query import SearchRequest, SearchResult
from app.services.search.hybrid import HybridSearch

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/", response_model=list[SearchResult])
async def search_documents(
    data: SearchRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_user),
):
    """Search documents using hybrid search."""
    search = HybridSearch(session)
    results = await search.search(
        query=data.query,
        limit=data.limit,
        session=session,
    )

    return [
        SearchResult(
            id=r["id"],
            title=r.get("title"),
            quick_summary=r.get("quick_summary"),
            url=r.get("url"),
            score=r.get("rrf_score", r.get("similarity", 0)),
        )
        for r in results
    ]
