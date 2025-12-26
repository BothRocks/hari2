# backend/tests/test_sse_utils.py
import pytest
from app.utils.sse import format_sse, parse_sse


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
