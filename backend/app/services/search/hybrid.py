# backend/app/services/search/hybrid.py
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.search.semantic import SemanticSearch
from app.services.search.keyword import KeywordSearch


def reciprocal_rank_fusion(
    *result_lists: list[dict],
    k: int = 60,
) -> list[dict]:
    """Combine multiple ranked lists using RRF."""
    scores: dict[str, float] = {}
    items: dict[str, dict] = {}

    for result_list in result_lists:
        for rank, item in enumerate(result_list):
            doc_id = item["id"]
            rrf_score = 1.0 / (k + rank + 1)
            scores[doc_id] = scores.get(doc_id, 0) + rrf_score
            if doc_id not in items:
                items[doc_id] = item

    # Sort by combined RRF score
    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

    return [
        {**items[doc_id], "rrf_score": scores[doc_id]}
        for doc_id in sorted_ids
    ]


class HybridSearch:
    def __init__(self, session: AsyncSession | None = None):
        self.session = session
        self.semantic = SemanticSearch(session)
        self.keyword = KeywordSearch(session)

    async def search(
        self,
        query: str,
        limit: int = 10,
        semantic_weight: float = 0.7,
        session: AsyncSession | None = None,
    ) -> list[dict]:
        """Hybrid search combining semantic and keyword search."""
        db = session or self.session

        # Run both searches
        semantic_results = await self.semantic.search(
            query, limit=limit * 2, session=db
        )
        keyword_results = await self.keyword.search(
            query, limit=limit * 2, session=db
        )

        # Combine with RRF
        combined = reciprocal_rank_fusion(semantic_results, keyword_results)

        return combined[:limit]
