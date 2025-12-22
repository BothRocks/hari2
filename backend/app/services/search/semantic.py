# backend/app/services/search/semantic.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.models.document import Document, ProcessingStatus
from app.services.pipeline.embedder import generate_embedding


class SemanticSearch:
    def __init__(self, session: AsyncSession | None = None):
        self.session = session

    async def search(
        self,
        query: str,
        limit: int = 10,
        threshold: float = 0.5,
        session: AsyncSession | None = None,
    ) -> list[dict]:
        """Search documents by semantic similarity."""
        db = session or self.session
        if not db:
            raise ValueError("Database session required")

        # Generate query embedding
        query_embedding = await generate_embedding(query)
        if not query_embedding:
            return []

        # pgvector cosine similarity search
        # 1 - cosine_distance gives similarity (0-1)
        sql = text("""
            SELECT
                id,
                title,
                quick_summary,
                keywords,
                url,
                1 - (embedding <=> :query_embedding::vector) as similarity
            FROM documents
            WHERE processing_status = 'completed'
                AND embedding IS NOT NULL
                AND 1 - (embedding <=> :query_embedding::vector) >= :threshold
            ORDER BY embedding <=> :query_embedding::vector
            LIMIT :limit
        """)

        result = await db.execute(
            sql,
            {
                "query_embedding": str(query_embedding),
                "threshold": threshold,
                "limit": limit,
            }
        )

        rows = result.fetchall()
        return [
            {
                "id": str(row.id),
                "title": row.title,
                "quick_summary": row.quick_summary,
                "keywords": row.keywords,
                "url": row.url,
                "similarity": float(row.similarity),
            }
            for row in rows
        ]
