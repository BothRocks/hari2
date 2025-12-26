"""Tests for document metadata validator."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.pipeline.validator import detect_issues, validate_and_correct


class TestDetectIssues:
    """Tests for rule-based issue detection."""

    def test_detects_generic_title(self):
        issues = detect_issues({"title": "template"})
        assert "generic_title" in issues

    def test_detects_single_word_title(self):
        issues = detect_issues({"title": "Report"})
        assert "single_word_title" in issues

    def test_detects_filename_as_title(self):
        issues = detect_issues({"title": "report_v2_final.pdf"})
        assert "filename_as_title" in issues

    def test_detects_generic_author(self):
        issues = detect_issues({"author": "admin"})
        assert "generic_author" in issues

    def test_detects_short_summary(self):
        issues = detect_issues({"summary": "This is short."})
        assert "short_summary" in issues

    def test_detects_few_keywords(self):
        issues = detect_issues({"keywords": ["one", "two"]})
        assert "few_keywords" in issues

    def test_detects_generic_keywords(self):
        issues = detect_issues({"keywords": ["business", "report", "document"]})
        assert "generic_keywords" in issues

    def test_no_issues_for_good_metadata(self):
        issues = detect_issues({
            "title": "Artificial Intelligence Market Analysis 2025",
            "author": "John Smith, PhD",
            "summary": " ".join(["word"] * 100),
            "keywords": ["AI", "machine learning", "neural networks", "automation", "robotics"],
        })
        assert len(issues) == 0


class TestValidateAndCorrect:
    """Tests for LLM-based correction."""

    @pytest.mark.asyncio
    async def test_returns_no_changes_when_no_issues(self):
        result = await validate_and_correct(
            content="Some document content",
            metadata={
                "title": "Good Title Here",
                "author": "Real Author",
                "summary": " ".join(["word"] * 100),
                "keywords": ["specific", "relevant", "keywords", "here", "now"],
            }
        )
        assert result["needs_review"] is False
        assert result["review_reasons"] == []

    @pytest.mark.asyncio
    async def test_flags_when_issues_detected(self):
        # Mock LLM to return corrections
        mock_llm_response = {
            "content": '{"title": "Corrected Title"}',
            "provider": "anthropic",
            "model": "claude-3-haiku",
            "input_tokens": 100,
            "output_tokens": 50,
        }

        with patch("app.services.pipeline.validator.LLMClient") as mock_llm_class:
            mock_instance = MagicMock()
            mock_instance.complete = AsyncMock(return_value=mock_llm_response)
            mock_llm_class.return_value = mock_instance

            result = await validate_and_correct(
                content="Some document content about AI trends",
                metadata={
                    "title": "template",
                    "author": None,
                    "summary": " ".join(["word"] * 100),
                    "keywords": ["AI", "trends", "technology", "market", "analysis"],
                }
            )
            assert result["needs_review"] is True
            assert "title_auto_corrected" in result["review_reasons"]
            assert result["original_metadata"]["title"] == "template"
            assert result["title"] == "Corrected Title"
