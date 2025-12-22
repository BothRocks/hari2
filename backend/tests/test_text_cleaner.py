import pytest
from app.services.pipeline.text_cleaner import clean_text, count_tokens


def test_clean_text_removes_extra_whitespace():
    """Test that multiple spaces are normalized to single space."""
    dirty = "Hello   world\n\n\n\ntest"
    result = clean_text(dirty)
    assert "   " not in result
    assert "\n\n\n\n" not in result


def test_clean_text_preserves_content():
    """Test that actual content is preserved during cleaning."""
    text = "Hello world. This is a test."
    result = clean_text(text)
    assert "Hello" in result
    assert "test" in result


def test_clean_text_empty_string():
    """Test that empty string returns empty string."""
    result = clean_text("")
    assert result == ""


def test_clean_text_none_handling():
    """Test that None input is handled gracefully."""
    # Should handle None by converting to empty string or raising appropriate error
    result = clean_text(None)
    assert result == ""


def test_clean_text_removes_control_characters():
    """Test that control characters are removed."""
    # Text with various control characters
    dirty = "Hello\x00World\x08Test\x1fContent"
    result = clean_text(dirty)
    assert "\x00" not in result
    assert "\x08" not in result
    assert "\x1f" not in result
    # Content should be preserved
    assert "Hello" in result
    assert "World" in result


def test_clean_text_preserves_unicode():
    """Test that Unicode characters are preserved."""
    text = "Hello 世界! Café ñoño"
    result = clean_text(text)
    assert "世界" in result
    assert "Café" in result
    assert "ñoño" in result


def test_clean_text_normalizes_line_breaks():
    """Test that excessive line breaks are normalized."""
    dirty = "Line 1\n\n\n\n\nLine 2"
    result = clean_text(dirty)
    # Should have at most 2 consecutive newlines
    assert "\n\n\n" not in result


def test_clean_text_strips_leading_trailing_whitespace():
    """Test that leading and trailing whitespace is removed."""
    dirty = "   Hello World   "
    result = clean_text(dirty)
    assert result == "Hello World"


def test_clean_text_handles_tabs():
    """Test that tabs are normalized to spaces."""
    dirty = "Hello\t\tWorld\tTest"
    result = clean_text(dirty)
    assert "\t\t" not in result
    assert "Hello" in result
    assert "World" in result


def test_clean_text_mixed_whitespace():
    """Test that mixed whitespace types are normalized."""
    dirty = "Hello  \t\n  World"
    result = clean_text(dirty)
    # Should normalize all whitespace
    assert "  \t\n  " not in result


def test_count_tokens_empty_string():
    """Test token count for empty string."""
    result = count_tokens("")
    assert result == 0


def test_count_tokens_none_handling():
    """Test token count for None input."""
    result = count_tokens(None)
    assert result == 0


def test_count_tokens_simple_text():
    """Test token count approximation for simple text."""
    text = "Hello world test"  # 3 words
    result = count_tokens(text)
    # 3 words * 1.3 = 3.9 -> 3 (int conversion)
    assert result == 3


def test_count_tokens_longer_text():
    """Test token count approximation for longer text."""
    text = "This is a longer sentence with ten words in it."  # 10 words
    result = count_tokens(text)
    # 10 words * 1.3 = 13
    assert result == 13


def test_count_tokens_with_extra_whitespace():
    """Test that extra whitespace doesn't inflate token count."""
    text = "Hello    world   test"  # 3 words with extra spaces
    result = count_tokens(text)
    # Should still count as 3 words -> 3
    assert result == 3
