"""URL content fetching service using Trafilatura with SSRF protection."""

import httpx
import trafilatura
from trafilatura.settings import use_config

from app.core.security import validate_url

# Configure trafilatura
config = use_config()
config.set("DEFAULT", "EXTRACTION_TIMEOUT", "30")

# Maximum number of redirects to follow
MAX_REDIRECTS = 10


async def fetch_url_content(url: str) -> dict[str, str | dict[str, str | None]]:
    """
    Fetch and extract content from URL using Trafilatura.

    Includes SSRF protection:
    - Validates initial URL against private IPs, localhost, etc.
    - Manually follows redirects with validation at each hop
    - Blocks redirects to unsafe URLs

    Args:
        url: The URL to fetch and extract content from

    Returns:
        Dictionary containing:
        - text: Extracted main content (empty string if extraction fails)
        - metadata: Dict with title, author, date (if available)
        - url: Final URL after following redirects
        - error: Error message (only present if request fails)
    """
    # Validate initial URL
    try:
        validate_url(url)
    except ValueError as e:
        return {"text": "", "error": f"URL validation failed: {e}"}

    try:
        current_url = url
        redirect_count = 0

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
            while True:
                response = await client.get(current_url)

                # Check if this is a redirect
                if response.is_redirect:
                    redirect_count += 1
                    if redirect_count > MAX_REDIRECTS:
                        return {"text": "", "error": f"Too many redirects (>{MAX_REDIRECTS})"}

                    # Get redirect location
                    location = response.headers.get("location")
                    if not location:
                        return {"text": "", "error": "Redirect without Location header"}

                    # Handle relative URLs
                    if location.startswith("/"):
                        from urllib.parse import urlparse, urlunparse

                        parsed = urlparse(current_url)
                        location = urlunparse(
                            (parsed.scheme, parsed.netloc, location, "", "", "")
                        )

                    # Validate redirect destination
                    try:
                        validate_url(location)
                    except ValueError as e:
                        return {
                            "text": "",
                            "error": f"Blocked redirect to unsafe URL: {e}",
                        }

                    current_url = location
                    continue

                # Not a redirect, check status
                response.raise_for_status()
                html = response.text
                break

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
            "url": current_url,  # Final URL after redirects
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
