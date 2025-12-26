# backend/tests/test_sse_utils.py
from app.utils.sse import build_thinking_message, chunk_sentences, format_sse, parse_sse


def test_format_sse_simple_event():
    """Format a simple SSE event."""
    result = format_sse("thinking", {"step": "retrieve", "message": "Searching..."})
    assert result == 'event: thinking\ndata: {"step": "retrieve", "message": "Searching..."}\n\n'


def test_format_sse_done_event():
    """Format done event with metadata."""
    result = format_sse("done", {"research_iterations": 2})
    assert result == 'event: done\ndata: {"research_iterations": 2}\n\n'


def test_parse_sse_single_event():
    """Parse a single SSE event."""
    raw = 'event: thinking\ndata: {"step": "retrieve", "message": "Searching..."}\n\n'
    events = parse_sse(raw)
    assert len(events) == 1
    assert events[0]["type"] == "thinking"
    assert events[0]["data"]["step"] == "retrieve"


def test_parse_sse_multiple_events():
    """Parse multiple SSE events in one chunk."""
    raw = (
        'event: thinking\ndata: {"step": "retrieve"}\n\n'
        'event: chunk\ndata: {"content": "Hello"}\n\n'
    )
    events = parse_sse(raw)
    assert len(events) == 2
    assert events[0]["type"] == "thinking"
    assert events[1]["type"] == "chunk"


def test_chunk_sentences_simple():
    """Chunk text into sentences."""
    text = "First sentence. Second sentence. Third one."
    chunks = list(chunk_sentences(text))
    assert chunks == ["First sentence. ", "Second sentence. ", "Third one."]


def test_chunk_sentences_with_abbreviations():
    """Handle common abbreviations."""
    text = "Dr. Smith said hello. Mr. Jones replied."
    chunks = list(chunk_sentences(text))
    assert chunks == ["Dr. Smith said hello. ", "Mr. Jones replied."]


def test_chunk_sentences_empty():
    """Handle empty text."""
    chunks = list(chunk_sentences(""))
    assert chunks == []


def test_chunk_sentences_no_period():
    """Handle text without periods."""
    text = "Just some text without periods"
    chunks = list(chunk_sentences(text))
    assert chunks == ["Just some text without periods"]


def test_build_thinking_message_retrieve():
    """Build message for retrieve node."""
    result = build_thinking_message("retrieve", {})
    assert result == {"step": "retrieve", "message": "Searching internal knowledge..."}


def test_build_thinking_message_evaluate_with_count():
    """Build message for evaluate node with document count."""
    result = build_thinking_message("evaluate", {"internal_results": [1, 2, 3, 4, 5]})
    assert result["step"] == "evaluate"
    assert "5 documents" in result["message"]


def test_build_thinking_message_research():
    """Build message for research node."""
    result = build_thinking_message("research", {"evaluation": {"missing_information": ["AI frameworks"]}})
    assert result["step"] == "research"
    assert "AI frameworks" in result["message"]


def test_build_thinking_message_generate():
    """Build message for generate node."""
    result = build_thinking_message("generate", {})
    assert result == {"step": "generate", "message": "Generating response..."}
