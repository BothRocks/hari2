"""Extractive summarization using Sumy's TextRank algorithm."""
from typing import Optional
from sumy.parsers.plaintext import PlaintextParser  # type: ignore
from sumy.nlp.tokenizers import Tokenizer  # type: ignore
from sumy.summarizers.text_rank import TextRankSummarizer  # type: ignore
from sumy.nlp.stemmers import Stemmer  # type: ignore
from sumy.utils import get_stop_words  # type: ignore
import nltk  # type: ignore


# Download required NLTK data
def _ensure_nltk_data() -> None:
    """Ensure required NLTK data is available."""
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt', quiet=True)
    try:
        nltk.data.find('tokenizers/punkt_tab')
    except LookupError:
        nltk.download('punkt_tab', quiet=True)


# Initialize NLTK data on module import
_ensure_nltk_data()


def extractive_summarize(
    text: Optional[str],
    sentence_count: int = 10,
    language: str = "english"
) -> str:
    """
    Extract key sentences using TextRank algorithm.

    Args:
        text: The input text to summarize. Can be None or empty.
        sentence_count: Number of sentences to extract (default: 10).
        language: Language of the text for tokenization (default: "english").

    Returns:
        A string containing the extracted summary sentences.
        Returns empty string if input is None or empty.
        Returns original text if it's shorter than requested sentence count.
    """
    # Handle None and empty text
    if not text:
        return ""

    # Handle whitespace-only text
    if not text.strip():
        return text

    # Handle invalid sentence counts
    if sentence_count <= 0:
        return text

    # Count sentences in text (simple approximation)
    sentence_markers = text.count('.') + text.count('!') + text.count('?')

    # If text is short enough, return as-is
    if sentence_markers <= sentence_count:
        return text

    try:
        parser = PlaintextParser.from_string(text, Tokenizer(language))
        stemmer = Stemmer(language)

        # Use TextRank summarizer
        summarizer = TextRankSummarizer(stemmer)
        summarizer.stop_words = get_stop_words(language)

        sentences = summarizer(parser.document, sentence_count)
        summary = " ".join(str(s) for s in sentences)

        return summary if summary else text

    except Exception:
        # Fallback: just take first N sentences
        # Split by common sentence terminators
        import re
        sentences = re.split(r'[.!?]+', text)
        # Filter out empty strings and take first N
        sentences = [s.strip() for s in sentences if s.strip()][:sentence_count]
        # Rejoin with periods
        if sentences:
            return '. '.join(sentences) + '.'
        return text
