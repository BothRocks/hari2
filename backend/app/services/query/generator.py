"""Query generator for RAG responses."""
from typing import Any

from app.services.llm.client import LLMClient

RESPONSE_PROMPT = """You are HARI, a knowledge assistant. Answer the user's question based on the provided context.

CONTEXT:
{context}

USER QUESTION:
{question}

Instructions:
- Answer based primarily on the provided context
- If the context doesn't contain enough information, acknowledge this
- Be concise and direct
- Cite sources when relevant by mentioning document titles

RESPONSE:
"""


async def generate_response(
    question: str,
    context: list[dict[str, Any]],
    llm_client: LLMClient | None = None,
) -> dict[str, Any]:
    """Generate a response using retrieved context."""
    client = llm_client or LLMClient()

    # Format context
    context_text = "\n\n".join([
        f"[{doc.get('title', 'Untitled')}]\n{doc.get('quick_summary', doc.get('summary', ''))}"
        for doc in context
    ])

    if not context_text:
        context_text = "No relevant documents found."

    prompt = RESPONSE_PROMPT.format(
        context=context_text,
        question=question,
    )

    try:
        response = await client.complete(
            prompt=prompt,
            system="You are HARI, a helpful knowledge assistant.",
            max_tokens=1000,
            temperature=0.7,
        )

        return {
            "answer": response["content"],
            "sources": [
                {"id": doc.get("id"), "title": doc.get("title"), "url": doc.get("url")}
                for doc in context
            ],
            "llm_metadata": {
                "provider": response["provider"],
                "model": response["model"],
            }
        }
    except Exception as e:
        return {"error": str(e)}
