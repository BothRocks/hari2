# backend/app/services/search/keyword.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


class KeywordSearch:
    def __init__(self, session: AsyncSession | None = None):
        self.session = session

    async def search(
        self,
        query: str,
        limit: int = 10,
        session: AsyncSession | None = None,
    ) -> list[dict]:
        """Search documents using PostgreSQL full-text search."""
        db = session or self.session
        if not db:
            raise ValueError("Database session required")

        # Handle empty query gracefully
        if not query or not query.strip():
            return []

        # Convert query to tsquery format
        # Simple approach: AND all words together
        words = query.strip().split()
        tsquery = " & ".join(words)

        sql = text("""
            SELECT
                id,
                title,
                quick_summary,
                keywords,
                url,
                ts_rank(
                    to_tsvector('english', coalesce(title, '') || ' ' || coalesce(summary, '')),
                    to_tsquery('english', :tsquery)
                ) as rank
            FROM documents
            WHERE processing_status = 'completed'
                AND to_tsvector('english', coalesce(title, '') || ' ' || coalesce(summary, ''))
                    @@ to_tsquery('english', :tsquery)
            ORDER BY rank DESC
            LIMIT :limit
        """)

        result = await db.execute(sql, {"tsquery": tsquery, "limit": limit})
        rows = result.fetchall()

        return [
            {
                "id": str(row.id),
                "title": row.title,
                "quick_summary": row.quick_summary,
                "keywords": row.keywords,
                "url": row.url,
                "rank": float(row.rank),
            }
            for row in rows
        ]
