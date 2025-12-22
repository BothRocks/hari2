from pydantic import BaseModel


class QueryRequest(BaseModel):
    query: str
    limit: int = 5


class SourceReference(BaseModel):
    id: str | None
    title: str | None
    url: str | None


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceReference]


class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    threshold: float = 0.5


class SearchResult(BaseModel):
    id: str
    title: str | None
    quick_summary: str | None
    url: str | None
    score: float
