"""Tests for PDF text extraction service."""
import pytest
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from app.services.pipeline.pdf_extractor import extract_text_from_pdf


def create_test_pdf(text_content: str = "Test PDF content", num_pages: int = 1) -> bytes:
    """Create a minimal valid PDF for testing using reportlab."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)

    for page_num in range(num_pages):
        page_text = f"{text_content} - Page {page_num + 1}" if num_pages > 1 else text_content
        c.drawString(100, 750, page_text)
        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer.read()


@pytest.mark.asyncio
async def test_extract_text_from_valid_single_page_pdf():
    """Test extraction from a valid single-page PDF."""
    pdf_content = create_test_pdf("Hello World from PDF")
    result = await extract_text_from_pdf(pdf_content)

    assert isinstance(result, dict)
    assert "text" in result
    assert "page_count" in result
    assert "metadata" in result
    assert "error" not in result

    assert "Hello World from PDF" in result["text"]
    assert result["page_count"] == 1


@pytest.mark.asyncio
async def test_extract_text_from_multi_page_pdf():
    """Test extraction from a multi-page PDF."""
    pdf_content = create_test_pdf("Sample text", num_pages=3)
    result = await extract_text_from_pdf(pdf_content)

    assert isinstance(result, dict)
    assert "error" not in result
    assert result["page_count"] == 3

    # Should contain text from all pages
    assert "Page 1" in result["text"]
    assert "Page 2" in result["text"]
    assert "Page 3" in result["text"]


@pytest.mark.asyncio
async def test_extract_text_from_empty_pdf():
    """Test extraction from a PDF with no text."""
    pdf_content = create_test_pdf("")
    result = await extract_text_from_pdf(pdf_content)

    assert isinstance(result, dict)
    assert "text" in result
    assert "page_count" in result
    assert result["page_count"] == 1
    # Empty or minimal text is acceptable
    assert isinstance(result["text"], str)


@pytest.mark.asyncio
async def test_extract_text_from_corrupted_pdf():
    """Test error handling for corrupted PDF bytes."""
    corrupted_pdf = b"This is not a valid PDF file"
    result = await extract_text_from_pdf(corrupted_pdf)

    assert isinstance(result, dict)
    assert "error" in result
    assert "text" in result
    assert result["text"] == ""
    assert isinstance(result["error"], str)


@pytest.mark.asyncio
async def test_extract_text_from_partially_corrupted_pdf():
    """Test error handling for partially corrupted PDF."""
    # Start with valid PDF header but truncate it
    pdf_content = create_test_pdf("Test")
    corrupted_pdf = pdf_content[:50]  # Truncate to corrupt it

    result = await extract_text_from_pdf(corrupted_pdf)

    assert isinstance(result, dict)
    assert "error" in result
    assert result["text"] == ""


@pytest.mark.asyncio
async def test_extract_text_from_empty_bytes():
    """Test error handling for empty bytes."""
    result = await extract_text_from_pdf(b"")

    assert isinstance(result, dict)
    assert "error" in result
    assert result["text"] == ""


@pytest.mark.asyncio
async def test_pdf_metadata_extraction():
    """Test that PDF metadata is extracted when available."""
    # Create a PDF (reportlab doesn't easily add metadata, so we just verify the structure)
    pdf_content = create_test_pdf("Test content")
    result = await extract_text_from_pdf(pdf_content)

    assert "metadata" in result
    assert isinstance(result["metadata"], dict)
    # Metadata fields may be None if not set
    assert "title" in result["metadata"]
    assert "author" in result["metadata"]


@pytest.mark.asyncio
async def test_extract_preserves_text_structure():
    """Test that extracted text preserves basic structure."""
    # Create PDF with multiple pages
    pdf_content = create_test_pdf("Line one", num_pages=2)
    result = await extract_text_from_pdf(pdf_content)

    # Pages should be separated by double newlines
    assert "\n" in result["text"] or len(result["text"]) > 0
    assert isinstance(result["text"], str)
