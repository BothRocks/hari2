"""PDF text extraction service for document ingestion pipeline."""
import io
from typing import Any
from PyPDF2 import PdfReader
from PyPDF2.errors import FileNotDecryptedError


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
        # Create PDF reader from bytes (strict=False tolerates malformed XMP metadata)
        reader = PdfReader(io.BytesIO(pdf_content), strict=False)

        # Handle encrypted PDFs
        if reader.is_encrypted:
            try:
                # Try empty password (some PDFs are "encrypted" but with no password)
                decrypt_result = reader.decrypt("")
                if decrypt_result == 0:
                    # Decryption failed - password required
                    return {
                        "text": "",
                        "error": "PDF is password-protected and cannot be processed",
                    }
            except Exception:
                return {
                    "text": "",
                    "error": "PDF is password-protected and cannot be processed",
                }

        pages_text = []

        # Extract text from each page
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text.strip())

        # Join pages with double newline separator
        full_text = "\n\n".join(pages_text)

        # Extract metadata if available
        metadata: dict[str, str | None] = {
            "title": None,
            "author": None,
        }

        try:
            if reader.metadata:
                metadata["title"] = reader.metadata.title if hasattr(reader.metadata, 'title') else None
                metadata["author"] = reader.metadata.author if hasattr(reader.metadata, 'author') else None
        except Exception:
            pass  # Malformed metadata (e.g. bad XMP) is not worth failing for

        return {
            "text": full_text,
            "page_count": len(reader.pages),
            "metadata": metadata,
        }

    except FileNotDecryptedError:
        return {
            "text": "",
            "error": "PDF is password-protected and cannot be processed",
        }
    except Exception as e:
        error_msg = str(e)
        # Check for crypto-related errors
        if "PyCryptodome" in error_msg or "Crypto" in error_msg or "AES" in error_msg:
            return {
                "text": "",
                "error": "PDF uses unsupported encryption format",
            }
        # Return error structure on any other failure
        return {
            "text": "",
            "error": f"Failed to read PDF: {error_msg}",
        }
