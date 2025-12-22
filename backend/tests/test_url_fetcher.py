import pytest
import httpx
import respx
from app.services.pipeline.url_fetcher import fetch_url_content


@pytest.mark.asyncio
@respx.mock
async def test_fetch_url_content_successful_extraction():
    """Test successful content extraction from HTML."""
    mock_html = """
    <html>
        <head>
            <title>Test Article</title>
            <meta name="author" content="John Doe">
            <meta name="date" content="2024-01-15">
        </head>
        <body>
            <article>
                <h1>Test Article</h1>
                <p>This is test content that should be extracted.</p>
            </article>
        </body>
    </html>
    """

    respx.get("https://example.com/article").mock(
        return_value=httpx.Response(200, text=mock_html)
    )

    result = await fetch_url_content("https://example.com/article")

    assert isinstance(result, dict)
    assert "text" in result
    assert "metadata" in result
    assert "url" in result
    assert result["text"] != ""
    assert "error" not in result
    assert result["url"] == "https://example.com/article"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_url_content_with_metadata():
    """Test metadata extraction from HTML."""
    mock_html = """
    <html>
        <head>
            <title>Test Title</title>
            <meta name="author" content="Jane Smith">
            <meta name="date" content="2024-01-20">
        </head>
        <body>
            <article>
                <p>Content here.</p>
            </article>
        </body>
    </html>
    """

    respx.get("https://example.com").mock(
        return_value=httpx.Response(200, text=mock_html)
    )

    result = await fetch_url_content("https://example.com")

    assert "metadata" in result
    assert result["metadata"]["title"] is not None
    # Note: trafilatura's metadata extraction may vary, so we just check structure
    assert "title" in result["metadata"]
    assert "author" in result["metadata"]
    assert "date" in result["metadata"]


@pytest.mark.asyncio
@respx.mock
async def test_fetch_url_content_follows_redirects():
    """Test that redirects are followed and final URL is returned."""
    mock_html = "<html><body><p>Final destination content</p></body></html>"

    respx.get("https://example.com/old").mock(
        return_value=httpx.Response(
            301,
            headers={"location": "https://example.com/new"}
        )
    )
    respx.get("https://example.com/new").mock(
        return_value=httpx.Response(200, text=mock_html)
    )

    result = await fetch_url_content("https://example.com/old")

    assert result["url"] == "https://example.com/new"
    assert "text" in result


@pytest.mark.asyncio
@respx.mock
async def test_fetch_url_content_404_error():
    """Test handling of 404 error."""
    respx.get("https://example.com/notfound").mock(
        return_value=httpx.Response(404, text="Not Found")
    )

    result = await fetch_url_content("https://example.com/notfound")

    assert isinstance(result, dict)
    assert "error" in result
    assert "HTTP error" in result["error"] or "404" in result["error"]
    assert result["text"] == ""


@pytest.mark.asyncio
@respx.mock
async def test_fetch_url_content_500_error():
    """Test handling of 500 server error."""
    respx.get("https://example.com/error").mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )

    result = await fetch_url_content("https://example.com/error")

    assert isinstance(result, dict)
    assert "error" in result
    assert "HTTP error" in result["error"] or "500" in result["error"]
    assert result["text"] == ""


@pytest.mark.asyncio
@respx.mock
async def test_fetch_url_content_timeout():
    """Test handling of network timeout."""
    respx.get("https://example.com/slow").mock(
        side_effect=httpx.TimeoutException("Request timed out")
    )

    result = await fetch_url_content("https://example.com/slow")

    assert isinstance(result, dict)
    assert "error" in result
    assert result["text"] == ""


@pytest.mark.asyncio
@respx.mock
async def test_fetch_url_content_connection_error():
    """Test handling of connection errors."""
    respx.get("https://example.com/unreachable").mock(
        side_effect=httpx.ConnectError("Connection failed")
    )

    result = await fetch_url_content("https://example.com/unreachable")

    assert isinstance(result, dict)
    assert "error" in result
    assert result["text"] == ""


@pytest.mark.asyncio
@respx.mock
async def test_fetch_url_content_empty_html():
    """Test handling of empty HTML response."""
    respx.get("https://example.com/empty").mock(
        return_value=httpx.Response(200, text="")
    )

    result = await fetch_url_content("https://example.com/empty")

    assert isinstance(result, dict)
    assert "text" in result
    assert result["text"] == ""
    assert "error" not in result


@pytest.mark.asyncio
@respx.mock
async def test_fetch_url_content_malformed_html():
    """Test handling of malformed HTML."""
    malformed_html = "<html><body><p>Unclosed paragraph"

    respx.get("https://example.com/malformed").mock(
        return_value=httpx.Response(200, text=malformed_html)
    )

    result = await fetch_url_content("https://example.com/malformed")

    # Should still return a dict, even if extraction fails
    assert isinstance(result, dict)
    assert "text" in result
    # Trafilatura should handle malformed HTML gracefully


@pytest.mark.asyncio
@respx.mock
async def test_fetch_url_content_with_tables():
    """Test that tables are included in extraction."""
    html_with_table = """
    <html>
        <body>
            <article>
                <p>Some text before table</p>
                <table>
                    <tr><td>Cell 1</td><td>Cell 2</td></tr>
                    <tr><td>Cell 3</td><td>Cell 4</td></tr>
                </table>
                <p>Some text after table</p>
            </article>
        </body>
    </html>
    """

    respx.get("https://example.com/table").mock(
        return_value=httpx.Response(200, text=html_with_table)
    )

    result = await fetch_url_content("https://example.com/table")

    assert isinstance(result, dict)
    assert "text" in result
    # The exact format depends on trafilatura's table extraction
    assert result["text"] != ""
