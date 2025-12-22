"""URL content fetching service using Trafilatura."""

import httpx
import trafilatura
from trafilatura.settings import use_config

# Configure trafilatura
config = use_config()
config.set("DEFAULT", "EXTRACTION_TIMEOUT", "30")


async def fetch_url_content(url: str) -> dict[str, str | dict[str, str | None]]:
    """
    Fetch and extract content from URL using Trafilatura.

    Args:
        url: The URL to fetch and extract content from

    Returns:
        Dictionary containing:
        - text: Extracted main content (empty string if extraction fails)
        - metadata: Dict with title, author, date (if available)
        - url: Final URL after following redirects
        - error: Error message (only present if request fails)
    """
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text

        # Extract main content
        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
        )

        # Extract metadata
        metadata = trafilatura.extract_metadata(html)

        return {
            "text": text or "",
            "metadata": {
                "title": metadata.title if metadata else None,
                "author": metadata.author if metadata else None,
                "date": str(metadata.date) if metadata and metadata.date else None,
            },
            "url": str(response.url),  # Final URL after redirects
        }
    except httpx.HTTPStatusError as e:
        return {"text": "", "error": f"HTTP error: {e.response.status_code}"}
    except httpx.TimeoutException as e:
        return {"text": "", "error": f"HTTP error: {e}"}
    except httpx.ConnectError as e:
        return {"text": "", "error": f"HTTP error: {e}"}
    except httpx.HTTPError as e:
        return {"text": "", "error": f"HTTP error: {e}"}
    except Exception as e:
        return {"text": "", "error": str(e)}
