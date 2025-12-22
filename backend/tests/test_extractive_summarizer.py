import pytest
from app.services.pipeline.extractive_summarizer import extractive_summarize


def test_extractive_summarize_returns_string():
    """Test that extractive_summarize returns a string."""
    text = "This is the first sentence. This is the second sentence. This is the third sentence. This is the fourth sentence. This is the fifth sentence."
    result = extractive_summarize(text, sentence_count=2)
    assert isinstance(result, str)
    assert len(result) > 0


def test_extractive_summarize_short_text():
    """Test that short text is returned as-is."""
    text = "Short text."
    result = extractive_summarize(text, sentence_count=5)
    assert result == text


def test_extractive_summarize_empty_text():
    """Test that empty text is handled gracefully."""
    result = extractive_summarize("", sentence_count=5)
    assert result == ""


def test_extractive_summarize_none_handling():
    """Test that None input is handled gracefully."""
    result = extractive_summarize(None, sentence_count=5)
    assert result == ""


def test_extractive_summarize_whitespace_only():
    """Test that whitespace-only text is handled."""
    result = extractive_summarize("   \n  \t  ", sentence_count=5)
    assert result.strip() == ""


def test_extractive_summarize_different_sentence_counts():
    """Test summarization with different sentence counts."""
    text = "First sentence here. Second sentence follows. Third one appears. Fourth sentence next. Fifth and final."

    # Request 1 sentence
    result1 = extractive_summarize(text, sentence_count=1)
    assert isinstance(result1, str)
    assert len(result1) > 0

    # Request 3 sentences
    result3 = extractive_summarize(text, sentence_count=3)
    assert isinstance(result3, str)
    assert len(result3) > 0


def test_extractive_summarize_language_parameter():
    """Test that language parameter is accepted."""
    text = "This is an English sentence. Another English sentence. A third English sentence."
    result = extractive_summarize(text, sentence_count=2, language="english")
    assert isinstance(result, str)
    assert len(result) > 0


def test_extractive_summarize_preserves_meaning():
    """Test that summarization preserves some of the original text."""
    text = """
    Artificial intelligence is transforming the world. Machine learning algorithms can now recognize patterns.
    Deep learning has revolutionized computer vision. Neural networks mimic the human brain.
    Natural language processing enables computers to understand text. AI will continue to advance rapidly.
    """.strip()

    result = extractive_summarize(text, sentence_count=2)
    assert isinstance(result, str)
    assert len(result) > 0
    # Result should be shorter than original
    assert len(result) < len(text)


def test_extractive_summarize_single_sentence():
    """Test handling of text with just one sentence."""
    text = "This is a single sentence."
    result = extractive_summarize(text, sentence_count=5)
    assert result == text


def test_extractive_summarize_zero_sentence_count():
    """Test handling of zero sentence count."""
    text = "First sentence. Second sentence. Third sentence."
    result = extractive_summarize(text, sentence_count=0)
    # Should return original or handle gracefully
    assert isinstance(result, str)


def test_extractive_summarize_negative_sentence_count():
    """Test handling of negative sentence count."""
    text = "First sentence. Second sentence. Third sentence."
    result = extractive_summarize(text, sentence_count=-1)
    # Should return original or handle gracefully
    assert isinstance(result, str)


def test_extractive_summarize_longer_text():
    """Test with a longer, more realistic text."""
    text = """
    Climate change is one of the most pressing issues facing humanity today. Rising global temperatures are causing
    widespread environmental disruption. Arctic ice caps are melting at an alarming rate. Sea levels are rising,
    threatening coastal communities worldwide. Extreme weather events are becoming more frequent and severe.
    Scientists agree that human activities are the primary cause. Burning fossil fuels releases greenhouse gases.
    Deforestation reduces the planet's capacity to absorb carbon dioxide. Immediate action is needed to reduce emissions.
    Renewable energy sources offer a sustainable alternative. Solar and wind power are becoming increasingly affordable.
    International cooperation is essential to address this global challenge. The Paris Agreement represents a step forward.
    However, more ambitious targets are needed. Individual actions also make a difference. Reducing consumption and
    choosing sustainable products helps. The future of our planet depends on the choices we make today.
    """.strip()

    result = extractive_summarize(text, sentence_count=3)
    assert isinstance(result, str)
    assert len(result) > 0
    assert len(result) < len(text)
    # Should contain at least one period
    assert "." in result


def test_extractive_summarize_with_mock_error():
    """Test that fallback works when TextRank fails."""
    from unittest.mock import patch

    text = "First sentence here! Second sentence follows? Third one appears. Fourth sentence next."

    # Mock TextRankSummarizer to raise an exception
    with patch('app.services.pipeline.extractive_summarizer.TextRankSummarizer') as mock_summarizer:
        mock_summarizer.side_effect = Exception("Mocked error")
        result = extractive_summarize(text, sentence_count=2)

        # Should use fallback and still return something
        assert isinstance(result, str)
        assert len(result) > 0
        assert "." in result
