"""PDF text extraction service for document ingestion pipeline."""
import io
from typing import Any
from PyPDF2 import PdfReader


async def extract_text_from_pdf(pdf_content: bytes) -> dict[str, Any]:
    """
    Extract text from PDF bytes.

    Args:
        pdf_content: Raw PDF file content as bytes

    Returns:
        Dictionary containing:
        - text: Extracted text from all pages (empty string on error)
        - page_count: Number of pages in PDF (only on success)
        - metadata: Dictionary with title and author (only on success)
        - error: Error message (only on failure)
    """
    try:
        # Create PDF reader from bytes
        reader = PdfReader(io.BytesIO(pdf_content))
        pages_text = []

        # Extract text from each page
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text.strip())

        # Join pages with double newline separator
        full_text = "\n\n".join(pages_text)

        # Extract metadata if available
        metadata = {
            "title": None,
            "author": None,
        }

        if reader.metadata:
            metadata["title"] = reader.metadata.title if hasattr(reader.metadata, 'title') else None
            metadata["author"] = reader.metadata.author if hasattr(reader.metadata, 'author') else None

        return {
            "text": full_text,
            "page_count": len(reader.pages),
            "metadata": metadata,
        }
    except Exception as e:
        # Return error structure on any failure
        return {
            "text": "",
            "error": str(e),
        }
