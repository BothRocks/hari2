"""SSE (Server-Sent Events) formatting utilities."""
import json
from typing import Any


def format_sse(event_type: str, data: dict[str, Any]) -> str:
    """
    Format data as an SSE event string.

    Args:
        event_type: Event type (thinking, chunk, sources, done, error)
        data: Event data dictionary

    Returns:
        SSE-formatted string with event and data lines
    """
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def parse_sse(raw: str) -> list[dict[str, Any]]:
    """
    Parse raw SSE text into list of events.

    Args:
        raw: Raw SSE text (may contain multiple events)

    Returns:
        List of parsed events with 'type' and 'data' keys
    """
    events = []
    current_event = {}

    for line in raw.split("\n"):
        if line.startswith("event: "):
            current_event["type"] = line[7:]
        elif line.startswith("data: "):
            try:
                current_event["data"] = json.loads(line[6:])
            except json.JSONDecodeError:
                current_event["data"] = line[6:]
        elif line == "" and current_event:
            if "type" in current_event and "data" in current_event:
                events.append(current_event)
            current_event = {}

    return events
