"""Document metadata validator with auto-correction."""
import json
import logging
import re
from typing import Any

from app.services.llm.client import LLMClient

logger = logging.getLogger(__name__)

GENERIC_TITLES = {"template", "untitled", "document", "doc", "file", "copy", "draft", "new", "test"}
GENERIC_AUTHORS = {"author", "admin", "user", "unknown", "anonymous", "n/a", "na", "none"}
GENERIC_KEYWORDS = {"business", "report", "document", "information", "data", "file", "content"}

FILENAME_PATTERN = re.compile(r"^[\w\-]+\.(pdf|doc|docx|txt|xlsx?)$", re.IGNORECASE)
USERNAME_PATTERN = re.compile(r"^[\w.]+@|^\w+_\w+$|^user\d+$", re.IGNORECASE)


def looks_like_filename(title: str) -> bool:
    """Check if title looks like a filename."""
    return bool(FILENAME_PATTERN.match(title.strip()))


def looks_like_username(author: str) -> bool:
    """Check if author looks like a username or email."""
    return bool(USERNAME_PATTERN.match(author.strip()))


def detect_issues(metadata: dict[str, Any]) -> list[str]:
    """
    Detect quality issues in document metadata using rules.

    Returns list of issue codes.
    """
    issues = []

    # Title checks
    title = (metadata.get("title") or "").lower().strip()
    if title in GENERIC_TITLES:
        issues.append("generic_title")
    elif title and len(title.split()) == 1 and len(title) < 20:
        issues.append("single_word_title")
    if looks_like_filename(metadata.get("title") or ""):
        issues.append("filename_as_title")

    # Author checks
    author = (metadata.get("author") or "").lower().strip()
    if author in GENERIC_AUTHORS:
        issues.append("generic_author")
    if author and looks_like_username(author):
        issues.append("author_looks_like_username")

    # Summary checks
    summary = metadata.get("summary") or ""
    if summary and len(summary.split()) < 50:
        issues.append("short_summary")

    # Keywords checks
    keywords = [k.lower() for k in (metadata.get("keywords") or [])]
    if 0 < len(keywords) < 3:
        issues.append("few_keywords")
    if keywords and set(keywords).issubset(GENERIC_KEYWORDS):
        issues.append("generic_keywords")

    return issues


CORRECTION_PROMPT = """Analyze this document and fix the metadata issues identified.

DOCUMENT CONTENT (first 5000 chars):
{content}

CURRENT METADATA:
- Title: {title}
- Author: {author}
- Summary: {summary}
- Keywords: {keywords}

ISSUES DETECTED: {issues}

Based on the actual document content, provide corrected values ONLY for fields with issues.
Respond with valid JSON only:
{{
  "title": "Corrected title based on content" or null if no fix needed,
  "author": "Corrected author" or null if no fix needed,
  "summary": "Corrected summary" or null if no fix needed,
  "keywords": ["corrected", "keywords"] or null if no fix needed
}}
"""


async def validate_and_correct(
    content: str,
    metadata: dict[str, Any],
    llm_client: LLMClient | None = None,
) -> dict[str, Any]:
    """
    Validate document metadata and auto-correct issues.

    Args:
        content: Document text content
        metadata: Extracted metadata (title, author, summary, keywords)
        llm_client: Optional LLM client

    Returns:
        Dictionary with:
            - needs_review: bool
            - review_reasons: list of issue codes
            - original_metadata: dict of original values (if corrected)
            - Corrected field values (title, author, etc.)
    """
    issues = detect_issues(metadata)

    if not issues:
        return {
            "needs_review": False,
            "review_reasons": [],
        }

    # Prepare result
    result = {
        "needs_review": True,
        "review_reasons": list(issues),
        "original_metadata": {},
    }

    # Try to auto-correct using LLM
    client = llm_client or LLMClient()

    prompt = CORRECTION_PROMPT.format(
        content=content[:5000],
        title=metadata.get("title"),
        author=metadata.get("author"),
        summary=metadata.get("summary", "")[:500],
        keywords=metadata.get("keywords"),
        issues=", ".join(issues),
    )

    try:
        response = await client.complete(
            prompt=prompt,
            system="You are a document metadata correction assistant. Respond only with valid JSON.",
            max_tokens=1000,
            temperature=0.3,
        )

        # Parse response
        content_text = response["content"]
        if "```json" in content_text:
            content_text = content_text.split("```json")[1].split("```")[0]
        elif "```" in content_text:
            content_text = content_text.split("```")[1].split("```")[0]

        corrections = json.loads(content_text.strip())

        # Apply corrections and track originals
        for field in ["title", "author", "summary", "keywords"]:
            if corrections.get(field) is not None:
                result["original_metadata"][field] = metadata.get(field)
                result[field] = corrections[field]

        # Update review_reasons to show what was auto-corrected
        corrected_fields = list(result["original_metadata"].keys())
        result["review_reasons"] = [f"{f}_auto_corrected" for f in corrected_fields] + [
            r for r in issues if not any(f in r for f in corrected_fields)
        ]

    except Exception as e:
        # If LLM fails, just flag without correction
        logger.warning("LLM correction failed: %s", e)

    return result
