# backend/app/services/pipeline/orchestrator.py
import hashlib
from typing import Any

import httpx

from app.services.pipeline.url_fetcher import fetch_url_content
from app.services.pipeline.pdf_extractor import extract_text_from_pdf
from app.services.pipeline.text_cleaner import clean_text, count_tokens
from app.services.pipeline.extractive_summarizer import extractive_summarize
from app.services.pipeline.synthesizer import synthesize_document
from app.services.pipeline.validator import validate_and_correct
from app.services.pipeline.embedder import generate_embedding
from app.services.quality.scorer import calculate_quality_score


class DocumentPipeline:
    """Orchestrates the document processing pipeline."""

    async def process_url(self, url: str) -> dict[str, Any]:
        """Process a URL through the full pipeline.

        Automatically detects if URL points to a PDF and routes accordingly.
        """
        # Check if URL is a PDF (by extension or content-type)
        is_pdf = await self._is_pdf_url(url)

        if is_pdf:
            # Download PDF and process as PDF
            pdf_content = await self._download_pdf(url)
            if pdf_content is None:
                return {"status": "failed", "error": "Failed to download PDF from URL"}
            return await self.process_pdf(pdf_content, filename=url.split("/")[-1])

        # Stage 1: Fetch HTML content
        fetch_result = await fetch_url_content(url)
        if "error" in fetch_result:
            return {"status": "failed", "error": fetch_result["error"]}

        return await self._process_text(
            text=fetch_result["text"],
            metadata=fetch_result.get("metadata", {}),
            source_url=url,
        )

    async def _is_pdf_url(self, url: str) -> bool:
        """Check if URL points to a PDF file.

        Checks both the URL extension and the Content-Type header.
        """
        # Quick check: URL ends with .pdf
        if url.lower().rstrip("/").endswith(".pdf"):
            return True

        # HEAD request to check Content-Type
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.head(url)
                content_type = response.headers.get("content-type", "").lower()
                return "application/pdf" in content_type
        except Exception:
            # If HEAD fails, fall back to extension check only
            return False

    async def _download_pdf(self, url: str) -> bytes | None:
        """Download PDF content from URL."""
        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.content
        except Exception:
            return None

    async def process_pdf(self, pdf_content: bytes, filename: str = "") -> dict[str, Any]:
        """Process PDF bytes through the full pipeline."""
        # Stage 1: Extract
        extract_result = await extract_text_from_pdf(pdf_content)
        if "error" in extract_result:
            return {"status": "failed", "error": extract_result["error"]}

        return await self._process_text(
            text=extract_result["text"],
            metadata=extract_result.get("metadata", {}),
            source_url=filename,
        )

    async def _process_text(self, text: str, metadata: dict[str, Any], source_url: str) -> dict[str, Any]:
        """Process extracted text through remaining pipeline stages."""
        # Stage 2: Clean
        cleaned_text = clean_text(text)
        if not cleaned_text:
            return {"status": "failed", "error": "No content extracted"}

        token_count = count_tokens(cleaned_text)

        # Stage 3: Extractive summary (for long texts)
        if token_count > 2000:
            extractive = extractive_summarize(cleaned_text, sentence_count=30)
        else:
            extractive = cleaned_text

        # Stage 4: LLM synthesis
        synthesis = await synthesize_document(extractive)
        if "error" in synthesis:
            return {"status": "failed", "error": synthesis["error"]}

        # Stage 5: Validate and auto-correct metadata
        validation = await validate_and_correct(
            content=cleaned_text,
            metadata={
                "title": metadata.get("title") or synthesis.get("title"),
                "author": synthesis.get("author"),
                "summary": synthesis.get("summary"),
                "keywords": synthesis.get("keywords"),
            }
        )

        # Merge corrections into synthesis
        final_title = validation.get("title") or metadata.get("title") or synthesis.get("title")
        final_author = validation.get("author") or synthesis.get("author")
        final_summary = validation.get("summary") or synthesis.get("summary")
        final_keywords = validation.get("keywords") or synthesis.get("keywords")

        # Stage 6: Generate embedding (use corrected summary)
        embed_text = final_summary or cleaned_text[:5000]
        embedding = await generate_embedding(embed_text)

        # Stage 7: Quality scoring
        quality_score = calculate_quality_score(
            summary=final_summary,
            quick_summary=synthesis.get("quick_summary"),
            keywords=final_keywords,
            industries=synthesis.get("industries"),
            has_embedding=embedding is not None,
        )

        # Generate content hash for deduplication
        content_hash = hashlib.sha256(cleaned_text.encode()).hexdigest()

        return {
            "status": "completed",
            "content": cleaned_text,
            "content_hash": content_hash,
            "title": final_title,
            "author": final_author,
            "summary": final_summary,
            "quick_summary": synthesis.get("quick_summary"),
            "keywords": final_keywords,
            "industries": synthesis.get("industries"),
            "language": synthesis.get("language"),
            "embedding": embedding,
            "quality_score": quality_score,
            "token_count": token_count,
            "llm_metadata": synthesis.get("llm_metadata"),
            # Validation results
            "needs_review": validation.get("needs_review", False),
            "review_reasons": validation.get("review_reasons"),
            "original_metadata": validation.get("original_metadata"),
        }
