from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.deps import require_user
from app.models.user import User
from app.schemas.query import QueryRequest, QueryResponse, SourceReference
from app.schemas.agent import AgentQueryRequest, AgentQueryResponse, AgentSourceReference
from app.services.search.hybrid import HybridSearch
from app.services.query.generator import generate_response
from app.agent.graph import run_agent, run_agent_stream

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


@router.post("/agent", response_model=AgentQueryResponse)
async def agentic_query(
    data: AgentQueryRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_user),
):
    """
    Query with agentic RAG - evaluates context sufficiency and
    automatically searches the web if internal knowledge is insufficient.
    """
    result = await run_agent(
        query=data.query,
        session=session,
        max_iterations=data.max_iterations,
        timeout_seconds=data.timeout_seconds,
    )

    if result.error:
        return AgentQueryResponse(
            answer=f"Error: {result.error}",
            sources=[],
            research_iterations=result.research_iterations,
            cost_usd=result.cost_spent_usd,
            error=result.error,
        )

    return AgentQueryResponse(
        answer=result.final_answer or "Unable to generate response.",
        sources=[
            AgentSourceReference(
                id=s.id,
                title=s.title,
                url=s.url,
                source_type=s.source_type,
                snippet=s.snippet,
            )
            for s in result.sources
        ],
        research_iterations=result.research_iterations,
        cost_usd=result.cost_spent_usd,
    )


@router.post("/stream")
async def stream_agentic_query(
    data: AgentQueryRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_user),
):
    """
    Stream agentic query with real-time reasoning visibility.

    Returns SSE stream with events:
    - thinking: Agent reasoning steps
    - chunk: Answer sentence fragments
    - sources: Source attribution
    - warning: Limit exceeded notifications
    - done: Completion signal with cost info
    - error: Inline errors (flow continues)
    """
    return StreamingResponse(
        run_agent_stream(
            query=data.query,
            session=session,
            max_iterations=data.max_iterations,
            timeout_seconds=data.timeout_seconds,
        ),
        media_type="text/event-stream",
    )
