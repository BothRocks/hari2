# backend/app/services/pipeline/embedder.py
from openai import OpenAI
from app.core.config import settings

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


async def generate_embedding(text: str | None) -> list[float] | None:
    """Generate embedding vector for text.

    Args:
        text: The text to generate an embedding for.

    Returns:
        A list of floats representing the embedding vector, or None if text is empty/None or on error.
    """
    if not text:
        return None

    try:
        client = OpenAI(api_key=settings.openai_api_key)

        # Truncate text if too long (8191 tokens max for text-embedding-3-small)
        # Using 30000 characters as a rough approximation
        truncated = text[:30000]

        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=truncated,
        )

        return response.data[0].embedding

    except Exception as e:
        print(f"Embedding error: {e}")
        return None


async def generate_embeddings_batch(texts: list[str]) -> list[list[float] | None]:
    """Generate embeddings for multiple texts.

    Args:
        texts: List of text strings to generate embeddings for.

    Returns:
        List of embedding vectors (or None for failed/empty texts).
    """
    results = []
    for text in texts:
        embedding = await generate_embedding(text)
        results.append(embedding)
    return results
