# backend/app/services/search/semantic.py
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.services.pipeline.embedder import generate_embedding
from app.core.config import settings


def apply_decay(
    raw_similarity: float,
    created_at: datetime,
    ignore_decay: bool = False,
) -> float:
    """Apply time-based decay to similarity score.

    Args:
        raw_similarity: Original similarity score (0-1)
        created_at: Document creation timestamp
        ignore_decay: If True, return raw score unchanged

    Returns:
        Decayed similarity score
    """
    if ignore_decay:
        return raw_similarity

    now = datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    age_months = (now - created_at).days / 30.0

    if age_months <= settings.decay_threshold_stale_months:
        weight = 1.0
    elif age_months <= settings.decay_threshold_obsolete_months:
        weight = settings.decay_weight_stale
    else:
        weight = settings.decay_weight_obsolete

    return raw_similarity * weight


class SemanticSearch:
    def __init__(self, session: AsyncSession | None = None):
        self.session = session

    async def search(
        self,
        query: str,
        limit: int = 10,
        threshold: float = 0.5,
        ignore_decay: bool = False,
        session: AsyncSession | None = None,
    ) -> list[dict]:
        """Search documents by semantic similarity with time decay."""
        db = session or self.session
        if not db:
            raise ValueError("Database session required")

        query_embedding = await generate_embedding(query)
        if not query_embedding:
            return []

        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        sql = text("""
            SELECT
                id,
                title,
                quick_summary,
                keywords,
                url,
                created_at,
                1 - (embedding <=> cast(:embedding as vector)) as raw_similarity
            FROM documents
            WHERE processing_status = 'COMPLETED'::processingstatus
                AND embedding IS NOT NULL
            ORDER BY embedding <=> cast(:embedding as vector)
            LIMIT :limit
        """)

        result = await db.execute(
            sql,
            {
                "embedding": embedding_str,
                "limit": limit * 2,  # Fetch more to allow filtering after decay
            }
        )

        rows = result.fetchall()

        # Apply decay, filter by threshold, and sort
        results = []
        for row in rows:
            decayed_similarity = apply_decay(
                row.raw_similarity,
                row.created_at,
                ignore_decay,
            )
            if decayed_similarity >= threshold:
                results.append({
                    "id": str(row.id),
                    "title": row.title,
                    "quick_summary": row.quick_summary,
                    "keywords": row.keywords,
                    "url": row.url,
                    "similarity": float(decayed_similarity),
                })

        # Sort by decayed similarity and limit
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]
