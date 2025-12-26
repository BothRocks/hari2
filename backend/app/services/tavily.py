"""Tavily web search service."""
from pydantic import BaseModel
from tavily import TavilyClient

from app.core.config import settings


class TavilyResult(BaseModel):
    """A single Tavily search result."""
    title: str
    url: str
    content: str
    score: float


class TavilyService:
    """Service for web search via Tavily API."""

    def __init__(self, api_key: str | None = None):
        """
        Initialize Tavily service.

        Args:
            api_key: Tavily API key (falls back to settings)
        """
        self.api_key = api_key or settings.tavily_api_key
        self._client: TavilyClient | None = None

    @property
    def client(self) -> TavilyClient:
        """Lazy-load Tavily client."""
        if not self._client:
            if not self.api_key:
                raise ValueError("Tavily API key not configured")
            self._client = TavilyClient(api_key=self.api_key)
        return self._client

    async def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",
    ) -> list[TavilyResult]:
        """
        Search the web using Tavily.

        Args:
            query: Search query
            max_results: Maximum results to return
            search_depth: "basic" or "advanced"

        Returns:
            List of search results
        """
        if not self.api_key:
            raise ValueError("Tavily API key not configured")

        # Tavily client is sync, but we wrap for async interface
        response = self.client.search(
            query=query,
            max_results=max_results,
            search_depth=search_depth,
        )

        results = []
        for item in response.get("results", []):
            results.append(TavilyResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                content=item.get("content", ""),
                score=item.get("score", 0.0),
            ))

        return results
